from typing import Callable, Type
from ssc_codegen.schema import BaseSchema
from ssc_codegen.document import BaseDocument
from ssc_codegen.static_checker.base import (
    AnalyzeResult,
    FMT_MAPPING_METHODS,
    SELECT_LIKE_EXPR,
    SELECT_CSS_EXPR,
    SELECT_XPATH_EXPR,
)
from ssc_codegen.tokens import StructType, VariableType, TokenType
from cssselect import SelectorSyntaxError
from ssc_codegen.selector_utils import validate_css_query, validate_xpath_query

CB_SCHEMA = Callable[[Type[BaseSchema]], AnalyzeResult]
CB_DOCUMENT = Callable[[Type[BaseSchema], str, BaseDocument], AnalyzeResult]


def prettify_expr_stack(d: BaseDocument, end: int) -> str:
    s = "D()"
    for e in d.stack[:end]:
        method = FMT_MAPPING_METHODS.get(e.kind)
        kw = e.kwargs
        s += f".{method}(" + ",".join(f"{k}={v!r}" for k, v in kw.items()) + ")"
    s += "# "
    return s


# schema check segment
def analyze_schema_split_doc_field(sc: Type[BaseSchema]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ in (
        StructType.LIST,
        StructType.DICT,
        StructType.FLAT_LIST,
    ):
        fields = sc.__get_mro_fields__()
        if not fields.get("__SPLIT_DOC__"):
            return AnalyzeResult.error(
                f"{sc.__name__} missing __SPLIT_DOC__ field"
            )
    return AnalyzeResult.ok()


def analyze_schema_key_field(sc: Type[BaseSchema]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ == StructType.DICT:
        fields = sc.__get_mro_fields__()
        if not fields.get("__KEY__"):
            return AnalyzeResult.error(f"{sc.__name__} missing __KEY__ field")
    return AnalyzeResult.ok()


def analyze_schema_value_field(sc: Type[BaseSchema]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ == StructType.DICT:
        fields = sc.__get_mro_fields__()
        if not fields.get("__VALUE__"):
            return AnalyzeResult.error(f"{sc.__name__} missing __VALUE__ field")
    return AnalyzeResult.ok()


def analyze_schema_item_field(sc: Type[BaseSchema]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ == StructType.FLAT_LIST:
        fields = sc.__get_mro_fields__()
        if not fields.get("__ITEM__"):
            return AnalyzeResult.error(f"{sc.__name__} missing __ITEM__ field")
    return AnalyzeResult.ok()


# document check segment
def analyze_field_type_static(
    sc: Type[BaseSchema], name: str, document: BaseDocument
) -> AnalyzeResult:
    cursor = VariableType.DOCUMENT
    for i, expr in enumerate(document.stack):
        if expr.accept_type == cursor:
            cursor = expr.ret_type
            continue
        # skip check any-like types
        elif expr.accept_type in (
            VariableType.ANY,
            VariableType.LIST_ANY,
        ) or cursor in (VariableType.ANY, VariableType.LIST_ANY):
            cursor = expr.ret_type
            continue
        method_trace = prettify_expr_stack(document, i)
        msg = f"{sc.__name__}.{name} = {method_trace} Expected type {expr.accept_type.name}, got {cursor.name}"
        return AnalyzeResult.error(msg)
    return AnalyzeResult.ok()


def analyze_field_default_value(
    sc: Type[BaseSchema], name: str, document: BaseDocument
) -> AnalyzeResult:
    if document.stack[0].kind != TokenType.EXPR_DEFAULT:
        # skip
        return AnalyzeResult.ok()

    elif name in ("__PRE_VALIDATE__", "__SPLIT_DOC__"):
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} # not allowed used default expr"
        )

    (default_value,) = document.stack[0].unpack_args()
    ret_type = document.stack_last_ret
    if default_value is None:
        # TODO: later impl check optional types
        return AnalyzeResult.ok()

    if isinstance(default_value, str):
        default_ast_type = VariableType.STRING
    elif isinstance(default_value, bool):
        default_ast_type = VariableType.BOOL
    elif isinstance(default_value, int):
        default_ast_type = VariableType.INT
    elif isinstance(default_value, float):
        default_ast_type = VariableType.FLOAT
    else:
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} # Unsupported default value: `{default_value!r}`<{type(default_value).__name__}>"
        )

    if default_ast_type != ret_type:
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} # default({default_value!r}) wrong last return type expr"
            f" (expected type `{default_ast_type.name}` got `{ret_type.name}`)"
        )
    elif name == "__KEY__" and default_ast_type != VariableType.STRING:
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} __KEY__ should be a string, not {default_ast_type.name}"
        )
    return AnalyzeResult.ok()


def analyze_field_html_queries(
    sc: Type[BaseSchema], name: str, document: BaseDocument
) -> AnalyzeResult:
    # todo: collect all query errors?
    for i, expr in enumerate(document.stack):
        if expr.kind not in SELECT_LIKE_EXPR:
            continue
        query = expr.kwargs["query"]
        if expr.kind in SELECT_CSS_EXPR:
            try:
                validate_css_query(query)
            except SelectorSyntaxError:
                expr_stack = prettify_expr_stack(document, i)
                return AnalyzeResult.error(
                    f"{sc.__name__}.{name} = D().{expr_stack} # invalid CSS query `{query!r}`"
                )
        elif expr.kind in SELECT_XPATH_EXPR:
            try:
                validate_xpath_query(query)
            except SelectorSyntaxError:
                expr_stack = prettify_expr_stack(document, i)
                return AnalyzeResult.error(
                    f"{sc.__name__}.{name} = D().{expr_stack} # invalid XPATH query `{query!r}`"
                )
    return AnalyzeResult.ok()


def analyze_field_split_doc_ret_type(
    sc: Type[BaseSchema], name: str, document: BaseDocument
) -> AnalyzeResult:
    if name != "__SPLIT_DOC__":
        return AnalyzeResult.ok()
    if document.stack_last_ret != VariableType.LIST_DOCUMENT:
        expr_stack = prettify_expr_stack(document, document.stack_last_index)
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} = D().{expr_stack}  # Expected type `{VariableType.LIST_DOCUMENT.name}`, "
            f"got `{document.stack_last_ret.name}`"
        )
    return AnalyzeResult.ok()
