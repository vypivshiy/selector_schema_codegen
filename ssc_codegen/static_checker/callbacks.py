import warnings
from typing import Callable, Type, TYPE_CHECKING

from cssselect import SelectorSyntaxError
from typing_extensions import assert_never

from ssc_codegen.ast_ import ExprDefaultValueWrapper
from ssc_codegen.selector_utils import validate_css_query, validate_xpath_query
from ssc_codegen.static_checker.base import (
    AnalyzeResult,
    FMT_MAPPING_METHODS,
    SELECT_LIKE_EXPR,
    SELECT_CSS_EXPR,
    SELECT_XPATH_EXPR,
)
from ssc_codegen.tokens import StructType, VariableType, TokenType

if TYPE_CHECKING:
    from ssc_codegen.schema import BaseSchema
    from ssc_codegen.document import BaseDocument

CB_SCHEMA = Callable[[Type["BaseSchema"]], AnalyzeResult]
CB_DOCUMENT = Callable[[Type["BaseSchema"], str, "BaseDocument"], AnalyzeResult]


def prettify_expr_stack(d: "BaseDocument", end: int) -> str:
    s = "D()"
    for e in d.stack[:end]:
        method = FMT_MAPPING_METHODS.get(e.kind)
        kw = e.kwargs
        s += f".{method}(" + ",".join(f"{k}={v!r}" for k, v in kw.items()) + ")"
    return s


