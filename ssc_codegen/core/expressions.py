"""Expression handlers — selectors, extract, string ops, regex, array, casts, control."""

from __future__ import annotations

import ast as _py_ast
import re as _re
from collections.abc import Sequence
from typing import Any, Callable, TypeAlias

from ssc_codegen.ast import (
    Assert,
    Attr,
    CheckMethod,
    CssRemove,
    CssSelect,
    CssSelectAll,
    Fallback,
    FallbackEnd,
    FallbackStart,
    Field,
    Filter,
    Fmt,
    Index,
    InitField,
    JsonDef,
    JsonDefField,
    Jsonify,
    Join,
    Key,
    Len,
    Lower,
    Ltrim,
    Match,
    Module,
    Nested,
    Node as AstNode,
    NormalizeSpace,
    PreValidate,
    Raw,
    Re,
    ReAll,
    ReSub,
    Repl,
    ReplMap,
    Return,
    RmPrefix,
    RmPrefixSuffix,
    RmSuffix,
    Rtrim,
    Self,
    Slice,
    Split,
    SplitDoc,
    Struct,
    StructFlatList,
    StructList,
    TableConfig,
    TableMatchKey,
    TableRow,
    Text,
    ToBool,
    ToFloat,
    ToInt,
    Trim,
    TypeDef,
    TypeDefField,
    TypeInfo,
    Unescape,
    Unique,
    Upper,
    Value,
    VariableType,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.exceptions import BuildTimeError
from kdlquery import KdlNode
from ssc_codegen.regex_utils import normalize_regex_pattern
from typing import cast

from ssc_codegen.core.contexts import LintContext, ParseContext, WalkCtx
from ssc_codegen.core.linter import (
    lint_pipeline_op,
    lint_validate_css,
    lint_validate_xpath,
    lint_wildcard_op,
)
from ssc_codegen.core.predicates import (
    parse_assert_expr,
    parse_filter_expr,
    parse_match_expr,
)

# ── Registration tables ─────────────────────────────────────────────────────────

CallbackReg = Callable[
    [KdlNode, "FieldLikeNode", ParseContext, LintContext], AstNode
]

FieldLikeNode: TypeAlias = (
    PreValidate
    | SplitDoc
    | TableConfig
    | TableRow
    | TableMatchKey
    | Key
    | Value
    | Field
    | InitField
)


# ── AST builder helpers ─────────────────────────────────────────────────────────


def resolve_selector_arg(
    query: str | int | float | bool, ctx: ParseContext
) -> str:
    q = str(query) if not isinstance(query, str) else query
    value = ctx.property_defines.get(q, query)
    return value if isinstance(value, str) else str(value)


def resolve_selector_child_name(name: str, ctx: ParseContext) -> str:
    value = ctx.property_defines.get(name, _decode_scalar(name))
    return value if isinstance(value, str) else str(value)


def _decode_scalar(text: str) -> Any:
    text = text.strip()
    if text == "#true":
        return True
    if text == "#false":
        return False
    if text == "#null":
        return None
    if _looks_like_raw_string(text):
        return _decode_raw_string(text)
    if text.startswith('"""') and text.endswith('"""'):
        return text[3:-3]
    if text.startswith('"') and text.endswith('"'):
        try:
            return _py_ast.literal_eval(text)
        except Exception:
            return text[1:-1]
    if _INTEGER_RE.fullmatch(text):
        return int(text.replace("_", ""), 10)
    if _FLOAT_RE.fullmatch(text):
        return float(text.replace("_", ""))
    return text


def _looks_like_raw_string(text: str) -> bool:
    return text.startswith("#") and '"' in text and text.endswith("#")


def _decode_raw_string(text: str) -> str:
    m = _re.fullmatch(r'(#+)("""|")(.*)\2\1', text, flags=_re.DOTALL)
    if not m:
        return text
    return m.group(3)


_INTEGER_RE = _re.compile(r"[+-]?\d(?:[\d_])*\Z")
_FLOAT_RE = _re.compile(
    r"[+-]?(?:\d(?:[\d_])*\.\d(?:[\d_])*|\d(?:[\d_])*[eE][+-]?\d(?:[\d_])*|\d(?:[\d_]*)\.\d(?:[\d_]*)[eE][+-]?\d(?:[\d_])*)\Z"
)

_DEFINE_REF_RE = _re.compile(r"\{\{([A-Z_][A-Z0-9_-]*)\}\}")


def _resolve_define_references(value: str, ctx: ParseContext) -> str:
    def _replacer(m: _re.Match) -> str:
        name = m.group(1)
        resolved = ctx.property_defines.get(name)
        if resolved is None:
            return m.group(0)
        return str(resolved)

    return _DEFINE_REF_RE.sub(_replacer, value)


_VAR_TYPE_MAP: dict[str, VariableType] = {
    "STRING": VariableType.STRING,
    "INT": VariableType.INT,
    "FLOAT": VariableType.FLOAT,
    "BOOL": VariableType.BOOL,
    "NULL": VariableType.NULL,
    "DOCUMENT": VariableType.DOCUMENT,
    "NESTED": VariableType.NESTED,
    "JSON": VariableType.JSON,
    # LIST_*/OPT_* aliases — map to base scalar types
    "LIST_STRING": VariableType.STRING,
    "LIST_INT": VariableType.INT,
    "LIST_FLOAT": VariableType.FLOAT,
    "LIST_DOCUMENT": VariableType.DOCUMENT,
    "LIST_AUTO": VariableType.AUTO,
    "OPT_STRING": VariableType.STRING,
    "OPT_INT": VariableType.INT,
    "OPT_FLOAT": VariableType.FLOAT,
}


def resolve_index_types(
    parent: FieldLikeNode,
) -> tuple[VariableType, VariableType, bool]:
    """Return (accept_base, ret_base, is_array) for Index/First/Last ops.

    These ops accept a list and return a scalar, so is_array is always False
    for the return side.
    """
    if parent.body:
        prev = parent.body[-1]
        accept = prev.ret
        ret = prev.ret
        return accept, ret, prev.is_array
    return VariableType.AUTO, VariableType.AUTO, True


def resolve_jsonify_type(
    json_def: JsonDef, path: str, ctx: ParseContext
) -> tuple[VariableType, bool]:
    """Resolve the return type and is_array for a jsonify operation.

    Returns (base_type, is_array).
    """
    ja = json_def.is_array
    if not path:
        return VariableType.JSON, ja
    segments = path.split(".")
    current_def = json_def
    current_is_array = ja
    for i, segment in enumerate(segments):
        if current_is_array and segment.isdigit():
            current_is_array = False
            continue
        field = None
        for f in current_def.body:
            if isinstance(f, JsonDefField) and (
                f.name == segment or f.alias == segment
            ):
                field = f
                break
        if field is None:
            return VariableType.JSON, False
        ti = field.type_info
        if ti is None:
            return VariableType.JSON, False
        if i == len(segments) - 1:
            return ti.base, ti.is_array
        if ti.base != VariableType.JSON:
            return VariableType.JSON, False
        if not ti.ref:
            return VariableType.JSON, False
        nested_def = ctx.json_defs.get(ti.ref)
        if not nested_def:
            return VariableType.JSON, False
        current_def = nested_def
        current_is_array = ti.is_array
    return VariableType.JSON, current_is_array


# ── Typedef builder ──────────────────────────────────────────────────────────────


def _compute_type_info(
    ret: VariableType, body: list[AstNode]
) -> TypeInfo | None:
    """Compute TypeInfo from a pipeline node's ret type and body contents."""
    ref: str | None = None
    is_arr = False
    if ret in (VariableType.NESTED, VariableType.JSON):
        for child in body:
            if isinstance(child, Nested):
                ref = child.struct_name
                is_arr = child.is_array
                break
            if isinstance(child, Jsonify):
                ref = child.schema_name
                is_arr = child.is_array
                break
    return TypeInfo(base=ret, is_array=is_arr, ref=ref)


def typedef_from_struct(struct: Struct, parent: Module) -> TypeDef:
    typedef = TypeDef(
        parent=parent, name=struct.name, struct_type=struct._typedef_type
    )
    for item in struct.body:
        if isinstance(item, (Field, Key, Value)):
            field_name = (
                item.name
                if isinstance(item, Field)
                else ("key" if isinstance(item, Key) else "value")
            )
            # Use the Field's own type_info (already correctly computed during
            # pipeline parsing) instead of recomputing via _compute_type_info,
            # which only propagates is_array for NESTED/JSON types.
            typedef.body.append(
                TypeDefField(
                    parent=typedef,
                    name=field_name,
                    type_info=item.type_info,
                )
            )
    return typedef


# ── Expression dispatch ──────────────────────────────────────────────────────────


def _build_expression(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
) -> AstNode:
    name = node.name

    # block define inlining
    if name in ctx.children_defines:
        for child in ctx.children_defines[name]:
            _build_expression(child, parent, ctx, lint)
        return parent.body[-1] if parent.body else parent

    # @<name> references
    if name.startswith("@") and name not in {
        "@doc",
        "@init",
        "@pre-validate",
        "@split-doc",
        "@key",
        "@value",
        "@table",
        "@rows",
        "@match",
    }:
        field_name = name[1:]
        struct = parent.parent
        if not isinstance(struct, Struct):
            raise BuildTimeError(f"@{field_name} outside of struct context")
        init_field = next(
            (
                i
                for i in struct.init.body
                if isinstance(i, InitField) and i.name == field_name
            ),
            None,
        )
        if init_field is None:
            raise BuildTimeError(
                f"Unknown @init reference '@{field_name}' in {type(parent).__name__}"
            )
        prev_type = init_field.ret
        return Self(
            parent=parent,
            accept=prev_type,
            ret=prev_type,
            is_array=init_field.is_array,
            name=field_name,
        )

    if name == "self":
        ref_name = str(node.args[0].value) if node.args else "<name>"
        raise BuildTimeError(
            f"'self {ref_name}' syntax is no longer supported; use '@{ref_name}' instead"
        )

    # dispatch
    handler = _EXPRESSION_HANDLERS.get(name)
    if handler is None:
        raise BuildTimeError(f"Unknown expression: {name}")
    return handler(node, parent, ctx, lint)


def parse_expressions(
    kdl_nodes: Sequence[KdlNode],
    parent: FieldLikeNode | CheckMethod,
    ctx: ParseContext,
    lint: LintContext,
    *,
    _add_return: bool = True,
) -> None:
    if not kdl_nodes:
        return

    prev_ctx = lint.walk_context
    lint.walk_context = WalkCtx.PIPELINE
    for node in kdl_nodes:
        if node.name in ctx.children_defines:
            lint.push(node.name)
            parse_expressions(
                ctx.children_defines[node.name],
                parent,
                ctx,
                lint,
                _add_return=False,
            )
            lint.pop()
            continue
        if node.name.startswith("@") and node.name not in {
            "@doc",
            "@init",
            "@pre-validate",
            "@split-doc",
            "@key",
            "@value",
            "@table",
            "@rows",
            "@match",
        }:
            field_name = node.name[1:]
            struct = parent.parent
            if not isinstance(struct, Struct):
                raise BuildTimeError(f"@{field_name} outside of struct context")
            init_field = next(
                (
                    i
                    for i in struct.init.body
                    if isinstance(i, InitField) and i.name == field_name
                ),
                None,
            )
            if init_field is None:
                raise BuildTimeError(
                    f"Unknown @init reference '@{field_name}' in {type(parent).__name__}"
                )
            prev_type = init_field.ret
            expr = Self(
                parent=parent,
                accept=prev_type,
                ret=prev_type,
                is_array=init_field.is_array,
                name=field_name,
            )
            parent.body.append(expr)
            continue
        if node.name == "self":
            ref_name = str(node.args[0].value) if node.args else "<name>"
            raise BuildTimeError(
                f"'self {ref_name}' syntax is no longer supported; use '@{ref_name}' instead"
            )
        handler = _EXPRESSION_HANDLERS.get(node.name)
        if handler is None:
            lint_wildcard_op(node, ctx, lint)
            raise BuildTimeError(f"Unknown expression: {node.name}")
        lint.push(node.name)
        lint_pipeline_op(node, lint)
        expr = handler(node, parent, ctx, lint)  # type: ignore[assignment,arg-type]
        if expr is None:
            lint.pop()
            continue
        if isinstance(expr, Fallback):
            lint.pop()
            continue
        elif isinstance(expr, Filter):
            parse_filter_expr(node.children, expr, ctx, lint)
        elif isinstance(expr, Assert):
            parse_assert_expr(node.children, expr, ctx, lint)
        elif isinstance(expr, Match):
            parse_match_expr(node.children, expr, ctx, lint)
        parent.body.append(expr)
        lint.pop()

    if _add_return and parent.body:
        last_ret = parent.body[-1].ret
        parent.body.append(Return(parent=parent, ret=last_ret, accept=last_ret))
        parent.ret = last_ret

        # Populate type_info on Field/Value/InitField
        if isinstance(parent, (Field, Value, InitField)):
            is_arr = (
                parent.body[-2].is_array if len(parent.body) >= 2 else False
            )
            ref: str | None = None
            if last_ret in (VariableType.NESTED, VariableType.JSON):
                for child in parent.body:
                    if isinstance(child, Nested):
                        ref = child.struct_name
                        is_arr = child.is_array
                        break
                    if isinstance(child, Jsonify):
                        ref = child.schema_name
                        is_arr = child.is_array
                        break
            parent.is_array = is_arr
            parent.type_info = TypeInfo(base=last_ret, is_array=is_arr, ref=ref)

    lint.walk_context = prev_ctx


# ── Expression handlers ─────────────────────────────────────────────────────────

_ExpressionHandler = Callable[
    [KdlNode, FieldLikeNode, ParseContext, LintContext], AstNode
]
_EXPRESSION_HANDLERS: dict[str, _ExpressionHandler] = {}


def _reg_expr(name: str):
    def decorator(fn: _ExpressionHandler) -> _ExpressionHandler:
        _EXPRESSION_HANDLERS[name] = fn
        return fn

    return decorator


# -- selectors ----------------------------------------------------------------


@_reg_expr("css")
def _expr_css(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if node.children:
        queries = [
            resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return CssSelect(parent=parent, queries=queries)
    query = resolve_selector_arg(node.args[0].value, ctx)
    lint_validate_css(node, lint, query)
    return CssSelect(parent=parent, query=query)


@_reg_expr("css-all")
def _expr_css_all(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if node.children:
        queries = [
            resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return CssSelectAll(parent=parent, queries=queries)
    query = resolve_selector_arg(node.args[0].value, ctx)
    lint_validate_css(node, lint, query)
    return CssSelectAll(parent=parent, query=query)


@_reg_expr("xpath")
def _expr_xpath(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if node.children:
        queries = [
            resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return XpathSelect(parent=parent, queries=queries)
    query = resolve_selector_arg(node.args[0].value, ctx)
    lint_validate_xpath(node, lint, query)
    return XpathSelect(parent=parent, query=query)


@_reg_expr("xpath-all")
def _expr_xpath_all(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if node.children:
        queries = [
            resolve_selector_child_name(c.name, ctx) for c in node.children
        ]
        return XpathSelectAll(parent=parent, queries=queries)
    query = resolve_selector_arg(node.args[0].value, ctx)
    lint_validate_xpath(node, lint, query)
    return XpathSelectAll(parent=parent, query=query)


@_reg_expr("css-remove")
def _expr_css_remove(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    lint_validate_css(node, lint, cast(str, query))
    return CssRemove(parent=parent, query=cast(str, query))


@_reg_expr("xpath-remove")
def _expr_xpath_remove(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    query = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    lint_validate_xpath(node, lint, cast(str, query))
    return XpathRemove(parent=parent, query=cast(str, query))


# -- extract --------------------------------------------------------------------


@_reg_expr("text")
def _expr_text(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if parent.body:
        prev = parent.body[-1]
        prev_type = prev.ret
        is_arr = prev.is_array
    else:
        prev_type = VariableType.DOCUMENT
        is_arr = False
    return Text(
        parent=parent,
        accept=prev_type,
        ret=VariableType.STRING,
        is_array=is_arr,
    )


@_reg_expr("raw")
def _expr_raw(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if parent.body:
        prev = parent.body[-1]
        prev_type = prev.ret
        is_arr = prev.is_array
    else:
        prev_type = VariableType.DOCUMENT
        is_arr = False
    return Raw(
        parent=parent,
        accept=prev_type,
        ret=VariableType.STRING,
        is_array=is_arr,
    )


@_reg_expr("attr")
def _expr_attr(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if parent.body:
        prev = parent.body[-1]
        prev_type = prev.ret
        is_arr = prev.is_array
    else:
        prev_type = VariableType.DOCUMENT
        is_arr = False
    return Attr(
        parent=parent,
        accept=prev_type,
        ret=VariableType.STRING,
        is_array=is_arr,
        keys=tuple(a.value for a in node.args),
    )


# -- string ---------------------------------------------------------------------


@_reg_expr("trim")
def _expr_trim(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    substr = (
        cast(
            str,
            ctx.property_defines.get(node.args[0].value, node.args[0].value),
        )
        if node.args
        else ""
    )
    prev = parent.body[-1]
    return Trim(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        substr=substr,
    )


@_reg_expr("ltrim")
def _expr_ltrim(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    substr = (
        cast(
            str,
            ctx.property_defines.get(node.args[0].value, node.args[0].value),
        )
        if node.args
        else ""
    )
    prev = parent.body[-1]
    return Ltrim(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        substr=substr,
    )


@_reg_expr("rtrim")
def _expr_rtrim(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    substr = (
        cast(
            str,
            ctx.property_defines.get(node.args[0].value, node.args[0].value),
        )
        if node.args
        else ""
    )
    prev = parent.body[-1]
    return Rtrim(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        substr=substr,
    )


@_reg_expr("normalize-space")
def _expr_norm_space(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    return NormalizeSpace(
        parent=parent, accept=prev.ret, ret=prev.ret, is_array=prev.is_array
    )


@_reg_expr("rm-prefix")
def _expr_rm_prefix(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    substr = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev = parent.body[-1]
    return RmPrefix(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        substr=cast(str, substr),
    )


@_reg_expr("rm-suffix")
def _expr_rm_suffix(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    substr = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev = parent.body[-1]
    return RmSuffix(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        substr=cast(str, substr),
    )


@_reg_expr("rm-prefix-suffix")
def _expr_rm_prefix_suffix(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    substr = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev = parent.body[-1]
    return RmPrefixSuffix(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        substr=cast(str, substr),
    )


@_reg_expr("fmt")
def _expr_fmt(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    tmpl = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    prev = parent.body[-1]
    return Fmt(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        template=cast(str, tmpl),
    )


@_reg_expr("repl")
def _expr_repl(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    if node.children:
        items = {
            str(child.name): str(child.args[0].value) for child in node.children
        }
        return ReplMap(
            parent=parent,
            accept=prev.ret,
            ret=prev.ret,
            is_array=prev.is_array,
            replacements=items,
        )
    old = cast(
        str, ctx.property_defines.get(node.args[0].value, node.args[0].value)
    )
    new = cast(
        str, ctx.property_defines.get(node.args[1].value, node.args[1].value)
    )
    return Repl(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        old=old,
        new=new,
    )


@_reg_expr("lower")
def _expr_lower(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    return Lower(
        parent=parent, accept=prev.ret, ret=prev.ret, is_array=prev.is_array
    )


@_reg_expr("upper")
def _expr_upper(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    return Upper(
        parent=parent, accept=prev.ret, ret=prev.ret, is_array=prev.is_array
    )


@_reg_expr("split")
def _expr_split(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    sep = cast(
        str, ctx.property_defines.get(node.args[0].value, node.args[0].value)
    )
    return Split(parent=parent, sep=sep)


@_reg_expr("join")
def _expr_join(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    sep = cast(
        str, ctx.property_defines.get(node.args[0].value, node.args[0].value)
    )
    return Join(parent=parent, sep=sep)


@_reg_expr("unescape")
def _expr_unescape(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    return Unescape(
        parent=parent, accept=prev.ret, ret=prev.ret, is_array=prev.is_array
    )


# -- regex ----------------------------------------------------------------------


@_reg_expr("re")
def _expr_re(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    pattern = normalize_regex_pattern(raw)
    prev = parent.body[-1]
    return Re(
        parent=parent,
        pattern=pattern,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
    )


@_reg_expr("re-all")
def _expr_re_all(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    pattern = normalize_regex_pattern(raw)
    return ReAll(parent=parent, pattern=pattern)


@_reg_expr("re-sub")
def _expr_re_sub(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    raw = ctx.property_defines.get(node.args[0].value, node.args[0].value)
    pattern = normalize_regex_pattern(raw)
    repl = cast(
        str, ctx.property_defines.get(node.args[1].value, node.args[1].value)
    )
    return ReSub(
        parent=parent,
        accept=prev.ret,
        ret=prev.ret,
        is_array=prev.is_array,
        pattern=pattern,
        repl=repl,
    )


# -- array ----------------------------------------------------------------------


@_reg_expr("index")
def _expr_index(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    accept, ret, _prev_is_array = resolve_index_types(parent)
    return Index(
        parent=parent,
        i=int(node.args[0].value),
        accept=accept,
        ret=ret,
        is_array=False,
    )


@_reg_expr("first")
def _expr_first(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    accept, ret, _prev_is_array = resolve_index_types(parent)
    return Index(parent=parent, i=0, accept=accept, ret=ret, is_array=False)


@_reg_expr("last")
def _expr_last(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    accept, ret, _prev_is_array = resolve_index_types(parent)
    return Index(parent=parent, i=-1, accept=accept, ret=ret, is_array=False)


@_reg_expr("slice")
def _expr_slice(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    start, end = int(node.args[0].value), int(node.args[1].value)
    if parent.body:
        prev = parent.body[-1]
        return Slice(
            parent=parent,
            start=start,
            end=end,
            accept=prev.ret,
            ret=prev.ret,
            is_array=prev.is_array,
        )
    return Slice(parent=parent, start=start, end=end)


@_reg_expr("len")
def _expr_len(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    return Len(parent=parent)


@_reg_expr("unique")
def _expr_unique(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    keep_order = bool(node.get_prop("keep-order") or False)
    return Unique(parent=parent, keep_order=keep_order)


# -- casts ----------------------------------------------------------------------


@_reg_expr("to-int")
def _expr_to_int(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    return ToInt(
        parent=parent,
        accept=prev.ret,
        ret=VariableType.INT,
        is_array=prev.is_array,
    )


@_reg_expr("to-float")
def _expr_to_float(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev = parent.body[-1]
    return ToFloat(
        parent=parent,
        accept=prev.ret,
        ret=VariableType.FLOAT,
        is_array=prev.is_array,
    )


@_reg_expr("to-bool")
def _expr_to_bool(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    prev_type = parent.body[-1].ret
    return ToBool(parent=parent, accept=prev_type)


@_reg_expr("jsonify")
def _expr_jsonify(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    schema_name = str(node.args[0].value)
    path = node.get_prop("path") or ""
    json_def = ctx.json_defs.get(schema_name)
    if json_def is None:
        lint.error(
            node,
            message=f"jsonify: JSON schema '{schema_name}' not found",
            code="E300",
        )
        return None
    ret_type, is_array = resolve_jsonify_type(json_def, path, ctx)
    return Jsonify(
        parent=parent,
        schema_name=schema_name,
        path=path,
        ret=ret_type,
        is_array=is_array,
    )


@_reg_expr("nested")
def _expr_nested(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    struct_name = str(node.args[0].value)
    struct = ctx.structs.get(struct_name)
    if struct is None:
        lint.error(
            node,
            message=f"nested: struct '{struct_name}' not found",
            code="E300",
        )
        return None
    is_array = isinstance(struct, (StructFlatList, StructList))
    return Nested(parent=parent, struct_name=struct_name, is_array=is_array)


# -- control --------------------------------------------------------------------


@_reg_expr("fallback")
def _expr_fallback(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    value = [] if not node.args else node.args[0].value
    prev = parent.body[-1]
    prev_type = prev.ret
    # For fallback #null, we don't change the type — is_optional is set on
    # the parent's type_info later in parse_expressions.  Here we just pass
    # the current type through unchanged.
    start_default = FallbackStart(parent=parent, value=value)
    end_default = FallbackEnd(
        parent=parent,
        value=value,
        accept=prev_type,
        ret=prev_type,
        is_array=prev.is_array,
    )
    parent.body.insert(0, start_default)
    parent.body.append(end_default)
    return Fallback(parent=parent, value=value)


@_reg_expr("filter")
def _expr_filter(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if not parent.body:
        return Filter(
            parent=parent,
            accept=VariableType.DOCUMENT,
            ret=VariableType.DOCUMENT,
            is_array=True,
        )
    prev = parent.body[-1]
    return Filter(
        parent=parent, accept=prev.ret, ret=prev.ret, is_array=prev.is_array
    )


@_reg_expr("assert")
def _expr_assert(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    if isinstance(parent, PreValidate) and not parent.body:
        return Assert(
            parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.NULL
        )
    if not parent.body:
        return Assert(
            parent=parent,
            accept=VariableType.DOCUMENT,
            ret=VariableType.DOCUMENT,
        )
    prev_type = parent.body[-1].ret
    return Assert(parent=parent, accept=prev_type, ret=prev_type)


@_reg_expr("match")
def _expr_match(
    node: KdlNode, parent: FieldLikeNode, ctx: ParseContext, lint: LintContext
):
    return Match(
        parent=parent, accept=VariableType.DOCUMENT, ret=VariableType.STRING
    )
