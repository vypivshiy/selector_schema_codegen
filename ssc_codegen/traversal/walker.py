from __future__ import annotations

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
    InitFieldCall,
    InitField,
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
)
from ssc_codegen.traversal.context import WalkContext

# Node categories — select the body-traversal mode.
# Container: depth+1, index=0, no advance between siblings.
_CONTAINER_NODES = (JsonDef, TypeDef, StructBase, Init)

# Pipeline: index advances after each node (delegated to walk_pipeline).
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

HandlerResult = list[str] | str | None


class BaseWalker:
    """Shared AST traversal core for all backends.

    Dispatches nodes to ``visit_*`` handlers via a class-level ``_DISPATCH``
    table.  Handlers return ``list[str]`` (complete codegen lines), ``str``
    (single line convenience), or ``None`` (no output).

    Body traversal is split into three modes, selected by node category:

    - **Container** (JsonDef, TypeDef, StructBase, Init):
      depth+1, index=0, siblings share the same index.
    - **Pipeline** (Field, InitField, PreValidate, ...):
      depth+1, index advances after each child.
    - **Predicate** (Filter, Assert, Match, LogicAnd/Or/Not):
      depth+1, index=0, index advances between predicate conditions.
    """

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
        # REST result artifacts
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

    # === DISPATCH ===

    def walk(self, node: Node, ctx: WalkContext) -> list[str]:
        """Dispatch a single node to its handler.

        Accepts ``list[str]``, ``str``, or ``None`` return values.
        Unknown node types (not in ``_DISPATCH``) produce no output.
        """
        name = self._DISPATCH.get(type(node))
        if name is None:
            return []
        result: HandlerResult = getattr(self, name)(node, ctx)
        if result is None:
            return []
        if isinstance(result, str):
            return [result]
        return result

    # === BODY TRAVERSAL ===

    def walk_children(self, node: Node, ctx: WalkContext) -> list[str]:
        """Traverse ``node.body`` using the mode selected by node category.

        - Container: depth+1, index=0, no advance.
        - Predicate: depth+1, index=0, advance after each child.
        - Pipeline: delegates to ``walk_pipeline`` at depth+1.

        Returns ``[]`` for nodes not in any category.
        """
        if isinstance(node, _PREDICATE_NODES):
            inner = ctx.deeper().reset_index()
            lines: list[str] = []
            for child in node.body:
                lines.extend(self.walk(child, inner))
                inner = inner.advance()
            return lines
        if isinstance(node, _CONTAINER_NODES):
            inner = ctx.deeper().reset_index()
            lines = []
            for child in node.body:
                lines.extend(self.walk(child, inner))
            return lines
        if isinstance(node, _PIPELINE_NODES):
            return self.walk_pipeline(node.body, ctx.deeper())
        return []

    def walk_pipeline(self, nodes: list[Node], ctx: WalkContext) -> list[str]:
        """Traverse a pipeline body: index advances after each node.

        ``Fallback`` nodes are handled specially: the handler owns its body
        traversal (calls ``walk_pipeline`` internally), and the outer ctx is
        advanced by the body node count at depth+1 — matching the legacy
        ``_emit_pipeline`` sync behaviour.
        """
        lines: list[str] = []
        for node in nodes:
            if isinstance(node, Fallback):
                lines.extend(self.walk(node, ctx))
                inner = ctx.deeper()
                for _ in node.body:
                    inner = inner.advance()
                ctx = inner
                continue
            lines.extend(self.walk(node, ctx))
            ctx = ctx.advance()
        return lines