def analyze_dict_schema_fields(sc: Type["BaseSchema"]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ != StructType.DICT:
        return AnalyzeResult.ok()
    # not allowed fields
    fields = sc.__get_mro_fields__()
    skip_fields = {"__SPLIT_DOC__", "__PRE_VALIDATE__", "__KEY__", "__VALUE__"}
    non_required_fields = [
        name for name in fields.keys() if name not in skip_fields
    ]
    if non_required_fields:
        fields = f"`{', '.join(non_required_fields)}`"  # type: ignore[assignment]
        return AnalyzeResult.error(
            f"{sc.__name__} (DICT) unnecessary fields (remove required): {fields}"
        )
    return AnalyzeResult.ok()


def analyze_flat_list_schema_fields(sc: Type["BaseSchema"]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ != StructType.FLAT_LIST:
        return AnalyzeResult.ok()
    # not allowed fields
    fields = sc.__get_mro_fields__()
    skip_fields = {"__SPLIT_DOC__", "__PRE_VALIDATE__", "__ITEM__"}
    non_required_fields = [
        name for name in fields.keys() if name not in skip_fields
    ]
    if non_required_fields:
        fields = f"`{', '.join(non_required_fields)}`"  # type: ignore[assignment]
        return AnalyzeResult.error(
            f"{sc.__name__} (FLAT_LIST) unnecessary fields (remove required): {fields}"
        )
    return AnalyzeResult.ok()


# schema check segment
def analyze_schema_split_doc_field(sc: Type["BaseSchema"]) -> AnalyzeResult:
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


def analyze_schema_key_field(sc: Type["BaseSchema"]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ == StructType.DICT:
        fields = sc.__get_mro_fields__()
        if not fields.get("__KEY__"):
            return AnalyzeResult.error(f"{sc.__name__} missing __KEY__ field")
    return AnalyzeResult.ok()


def analyze_schema_value_field(sc: Type["BaseSchema"]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ == StructType.DICT:
        fields = sc.__get_mro_fields__()
        if not fields.get("__VALUE__"):
            return AnalyzeResult.error(f"{sc.__name__} missing __VALUE__ field")
    return AnalyzeResult.ok()


def analyze_schema_item_field(sc: Type["BaseSchema"]) -> AnalyzeResult:
    if sc.__SCHEMA_TYPE__ == StructType.FLAT_LIST:
        fields = sc.__get_mro_fields__()
        if not fields.get("__ITEM__"):
            return AnalyzeResult.error(f"{sc.__name__} missing __ITEM__ field")
    return AnalyzeResult.ok()


# document check segment
def analyze_field_type_static(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    cursor = VariableType.DOCUMENT
    for i, expr in enumerate(document.stack):
        if expr.accept_type == cursor:
            cursor = expr.ret_type
            continue
        elif expr.accept_type == VariableType.LIST_ANY:
            if cursor not in (
                VariableType.LIST_STRING,
                VariableType.LIST_INT,
                VariableType.LIST_FLOAT,
                VariableType.LIST_DOCUMENT,
            ):
                method_trace = prettify_expr_stack(document, i)
                msg = (
                    f"{sc.__name__}.{name} = {method_trace} Expected type(s) ({VariableType.LIST_STRING.name},"
                    f"{VariableType.LIST_INT.name}, {VariableType.LIST_FLOAT.name}, {VariableType.LIST_DOCUMENT.name}) "
                    f"got {cursor.name}"
                )
                return AnalyzeResult.error(msg)
            elif expr.exclude_types and cursor in expr.exclude_types:
                method_trace = prettify_expr_stack(document, i)
                exclude_types = ", ".join([i.name for i in expr.exclude_types])
                msg = (
                    f"{sc.__name__}.{name} = {method_trace} Not expect type(s) ({exclude_types}) "
                    f"got {cursor.name}"
                )
                return AnalyzeResult.error(msg)
            continue
        elif expr.accept_type == VariableType.ANY:
            if expr.exclude_types and cursor in expr.exclude_types:
                method_trace = prettify_expr_stack(document, i)
                exclude_types = ", ".join([i.name for i in expr.exclude_types])
                msg = (
                    f"{sc.__name__}.{name} = {method_trace} Not expect type(s) ({exclude_types}) "
                    f"got {cursor.name}"
                )
                return AnalyzeResult.error(msg)
            cursor = expr.ret_type
            continue

        elif cursor in (VariableType.ANY, VariableType.LIST_ANY):
            cursor = expr.ret_type
            continue

        method_trace = prettify_expr_stack(document, i)
        msg = f"{sc.__name__}.{name} = {method_trace} Expected type {expr.accept_type.name}, got {cursor.name}"
        return AnalyzeResult.error(msg)
    return AnalyzeResult.ok()


def analyze_field_default_value(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    default_expr_pos = [
        (i, expr)
        for i, expr in enumerate(document.stack)
        if expr.kind == TokenType.EXPR_DEFAULT
    ]
    if not default_expr_pos:
        return AnalyzeResult.ok()

    elif (index := default_expr_pos[0][0]) and index != 0:
        return AnalyzeResult.error(
            f"{sc.__name__}.{name}  # default expr should be a first, not {index} position"
        )

    elif name in ("__PRE_VALIDATE__", "__SPLIT_DOC__"):
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} # not allowed used default expr"
        )

    default_value, *_ = document.stack[0].unpack_args()
    ret_type = document.stack_last_ret
    # ExprDefaultValueWrapper node,
    # in ast-build stage will be unwrapped to ExprDefaultValueStart and ExprDefaultValueEnd nodes
    if default_value is None:
        if ret_type in (
            VariableType.DOCUMENT,
            VariableType.LIST_DOCUMENT,
            VariableType.BOOL,
        ):
            return AnalyzeResult.error(
                f"Default value cannot return type(s) ({VariableType.DOCUMENT.name}, "
                f"{VariableType.LIST_DOCUMENT.name}, {VariableType.BOOL.name})"
            )
        return AnalyzeResult.ok()

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
                f"{sc.__name__}.{name} # not supported pass values to list",
                category=SyntaxWarning,
            )
        default_ast_type = ret_type
    else:
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} # Unsupported default value: `{default_value!r}`<{type(default_value).__name__}>"
        )

    if isinstance(default_value, list) and default_ast_type not in (
        VariableType.LIST_STRING,
        VariableType.LIST_INT,
        VariableType.LIST_FLOAT,
    ):
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} # default({default_value!r}) wrong last list return type expr"
            f" (expected type(s) "
            f"`{(VariableType.LIST_STRING.name, VariableType.LIST_FLOAT.name, VariableType.LIST_INT.name)}` "
            f"got `{ret_type.name}`)"
        )
    elif default_ast_type != ret_type:
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
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
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
                    f"{sc.__name__}.{name} = {expr_stack} # invalid CSS query `{query!r}`"
                )
        elif expr.kind in SELECT_XPATH_EXPR:
            try:
                validate_xpath_query(query)
            except SelectorSyntaxError:
                expr_stack = prettify_expr_stack(document, i)
                return AnalyzeResult.error(
                    f"{sc.__name__}.{name} = {expr_stack} # invalid XPATH query `{query!r}`"
                )
    return AnalyzeResult.ok()


