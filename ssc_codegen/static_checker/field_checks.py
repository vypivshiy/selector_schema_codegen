from typing import List
import warnings
from cssselect import SelectorSyntaxError

from ssc_codegen.tokens import VariableType, TokenType, TOKENS_REGEX
from ssc_codegen.selector_utils import validate_css_query, validate_xpath_query
from ssc_codegen.ast_ import ExprDefaultValueWrapper
from ssc_codegen.document_utlis import analyze_re_expression
from ssc_codegen.static_checker.base import FMT_MAPPING_METHODS
from ssc_codegen.static_checker.utils import (
    FieldCheckContext,
    AnalysisError
)


def check_field_type_static(ctx: FieldCheckContext) -> List[AnalysisError]:
    errors = []
    cursor = VariableType.DOCUMENT

    for i, expr in enumerate(ctx.document.stack):
        accept = expr.accept_type
        ret = expr.ret_type
        exclude = expr.exclude_types

        compatible = False
        if accept == cursor:
            compatible = True
        elif accept == VariableType.ANY:
            compatible = True
        elif accept == VariableType.LIST_ANY and cursor in (
            VariableType.LIST_STRING,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
            VariableType.LIST_DOCUMENT,
        ):
            compatible = True
        elif cursor in (VariableType.ANY, VariableType.LIST_ANY):
            compatible = True

        if compatible:
            if exclude and cursor in exclude:
                pass
            else:
                cursor = ret
                continue

        # Определяем проблемный метод
        method_name = FMT_MAPPING_METHODS.get(expr.kind, "unknown")

        msg = f"Cannot call .{method_name}() on {cursor.name.lower()} value"
        tip = ""

        if (
            i > 0
            and ctx.document.stack[i - 1].kind == ExprDefaultValueWrapper.kind
            and cursor in (VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
            and accept in (VariableType.STRING, VariableType.LIST_STRING)
        ):
            tip = (
                "After `default()` you must extract text/attribute before calling string methods. "
                "Use `.text()`, `.attr('...')`, or pseudoselectors like `::text` first."
            )
        elif cursor in (
            VariableType.DOCUMENT,
            VariableType.LIST_DOCUMENT,
        ) and accept in (VariableType.STRING, VariableType.LIST_STRING):
            tip = (
                "You forgot to extract text/attribute after selector. "
                "Use `.text()`, `.attr('...')`, or `::text` / `::attr(...)` in CSS."
            )

        errors.append(
            AnalysisError(
                message=msg,
                tip=tip,
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
                problem_method=method_name,
            )
        )
        cursor = ret

    return errors


def check_field_default_value(ctx: FieldCheckContext) -> List[AnalysisError]:
    errors = []
    stack = ctx.document.stack
    default_nodes = [
        (i, n) for i, n in enumerate(stack) if n.kind == TokenType.EXPR_DEFAULT
    ]

    if not default_nodes:
        return []

    if len(default_nodes) > 1:
        errors.append(
            AnalysisError(
                message=f"{ctx.schema.__name__}.{ctx.field_name}: multiple `default()` calls",
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        )

    idx, first_default = default_nodes[0]
    if idx != 0:
        errors.append(
            AnalysisError(
                message=f"{ctx.schema.__name__}.{ctx.field_name}: `default()` must be the first call, not at position {idx}",
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        )

    if ctx.field_name in ("__PRE_VALIDATE__", "__SPLIT_DOC__"):
        errors.append(
            AnalysisError(
                message=f"{ctx.schema.__name__}.{ctx.field_name}: `default()` is not allowed in magic fields",
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        )

    default_value = first_default.kwargs["value"]
    final_type = ctx.document.stack_last_ret

    if default_value is None:
        if final_type in (
            VariableType.DOCUMENT,
            VariableType.LIST_DOCUMENT,
            VariableType.BOOL,
        ):
            msg = f"Default value cannot be None for type(s) ({VariableType.DOCUMENT.name}, {VariableType.LIST_DOCUMENT.name}, {VariableType.BOOL.name})"
            errors.append(
                AnalysisError(
                    message=f"{ctx.schema.__name__}.{ctx.field_name}: {msg}",
                    field_name=ctx.field_name,
                    lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                    filename=ctx.filename,
                )
            )
        return errors

    # Infer type of default value
    if isinstance(default_value, str):
        default_ast_type = VariableType.STRING
    elif isinstance(default_value, bool):
        default_ast_type = VariableType.BOOL
    elif isinstance(default_value, int):
        default_ast_type = VariableType.INT
    elif isinstance(default_value, float):
        default_ast_type = VariableType.FLOAT
    elif isinstance(default_value, list):
        if len(default_value) != 0:
            warnings.warn(
                f"{ctx.schema.__name__}.{ctx.field_name}: not supported pass values to list",
                category=SyntaxWarning,
            )
        default_ast_type = final_type
    else:
        errors.append(
            AnalysisError(
                message=f"{ctx.schema.__name__}.{ctx.field_name}: Unsupported default value: `{default_value!r}`<{type(default_value).__name__}>",
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        )
        return errors

    if isinstance(default_value, list):
        if default_ast_type not in (
            VariableType.LIST_STRING,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
        ):
            msg = (
                f"default({default_value!r}) wrong last list return type expr "
                f"(expected type(s) {(VariableType.LIST_STRING.name, VariableType.LIST_FLOAT.name, VariableType.LIST_INT.name)}) "
                f"got `{final_type.name}`"
            )
            errors.append(
                AnalysisError(
                    message=f"{ctx.schema.__name__}.{ctx.field_name}: {msg}",
                    field_name=ctx.field_name,
                    lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                    filename=ctx.filename,
                )
            )
    elif default_ast_type != final_type:
        msg = f"default({default_value!r}) wrong last return type expr (expected type `{default_ast_type.name}` got `{final_type.name}`)"
        errors.append(
            AnalysisError(
                message=f"{ctx.schema.__name__}.{ctx.field_name}: {msg}",
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        )
    elif (
        ctx.field_name == "__KEY__" and default_ast_type != VariableType.STRING
    ):
        msg = f"__KEY__ should be a string, not {default_ast_type.name}"
        errors.append(
            AnalysisError(
                message=f"{ctx.schema.__name__}.{ctx.field_name}: {msg}",
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        )

    return errors


def check_field_html_queries(ctx: FieldCheckContext) -> List[AnalysisError]:
    errors = []
    SELECT_CSS_EXPR = (
        TokenType.EXPR_CSS,
        TokenType.EXPR_CSS_ALL,
        TokenType.IS_CSS,
    )
    SELECT_XPATH_EXPR = (
        TokenType.EXPR_XPATH,
        TokenType.EXPR_XPATH_ALL,
        TokenType.IS_XPATH,
    )

    for i, expr in enumerate(ctx.document.stack):
        if expr.kind not in SELECT_CSS_EXPR + SELECT_XPATH_EXPR:
            continue
        query = expr.kwargs.get("query", "")
        try:
            if expr.kind in SELECT_CSS_EXPR:
                validate_css_query(query)
            elif expr.kind in SELECT_XPATH_EXPR:
                validate_xpath_query(query)
        except SelectorSyntaxError as e:
            method_name = FMT_MAPPING_METHODS.get(expr.kind, "unknown")
            kind = "CSS" if expr.kind in SELECT_CSS_EXPR else "XPath"
            msg = f"Invalid {kind} selector in .{method_name}()"
            errors.append(
                AnalysisError(
                    message=msg,
                    tip=str(e),
                    field_name=ctx.field_name,
                    lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                    filename=ctx.filename,
                    problem_method=method_name,
                )
            )
    return errors


def check_field_split_doc_ret_type(
    ctx: FieldCheckContext,
) -> List[AnalysisError]:
    if ctx.field_name != "__SPLIT_DOC__":
        return []
    if ctx.document.stack_last_ret != VariableType.LIST_DOCUMENT:
        expr_repr = "" # TODO ???
        msg = f"{ctx.schema.__name__}.{ctx.field_name} = {expr_repr}  # Expected type `{VariableType.LIST_DOCUMENT.name}`, got `{ctx.document.stack_last_ret.name}`"
        return [
            AnalysisError(
                message=msg,
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        ]
    return []


def check_field_key_ret_type(ctx: FieldCheckContext) -> List[AnalysisError]:
    if ctx.field_name != "__KEY__":
        return []
    if (
        ctx.document.stack
        and ctx.document.stack[0].kind == TokenType.EXPR_DEFAULT
    ):
        value = ctx.document.stack[0].kwargs["value"]
        if not isinstance(value, str):
            expr_repr = _prettify_expr_at(
                ctx.document, len(ctx.document.stack) - 1
            )
            msg = f"{ctx.schema.__name__}.{ctx.field_name} = {expr_repr}  # default value should be a string, not `value<{type(value).__name__}>`"
            return [
                AnalysisError(
                    message=msg,
                    field_name=ctx.field_name,
                    lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                    filename=ctx.filename,
                )
            ]
    if ctx.document.stack_last_ret != VariableType.STRING:
        expr_repr = _prettify_expr_at(ctx.document, len(ctx.document.stack) - 1)
        msg = f"{ctx.schema.__name__}.{ctx.field_name} = {expr_repr}  # Expected type `{VariableType.STRING.name}`, got `{ctx.document.stack_last_ret.name}`"
        return [
            AnalysisError(
                message=msg,
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        ]
    return []


def check_other_field_type(ctx: FieldCheckContext) -> List[AnalysisError]:
    if getattr(ctx.document, "__IS_LITERAL_DOC__", False):
        return []
    if ctx.field_name in ("__KEY__", "__SPLIT_DOC__", "__PRE_VALIDATE__"):
        return []
    if ctx.document.stack_last_ret in (
        VariableType.LIST_DOCUMENT,
        VariableType.DOCUMENT,
    ):
        expr_repr = _prettify_expr_at(ctx.document, len(ctx.document.stack) - 1)
        msg = f"{ctx.schema.__name__}.{ctx.field_name} = {expr_repr}  # Not allowed type(s) `{VariableType.LIST_DOCUMENT.name}, {VariableType.DOCUMENT.name}`"
        return [
            AnalysisError(
                message=msg,
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        ]
    return []


def check_regex_expr(ctx: FieldCheckContext) -> List[AnalysisError]:
    re_exprs = [
        expr for expr in ctx.document.stack if expr.kind in TOKENS_REGEX
    ]
    if not re_exprs:
        return []

    errors = []
    for expr in re_exprs:
        pattern = expr.kwargs["pattern"]
        result = None
        if expr.kind in (TokenType.EXPR_REGEX, TokenType.EXPR_REGEX_ALL):
            result = analyze_re_expression(pattern, max_groups=1)
        elif expr.kind in (
            TokenType.EXPR_REGEX_SUB,
            TokenType.EXPR_LIST_REGEX_SUB,
            TokenType.IS_STRING_REGEX_MATCH,
            TokenType.ALL_LIST_STRING_REGEX_MATCH,
            TokenType.ANY_LIST_STRING_REGEX_MATCH,
        ):
            result = analyze_re_expression(pattern, allow_empty_groups=True)

        if result and not result.value:
            expr_repr = _prettify_expr_at(
                ctx.document, len(ctx.document.stack) - 1
            )
            msg = f"{ctx.schema.__name__}.{ctx.field_name} = {expr_repr}  # {result.msg}"
            errors.append(
                AnalysisError(
                    message=msg,
                    tip=result.tip,
                    field_name=ctx.field_name,
                    lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                    filename=ctx.filename,
                )
            )
    return errors


def check_jsonify_expr(ctx: FieldCheckContext) -> List[AnalysisError]:
    has_json = any(
        expr.kind == TokenType.TO_JSON for expr in ctx.document.stack
    )
    has_default = any(
        expr.kind == TokenType.EXPR_DEFAULT for expr in ctx.document.stack
    )
    if has_json and has_default:
        expr_repr = _prettify_expr_at(ctx.document, len(ctx.document.stack) - 1)
        msg = f"{ctx.schema.__name__}.{ctx.field_name} = {expr_repr} # jsonify not allowed with default expr"
        return [
            AnalysisError(
                message=msg,
                field_name=ctx.field_name,
                lineno=ctx.field_meta.lineno if ctx.field_meta else None,
                filename=ctx.filename,
            )
        ]
    return []
