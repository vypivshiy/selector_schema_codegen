from typing import Callable, ClassVar, cast, Any, TypeVar

from ssc_codegen.ast_ import (
    BaseAstNode,
    ModuleProgram,
    Docstring,
    ModuleImports,
    TypeDef,
    TypeDefField,
    JsonStruct,
    JsonStructField,
    StructParser,
    StructFieldMethod,
    StructInitMethod,
    StructPartDocMethod,
    StructPreValidateMethod,
    StartParseMethod,
    FilterOr,
    FilterAnd,
    FilterNot,
)
from ssc_codegen.tokens import StructType, TokenType

T_NODE = TypeVar("T_NODE", bound=BaseAstNode[Any, Any])
CB_FMT_DEBUG_COMMENT = Callable[[BaseAstNode[Any, Any], str], str]
CB_AST_BIND = Callable[[T_NODE], str]
CB_AST_DECORATOR = Callable[[CB_AST_BIND], CB_AST_BIND]


def debug_comment_cb(node: BaseAstNode, comment_prefix: str) -> str:
    """Generate a debug comment for an AST node.

    Creates a formatted string containing information about the node's type,
    return type (if applicable), and other relevant details for debugging purposes.

    Args:
        node: The AST node to generate a comment for.
        comment_prefix: The prefix to add to each line of the comment.

    Returns:
        A formatted string containing debug information about the node.
    """
    match node.kind:
        case TokenType.EXPR_RETURN:
            token = f"{comment_prefix}Token: {node.kind.name} ret_type: {node.ret_type.name}"
        case TokenType.EXPR_NO_RETURN:
            token = f"{comment_prefix}Token: {node.kind.name}"
        case TokenType.STRUCT_PARSE_START:
            parent = node.parent
            parent = cast(StructParser, parent)
            return f"{comment_prefix}Token: {node.kind.name}, type: {parent.struct_type.name}"
        case _:
            token = f"{comment_prefix}Token: {node.kind.name}, kwargs: {node.kwargs}"
    if node.classvar_hooks:
        fmt_hooks = ", ".join(
            f"{v.kind.name} {v.kwargs}" for v in node.classvar_hooks.values()
        )
        return f"{token}\n{comment_prefix}{fmt_hooks}"
    return token


