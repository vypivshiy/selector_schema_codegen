from abc import ABC, abstractmethod
import inspect
from dataclasses import dataclass, replace
from typing import Any, Iterable, Iterator, TypeAlias

from ssc_codegen.ast import (
    Node,
    Module,
    Utilities,
    JsonDef,
    JsonDefField,
    TypeDef,
    TypeDefField,
    Struct,
    StructBase,
    StructRest,
    StartParse,
    Init,
    InitField,
    InitFieldCall,
    Field,
    PreValidate,
    CheckMethod,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableMatchKey,
    TableRows,
    MethodRest,
    MethodFetch,
    ErrorResponse,
    ResultVariantDef,
    ResultAliasDef,
    MatcherListDef,
    Template,
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
    Attr,
    Text,
    Raw,
    Trim,
    Ltrim,
    Rtrim,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    NormalizeSpace,
    Unescape,
    Re,
    ReAll,
    ReSub,
    Index,
    Slice,
    Len,
    Unique,
    ToInt,
    ToFloat,
    ToBool,
    Jsonify,
    Nested,
    Self,
    Return,
    Fallback,
    Filter,
    Assert,
    Match,
    LogicAnd,
    LogicNot,
    LogicOr,
    PredCss,
    PredXpath,
    PredHasAttr,
    PredAttrContains,
    PredAttrStarts,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredTextContains,
    PredTextStarts,
    PredTextEnds,
    PredTextRe,
    PredContains,
    PredEq,
    PredNe,
    PredStarts,
    PredEnds,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
    PredRe,
    PredReAll,
    PredReAny,
    CodeEndHook,
    CodeStartHook,
    TypeInfo,
    VariableType as VT,
    StructType as ST,
    PlaceholderSpec,
)
from ssc_codegen.converters.base import ConverterContext
from ssc_codegen.converters.helpers import to_pascal_case

# Node categories — select the body-traversal mode (ported from base.py).
# Container: depth+1, index=0, no advance between siblings.
_CONTAINER_NODES = (JsonDef, TypeDef, StructBase, Init)

# Pipeline: index advances after each node (delegated to _emit_pipeline).
_PIPELINE_NODES = (
    Field,
    InitField,
    PreValidate,
    CheckMethod,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableMatchKey,
    TableRows,
)

# Predicate: depth+1, index=0, advance between siblings.
_PREDICATE_NODES = (Filter, Assert, Match, LogicNot, LogicAnd, LogicOr)


@dataclass(frozen=True)
class StdDef:
    """Signal: register a std-library helper, co-located with its caller.

    Yield ``STD(name, code=..., imports=...)`` from a ``visit_*`` method
    right next to the line that calls the helper — the definition is
    self-contained (no external ``STD_LIBS`` registry to keep in sync).
    Registration is idempotent by ``name``: the first emission for a name
    wins; subsequent ones are no-ops (identical bodies are expected within
    a single conversion, since a converter runs exactly one dialect).

    ``imports`` are pulled into the std import pool automatically.
    ``code`` is the helper body as a string in the target language;
    ``inspect.cleandoc`` is applied at render time so authors can indent
    freely.
    """

    name: str
    imports: list[str]
    code: str


@dataclass(frozen=True)
class ImportUse:
    """Signal: register a main-module import line.

    Use ``IMPORT(line)`` for imports required by the main generated code
    (type annotations, direct library calls, etc.). Std-helper imports
    are pulled automatically from the co-located ``STD()`` emissions and
    go to the std pool.
    """

    line: str


def STD(name: str, *, code: str, imports: list[str] | None = None) -> StdDef:
    """Sugar for ``yield StdDef(name, imports, code)``.

    ``code`` is the helper source (target-language string, required).
    ``imports`` is optional (defaults to no extra imports).

    Example::

        def visit_attr(self, node, ctx):
            yield STD(
                "std_get_attr",
                code="def std_get_attr(el, key): return ' '.join(el.get_attribute_list(key))",
            )
            yield f"{ctx.indent}{ctx.nxt} = std_get_attr({ctx.prv}, {key})"
    """
    return StdDef(name, list(imports) if imports else [], code)


def IMPORT(line: str) -> ImportUse:
    """Sugar for ``yield ImportUse(line)``."""
    return ImportUse(line)


VisitStream: TypeAlias = (
    Iterator[str | None | Iterable[str] | StdDef | ImportUse] | None
)

# TODO: replace to sentinel object
TRAVERSE = None


# ===========================================================================
# Shared AST utilities (language-agnostic, used by all dialects)
# ===========================================================================


def module_has_rest(module: Module) -> bool:
    """True if the module contains at least one REST struct."""
    return any(isinstance(n, StructRest) for n in module.body)


def module_is_rest_only(module: Module) -> bool:
    """True if ALL structs in the module are REST structs (or there are none)."""
    structs = [n for n in module.body if isinstance(n, StructBase)]
    return len(structs) == 0 or all(isinstance(s, StructRest) for s in structs)


def err_subclass_name(struct_name: str, err: "ErrorResponse") -> str:
    """Deterministic error-subclass name from struct name + error spec.

    Re-exported from ``core/rest_artifacts`` (the canonical home) for backwards
    compatibility — existing converters import it from here.
    """
    from ssc_codegen.core.rest_artifacts import (
        err_subclass_name as _impl,
    )

    return _impl(struct_name, err)


def dict_entry_placeholder(tmpl: Template) -> PlaceholderSpec | None:
    """Return the PlaceholderSpec for a dict entry value, or None."""
    return tmpl.single_placeholder()


def dict_needs_builder(d: dict[str, Template]) -> bool:
    """True if any dict entry has an optional or bracket-style array placeholder."""
    for tmpl in d.values():
        ph = tmpl.single_placeholder()
        if ph is None:
            continue
        if ph.is_optional:
            return True
        if ph.is_array and ph.style == "bracket":
            return True
    return False


def find_predicate_container(node: Node) -> Node | None:
    """Walk the parent chain to find the enclosing Filter/Assert/Match/PreValidate."""
    cur = node.parent
    while cur:
        if isinstance(cur, (Filter, Assert, Match, PreValidate)):
            return cur
        cur = cur.parent
    return None


