from abc import ABC, abstractmethod
from dataclasses import replace

from ssc_codegen.ast import (
    Node,
    Module,
    Docstring,
    Utilities,
    JsonDef,
    JsonDefField,
    TypeDef,
    TypeDefField,
    StructBase,
    StructItem,
    StructList,
    StructFlatList,
    StructDict,
    StructTable,
    StructRest,
    StructDocstring,
    StartParse,
    Init,
    InitField,
    Field,
    PreValidate,
    CheckMethod,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableMatchKey,
    TableRow,
    MethodRest,
    MethodFetch,
    ErrorResponse,
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
    FallbackStart,
    FallbackEnd,
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
    PredRange,
    PredIn,
    PredGe,
    PredGt,
    PredLe,
    PredLt,
    PredRe,
    PredReAll,
    PredReAny,
    CodeEndHook,
    CodeStartHook,
)
from ssc_codegen.converters.base import ConverterContext

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
    TableRow,
)

# Predicate: depth+1, index=0, advance between siblings.
_PREDICATE_NODES = (Filter, Assert, Match, LogicNot, LogicAnd, LogicOr)


class Visitor(ABC):
    """Base transpiler visitor: walks the AST and dispatches nodes to visit_* methods.

    CONTRACT for visit_* methods (generators):
        - `yield "..."`   -> emit a line
        - `yield` (None)  -> traverse node.body, then resume the method (pre/post hook)
        - `yield [...]`   -> extend with a list of lines
        - `yield from it` -> delegate to an iterable
        - `return` / non-generator -> no-op

    `""` is preserved as a blank line; `None` is reserved as the traverse-children signal.
    """

    def __init__(self, var_name: str = "v", indent: str = " " * 4) -> None:
        self.var_name = var_name
        self.indent = indent

    # === CORE ===
    def convert(self, module_ast: Module, **meta) -> str:
        """Entry point: generate target code from the AST (main.py-compatible).

        Creates a ConverterContext, emits the file header via visit_module,
        then walks module_ast.body through visit(). `meta` is forwarded to ctx.meta.
        """
        ctx = ConverterContext(
            var_name=self.var_name, indent_char=self.indent, meta=dict(meta)
        )
        lines: list[str] = list(self.visit_module(module_ast, ctx))
        for node in module_ast.body:
            lines.extend(self.visit(node, ctx))
        return "\n".join(lines)

    def visit(self, node: Node, ctx: ConverterContext) -> list[str]:
        """Universal AST visitor: dispatches a node to visit_* and intercepts bare-yield.

        Walks the whole AST tree and hands nodes off to the concrete handler code.
        """
        name = self._DISPATCH.get(type(node))
        if name is None:
            return []
        gen = getattr(self, name)(node, ctx)
        if gen is None:
            return []
        lines: list[str] = []
        for item in gen:
            if item is None:
                lines.extend(self._emit_body(node, ctx))
            elif isinstance(item, str):
                lines.append(item)
            else:
                lines.extend(x for x in item if x)
        return lines

    def _emit_body(self, node: Node, ctx: ConverterContext) -> list[str]:
        """Traverse a node's body. The mode is selected by category (_CONTAINER/_PREDICATE/_PIPELINE).

        Ported from base.BaseConverter._emit_node (three modes + the InitField special case).
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
            if isinstance(node, InitField):
                return self._emit_pipeline(node.body, ctx)
            return self._emit_pipeline(node.body, ctx.deeper())
        return []

    def _emit_pipeline(
        self, nodes: list[Node], ctx: ConverterContext
    ) -> list[str]:
        """Traverse a pipeline body (Field.body, etc.): index advances after each node.

        FallbackStart/FallbackEnd are handled specially: nodes between them are emitted
        at depth+1 so the try-block is indented correctly.
        Ported verbatim from base.BaseConverter._emit_pipeline.
        """
        lines: list[str] = []
        in_fallback = False
        fallback_ctx = ctx
        for node in nodes:
            if isinstance(node, FallbackStart):
                in_fallback = True
                lines.extend(self.visit(node, ctx))
                fallback_ctx = replace(ctx, depth=ctx.depth + 1)
                continue
            elif isinstance(node, FallbackEnd):
                in_fallback = False
                ctx = replace(ctx, index=fallback_ctx.index, depth=ctx.depth)
                lines.extend(self.visit(node, ctx))
                continue
            if in_fallback:
                lines.extend(self.visit(node, fallback_ctx))
                fallback_ctx = fallback_ctx.advance()
                ctx = replace(ctx, index=fallback_ctx.index)
            else:
                lines.extend(self.visit(node, ctx))
                ctx = ctx.advance()
        return lines

    # === DISPATCH TABLE ===
    # Single source of truth: node -> visit_* method name.
    # A concrete subclass must implement every method (otherwise the call raises TypeError).
    _DISPATCH: dict[type[Node], str] = {
        # module
        Module: "visit_module",
        Docstring: "visit_docstring",
        Utilities: "visit_utilities",
        CodeStartHook: "visit_code_start_hook",
        CodeEndHook: "visit_code_end_hook",
        # typedef / jsondef
        JsonDef: "visit_jsondef",
        JsonDefField: "visit_jsondef_field",
        TypeDef: "visit_typedef",
        TypeDefField: "visit_typedef_field",
        # struct
        StructItem: "visit_struct_item",
        StructList: "visit_struct_list",
        StructFlatList: "visit_struct_flat_list",
        StructDict: "visit_struct_dict",
        StructTable: "visit_struct_table",
        StructRest: "visit_struct_rest",
        StructDocstring: "visit_struct_docstring",
        StartParse: "visit_start_parse",
        Init: "visit_init",
        InitField: "visit_init_field",
        Field: "visit_field",
        PreValidate: "visit_pre_validate",
        CheckMethod: "visit_check_method",
        SplitDoc: "visit_split_doc",
        Key: "visit_key",
        Value: "visit_value",
        TableConfig: "visit_table_config",
        TableMatchKey: "visit_table_match_key",
        TableRow: "visit_table_row",
        MethodFetch: "visit_method_fetch",
        MethodRest: "visit_method_rest",
        ErrorResponse: "visit_error_response",
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
        FallbackStart: "visit_fallback_start",
        FallbackEnd: "visit_fallback_end",
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
        PredRange: "visit_pred_range",
        PredIn: "visit_predicate_in",
        PredGe: "visit_predicate_ge",
        PredGt: "visit_predicate_gt",
        PredLe: "visit_predicate_le",
        PredLt: "visit_predicate_lt",
        PredRe: "visit_predicate_re",
        PredReAll: "visit_predicate_re_all",
        PredReAny: "visit_predicate_re_any",
    }

    # NODE APIS. need override
    @abstractmethod
    def std_lib(self, name: str):
        """Emit the standard library to simplify expression codegen.

        The code may be inlined into the module.

        Note: do not implement an std equivalent when the operation translates
        natively from the AST in a single line.
        """

    @abstractmethod
    def visit_module(self, node: Module, ctx: ConverterContext):
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
        """

    @abstractmethod
    def visit_docstring(self, node: Docstring):
        """DEPRECATED: docstring is now a ``Module.doc`` field, emitted by
        ``visit_module``. This handler is retained as a no-op for any
        manually-constructed ``Docstring`` nodes; it will be removed once
        the deprecated class is dropped.
        """

    @abstractmethod
    def visit_utilities(self, node: Utilities, ctx: ConverterContext):
        """
        Auto-generated AST node (not user-authored).

        Used to emit inlined std code when a separate runtime module is not generated.
        """

    @abstractmethod
    def visit_code_start_hook(self, node: CodeStartHook, ctx: ConverterContext):
        """
        Auto-generated AST node (not user-authored).

        Special AST hook: extra code can be inserted right after the Utilities node.

        Return None when not needed.
        """

    @abstractmethod
    def visit_code_end_hook(self, node: CodeEndHook, ctx: ConverterContext):
        """
        Auto-generated AST node (not user-authored).

        Special AST hook: extra code can be inserted at the end of the file.

        Return None when not needed.
        """

    # === TYPES ===
    @abstractmethod
    def visit_jsondef(self, node: JsonDef, ctx: ConverterContext):
        """
        KDL: `json <name> { ... }`

        Emit a struct/type annotation used to type JSON data.
        """

    @abstractmethod
    def visit_jsondef_field(self, node: JsonDefField, ctx: ConverterContext):
        """
        KDL: `json <name> { field... }`

        Emit a typed field of a JsonDef struct.
        Derive the type from `node.ret`.
        """

    @abstractmethod
    def visit_typedef(self, node: TypeDef, ctx: ConverterContext):
        """
        Auto-generated AST node (not user-authored); derived from a non-rest `struct`.

        Emit a struct/type annotation used to type data for HTML-parser structs.
        """

    @abstractmethod
    def visit_typedef_field(self, node: TypeDefField, ctx: ConverterContext):
        """
        Auto-generated AST node (not user-authored); derived from a non-rest `struct`.

        Emit a typed field of a TypeDef struct.
        Derive the type from `node.ret`.
        """

    # === STRUCT ===
    # TODO: unify into a single struct node?
    @abstractmethod
    def visit_struct_item(self, node: StructItem, ctx: ConverterContext):
        """
        KDL: `struct <name> { ... } | (item)struct <name> { ... } | struct <name> type=item { ... }`

        Emit the struct/class header.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_struct_list(self, node: StructList, ctx: ConverterContext):
        """
        KDL: `struct <name> type=list { ... } | (list)struct <name> { ... }`

        Emit the struct/class header.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_struct_flat_list(
        self, node: StructFlatList, ctx: ConverterContext
    ):
        """
        KDL: `struct <name> type=flat { ... } | (flat)struct <name> { ... }`

        Emit the struct/class header.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_struct_dict(self, node: StructDict, cxt: ConverterContext):
        """
        KDL: `struct <name> type=dict { ... } | (dict)struct <name> { ... }`

        Emit the struct/class header.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_struct_table(self, node: StructTable, ctx: ConverterContext):
        """
        KDL: `struct <name> type=table { ... } | (table)struct <name> { ... }`

        Emit the struct/class header.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_struct_rest(self, node: StructRest, ctx: ConverterContext):
        """
        KDL: `struct <name> type=rest { ... } | (rest)struct <name> { ... }`

        Emit the struct/class header used to call REST methods.

        If documented, emit the docstring.
        """

    @abstractmethod
    def visit_struct_docstring(
        self, node: StructDocstring, ctx: ConverterContext
    ):
        """DEPRECATED: struct docstring is now a ``StructBase.doc`` field.

        The converter picks the position (top/bottom of the class declaration)
        per target language. This handler is retained as a no-op for any
        manually-constructed ``StructDocstring`` nodes.
        """
        pass

    @abstractmethod
    def visit_init(self, node: Init, ctx: ConverterContext):
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
    def visit_init_field(self, node: InitField, ctx: ConverterContext):
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
    def visit_field(self, node: Field, ctx: ConverterContext):
        """

        KDL: `struct Foo { <name> { ... }... }`

        Emit the header of a private struct method whose value is computed when StartParse runs.
        """

    @abstractmethod
    def visit_pre_validate(self, node: PreValidate, ctx: ConverterContext):
        """

        KDL: `@pre-validate { ... }`

        Emit the header of a private struct method that validates the value before parsing.
        - The document is not modified.
        - This field is expected to apply `assert` blocks.
        - On a failed check the code raises/returns an error.
        """

    @abstractmethod
    def visit_check_method(self, node: CheckMethod, ctx: ConverterContext):
        """

        KDL: `@check <name> { ... }`

        Emit the header of a public struct method that can be called for basic checks.
        - Always returns a boolean.
        """

    @abstractmethod
    def visit_split_doc(self, node: SplitDoc, ctx: ConverterContext):
        """

        KDL: `@split-doc { ... }`

        Emit the header of a private struct method that splits the document into parts by a selector (e.g. into cards).
        - Always returns TypeInfo(Document, is_array=True).
        """

    @abstractmethod
    def visit_key(self, node: Key, ctx: ConverterContext):
        """
        KDL: `@key { ... }`

        Emit the header of a private method for StructDict that produces the key. Always returns STRING.
        """

    @abstractmethod
    def visit_value(self, node: Value, ctx: ConverterContext):
        """
        KDL: `@value { ... }`

        1. Emit the header of a private method for StructDict that produces the value.
        2. (ADHOC) Emit the header of a private method for StructTable that extracts the value from a table row.
        """

    @abstractmethod
    def visit_table_config(self, node: TableConfig, ctx: ConverterContext):
        """
        KDL: `@table { ... }`
        Emit the header of a private method for StructTable that selects the <table>-like element.
        """

    @abstractmethod
    def visit_table_match_key(self, node: TableMatchKey, ctx: ConverterContext):
        """
        KDL: `@match { ... }`

        Emit the header of a private method for StructTable that extracts the "key" value from the table. Always returns STRING.
        Used to match values in HTML tables.
        """

    @abstractmethod
    def visit_table_row(self, node: TableRow, ctx: ConverterContext):
        """
        KDL: `@rows { ... }`

        Emit the header of a private method that extracts all rows from the table. Always returns DOCUMENT (is_array=True).
        """

    @abstractmethod
    def visit_method_fetch(self, node: MethodFetch, ctx: ConverterContext):
        """
        KDL: `@request ...`

        For HTML-parser structs: an optional classmethod constructor that performs the HTTP request and initialises the instance.

        - Does not configure the HTTP client — it is passed as the first argument and must be configured externally.
        - Signature: (HttpClient, *, params...).
        """

    @abstractmethod
    def visit_method_rest(self, node: MethodRest, ctx: ConverterContext):
        """
        KDL: `@request ...`

        For REST-API structs: adds a method that sends the request and returns the JSON result.

        - Does not configure the HTTP client — it is passed as the first argument and must be configured externally.
        - Signature: (HttpClient, *, params...).
        - TIP: for simplicity, ergonomics and portability, prefer returning (and generating) monad-like result types.
        """

    @abstractmethod
    def visit_error_response(self, node: ErrorResponse, ctx: ConverterContext):
        """
        TODO: define the error-response contract.
        """

    @abstractmethod
    def visit_start_parse(self, node: StartParse, ctx: ConverterContext):
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
    def visit_css_select(self, node: CssSelect, ctx: ConverterContext):
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
    def visit_css_select_all(self, node: CssSelectAll, ctx: ConverterContext):
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
    def visit_css_remove(self, node: CssRemove, ctx: ConverterContext):
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
    def visit_xpath_select(self, node: XpathSelect, ctx: ConverterContext):
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
    ):
        """
        kdl: `xpath-all query | xpath-all { query1; query2... }`

        TYPES:
            - DOCUMENT -> DOCUMENT[]

        - Extract all elements matching the XPATH selector.
        - If multiple queries are passed, return the elements from the first selector that matches.
        - No need to handle null/None.
        """

    @abstractmethod
    def visit_xpath_remove(self, node: XpathRemove, ctx: ConverterContext):
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
    def visit_text(self, node: Text, ctx: ConverterContext):
        """
        kdl: `text`

        TYPES:
            - DOCUMENT -> STRING
            - DOCUMENT[] -> STRING[]

        - Extract the element's text.
        - If DOCUMENT(array=true), extract from each element and return a flat list.
        """

    @abstractmethod
    def visit_raw(self, node: Raw, ctx: ConverterContext):
        """
        kdl: `raw`

        TYPES:
            - DOCUMENT -> STRING
            - DOCUMENT[] -> STRING[]

        - Extract the element's raw HTML (htmlOuter; descendants included).
        - If DOCUMENT(array=true), extract from each element and return a flat list.
        """

    @abstractmethod
    def visit_attr(self, node: Attr, ctx: ConverterContext):
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
    def visit_trim(self, node: Trim, ctx: ConverterContext):
        """
        kdl: `trim <chars>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Strip characters from the LEFT and RIGHT.
        - If <chars> is empty, strip all whitespace.
        """

    @abstractmethod
    def visit_l_trim(self, node: Ltrim, ctx: ConverterContext):
        """
        kdl: `ltrim <chars>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Strip characters from the LEFT.
        - If <chars> is empty, strip all whitespace.
        """

    @abstractmethod
    def visit_r_trim(self, node: Rtrim, ctx: ConverterContext):
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
    def visit_rm_prefix(self, node: RmPrefix, ctx: ConverterContext):
        """
        kdl: `rm-prefix <substr>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Remove a prefix matching the substring.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_rm_suffix(self, node: RmSuffix, ctx: ConverterContext):
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
    ):
        """
        kdl: `rm-prefix-suffix <substr>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Remove the prefix, then the suffix matching the substring.
        """

    @abstractmethod
    def visit_format(self, node: Fmt, ctx: ConverterContext):
        """
        kdl: `fmt <template>`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Substitute the previous value into the template.
        - The template placeholder/hole is `{{}}` — translate it to the target equivalent.
        """

    @abstractmethod
    def visit_repl(self, node: Repl, ctx: ConverterContext):
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
    def visit_repl_map(self, node: ReplMap, ctx: ConverterContext):
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
    def visit_lower(self, node: Lower, ctx: ConverterContext):
        """
        kdl: `lower`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Convert to lowercase.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_upper(self, node: Upper, ctx: ConverterContext):
        """
        kdl: `upper`

        TYPES:
            - STRING -> STRING
            - STRING[] -> STRING[]

        - Convert to uppercase.
        - STRING(array) — applied to every element.
        """

    @abstractmethod
    def visit_split(self, node: Split, ctx: ConverterContext):
        """
        kdl: `split <sep>`

        TYPES:
            - STRING -> STRING[]

        - Split by the substring.
        """

    @abstractmethod
    def visit_join(self, node: Join, ctx: ConverterContext):
        """
        kdl: `join <sep>`

        TYPES:
            - STRING[] -> STRING

        - Join into a single string using `sep` as the separator.
        """

    @abstractmethod
    def visit_norm_space(self, node: NormalizeSpace, ctx: ConverterContext):
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
    def visit_unescape(self, node: Unescape, ctx: ConverterContext):
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
    def visit_re(self, node: Re, ctx: ConverterContext):
        """
        kdl: `re <pattern>`

        TYPES:
            - STRING -> STRING

        - Capture **exactly one group**.
        - Basic PCRE syntax without advanced features like lookahead, lookbehind, named groups.
        """

    @abstractmethod
    def visit_re_all(self, node: ReAll, ctx: ConverterContext):
        """
        kdl: `re-all <pattern>`

        TYPES:
            - STRING -> STRING[]

        - Capture **exactly one group**.
        - Basic PCRE syntax without advanced features like lookahead, lookbehind, named groups.
        """

    @abstractmethod
    def visit_re_sub(self, node: ReSub, ctx: ConverterContext):
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
    def visit_index(self, node: Index, ctx: ConverterContext):
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
    def visit_slice(self, node: Slice, ctx: ConverterContext):
        """
        kdl: `slice <START> <END>`

        TYPES:
            - AUTO[] -> AUTO[]

        TODO (few tests, rarely used in practice).
        """

    @abstractmethod
    def visit_len(self, node: Len, ctx: ConverterContext):
        """
        kdl: `len`

        TYPES:
            - AUTO[] -> INT

        - Get the length of the previous element.
        - Works only with is_array=true; does not take the length of strings.
        """

    @abstractmethod
    def visit_unique(self, node: Unique, ctx: ConverterContext):
        """
        kdl: `unique`

        TYPES:
            - STRING[] -> STRING[]

        - Remove duplicates.
        - If keep_order=True, use an algorithm that preserves element order.
        """

    # === CASTS ===
    @abstractmethod
    def visit_to_int(self, node: ToInt, ctx: ConverterContext):
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
    def visit_to_float(self, node: ToFloat, ctx: ConverterContext):
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
    def visit_to_bool(self, node: ToBool, ctx: ConverterContext):
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
    def visit_jsonify(self, node: Jsonify, ctx: ConverterContext):
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
    def visit_nested(self, node: Nested, ctx: ConverterContext):
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
    def visit_self(self, node: Self, ctx: ConverterContext):
        """
        kdl: `self <init-field-name>` (deprecated)
        kdl: `@<init-field-name>`

        TYPES:
            - DOCUMENT -> AUTO

        - Always the first call.
        - Copy the precomputed value from this field (its data type is whatever the init-field returned).
        """

    @abstractmethod
    def visit_return(self, node: Return, ctx: ConverterContext):
        """
        Auto-generated AST node.

        - The last value in a field is returned; the type is inferred automatically.
        - For PreValidate it is always null/None (returns nothing).
        """

    @abstractmethod
    def visit_fallback_start(self, node: FallbackStart, ctx: ConverterContext):
        """
        kdl: `fallback <value>|{}`

        - Combined, FallbackStart + FallbackEnd form a try/catch.
        - If the target has no such construct, emulate it.
            - e.g. in Go via `defer func(){ recover <value> }()` + `panic`.
        """

    @abstractmethod
    def visit_fallback_end(self, node: FallbackEnd, ctx: ConverterContext):
        """
        kdl: `fallback <value>|{}`

        - Combined, FallbackStart + FallbackEnd form a try/catch.
        - If the target has no such construct, emulate it.
            - e.g. in Go via `defer func(){ recover <value> }()` + `panic`.
        """

    # === PREDICATE CALLS ===
    @abstractmethod
    def visit_filter(self, node: Filter, ctx: ConverterContext):
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
    def visit_assert(self, node: Assert, ctx: ConverterContext):
        """
        kdl: `assert { ... }`

        TYPES:
            - AUTO -> AUTO

        - Filter by the inner predicates.
        - If the value is false, raise an error.
        - Multiple predicates default to AND.
        """

    @abstractmethod
    def visit_match(self, node: Match, ctx: ConverterContext):
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
    def visit_logic_and(self, node: LogicAnd, ctx: ConverterContext):
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
    def visit_logic_or(self, node: LogicOr, ctx: ConverterContext):
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
    def visit_logic_not(self, node: LogicNot, ctx: ConverterContext):
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
    def visit_predicate_css(self, node: PredCss, ctx: ConverterContext):
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
    def visit_predicate_xpath(self, node: PredXpath, ctx: ConverterContext):
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
    ):
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
    ):
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
    ):
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
    ):
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
    def visit_predicate_attr_eq(self, node: PredAttrEq, ctx: ConverterContext):
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
    def visit_predicate_attr_ne(self, node: PredAttrNe, ctx: ConverterContext):
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
    def visit_predicate_attr_re(self, node: PredAttrRe, ctx: ConverterContext):
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
    ):
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
    ):
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
    ):
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
    def visit_predicate_text_re(self, node: PredTextRe, ctx: ConverterContext):
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
    ):
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
    def visit_predicate_eq(self, node: PredEq, ctx: ConverterContext):
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
    def visit_predicate_ne(self, node: PredNe, ctx: ConverterContext):
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
    def visit_predicate_starts(self, node: PredStarts, ctx: ConverterContext):
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
    def visit_predicate_ends(self, node: PredEnds, ctx: ConverterContext):
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
    def visit_predicate_re(self, node: PredRe, ctx: ConverterContext):
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

    # TODO: remove: dup expr with contains <values...>
    def visit_predicate_in(self, node: PredIn, ctx: ConverterContext):
        """
        kdl:`in <values...>`
        """

    @abstractmethod
    def visit_predicate_ge(self, node: PredGe, ctx: ConverterContext):
        # TODO: remove, use len-ge
        """
        kdl:`ge`

        - `>=`
        - used in `assert` only expr
        - compare by len (string or array-like expr)
        """

    @abstractmethod
    def visit_predicate_gt(self, node: PredGt, ctx: ConverterContext):
        # TODO: remove, use len-gt
        """
        kdl:`gt`

        - `>`
        - used in `assert` only expr
        - compare by len (string or array-like expr)
        """

    @abstractmethod
    def visit_predicate_le(self, node: PredLe, ctx: ConverterContext):
        # TODO: remove, use len-le
        """
        kdl:`le`

        - `<=`
        - used in `assert` only expr
        - compare by len (string or array-like expr)
        """

    @abstractmethod
    def visit_predicate_lt(self, node: PredLt, ctx: ConverterContext):
        # TODO: remove, use len-lt
        """
        kdl:`lt`

        `<`
        - used in `assert` only expr
        - compare by len (string or array-like expr)
        """

    # === LOGIC LEN ===
    @abstractmethod
    def visit_predicate_re_all(self, node: PredReAll, ctx: ConverterContext):
        """
        kdl:`re-all <pattern>`

        TYPES:
            - STRING[] -> STRING[]

        - Accepts STRING(array=true).
        - All strings must match the pattern.
        """

    @abstractmethod
    def visit_predicate_re_any(self, node: PredReAny, ctx: ConverterContext):
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
    ):
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
    ):
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
    ):
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
    ):
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
    ):
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
    ):
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
    ):
        """
        kdl:`len-range <start> <end>`

        TYPES:
            - AUTO[] -> AUTO[]
            - STRING -> STRING

        - START > len > END
        """

    @abstractmethod
    def visit_pred_range(self, node: PredRange, ctx: ConverterContext):
        """
        kdl:`range <start> <end>`

        TYPES:
            - STRING -> STRING

        - assert-only expression.
        - START < len < END (compared by string/array length).
        - Shortcut for PredGt + PredLt.
        """