class BaseCodeConverter:
    """Base AST visitor class and code converter.

    This class serves as the foundation for converting AST nodes into code.
    Visitors are set using decorators that point to specific TokenTypes.

    Decorator hooks can be overridden:
    - As defaults, __call__ methods set @pre decorator
    - @pre - First trigger visitor entrypoint
    - @post - Second trigger visitor entrypoint (for closing brackets or other logic).
    It will be called when the broadcast of all nodes and the container body is transpiled.

    Example:
        ```
        CONVERTER = BaseCodeConverter()

        # recommended use <node>.kind call as key in decorators instead TokenType.<TOKEN>
        @CONVERTER(ModuleImports.kind)
        def pre_imports(_node: ModuleImports) -> str:
            # implement imports stmt
            return '''from bs4 import BeautifulSoap'''

        # TypeDef and StartParseMethod node allow add extra second shortcut as StructType for
        # increase code readability and simplify codegen

        # TYPEDEF Impl
        # post_callback - shortcut for minify typical end expr (eg: close parens)

        # generate type for StructType.ITEM parser
        @CONVERTER(TypeDef.kind, StructType.ITEM, post_callback=lambda _: "})")
        def pre_typedef_item(node: TypeDef) -> str:
            name, _ = node.unpack_args()
            return f'T_{name} = TypedDict("T_{name}", ' + "{"

        # generate type for StructType.DICT parser
        @CONVERTER(TypeDef.kind, StructType.DICT)
        def pre_typedef_dict(node: TypeDef) -> str:
            name, _ = node.unpack_args()
            type_ = get_typedef_field_by_name(node, "__VALUE__")
            return f"T_{name} = Dict[str, {type_}]"

        # StartParse impl
        @CONVERTER(StartParseMethod.kind, StructType.ITEM)
        def pre_start_parse_item(node: StartParseMethod) -> str:
            # some impl for ItEM struct
            return ""

        @CONVERTER(StartParseMethod.kind, StructType.LIST)
        def pre_start_parse_list(node: StartParseMethod) -> str:
            # some impl for LIST struct
            return ""
        ```

    Attributes:
        TEST_EXCLUDE_NODES: List of token types to exclude from tests.
    """

    TEST_EXCLUDE_NODES: ClassVar[list[TokenType]] = [
        # build-ins, not used in converters
        TokenType.VARIABLE,
        TokenType.EXPR_DEFAULT,
        TokenType.MODULE,
        TokenType.CODE_START,
        TokenType.CODE_END,
        TokenType.STRUCT_CALL_FUNCTION,
        TokenType.STRUCT_CALL_CLASSVAR,
    ]
    """Developer class variable that marks nodes to exclude in tests."""

    def __init__(
        self,
        debug_instructions: bool = False,
        debug_comment_prefix: str = "",
        comment_prefix_sep: str = "\n",
        debug_cb: CB_FMT_DEBUG_COMMENT = debug_comment_cb,
    ) -> None:
        """
        Arguments:
        debug_instructions: enable debug instructions (add comment for every generated instruction. used in debug codegen output)
        debug_comment_prefix: comment line prefix (used in debug codegen output)
        debug_cb: callback formatting comment (used in debug codegen output)
        """
        self._debug_instructions = debug_instructions
        self._debug_comment_prefix = debug_comment_prefix
        self._debug_cb = debug_cb
        self._comment_prefix_sep = comment_prefix_sep
        self.pre_definitions: dict[
            TokenType | int | tuple[TokenType, StructType], CB_AST_BIND
        ] = {}
        self.post_definitions: dict[
            TokenType | int | tuple[TokenType, StructType], CB_AST_BIND
        ] = {}

    @property
    def comment_prefix_sep(self) -> str:
        return self._comment_prefix_sep

    @comment_prefix_sep.setter
    def comment_prefix_sep(self, comment_prefix_sep: str) -> None:
        self._comment_prefix_sep = comment_prefix_sep

    @property
    def comment_prefix(self) -> str:
        return self._debug_comment_prefix

    @comment_prefix.setter
    def comment_prefix(self, value: str) -> None:
        self._debug_comment_prefix = value

    @property
    def debug_instructions(self) -> bool:
        return self._debug_instructions

    @debug_instructions.setter
    def debug_instructions(self, value: bool) -> None:
        self._debug_instructions = value

    def pre(
        self,
        for_definition: TokenType,
        for_struct_definition: StructType | None = None,
        *,
        post_callback: Callable[[BaseAstNode], str] | str | None = None,
    ) -> CB_AST_DECORATOR:
        """Define a pre-conversion decorator for the given TokenType.

        optional allow set post callback for simple string casts like close brackets etc

        StartParseMethod and TypeDef nodes has shortcut (StartParseMethod.kind, StructType.<TYPE>) for simplify callback generators
        """
        if for_struct_definition and for_definition not in (
            StartParseMethod.kind,
            TypeDef.kind,
        ):
            raise TypeError(
                "Add struct definition allowed only for `StartParseMethod` and `TypeDef` nodes"
            )

        def decorator(func: CB_AST_BIND) -> CB_AST_BIND:
            if for_struct_definition:
                self.pre_definitions[
                    (for_definition, for_struct_definition)
                ] = func
            else:
                self.pre_definitions[for_definition] = func
            return func

        if post_callback:
            if for_struct_definition:
                self.post_definitions[
                    (for_definition, for_struct_definition)
                ] = post_callback  # type: ignore[assignment]
            self.post_definitions[for_definition] = post_callback  # type: ignore[assignment]

        return decorator

    def post(
        self,
        for_definition: TokenType,
        for_struct_definition: StructType | None = None,
    ) -> CB_AST_DECORATOR:
        """Define a post-conversion decorator for the given TokenType.

        This method creates a decorator that registers a function to be called
        after the main conversion of a node of the specified type. It's typically
        used for closing brackets or other logic that should happen after the
        main node processing.

        Args:
            for_definition: The TokenType to associate with this post-conversion function.
            for_struct_definition: Optional StructType for specific struct definitions (for StartParseMethod and TypeDef).

        Returns:
            A decorator function that registers the post-conversion handler.

        Raises:
            TypeError: If struct definition is provided for unsupported node types.
        """
        if for_struct_definition and for_definition not in (
            StartParseMethod.kind,
            TypeDef.kind,
        ):
            raise TypeError(
                "Add struct definition allowed only for `StartParseMethod` or `TypeDef` nodes"
            )

        def decorator(func: CB_AST_BIND) -> CB_AST_BIND:
            if for_struct_definition:
                self.post_definitions[
                    (for_definition, for_struct_definition)
                ] = func
            else:
                self.post_definitions[for_definition] = func
            return func

        return decorator

    def __call__(
        self,
        for_definition: TokenType,
        for_struct_definition: StructType | None = None,
        *,
        post_callback: Callable[[BaseAstNode], str] | None = None,
    ) -> CB_AST_DECORATOR:
        """Alias for pre decorator.

        Provides a convenient way to use the pre decorator by calling the class instance
        directly. This is equivalent to calling the pre() method.

        Args:
            for_definition: The TokenType to associate with this conversion function.
            for_struct_definition: Optional StructType for specific struct definitions (only for StartParseMethod and TypeDef nodes).
            post_callback: Optional callback function for post-processing.

        Returns:
            A decorator function that registers the conversion handler.
        """
        return self.pre(
            for_definition, for_struct_definition, post_callback=post_callback
        )

    def _pre_convert_node(
        self, node: BaseAstNode, st_type: StructType | None = None
    ) -> str:
        """Convert the AST node using the pre-definition function.

        This method applies the registered pre-conversion function to an AST node,
        optionally using a specific struct type for more granular control. It handles
        both simple node conversions and struct-specific conversions.

        Args:
            node: The AST node to convert.
            st_type: Optional StructType for struct-specific conversions.

        Returns:
            The result of applying the pre-conversion function to the node,
            or an empty string if no matching function is found.
        """
        # syntax sugar: split generate start_parse methods by part callbacks
        if (
            node.kind in (StartParseMethod.kind, TypeDef.kind)
            and st_type
            and (pre_func := self.pre_definitions.get((node.kind, st_type)))
        ):
            if self.debug_instructions:
                return f"{self._debug_cb(node, self.comment_prefix)}{self.comment_prefix_sep}{pre_func(node)}"
            return pre_func(node)

        # old realisation use
        if pre_func := self.pre_definitions.get(node.kind):
            if self.debug_instructions:
                return f"{self._debug_cb(node, self.comment_prefix)}{self.comment_prefix_sep}{pre_func(node)}"
            return pre_func(node)
        return ""

    def _post_convert_node(
        self, node: BaseAstNode, st_type: StructType | None = None
    ) -> str:
        """Convert the AST node using the post-definition function.

        This method applies the registered post-conversion function to an AST node,
        optionally using a specific struct type for more granular control. It's typically
        used for closing brackets or other logic that should happen after the main
        node processing.

        Args:
            node: The AST node to convert.
            st_type: Optional StructType for struct-specific conversions.

        Returns:
            The result of applying the post-conversion function to the node,
            or an empty string if no matching function is found.
        """
        # syntax sugar: split generate start_parse methods by part callbacks
        if (
            node.kind in (StartParseMethod.kind, TypeDef.kind)
            and st_type
            and StartParseMethod.kind
            and (post_func := self.post_definitions.get((node.kind, st_type)))
        ):
            if self.debug_instructions:
                return f"{self._debug_cb(node, self.comment_prefix)}{self.comment_prefix_sep}{post_func(node)}"
            return post_func(node)

        if post_func := self.post_definitions.get(node.kind):
            return post_func(node)
        return ""

    def convert_program(
        self, ast_program: ModuleProgram, comment: str = ""
    ) -> list[str]:
        """Convert the module AST to code parts.

        This method converts an entire module AST into a list of code parts,
        starting with an optional comment and processing all nodes in the AST.

        Args:
            ast_program: The ModuleProgram AST node to convert.
            comment: An optional comment to include at the beginning of the output.

        Returns:
            A list of strings representing the converted code parts,
            with empty strings filtered out.
        """
        acc = [comment]
        result = self.convert(ast_program, acc)
        return [i for i in result if i]

    def convert(
        self, ast_entry: BaseAstNode, acc: list[str] | None = None
    ) -> list[str]:
        """Convert an AST node into code parts.

        This method dispatches the conversion of an AST node to the appropriate
        conversion method based on the node's type. It builds up a list of code
        parts by processing the node and its children.

        Args:
            ast_entry: The AST node to convert.
            acc: An optional accumulator list to append code parts to.

        Returns:
            A list of strings representing the converted code parts.
        """
        acc = acc or []
        match ast_entry.kind:
            case TokenType.MODULE:
                ast_entry = cast(ModuleProgram, ast_entry)
                self._convert_module(ast_entry, acc)
            case TokenType.DOCSTRING:
                ast_entry = cast(Docstring, ast_entry)
                self._convert_docstring(ast_entry, acc)
            case TokenType.IMPORTS:
                ast_entry = cast(ModuleImports, ast_entry)
                self._convert_imports(ast_entry, acc)
            case TokenType.TYPEDEF:
                ast_entry = cast(TypeDef, ast_entry)
                self._convert_typedef(ast_entry, acc)
            case TokenType.TYPEDEF_FIELD:
                ast_entry = cast(TypeDefField, ast_entry)
                self._convert_typedef_field(ast_entry, acc)
            case TokenType.STRUCT:
                ast_entry = cast(StructParser, ast_entry)
                self._convert_struct(ast_entry, acc)
            case TokenType.JSON_STRUCT:
                ast_entry = cast(JsonStruct, ast_entry)
                self._convert_json_struct(ast_entry, acc)
            case TokenType.JSON_FIELD:
                ast_entry = cast(JsonStructField, ast_entry)
                self._convert_json_struct_field(ast_entry, acc)

            case (
                TokenType.EXPR_FILTER
                | TokenType.EXPR_DOC_FILTER
                | TokenType.FILTER_OR
                | TokenType.FILTER_AND
                | TokenType.FILTER_NOT
            ):
                ast_entry = cast(FilterOr | FilterAnd | FilterNot, ast_entry)
                self._convert_logic_filter(ast_entry, acc)
            case (
                TokenType.STRUCT_PART_DOCUMENT
                | TokenType.STRUCT_PRE_VALIDATE
                | TokenType.STRUCT_PARSE_START
                | TokenType.STRUCT_FIELD
                | TokenType.STRUCT_INIT
            ):
                ast_entry = cast(
                    StructFieldMethod
                    | StartParseMethod
                    | StructPartDocMethod
                    | StructPreValidateMethod
                    | StructInitMethod,
                    ast_entry,
                )
                self._convert_struct_method(ast_entry, acc)
            case _:
                self._convert_default(ast_entry, acc)
        return acc

    def _convert_logic_filter(
        self, ast_entry: FilterOr | FilterAnd | FilterNot, acc: list[str]
    ) -> None:
        """Convert a logical filter node (OR, AND, NOT) and its children.

        This method handles the conversion of logical filter operations, appending
        the pre-conversion result, processing all child nodes, and then appending
        the post-conversion result.

        For example, an AND filter with two children would be converted as:
        AND(body=[F1, F2]) ->
        AND ( (OPEN)
              F1 and F2
        ) (CLOSE)

        Args:
            ast_entry: The logical filter node (FilterOr, FilterAnd, or FilterNot) to convert.
            acc: The accumulator list to append code parts to.
        """
        # AND(body=[F1, F2]) ->
        # AND ( (OPEN)
        #       F1 and F2
        # ) (CLOSE)
        acc.append(self._pre_convert_node(ast_entry))
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_module(self, ast_entry: ModuleProgram, acc: list[str]) -> None:
        """Handle module conversion.

        This method processes all nodes in a module's body by recursively converting
        each one and appending the results to the accumulator.

        Args:
            ast_entry: The ModuleProgram node to convert.
            acc: The accumulator list to append code parts to.
        """
        for node in ast_entry.body:
            self.convert(node, acc)

    def _convert_docstring(self, ast_entry: Docstring, acc: list[str]) -> None:
        """Handle docstring conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_imports(
        self, ast_entry: ModuleImports, acc: list[str]
    ) -> None:
        """Handle imports conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_typedef(self, ast_entry: TypeDef, acc: list[str]) -> None:
        """Handle typedef conversion."""
        _, st_type = ast_entry.unpack_args()
        self._convert_node_with_struct_type(ast_entry, acc)
        # acc.append(self._pre_convert_node(ast_entry))
        # # TYPEDEF_FIELD call
        # for node in ast_entry.body:
        #     self.convert(node, acc)
        # acc.append(self._post_convert_node(ast_entry))

    def _convert_typedef_field(
        self, ast_entry: TypeDefField, acc: list[str]
    ) -> None:
        """Handle typedef field conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_json_struct(
        self, ast_entry: JsonStruct, acc: list[str]
    ) -> None:
        acc.append(self._pre_convert_node(ast_entry))
        # JSON_ST_FIELD call
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_json_struct_field(
        self, ast_entry: JsonStructField, acc: list[str]
    ) -> None:
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))

    def _convert_struct(self, ast_entry: StructParser, acc: list[str]) -> None:
        """Handle struct conversion."""
        # pre_CLASS/STRUCT HEADER
        # pre_CONSTRUCTOR post_CONSTRUCTOR
        # BODY
        # post_CLASS/STRUCT
        # class header (with docstring) -> constructor -> body -> class footer
        acc.append(self._pre_convert_node(ast_entry))
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry))

    def _convert_node_with_struct_type(
        self, ast_entry: StartParseMethod | TypeDef, acc: list[str]
    ) -> None:
        if isinstance(ast_entry, StartParseMethod):
            st_node = ast_entry.parent
            st_node = cast(StructParser | TypeDef, ast_entry.parent)
            st_type = st_node.kwargs["struct_type"]
        else:
            # TYPEDEF
            _, st_type = ast_entry.unpack_args()
        # 0.11 new shortcut API (with backport support)
        acc.append(self._pre_convert_node(ast_entry, st_type))
        for node in ast_entry.body:
            self.convert(node, acc)
        acc.append(self._post_convert_node(ast_entry, st_type))

    def _convert_struct_method(
        self,
        ast_entry: StructFieldMethod
        | StructInitMethod
        | StructPartDocMethod
        | StructPreValidateMethod
        | StartParseMethod,
        acc: list[str],
    ) -> None:
        """Handle struct method headers and bodies."""
        if ast_entry.kind == StartParseMethod.kind:
            ast_entry = cast(StartParseMethod, ast_entry)
            self._convert_node_with_struct_type(ast_entry, acc)
        else:
            acc.append(self._pre_convert_node(ast_entry))
            for node in ast_entry.body:
                self.convert(node, acc)
            acc.append(self._post_convert_node(ast_entry))

    def _convert_default(self, ast_entry: BaseAstNode, acc: list[str]) -> None:
        """Handle default node conversion."""
        acc.append(self._pre_convert_node(ast_entry))
        acc.append(self._post_convert_node(ast_entry))
