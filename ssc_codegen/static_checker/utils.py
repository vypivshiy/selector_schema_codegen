from dataclasses import dataclass
from typing import Optional, Type, TYPE_CHECKING, Union

from ssc_codegen.schema import BaseSchema
from ssc_codegen.document import BaseDocument
from ssc_codegen.ast_ import BaseAstNode
from ssc_codegen.tokens import TokenType
from ssc_codegen.ast_build.metadata import SchemaMetadata, FieldMetadata


if TYPE_CHECKING:
    pass


def _prettify_expr_at(doc_or_node: Union[BaseDocument, BaseAstNode], index: int) -> str:
    """Convert an AST expression to a human-readable string representation.
    
    Args:
        doc_or_node: Either a BaseDocument (uses stack) or a BaseAstNode
        index: The index in the stack (if doc) or position to show
    
    Returns:
        A human-readable string representation of the expression
    """
    if isinstance(doc_or_node, BaseDocument):
        stack = doc_or_node.stack
    else:
        stack = doc_or_node.body if hasattr(doc_or_node, 'body') else []
    
    if index < 0 or index >= len(stack):
        return "<expr>"
    
    node = stack[index]
    return _format_node(node)


def _format_node(node: BaseAstNode) -> str:
    """Format a single AST node as a readable string."""
    kind = node.kind
    
    # Mapping from TokenType to method name and format string
    method_map = {
        TokenType.EXPR_DEFAULT: ("default", "{value}"),
        TokenType.EXPR_NESTED: ("sub_parser", "{name}"),
        TokenType.EXPR_CSS: ("css", "'{query}'"),
        TokenType.EXPR_XPATH: ("xpath", "'{query}'"),
        TokenType.EXPR_CSS_ALL: ("css_all", "'{query}'"),
        TokenType.EXPR_XPATH_ALL: ("xpath_all", "'{query}'"),
        TokenType.EXPR_ATTR: ("attr", "'{key}'"),
        TokenType.EXPR_ATTR_ALL: ("attr", "'{key}'"),
        TokenType.EXPR_TEXT: ("text", ""),
        TokenType.EXPR_TEXT_ALL: ("text", ""),
        TokenType.EXPR_RAW: ("raw", ""),
        TokenType.EXPR_RAW_ALL: ("raw", ""),
        TokenType.EXPR_REGEX: ("re", "'{pattern}'"),
        TokenType.EXPR_REGEX_ALL: ("re_all", "'{pattern}'"),
        TokenType.EXPR_REGEX_SUB: ("re_sub", "'{pattern}', '{ repl }'"),
        TokenType.EXPR_STRING_TRIM: ("trim", "'{chars}'"),
        TokenType.EXPR_STRING_LTRIM: ("ltrim", "'{chars}'"),
        TokenType.EXPR_STRING_RTRIM: ("rtrim", "'{chars}'"),
        TokenType.EXPR_STRING_REPLACE: ("repl", "'{old}', '{new}'"),
        TokenType.EXPR_STRING_FORMAT: ("fmt", "'{fmt}'"),
        TokenType.EXPR_STRING_SPLIT: ("split", "'{sep}'"),
        TokenType.EXPR_STRING_RM_PREFIX: ("rm_prefix", "'{prefix}'"),
        TokenType.EXPR_STRING_RM_SUFFIX: ("rm_suffix", "'{suffix}'"),
        TokenType.EXPR_STRING_RM_PREFIX_AND_SUFFIX: ("rm_prefix_suffix", "'{prefix}', '{suffix}'"),
        TokenType.EXPR_STRING_MAP_REPLACE: ("map_repl", "{mapping}"),
        TokenType.EXPR_STRING_UNESCAPE: ("unescape", ""),
        TokenType.EXPR_LIST_REGEX_SUB: ("re_sub", "'{pattern}', '{ repl }'"),
        TokenType.EXPR_LIST_STRING_TRIM: ("trim", "'{chars}'"),
        TokenType.EXPR_LIST_STRING_LTRIM: ("ltrim", "'{chars}'"),
        TokenType.EXPR_LIST_STRING_RTRIM: ("rtrim", "'{chars}'"),
        TokenType.EXPR_LIST_STRING_FORMAT: ("fmt", "'{fmt}'"),
        TokenType.EXPR_LIST_STRING_REPLACE: ("repl", "'{old}', '{new}'"),
        TokenType.EXPR_LIST_STRING_RM_PREFIX: ("rm_prefix", "'{prefix}'"),
        TokenType.EXPR_LIST_STRING_RM_SUFFIX: ("rm_suffix", "'{suffix}'"),
        TokenType.EXPR_LIST_STRING_RM_PREFIX_AND_SUFFIX: ("rm_prefix_suffix", "'{prefix}', '{suffix}'"),
        TokenType.EXPR_LIST_STRING_MAP_REPLACE: ("map_repl", "{mapping}"),
        TokenType.EXPR_LIST_STRING_UNESCAPE: ("unescape", ""),
        TokenType.EXPR_LIST_ANY_INDEX: ("index", "{idx}"),
        TokenType.EXPR_LIST_JOIN: ("join", "'{sep}'"),
        TokenType.EXPR_LIST_LEN: ("to_len", ""),
        TokenType.EXPR_LIST_UNIQUE: ("unique", ""),
        TokenType.IS_EQUAL: ("is_equal", "{value}"),
        TokenType.IS_CONTAINS: ("is_contains", "'{value}'"),
        TokenType.IS_CSS: ("is_css", "'{query}'"),
        TokenType.IS_XPATH: ("is_xpath", "'{query}'"),
        TokenType.IS_STRING_REGEX_MATCH: ("is_re", "'{pattern}'"),
        TokenType.ANY_LIST_STRING_REGEX_MATCH: ("any_is_re", "'{pattern}'"),
        TokenType.ALL_LIST_STRING_REGEX_MATCH: ("all_is_re", "'{pattern}'"),
        TokenType.TO_INT: ("to_int", ""),
        TokenType.TO_INT_LIST: ("to_int", ""),
        TokenType.TO_FLOAT: ("to_float", ""),
        TokenType.TO_FLOAT_LIST: ("to_float", ""),
        TokenType.TO_JSON: ("jsonify", ""),
        TokenType.TO_BOOL: ("to_bool", ""),
        TokenType.EXPR_FILTER: ("filter", "{cond}"),
        TokenType.EXPR_CSS_REMOVE: ("css_remove", "'{query}'"),
        TokenType.EXPR_XPATH_REMOVE: ("xpath_remove", "'{query}'"),
        TokenType.EXPR_MAP_ATTRS: ("attrs_map", ""),
        TokenType.EXPR_MAP_ATTRS_ALL: ("attrs_map", ""),
        TokenType.TO_JSON_DYNAMIC: ("jsonify_dynamic", "{struct}"),
    }
    
    if kind in method_map:
        method_name, fmt = method_map[kind]
        # Extract arguments from kwargs
        args = []
        for key in node.kwargs:
            val = node.kwargs[key]
            if isinstance(val, str) and len(val) > 20:
                val = val[:17] + "..."
            args.append(str(val))
        return method_name + "(" + ", ".join(args) + ")"
    
    # Fallback for unknown token types
    return f"<{kind.name}>"


@dataclass
class AnalysisError:
    message: str
    tip: str = ""
    field_name: Optional[str] = None
    lineno: Optional[int] = None
    filename: Optional[str] = None
    problem_method: Optional[str] = None


@dataclass
class SchemaCheckContext:
    schema: Type[BaseSchema]
    schema_meta: Optional[SchemaMetadata] = None
    filename: Optional[str] = None


@dataclass
class FieldCheckContext:
    schema: Type[BaseSchema]
    field_name: str
    document: BaseDocument
    field_meta: Optional[FieldMetadata] = None
    filename: Optional[str] = None