def analyze_field_split_doc_ret_type(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    if name != "__SPLIT_DOC__":
        return AnalyzeResult.ok()
    if document.stack_last_ret != VariableType.LIST_DOCUMENT:
        expr_stack = prettify_expr_stack(document, document.stack_last_index)
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} = {expr_stack}  # Expected type `{VariableType.LIST_DOCUMENT.name}`, "
            f"got `{document.stack_last_ret.name}`"
        )
    return AnalyzeResult.ok()


def analyze_field_key_ret_type(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    if name != "__KEY__":
        return AnalyzeResult.ok()
    if (
        document.stack
        and document.stack[0].kind == ExprDefaultValueWrapper.kind
    ):
        value = document.stack[0].kwargs["value"]
        if not isinstance(value, str):
            expr_stack = prettify_expr_stack(
                document, document.stack_last_index
            )
            return AnalyzeResult.error(
                f"{sc.__name__}.{name} = {expr_stack}  # default value should be a string, not `value<{type(value).__name__}>`"
            )
    if document.stack_last_ret != VariableType.STRING:
        expr_stack = prettify_expr_stack(document, document.stack_last_index)
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} = {expr_stack}  # Expected type `{VariableType.STRING.name}`, "
            f"got `{document.stack_last_ret.name}`"
        )
    return AnalyzeResult.ok()


def analyze_other_field_type(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    # skip
    if name in ("__KEY__", "__SPLIT_DOC__", "__PRE_VALIDATE__"):
        return AnalyzeResult.ok()
    if document.stack_last_ret in (
        VariableType.LIST_DOCUMENT,
        VariableType.DOCUMENT,
    ):
        expr_stack = prettify_expr_stack(document, document.stack_last_index)
        return AnalyzeResult.error(
            f"{sc.__name__}.{name} = {expr_stack}  # Not allowed type(s) "
            f"`{VariableType.LIST_DOCUMENT.name}, {VariableType.DOCUMENT.name} {VariableType.BOOL.name}`"
        )
    return AnalyzeResult.ok()


def analyze_regex_expr(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    re_exprs = [i for i in document.stack if i.kind in TokenType.regex_tokens()]
    if not re_exprs:
        return AnalyzeResult.ok()
    from ssc_codegen.document_utlis import analyze_re_expression

    for re_expr in re_exprs:
        match re_expr.kind:
            case TokenType.EXPR_REGEX | TokenType.EXPR_REGEX_ALL:
                result = analyze_re_expression(
                    re_expr.kwargs["pattern"], max_groups=1
                )
                if not result:
                    expr_stack = prettify_expr_stack(
                        document, document.stack_last_index
                    )
                    return AnalyzeResult.error(
                        f"{sc.__name__}.{name} = {expr_stack}  # {result.msg}"
                    )
            case (
                TokenType.EXPR_REGEX_SUB
                | TokenType.EXPR_LIST_REGEX_SUB
                | TokenType.IS_STRING_REGEX_MATCH
            ):
                result = analyze_re_expression(
                    re_expr.kwargs["pattern"], allow_empty_groups=True
                )
                if not result:
                    expr_stack = prettify_expr_stack(
                        document, document.stack_last_index
                    )
                    return AnalyzeResult.error(
                        f"{sc.__name__}.{name} = {expr_stack}  # {result.msg}"
                    )
            case _:
                assert_never(re_expr.kind)  # type: ignore
    return AnalyzeResult.ok()


def analyze_jsonify_expr(
    sc: Type["BaseSchema"], name: str, document: "BaseDocument"
) -> AnalyzeResult:
    have_json_expr = any(i.kind == TokenType.TO_JSON for i in document.stack)
    if not have_json_expr:
        return AnalyzeResult.ok()
    have_default_expr = any(
        expr.kind == TokenType.EXPR_DEFAULT for expr in document.stack
    )
    if not have_default_expr:
        return AnalyzeResult.ok()
    expr_stack = prettify_expr_stack(document, document.stack_last_index)
    return AnalyzeResult.error(
        f"{sc.__name__}.{name} = {expr_stack} # jsonify not allowed default expr"
    )