class Visitor(ABC):
    """Base transpiler visitor: walks the AST and dispatches nodes to visit_* methods.

    CONTRACT for visit_* methods (generators):
        - `yield "..."`       -> emit a line
        - `yield TRAVERSE`    -> traverse node.body, then resume the method (pre/post hook)
        - `yield [...]`       -> extend with a list of lines (signals allowed inside)
        - `yield STD(...)`    -> register a co-located std helper (name + code + imports)
        - `yield IMPORT(ln)`  -> register a main-module import line
        - `yield from it`     -> delegate to an iterable
        - `return` / non-generator -> no-op

    `""` is preserved as a blank line; `TRAVERSE` (None) is the traverse-children signal.

    CONTRACT for visit_* methods (reliability):
        - MUST be deterministic: same (node, ctx) -> same yields.
        - MUST NOT have side effects beyond yielding. The two-pass `convert_all`
          runs every visit_* twice (collect + emit).
    """

    # === CLASS-LEVEL CONFIG (override in subclasses) ===
    STD_MODULE_NAME: str = "ssc_std"

    # --- type resolution spelling (data, not behaviour) ---
    DEFAULT_TYPE: str = "Any"
    TYPES: dict[VT, str] = {}
    ARRAY_TYPE_FMT: str = "List[{}]"
    OPTIONAL_TYPE_FMT: str = "Optional[{}]"
    OPTIONAL_ON_OMITEMPTY: bool = False
    DOCUMENT_TYPE: str = "Any"
    DOCUMENT_ARRAY_TYPE: str = "List[Any]"

    # --- predicate formatting ---
    AND_OP: str = "and"

    def __init__(self, var_name: str = "v", indent: str = " " * 4) -> None:
        self.var_name = var_name
        self.indent = indent
        self._file_providers: dict[str, Any] = {}
        self._reset_state()

    # === STATE ===
    def _reset_state(self) -> None:
        """Clear per-conversion state. Called at start of every convert_*."""
        self._std_defs: dict[
            str, tuple[list[str], str]
        ] = {}  # name -> (imports, code)
        self._main_imports: dict[
            str, None
        ] = {}  # ordered set, from IMPORT signals
        self._std_imports: dict[
            str, None
        ] = {}  # ordered set, from STD() emissions

    # === FILE PROVIDERS ===
    def file(self, filename: str):
        """Register a support file provider.

        The decorated function receives ``(module_ast, meta)`` and returns
        the file content as a string.  *meta* is the dict of kwargs passed
        to ``convert_all(**meta)``.
        """

        def decorator(fn):
            self._file_providers[filename] = fn
            return fn

        return decorator

    # === PUBLIC API ===
    def convert(self, module_ast: Module, **meta) -> str:
        """Shortcut: single file in inline mode. Returns main content only.

        Equivalent to ``convert_all(module_ast, inline_std=True, **meta)[""]``.
        """
        return self.convert_all(module_ast, inline_std=True, **meta)[""]

    def convert_all(self, module_ast: Module, **meta) -> dict[str, str]:
        """Convert a single module. Two-pass: collect signals, then emit.

        meta:
            inline_std (bool, default True): inline helpers/imports or split.
            std_module_name (str): override STD_MODULE_NAME.

        Returns:
            ``{"": main_content}`` when inline_std=True.
            ``{"": main_content, "<std_module_name>": std_content}`` when inline_std=False
            and at least one std helper is used.
            Additional files from ``@converter.file(name)`` providers are
            included when registered.
        """
        self._reset_state()
        ctx = self._make_ctx(meta)
        lines = self._convert_two_pass(module_ast, ctx)
        out: dict[str, str] = {"": "\n".join(lines)}
        if not ctx.meta.get("inline_std", True) and self._std_defs:
            name = ctx.meta.get("std_module_name", self.STD_MODULE_NAME)
            out[name] = self._render_std_module(ctx)
        for fname, provider in self._file_providers.items():
            out[fname] = provider(module_ast, ctx.meta)
        return out

    def convert_batch(
        self,
        modules: list[tuple[str, Module]],
        **meta,
    ) -> dict[str, str]:
        """Convert multiple modules with shared state.

        inline_std=True (default):
            Each file is self-contained (helpers inlined per file).
        inline_std=False:
            N main files + ONE shared std module containing the union of all
            used helpers. Each main file imports only what it actually uses.

        Args:
            modules: list of ``(output_name, module_ast)`` tuples.
            **meta: forwarded to ctx.meta. Common keys: ``inline_std``,
                ``std_module_name``.

        Returns:
            ``{output_name: content}`` for each module, plus
            ``{std_module_name: std_content}`` when inline_std=False and at
            least one std helper is used.
        """
        inline = meta.get("inline_std", True)
        ctx = self._make_ctx({**meta, "inline_std": inline})

        if inline:
            results: dict[str, str] = {}
            for name, module_ast in modules:
                self._reset_state()
                results[name] = "\n".join(
                    self._convert_two_pass(module_ast, ctx)
                )
            return results

        # Separated mode: collect union of std usage across all files
        shared_std_defs: dict[str, tuple[list[str], str]] = {}
        shared_std_imports: dict[str, None] = {}
        for _, module_ast in modules:
            self._reset_state()
            self._collect_signals(module_ast, ctx)
            shared_std_defs.update(self._std_defs)
            shared_std_imports.update(self._std_imports)

        # Generate the single shared std module (if any helpers are used)
        results = {}
        std_module_name = ctx.meta.get("std_module_name", self.STD_MODULE_NAME)
        if shared_std_defs:
            self._reset_state()
            self._std_defs = dict(shared_std_defs)
            self._std_imports = dict(shared_std_imports)
            results[std_module_name] = self._render_std_module(ctx)

        # Generate each main module independently — visit_utilities reads
        # this file's _std_defs (NOT the union) to emit a correct
        # `from ssc_std import ...` line for THIS file.
        for name, module_ast in modules:
            self._reset_state()
            results[name] = "\n".join(self._convert_two_pass(module_ast, ctx))

        return results

    # === CORE (single-module two-pass pipeline) ===
    def _convert_two_pass(
        self, module_ast: Module, ctx: ConverterContext
    ) -> list[str]:
        """Pass 1: collect signals (output discarded). Pass 2: emit."""
        self._collect_signals(module_ast, ctx)
        lines: list[str] = self._process_gen(
            self.visit_module(module_ast, ctx), None, None
        )
        for node in module_ast.body:
            lines.extend(self.visit(node, ctx))
        return lines

    def _collect_signals(
        self, module_ast: Module, ctx: ConverterContext
    ) -> None:
        """Pass 1: walk AST and populate signal pools. Output discarded.

        ``visit()`` is called for every node; signal handling (StdDef/ImportUse)
        accumulates into ``_std_defs`` / ``_main_imports`` / ``_std_imports``
        via ``setdefault``. The returned line lists are thrown away.
        """
        self._process_gen(self.visit_module(module_ast, ctx), None, None)
        for node in module_ast.body:
            self.visit(node, ctx)

    def visit(self, node: Node, ctx: ConverterContext) -> list[str]:
        """Universal AST visitor: dispatches a node to visit_* and intercepts signals.

        Walks the whole AST tree and hands nodes off to the concrete handler code.
        """
        name = self._DISPATCH.get(type(node))
        if name is None:
            return []
        gen = getattr(self, name)(node, ctx)
        return self._process_gen(gen, node, ctx)

    def _process_gen(
        self,
        gen: VisitStream,
        node: Node | None = None,
        ctx: ConverterContext | None = None,
    ) -> list[str]:
        """Process a generator output: handle signals, collect lines.

        ``node`` and ``ctx`` are required only when the generator may yield
        ``TRAVERSE`` (None) — ``_emit_body`` is then called to walk
        ``node.body``. Pass ``None`` for both when called on generators that
        never traverse children (e.g. ``visit_module``).
        """
        if gen is None:
            return []
        lines: list[str] = []
        for item in gen:
            if item is None:
                if node is not None and ctx is not None:
                    lines.extend(self._emit_body(node, ctx))
            else:
                self._handle_yield_item(item, lines)
        return lines

    def _handle_yield_item(self, item: Any, lines: list[str]) -> None:
        """Process a single non-None yield item (signal or line)."""
        if isinstance(item, StdDef):
            self._register_std(item.name, item.imports, item.code)
        elif isinstance(item, ImportUse):
            self._register_import_use(item.line)
        elif isinstance(item, str):
            lines.append(item)
        elif isinstance(item, (list, tuple)):
            for x in item:
                if x is None:
                    continue
                self._handle_yield_item(x, lines)
        else:
            raise TypeError(f"unsupported yield value: {item!r}")

    def _emit_body(self, node: Node, ctx: ConverterContext) -> list[str]:
        """Traverse a node's body. The mode is selected by category (_CONTAINER/_PREDICATE/_PIPELINE).

        Ported from base.BaseConverter._emit_node (three modes).
        """
        if isinstance(node, _PREDICATE_NODES):
            pred_ctx = replace(ctx, depth=ctx.depth + 1, index=0)
            lines: list[str] = []
            for child in node.body:
                lines.extend(self.visit(child, pred_ctx))
                pred_ctx = pred_ctx.advance()
            return lines
        if isinstance(node, _CONTAINER_NODES):
            inner_ctx = replace(ctx, depth=ctx.depth + 1, index=0)
            lines = []
            for child in node.body:
                lines.extend(self.visit(child, inner_ctx))
            return lines
        if isinstance(node, _PIPELINE_NODES):
            return self._emit_pipeline(node.body, ctx.deeper())
        return []

    def _emit_pipeline(
        self, nodes: list[Node], ctx: ConverterContext
    ) -> list[str]:
        """Traverse a pipeline body (Field.body, etc.): index advances after each node.

        ``Fallback`` nodes are handled specially: the generator's ``yield TRAVERSE``
        signal triggers body traversal at depth+1 with advancing index, then the
        outer ctx is synced so subsequent nodes (e.g. Return) see the correct
        variable.
        """
        lines: list[str] = []
        for node in nodes:
            if isinstance(node, Fallback):
                inner_ctx = ctx.deeper()
                gen = self.visit_fallback(node, ctx)
                if gen is not None:
                    for item in gen:
                        if item is None:
                            for child in node.body:
                                lines.extend(self.visit(child, inner_ctx))
                                inner_ctx = inner_ctx.advance()
                        else:
                            self._handle_yield_item(item, lines)
                ctx = inner_ctx
                continue
            lines.extend(self.visit(node, ctx))
            ctx = ctx.advance()
        return lines

    # === STD / IMPORT POOLS ===
    def _make_ctx(self, meta: dict) -> ConverterContext:
        """Build a fresh ConverterContext from meta dict."""
        return ConverterContext(
            var_name=self.var_name, indent_char=self.indent, meta=dict(meta)
        )

    def _register_std(self, name: str, imports: list[str], code: str) -> None:
        """Record a std helper definition (idempotent by name).

        First emission for a name wins; imports always accumulate into the
        std import pool (deduped).
        """
        self._std_defs.setdefault(name, (list(imports), code))
        for imp in imports:
            self._std_imports.setdefault(imp, None)

    def _register_import_use(self, line: str) -> None:
        """Record a main-module import line."""
        self._main_imports.setdefault(line, None)

    def _render_std_section(self, ctx: ConverterContext) -> list[str]:
        """Render std section for the MAIN module.

        - inline mode: merged imports + helper bodies.
        - separated mode: main imports + ``from <std_module> import ...``.

        Returns an empty list when no std helpers are used.
        """
        if not self._std_defs:
            return []

        if ctx.meta.get("inline_std", True):
            body_lines: list[str] = []
            for _imports, code in self._std_defs.values():
                body_lines.extend(inspect.cleandoc(code).splitlines())
                body_lines.append("")
            # std-helper imports only; main-module imports are emitted by the
            # converter's visit_utilities (they must appear regardless of
            # whether any std helper is used).
            return [*self._std_imports, "", *body_lines]

        module_name = ctx.meta.get("std_module_name", self.STD_MODULE_NAME)
        return [f"from {module_name} import {', '.join(self._std_defs)}"]

    def _render_std_module(self, ctx: ConverterContext) -> str:
        """Render the standalone std runtime module content (separated mode)."""
        lines: list[str] = ["# autogenerated std runtime. DO NOT EDIT", ""]
        lines.extend(self._std_imports)
        for _imports, code in self._std_defs.values():
            lines.append("")
            lines.extend(inspect.cleandoc(code).splitlines())
        return "\n".join(lines)

    # === SHARED TYPE RESOLUTION (concrete, data-driven by class attrs) ===
    def _resolve_type(self, type_info: TypeInfo | None) -> str:
        """Render a TypeInfo into a target-language type annotation string.

        Spelling is controlled entirely by class attrs (TYPES,
        ARRAY_TYPE_FMT, OPTIONAL_TYPE_FMT, DOCUMENT_TYPE, etc.) so the
        algorithm is identical for every dialect.
        """
        if type_info is None:
            return self.DEFAULT_TYPE
        if type_info.base == VT.NESTED and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Type"
        elif type_info.base == VT.JSON and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Json"
        elif type_info.base == VT.DOCUMENT:
            t = (
                self.DOCUMENT_ARRAY_TYPE
                if type_info.is_array
                else self.DOCUMENT_TYPE
            )
        else:
            t = self.TYPES.get(type_info.base, self.DEFAULT_TYPE)
        if type_info.is_array and type_info.base != VT.DOCUMENT:
            t = self.ARRAY_TYPE_FMT.format(t)
        if type_info.is_optional or (
            self.OPTIONAL_ON_OMITEMPTY and type_info.omitempty
        ):
            t = self.OPTIONAL_TYPE_FMT.format(t)
        return t

    def _resolve_start_parse_t_ret(self, struct: StructBase, name: str) -> str:
        """Return-type annotation for the public parse() method.

        Derived from class attrs — no separate lookup table needed.
        """
        match struct.type:
            case ST.ITEM | ST.DICT | ST.TABLE:
                return f"{name}Type"
            case ST.LIST:
                return self.ARRAY_TYPE_FMT.format(f"{name}Type")
            case ST.FLAT:
                return self.ARRAY_TYPE_FMT.format(self.TYPES[VT.STRING])

    def _pred_line(self, ctx: ConverterContext, cond: str) -> str:
        """Format one predicate condition; join siblings with AND_OP."""
        prefix = "" if ctx.index == 0 else f"{self.AND_OP} "
        return f"{ctx.indent}{prefix}{cond}"

    # === DISPATCH TABLE ===
    # Single source of truth: node -> visit_* method name.
    # A concrete subclass must implement every method (otherwise the call raises TypeError).
    _DISPATCH: dict[type[Node], str] = {
        # module
        Module: "visit_module",
        Utilities: "visit_utilities",
        CodeStartHook: "visit_code_start_hook",
        CodeEndHook: "visit_code_end_hook",
        # typedef / jsondef
        JsonDef: "visit_jsondef",
        JsonDefField: "visit_jsondef_field",
        TypeDef: "visit_typedef",
        TypeDefField: "visit_typedef_field",
        # struct
        Struct: "visit_struct",
        StructRest: "visit_struct_rest",
        StartParse: "visit_start_parse",
        Init: "visit_init",
        InitFieldCall: "visit_init_field_call",
        InitField: "visit_init_field",
        Field: "visit_field",
        PreValidate: "visit_pre_validate",
        CheckMethod: "visit_check_method",
        SplitDoc: "visit_split_doc",
        Key: "visit_key",
        Value: "visit_value",
        TableConfig: "visit_table_config",
        TableMatchKey: "visit_table_match_key",
        TableRows: "visit_table_rows",
        MethodFetch: "visit_method_fetch",
        MethodRest: "visit_method_rest",
        ErrorResponse: "visit_error_response",
        # REST result artifacts (synthesized before StructRest)
        ResultVariantDef: "visit_result_variant_def",
        ResultAliasDef: "visit_result_alias_def",
        MatcherListDef: "visit_matcher_list_def",
        # selectors
        CssSelect: "visit_css_select",
        CssSelectAll: "visit_css_select_all",
        CssRemove: "visit_css_remove",
        XpathSelect: "visit_xpath_select",
        XpathSelectAll: "visit_xpath_select_all",
        XpathRemove: "visit_xpath_remove",
        Text: "visit_text",
        Raw: "visit_raw",
        Attr: "visit_attr",
        # string
        Trim: "visit_trim",
        Ltrim: "visit_l_trim",
        Rtrim: "visit_r_trim",
        RmPrefix: "visit_rm_prefix",
        RmSuffix: "visit_rm_suffix",
        RmPrefixSuffix: "visit_rm_prefix_suffix",
        Fmt: "visit_format",
        Repl: "visit_repl",
        ReplMap: "visit_repl_map",
        Lower: "visit_lower",
        Upper: "visit_upper",
        Split: "visit_split",
        Join: "visit_join",
        NormalizeSpace: "visit_norm_space",
        Unescape: "visit_unescape",
        # regex
        Re: "visit_re",
        ReAll: "visit_re_all",
        ReSub: "visit_re_sub",
        # array
        Index: "visit_index",
        Slice: "visit_slice",
        Len: "visit_len",
        Unique: "visit_unique",
        # cast
        ToInt: "visit_to_int",
        ToFloat: "visit_to_float",
        ToBool: "visit_to_bool",
        Jsonify: "visit_jsonify",
        Nested: "visit_nested",
        # control
        Self: "visit_self",
        Return: "visit_return",
        Fallback: "visit_fallback",
        # predicate containers
        Filter: "visit_filter",
        Assert: "visit_assert",
        Match: "visit_match",
        # logic
        LogicAnd: "visit_logic_and",
        LogicOr: "visit_logic_or",
        LogicNot: "visit_logic_not",
        # predicates
        PredCss: "visit_predicate_css",
        PredXpath: "visit_predicate_xpath",
        PredHasAttr: "visit_predicate_has_attr",
        PredAttrContains: "visit_predicate_attr_contains",
        PredAttrStarts: "visit_predicate_attr_starts",
        PredAttrEnds: "visit_predicate_attr_ends",
        PredAttrEq: "visit_predicate_attr_eq",
        PredAttrNe: "visit_predicate_attr_ne",
        PredAttrRe: "visit_predicate_attr_re",
        PredTextContains: "visit_predicate_text_contains",
        PredTextStarts: "visit_predicate_text_starts",
        PredTextEnds: "visit_predicate_text_ends",
        PredTextRe: "visit_predicate_text_re",
        PredContains: "visit_predicate_contains",
        PredEq: "visit_predicate_eq",
        PredNe: "visit_predicate_ne",
        PredStarts: "visit_predicate_starts",
        PredEnds: "visit_predicate_ends",
        PredCountEq: "visit_predicate_count_eq",
        PredCountGt: "visit_predicate_count_gt",
        PredCountLt: "visit_predicate_count_lt",
        PredCountNe: "visit_predicate_count_ne",
        PredCountGe: "visit_predicate_count_ge",
        PredCountLe: "visit_predicate_count_le",
        PredCountRange: "visit_pred_count_range",
        PredRe: "visit_predicate_re",
        PredReAll: "visit_predicate_re_all",
        PredReAny: "visit_predicate_re_any",
    }

    # NODE APIS. need override
    @abstractmethod
    def visit_module(self, node: Module, ctx: ConverterContext) -> VisitStream:
        """
        Auto-generated AST node (not user-authored).

        Root node of the parser module. Emits, in order:
        1. The autogenerated header banner ("autogenerated by ssc-gen
           DO NOT EDIT").
        2. If ``node.doc`` is present, the module-level docstring.
        3. Base import statements, varied by module shape (REST present,
           REST-only, separate runtime) and build options (http_client).
        4. Target-specific extra imports (parser library, HTTP client).

        Subclasses must also pick the correct position (top/bottom) for
        per-struct docstrings via the ``StructBase.doc`` field — e.g. Python
        places the docstring below the class declaration, JS/Go place it
        above.

        Prefer ``IMPORT(line)`` signals over hardcoded import strings so the
        core can deduplicate across main code, std helpers, and other sources.
        """

    def visit_utilities(
        self, node: Utilities, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored).

        Default implementation emits the std runtime section by reading
        ``self._std_defs`` (populated during pass 1 of ``convert_all``).

        - inline_std=True: merged imports + helper bodies, all in the main file.
        - inline_std=False: main imports + ``from <std_module> import ...``.

        Override only if a target language needs custom orchestration
        (e.g. JS bundler-specific import statements). In that case you are
        responsible for honoring ``ctx.meta.get("inline_std", True)``.
        """
        return iter(self._render_std_section(ctx))

    @abstractmethod
    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored).

        Special AST hook: extra code can be inserted right after the Utilities node.

        Return None when not needed.
        """

    @abstractmethod
    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored).

        Special AST hook: extra code can be inserted at the end of the file.

        Return None when not needed.
        """

    # === TYPES ===
    @abstractmethod
    def visit_jsondef(
        self, node: JsonDef, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `json <name> { ... }`

        Emit a struct/type annotation used to type JSON data.
        """

    @abstractmethod
    def visit_jsondef_field(
        self, node: JsonDefField, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `json <name> { field... }`

        Emit a typed field of a JsonDef struct.
        Derive the type from `node.ret`.
        """

    @abstractmethod
    def visit_typedef(
        self, node: TypeDef, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored); derived from a non-rest `struct`.

        Emit a struct/type annotation used to type data for HTML-parser structs.
        """

    @abstractmethod
    def visit_typedef_field(
        self, node: TypeDefField, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored); derived from a non-rest `struct`.

        Emit a typed field of a TypeDef struct.
        Derive the type from `node.ret`.
        """

    # === STRUCT ===
    # TODO: unify into a single struct node?
    @abstractmethod
    def visit_struct(self, node: Struct, ctx: ConverterContext) -> VisitStream:
        """

        Emit the struct/class header.
        If documented, emit the docstring.

        ITEM:
        KDL: `struct <name> { ... } | (item)struct <name> { ... } | struct <name> type=item { ... }`
        LIST:
        KDL: `struct <name> type=list { ... } | (list)struct <name> { ... }`
        FLAT:
        KDL: `struct <name> type=flat { ... } | (flat)struct <name> { ... }`
        DICT:
        KDL: `struct <name> type=dict { ... } | (dict)struct <name> { ... }`
        TABLE:
        KDL: `struct <name> type=table { ... } | (table)struct <name> { ... }`
        REST:
            SEPARATED IN `visit_struct_rest`
        """

    @abstractmethod
    def visit_struct_rest(
        self, node: StructRest, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `struct <name> type=rest { ... } | (rest)struct <name> { ... }`

        Emit the struct/class header used to call REST methods.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_init(self, node: Init, ctx: ConverterContext) -> VisitStream:
        """
        KDL:
            ```
            // vvvvv
            @init {

                <name> {
                    ...
                    }
            }
            ```

        Emit the public constructor of the struct/class.

        1. Store the DOM-like Document/Element of the input HTML.
        2. If `InitField` entries exist, invoke them up front and store the results on the instance.
        """

    @abstractmethod
    def visit_init_field(
        self, node: InitField, ctx: ConverterContext
    ) -> VisitStream:
        """

        KDL:
            ```
            @init {
             // vvvvv
                <name> {
                    ...
                    }
            }
            ```

        Emit the header of a private struct method that pre-extracts a value.
        """

    @abstractmethod
    def visit_init_field_call(
        self, node: InitFieldCall, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored).

        The call-site inside the constructor that invokes the corresponding
        ``InitField`` method and caches the result on the instance.
        """

    @abstractmethod
    def visit_field(self, node: Field, ctx: ConverterContext) -> VisitStream:
        """

        KDL: `struct Foo { <name> { ... }... }`

        Emit the header of a private struct method whose value is computed when StartParse runs.
        """

    @abstractmethod
    def visit_pre_validate(
        self, node: PreValidate, ctx: ConverterContext
    ) -> VisitStream:
        """

        KDL: `@pre-validate { ... }`

        Emit the header of a private struct method that validates the value before parsing.
        - The document is not modified.
        - This field is expected to apply `assert` blocks.
        - On a failed check the code raises/returns an error.
        """

    @abstractmethod
    def visit_check_method(
        self, node: CheckMethod, ctx: ConverterContext
    ) -> VisitStream:
        """

        KDL: `@check <name> { ... }`

        Emit the header of a public struct method that can be called for basic checks.
        - Always returns a boolean.
        """

    @abstractmethod
    def visit_split_doc(
        self, node: SplitDoc, ctx: ConverterContext
    ) -> VisitStream:
        """

        KDL: `@split-doc { ... }`

        Emit the header of a private struct method that splits the document into parts by a selector (e.g. into cards).
        - Always returns TypeInfo(Document, is_array=True).
        """

    @abstractmethod
    def visit_key(self, node: Key, ctx: ConverterContext) -> VisitStream:
        """
        KDL: `@key { ... }`

        Emit the header of a private method for StructDict that produces the key. Always returns STRING.
        """

    @abstractmethod
    def visit_value(self, node: Value, ctx: ConverterContext) -> VisitStream:
        """
        KDL: `@value { ... }`

        1. Emit the header of a private method for StructDict that produces the value.
        2. (ADHOC) Emit the header of a private method for StructTable that extracts the value from a table row.
        """

    @abstractmethod
    def visit_table_config(
        self, node: TableConfig, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `@table { ... }`
        Emit the header of a private method for StructTable that selects the <table>-like element.
        """

    @abstractmethod
    def visit_table_match_key(
        self, node: TableMatchKey, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `@match { ... }`

        Emit the header of a private method for StructTable that extracts the "key" value from the table. Always returns STRING.
        Used to match values in HTML tables.
        """

    @abstractmethod
    def visit_table_rows(
        self, node: TableRows, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `@rows { ... }`

        Emit the header of a private method that extracts all rows from the table. Always returns DOCUMENT (is_array=True).
        """

    @abstractmethod
    def visit_method_fetch(
        self, node: MethodFetch, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `@request ...`

        For HTML-parser structs: an optional classmethod constructor that performs the HTTP request and initialises the instance.

        - Does not configure the HTTP client — it is passed as the first argument and must be configured externally.
        - Signature: (HttpClient, *, params...).
        """

    @abstractmethod
    def visit_method_rest(
        self, node: MethodRest, ctx: ConverterContext
    ) -> VisitStream:
        """
        KDL: `@request ...`

        For REST-API structs: adds a method that sends the request and returns the JSON result.

        - Does not configure the HTTP client — it is passed as the first argument and must be configured externally.
        - Signature: (HttpClient, *, params...).
        - TIP: for simplicity, ergonomics and portability, prefer returning (and generating) monad-like result types.
        """

    @abstractmethod
    def visit_error_response(
        self, node: ErrorResponse, ctx: ConverterContext
    ) -> VisitStream:
        """
        TODO: define the error-response contract.
        """

    @abstractmethod
    def visit_result_variant_def(
        self, node: ResultVariantDef, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (synthesized from StructRest.errors).

        Emit one error-subclass declaration (e.g. ``@dataclass class XErr(Err[T])``
        in Python, ``@typedef`` in JS).  Sits at module level before the struct.
        """

    @abstractmethod
    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (synthesized from MethodRest).

        Emit one result-union alias per method (e.g. ``GetUserResult = Union[...]``
        in Python, JSDoc ``@typedef`` in JS).  Sits at module level before the struct.
        """

    @abstractmethod
    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (synthesized from StructRest.errors).

        Emit the per-struct error-matcher list (e.g. ``_x_matchers = [ErrMatcher(...)]``
        in Python, ``const _xMatchers = [...]`` in JS).  Carries RAW condition
        data (required_keys + conditions); the visitor renders the check
        expression in the target language spelling.  Sits at module level before
        the struct.
        """

    @abstractmethod
    def visit_start_parse(
        self, node: StartParse, ctx: ConverterContext
    ) -> VisitStream:
        """
        Auto-generated AST node (not user-authored).

        Emit the header of the public method start_parse / startParse that runs the parser and returns the result.

        Both the header and the body must be emitted.

        Strategies (pseudocode):

        StructItem:
            ```
            fn start_parse() {
                PreValidate(document) // if defined
                result = {}
                result[field_name1] = ParseField1(document)
                result[field_name2] = ParseField2(document)
                ...
                return result
            }
            ```
        StructList:
            ```
            fn start_parse() {
                PreValidate(document) // if defined
                results = []
                parts = SplitDoc(document)
                result = {}
                for part in parts {
                    result[field_name1] = ParseField1(document)
                    result[field_name2] = ParseField2(document)
                    ...
                    results.append(result)
                    result = {}
                }
                return results
            }
            ```
        StructDict (key, value - stable keys, allow hardcode):
            ```
            fn start_parse() {
                PreValidate(document) // if defined
                result = {}
                parts = SplitDoc(document)
                for part in parts {
                    key = ParseKey(part)
                    value = ParseValue(part)
                    result[key] = value
                }
                return result
            }
            ```

        StructFlatList (allow STRING only):
            ```
            fn start_parse() {
                PreValidate(document) // if defined
                results = []
                // in codegen: allow check return type and simplify code
                result1: string = ParseField1(document)
                results.append(result1)
                result2: string[] = ParseField2(document)
                results.extend(results2)
                ...
                // finally, drop duplicates.
                // dont remember check keep_order flag: if true - implement algorith with keep ordering all colleceted elements
                results = list(set(results))
                return results
            }
            ```
        StructTable:
            - TIP: null/None is used in the project; use a SENTINEL object for the checks.

            ```
            NOT_VALID_ROW = Sentinel()

            fn start_parse() {
                PreValidate(document) // if defined
                results = {}

                table = TableConfig(document)  // @table
                rows = TableRow(table)   // @rows
                for row in rows {
                    field1 = ParseField1(row)
                    // test with sentinel object
                    if field1 != NOT_VALID_ROW {
                        results[field_name1] = field1
                        continue
                    }
                    // next row tests if not passed
                    field2 = ParseField2(row)
                    if field2 != NOT_VALID_ROW {
                        results[field_name2] = field1
                        continue
                    }
                    ...
                }
                return results
            }
            ```

        StructRest: this method is not used and no AST node is generated — skip it.
        """
        # TODO: research generate transform callers. rationale: simplify generate???
        # StartParseSetup
        # CallPreValidate
        # CallStartParse
        # Return???

    # === EXPRESSIONS ===

    # === SELECTORS ===
    @abstractmethod
    def visit_css_select(
        self, node: CssSelect, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `css query | css { query1; query2... }`

        TYPES:
            - DOCUMENT -> DOCUMENT

        - Extract the first element matching the CSS selector.
        - If multiple queries are passed, return the element from the first selector that matches.
        - Do not enforce CSS3/CSS4 — it depends on the target library.
        - No need to handle null/None.
        """

    @abstractmethod
    def visit_css_select_all(
        self, node: CssSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `css-all query | css-all { query1; query2... }`

        TYPES:
            - DOCUMENT -> DOCUMENT[]

        - Extract all elements matching the CSS selector.
        - If multiple queries are passed, return the elements from the first selector that matches.
        - Do not enforce CSS3/CSS4 — it depends on the target library.
        - No need to handle null/None.
        """

    @abstractmethod
    def visit_css_remove(
        self, node: CssRemove, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `css-remove query`

        TYPES:
            - DOCUMENT -> DOCUMENT

        - Remove elements matching the CSS selector from the root document.
        - Has side effects.
        - Ideally descendants are removed too (unverified).
        - This op usually returns nothing; remember to assign a new variable.
        """

    @abstractmethod
    def visit_xpath_select(
        self, node: XpathSelect, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `xpath query | xpath { query1; query2... }`

        TYPES:
            - DOCUMENT -> DOCUMENT

        - Extract the first element matching the XPATH selector.
        - If multiple queries are passed, return the element from the first selector that matches.
        - No need to handle null/None.
        """

    @abstractmethod
    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `xpath-all query | xpath-all { query1; query2... }`

        TYPES:
            - DOCUMENT -> DOCUMENT[]

        - Extract all elements matching the XPATH selector.
        - If multiple queries are passed, return the elements from the first selector that matches.
        - No need to handle null/None.
        """

    @abstractmethod
    def visit_xpath_remove(
        self, node: XpathRemove, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `xpath-remove query`

        TYPES:
            - DOCUMENT -> DOCUMENT

        - Remove elements matching the XPATH selector from the root document.
        - Has side effects.
        - Ideally descendants are removed too (unverified).
        - This op usually returns nothing; remember to assign a new variable.
        """

    @abstractmethod
    def visit_text(self, node: Text, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `text`

        TYPES:
            - DOCUMENT -> STRING
            - DOCUMENT[] -> STRING[]

        - Extract the element's text.
        - If DOCUMENT(array=true), extract from each element and return a flat list.
        """

    @abstractmethod
    def visit_raw(self, node: Raw, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `raw`

        TYPES:
            - DOCUMENT -> STRING
            - DOCUMENT[] -> STRING[]

        - Extract the element's raw HTML (htmlOuter; descendants included).
        - If DOCUMENT(array=true), extract from each element and return a flat list.
        """

    @abstractmethod
    def visit_attr(self, node: Attr, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `attr <name>...`

        TYPES:
            - DOCUMENT -> STRING
            - DOCUMENT[] -> STRING[]

        - Extract the attribute by key.
        - DOCUMENT:
            - If a single key, access it directly; raising on a missing key is acceptable.
            - If >1 key, check key presence and collect all attributes (STRING(array=true)).
        - DOCUMENT(array=true):
            - If a single key, check presence and extract from every element.
            - If >2 keys, check presence. **Collect all found attributes into a flat list.**
        """

    # === STRING ===
    @abstractmethod
    def visit_trim(self, node: Trim, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `trim <chars>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Strip characters from the LEFT and RIGHT.
        - If <chars> is empty, strip all whitespace.
        """

    @abstractmethod
    def visit_l_trim(self, node: Ltrim, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `ltrim <chars>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Strip characters from the LEFT.
        - If <chars> is empty, strip all whitespace.
        """

    @abstractmethod
    def visit_r_trim(self, node: Rtrim, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `rtrim <chars>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Strip characters from the RIGHT.
        - If <chars> is empty, strip all whitespace.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_rm_prefix(
        self, node: RmPrefix, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `rm-prefix <substr>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Remove a prefix matching the substring.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_rm_suffix(
        self, node: RmSuffix, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `rm-suffix <substr>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Remove a suffix matching the substring.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `rm-prefix-suffix <substr>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Remove the prefix, then the suffix matching the substring.
        """

    @abstractmethod
    def visit_format(self, node: Fmt, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `fmt <template>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Substitute the previous value into the template.
        - The template placeholder/hole is `{{}}` — translate it to the target equivalent.
        """

    @abstractmethod
    def visit_repl(self, node: Repl, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `repl <old> <new>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Replace a substring.
        - Replaces all occurrences; no limit.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_repl_map(
        self, node: ReplMap, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `repl {<old1> <new1>; <old2> <new2>}`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Replace a set of substrings.
        - Replaces all occurrences; no limit.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_lower(self, node: Lower, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `lower`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Convert to lowercase.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_upper(self, node: Upper, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `upper`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Convert to uppercase.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_split(self, node: Split, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `split <sep>`

        TYPES:
            - STRING -> STRING[]

        - Split by the substring.
        """

    @abstractmethod
    def visit_join(self, node: Join, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `join <sep>`

        TYPES:
            - STRING[] -> STRING

        - Join into a single string using `sep` as the separator.
        """

    @abstractmethod
    def visit_norm_space(
        self, node: NormalizeSpace, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `normalize-space`

        TYPES:
            - STRING[] -> STRING[]
            - STRING -> STRING

        - Whitespace normalisation.
            - Strip all whitespace from the LEFT and RIGHT.
            - Collapse long runs of whitespace to a single space.

        std implementation pseudocode to call:

        ```
         def normalize_text(text: str) -> str:
            return ' '.join(text.split()) if text else ""
        ```
        """

    @abstractmethod
    def visit_unescape(
        self, node: Unescape, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `unescape`

        TYPES:
            - STRING[] -> STRING[]
            - STRING -> STRING

        - Universal unescape. Unescapes EVERYTHING.

        std implementation pseudocode to call:

        ```
        import re
        from html import unescape

        RE_HEX_ENTITY = re.compile(r'&#x([0-9a-fA-F]+);')
        RE_UNICODE_ENTITY = re.compile(r'\\\\u([0-9a-fA-F]{4})')
        RE_BYTES_ENTITY = re.compile(r'\\\\x([0-9a-fA-F]{2})')
        RE_CHARS_MAP = {'\\b': '\\b', '\\f': '\\f', '\\n': '\\n', '\\r': '\\r', '\\t': '\\t'}

        def std_unescape(text: str) -> str
            s = unescape(text)
            s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
            s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
            s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
            for ch, r in _RE_CHARS_MAP.items():
                s = s.replace(ch, r)
            return s
        ```
        """

    # === REGEX ===

    @abstractmethod
    def visit_re(self, node: Re, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `re <pattern>`

        TYPES:
            - STRING -> STRING

        - Capture **exactly one group**.
        - Basic PCRE syntax without advanced features like lookahead, lookbehind, named groups.
        """

    @abstractmethod
    def visit_re_all(self, node: ReAll, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `re-all <pattern>`

        TYPES:
            - STRING -> STRING[]

        - Capture **exactly one group**.
        - Basic PCRE syntax without advanced features like lookahead, lookbehind, named groups.
        """

    @abstractmethod
    def visit_re_sub(self, node: ReSub, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `re-sub <pattern> <repl>`

        TYPES:
            - STRING[] -> STRING[]
            - STRING -> STRING

        - Capture groups are not honoured.
        - Basic PCRE syntax without advanced features like lookahead, lookbehind, named groups.
        - No limit — replaces every match.
        """

    # === ARRAY ===
    @abstractmethod
    def visit_index(self, node: Index, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `index <N>`
        aliases:
            `first` == `index 0`
            `last` == `index -1`

        TYPES:
            - AUTO[] -> AUTO

        - Indexing starts at 0.
        - Supports negative indices. If the target does not, translate to `PRV[len(PRV) - N]`.
        """

    @abstractmethod
    def visit_slice(self, node: Slice, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `slice <START> <END>`

        TYPES:
            - AUTO[] -> AUTO[]

        TODO (few tests, rarely used in practice).
        """

    @abstractmethod
    def visit_len(self, node: Len, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `len`

        TYPES:
            - AUTO[] -> INT

        - Get the length of the previous element.
        - Works only with is_array=true; does not take the length of strings.
        """

    @abstractmethod
    def visit_unique(self, node: Unique, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `unique`

        TYPES:
            - STRING[] -> STRING[]

        - Remove duplicates.
        - If keep_order=True, use an algorithm that preserves element order.
        """

    # === CASTS ===
    @abstractmethod
    def visit_to_int(self, node: ToInt, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `to-int`

        TYPES:
            - STRING[] -> INT[]
            - STRING -> INT

        - Cast to int64 (int32 on x86).
        - Does not validate input — that is the user's responsibility.
        - STRING(array).
        """

    @abstractmethod
    def visit_to_float(
        self, node: ToFloat, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `to-float`

        TYPES:
            - STRING[] -> FLOAT[]
            - STRING -> FLOAT

        - Cast to float64 (float32 on x86).
        - Does not validate input — that is the user's responsibility.
        - STRING(array).
        """

    @abstractmethod
    def visit_to_bool(self, node: ToBool, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `to-bool`

        TYPES:
            - AUTO -> BOOL
            - AUTO[] -> BOOL

        - Cast to boolean.
        - Return false for:
            - null/None
            - empty string
            - empty array
            - int == 0
        - Otherwise return true.
        """

    @abstractmethod
    def visit_jsonify(
        self, node: Jsonify, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `jsonify <JsonStruct> <path?>`

        TYPES:
            - STRING -> JSON

        - Does not validate the json-like input string.
        - If a path is given, first extract the JSON object from it.
        - Then annotate/serialise as the JsonStruct.
        - Always the last operation.
        """

    @abstractmethod
    def visit_nested(self, node: Nested, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `nested <Struct>`

        TYPES:
            - DOCUMENT -> NESTED

        - Always the first call (type DOCUMENT).
        - No other expressions are applied.
        - Calls the nested parser's constructor, then returns its value.
        """

    # === CONTROLS ===
    @abstractmethod
    def visit_self(self, node: Self, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `self <init-field-name>` (deprecated)
        kdl: `@<init-field-name>`

        TYPES:
            - DOCUMENT -> AUTO

        - Always the first call.
        - Copy the precomputed value from this field (its data type is whatever the init-field returned).
        """

    @abstractmethod
    def visit_return(self, node: Return, ctx: ConverterContext) -> VisitStream:
        """
        Auto-generated AST node.

        - The last value in a field is returned; the type is inferred automatically.
        - For PreValidate it is always null/None (returns nothing).
        """

    @abstractmethod
    def visit_fallback(
        self, node: Fallback, ctx: ConverterContext
    ) -> VisitStream:
        """kdl: `fallback <value>|{}`

        Error-recovery wrapper: catches any exception in the pipeline and
        returns a literal value instead.

        ``node.body`` contains all pipeline ops that form the try-block.
        ``node.value`` is the fallback literal.

        Use ``yield TRAVERSE`` to signal body traversal — the framework
        walks ``node.body`` at ``depth+1`` with advancing pipeline index,
        then syncs the outer index so subsequent nodes (e.g. Return) see
        the correct variable.

        Target-language strategies:

        - Python/JS/etc (try/catch available):
            ``yield f"{ctx.indent}try:"``
            ``yield TRAVERSE``
            ``yield f"{ctx.indent}except Exception:"``
            ``yield f"{ctx.indent}    return {node.value!r}"``

        - Go (no try/catch): use ``defer func() {{ recover() }}()`` or a
          ``std_fallback`` helper via ``STD(...)``.

        - Other languages without try/catch: emit a std helper that wraps
          the body in a closure and catches errors internally.
        """

    # === PREDICATE CALLS ===
    @abstractmethod
    def visit_filter(self, node: Filter, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `filter { ... }`

        TYPES:
            - DOCUMENT[] -> DOCUMENT[]
            - STRING[] -> STRING[]

        - Accepts DOCUMENT(array=true) | STRING(array=true).
        - Filter by the inner predicates; return the values that evaluate to true.
        - Multiple predicates default to AND.
        """

    @abstractmethod
    def visit_assert(self, node: Assert, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `assert { ... }`

        TYPES:
            - AUTO -> AUTO

        - Filter by the inner predicates.
        - If the value is false, raise an error.
        - Multiple predicates default to AND.
        """

    @abstractmethod
    def visit_match(self, node: Match, ctx: ConverterContext) -> VisitStream:
        """
        kdl: `match { ... }`

        TYPES:
            - STRING -> STRING

        - Special construct for fields in StructTable.
        - Type is STRING.
        - Filter by the inner predicates.
        - Multiple predicates default to AND.

        """

    # === LOGICAL ===
    @abstractmethod
    def visit_logic_and(
        self, node: LogicAnd, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `and { ... }`

        - Inside an `and` construct, separate by logical AND.

        example:

        ```
        and {a; b; c}
        ```
        equivalent to:

        ```
        (a && b && c)
        ```
        """

    @abstractmethod
    def visit_logic_or(
        self, node: LogicOr, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `or { ... }`

        - Inside an `or` construct, separate by logical OR.

        example:

        ```
        or {a; b; c }
        ```
        equivalent to:

        ```
        (a || b || c)
        ```
        """

    @abstractmethod
    def visit_logic_not(
        self, node: LogicNot, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `not { ... }`

        - Invert the result of the inner predicates.

        example:

        ```
        not { a; b; c }
        not { or {a; b; c} }
        ```
        equivalent to:
        ```
        !(a && b && c) && !((a || b || c))
        ```
        """

    # === LOGIC SELECTORS ===
    @abstractmethod
    def visit_predicate_css(
        self, node: PredCss, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `css <query>`

        TYPES:
            - DOCUMENT

        Check whether the query matches.

        example:
        ```
        e.select("a") // true if exists else false
        ```
        """

    @abstractmethod
    def visit_predicate_xpath(
        self, node: PredXpath, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `xpath <query>`

        TYPES:
            - DOCUMENT

        Check whether the query matches.

        example:
        ```
        e.xpath("a") // true if exists else false
        ```
        """

    @abstractmethod
    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `has-attr <attrs...>`

        TYPES:
            - DOCUMENT

        Check by attribute keys.
        - If more than one key is passed, convert to any(...).

        example:
        ```
        has-attr "href" // e.get("href")
        has-attr "href" "src" // any(e.get(k) for k in ["href", "src"])
        ```
        """

    @abstractmethod
    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `attr-contains <key> <substr...>`

        TYPES:
            - DOCUMENT

        Check whether the attribute value contains the substring.
        - No need to check key presence.
        - Multiple substrings convert to any().
        examples:
        ```
        attr-contains "class" "btn-"
        // "btn-" in e["class"]
        ```

        ```
        attr-contains "class" "btn-" "select-"
        // any(v in e["class"] for v in ["btn-", "select-"])
        ```
        """

    @abstractmethod
    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `attr-starts <key> <substr...>`

        TYPES:
            - DOCUMENT

        Check whether the attribute value starts with the substring.
        - No need to check key presence.
        - Multiple substrings convert to any().
        examples:
        ```
        attr-starts "class" "btn-"
        // e["class"].startswith("btn-")
        ```

        ```
        attr-starts "class" "btn-" "select-"
        // any(e["class"].startswith(v) for v in ["btn-", "select-"])
        ```
        """

    @abstractmethod
    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl: `attr-ends <key> <substr...>`

        TYPES:
            - DOCUMENT

        Check whether the attribute value ends with the substring.
        - No need to check key presence.
        - Multiple substrings convert to any().
        examples:
        ```
        attr-ends "class" "btn-"
        // e["class"].endswith("btn-")
        ```

        ```
        attr-ends "class" "btn-" "select-"
        // any(e["class"].endswith(v) for v in ["btn-", "select-"])
        ```
        """

    @abstractmethod
    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`attr-eq <key> <value...>`

        TYPES:
            - DOCUMENT

        Check whether the attribute value equals the value.
        - No need to check key presence.
        - Multiple values convert to any().
        examples:
        ```
        attr-eq "class" "btn"
        // e["class"] == "btn"
        ```

        ```
        attr-eq "class" "btn" "select"
        // any(e["class"] == v for v in ["btn-", "select-"])
        """

    @abstractmethod
    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`attr-ne <key> <value...>`

        TYPES:
            - DOCUMENT

        Check whether the attribute value differs from the value.
        - No need to check key presence.
        - Multiple values convert to all().
        examples:
        ```
        attr-ne "class" "btn"
        // e["class"] != "btn"
        ```

        ```
        attr-ne "class" "btn" "select"
        // all(e["class"] != v for v in ["btn-", "select-"])
        """

    @abstractmethod
    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`attr-re <key> <pattern>`

        TYPES:
            - DOCUMENT

        Check whether the attribute value matches the regex.
        - No need to check key presence.

        example:

        ```
        attr-re "href" "\\d+"
        // e["href"].test("\\d+")
        ```
        """

    @abstractmethod
    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`text-contains <value...>`

        TYPES:
            - DOCUMENT

        Check whether the element text contains the substring.
        - Multiple substrings convert to any().

        example:

        ```
        text-contains "docs"
        // "docs" in e.text
        ```

        ```
        text-contains "docs" "foo"
        // any(v in e.text for v in ["docs", "foo"])
        ```
        """

    @abstractmethod
    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`text-starts <value...>`

        TYPES:
            - DOCUMENT

        Check whether the element text starts with the substring.
        - Multiple substrings convert to any().

        example:

        ```
        text-starts "docs"
        // e.text.startswith("docs")
        ```

        ```
        text-starts "docs" "foo"
        // any(e.text.startswith(v) for v in ["docs", "foo"])
        ```
        """

    @abstractmethod
    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`text-ends <value...>`

        TYPES:
            - DOCUMENT

        Check whether the element text ends with the substring.
        - Multiple substrings convert to any().

        example:

        ```
        text-ends "docs"
        // e.text.endswith("docs")
        ```

        ```
        text-ends "docs" "foo"
        // any(e.text.endswith(v) for v in ["docs", "foo"])
        ```
        """

    @abstractmethod
    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`text-re <pattern>`

        TYPES:
            - DOCUMENT

        Check whether the element text matches the pattern.

        example:

        ```
        text-re "\\d+"
        // e.text.test("\\d+")
        ```
        """

    # === LOGIC STRING ===
    @abstractmethod
    def visit_predicate_contains(
        self, node: PredContains, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`contains <value...>`

        TYPES:
            - STRING

        Check whether the string contains the value(s).
        - Multiple substrings convert to any().

        examples:
        ```
        contains "a"
        // "a" in e
        ```

        ```
        contains "a" "b"
        // any(v in e for v in ["a", "b"])
        ```
        """

    @abstractmethod
    def visit_predicate_eq(
        self, node: PredEq, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`eq <value...>`

        TYPES:
            - STRING

        Check whether the string equals the value(s).
        - If a single integer is passed, compare by length.
        - Multiple substrings convert to any().

        examples:
        ```
        eq "a"
        // e == "a"
        ```

        ```
        eq 10
        // len(e) == 10
        ```

        ```
        eq "a" "b"
        // any(e == v for v in ["a", "b"])
        ```
        """

    @abstractmethod
    def visit_predicate_ne(
        self, node: PredNe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`ne <value...>`

        TYPES:
            - STRING

        Check whether the string differs from the value(s).
        - If a single integer is passed, compare by length.
        - Multiple values convert to all().

        examples:
        ```
        ne "a"
        // e != "a"
        ```

        ```
        ne 10
        // len(e) != 10
        ```

        ```
        ne "a" "b"
        // all(e != v for v in ["a", "b"])
        ```
        """

    @abstractmethod
    def visit_predicate_starts(
        self, node: PredStarts, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`starts <values...>`

        TYPES:
            - STRING

        Check whether the string starts with the value(s).
        - Multiple values convert to any().

        examples:
        ```
        starts "foo"
        // e.startswith("foo")
        starts "foo" "bar"
        // any(e.startswith(v) for v in ["foo", "bar"])
        ```
        """

    @abstractmethod
    def visit_predicate_ends(
        self, node: PredEnds, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`ends <values...>`

        TYPES:
            - STRING

        Check whether the string ends with the value(s).
        - Multiple values convert to any().

        examples:
        ```
        ends "foo"
        // e.endswith("foo")
        ends "foo" "bar"
        // any(e.endswith(v) for v in ["foo", "bar"])
        ```
        """

    @abstractmethod
    def visit_predicate_re(
        self, node: PredRe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`re <pattern>`

        TYPES:
            - STRING

        Check whether the string matches the pattern.

        example:

        ```
        re "\\d+"
        // e.test("\\d+")
        ```
        """

    # === LOGIC LEN ===
    @abstractmethod
    def visit_predicate_re_all(
        self, node: PredReAll, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`re-all <pattern>`

        TYPES:
            - STRING[] -> STRING[]

        - Accepts STRING(array=true).
        - All strings must match the pattern.
        """

    @abstractmethod
    def visit_predicate_re_any(
        self, node: PredReAny, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`re-any <pattern>`

        TYPES:
            - STRING[] -> STRING[]

        - Accepts STRING(array=true).
        - At least one string must match the pattern.
        """

    @abstractmethod
    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-eq <N>`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - len ==
        """

    @abstractmethod
    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-ne`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - len !=
        """

    @abstractmethod
    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-gt`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - len >
        """

    @abstractmethod
    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-lt <N>`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - len <
        """

    @abstractmethod
    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-ge`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - len >=
        """

    @abstractmethod
    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-le`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - len <=
        """

    @abstractmethod
    def visit_pred_count_range(
        self, node: PredCountRange, ctx: ConverterContext
    ) -> VisitStream:
        """
        kdl:`len-range <start> <end>`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - START > len > END
        """
