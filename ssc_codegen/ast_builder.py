import json
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any, Type

from . import Json
from .ast_build_utils import (
    check_schema_required_fields,
    extract_schemas_from_module,
    assert_ret_type_not_document,
    assert_split_doc_is_list_document,
    assert_schema_dict_key_is_string,
    unwrap_default_expr,
    assert_split_doc_ret_type_is_list_document,
    cast_ret_type_to_optional,
    assert_field_document_variable_types,
    extract_json_structs_from_module,
)
from .ast_ssc import (
    BaseAstNode,
    BaseExpression,
    CallStructFunctionExpression,
    Docstring,
    ModuleImports,
    ModuleProgram,
    NoReturnExpression,
    PartDocFunction,
    PreValidateFunction,
    ReturnExpression,
    StructFieldFunction,
    StructParser,
    TypeDef,
    Variable,
    JsonStruct,
    JsonStructField,
)
from .consts import SIGNATURE_MAP
from .document import BaseDocument
from .document_utlis import convert_css_to_xpath, convert_xpath_to_css
from .schema import (
    BaseSchema,
)
from .tokens import TokenType, VariableType


def fill_variables_stack_expr(
    stack: list[BaseExpression], *, ret_expr: bool = True
) -> list[BaseExpression]:
    """insert variable nodes to stack of expressions"""
    tmp_stack = stack.copy()
    ret_type = tmp_stack[-1].ret_type
    first_expr = tmp_stack[0]
    if first_expr.kind == TokenType.EXPR_DEFAULT_START:
        # last token - TT.DefaultEnd
        ret_type = tmp_stack[-2].ret_type
        # used for convert return type
        if first_expr.value is None:  # type: ignore[attr-defined]
            ret_type = cast_ret_type_to_optional(ret_type)
            # set DefaultEnd ret_type as DefaultStartToken
            tmp_stack[-1].ret_type = ret_type
        elif isinstance(first_expr.value, str):  # type: ignore[attr-defined]
            tmp_stack[-1].ret_type = VariableType.STRING
            if ret_type != VariableType.STRING:
                msg = f"wrong default type passed (should be a STRING or NULL, got {ret_type.name})"
                raise TypeError(msg)
        elif isinstance(first_expr.value, float):  # type: ignore[attr-defined]
            tmp_stack[-1].ret_type = VariableType.FLOAT
            if ret_type != VariableType.FLOAT:
                msg = f"wrong default type passed (should be a FLOAT or NULL, got {ret_type.name})"
                raise TypeError(msg)
        elif isinstance(first_expr.value, int):  # type: ignore[attr-defined]
            tmp_stack[-1].ret_type = VariableType.INT
            if ret_type != VariableType.INT:
                msg = f"wrong default type passed (should be a INT or NULL, got {ret_type.name})"
                raise TypeError(msg)
        else:
            msg = f"{first_expr.value!r}<{type(first_expr.value).__name__}> default operation not support this type"
            raise TypeError(msg)

    expr_count = len(tmp_stack)
    for i, expr in enumerate(tmp_stack):
        expr.variable = Variable(num=i, count=expr_count, type=expr.accept_type)

    if ret_expr:
        var = Variable(num=expr_count - 1, count=expr_count, type=ret_type)
        if first_expr.kind == TokenType.EXPR_DEFAULT_START:
            # before TokenType.EXPR_DEFAULT_END push expr
            tmp_stack.insert(
                len(tmp_stack) - 1,
                ReturnExpression(variable=var, ret_type=ret_type),
            )
        else:
            tmp_stack.append(ReturnExpression(variable=var, ret_type=ret_type))
    else:
        # actual used in __PRE_VALIDATE__, not need check default expr
        tmp_stack.append(
            NoReturnExpression(
                variable=Variable(
                    num=expr_count - 1, count=expr_count, type=VariableType.NULL
                )
            )
        )
    return tmp_stack


def field_signature_to_string(
    item: str | dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any] | str:
    """
    Recursively replaces Enum values with their underlying values.
    Ignores strings and traverses dicts and lists.
    """
    if isinstance(item, VariableType):
        if var_type := SIGNATURE_MAP.get(item):
            return var_type
        msg = f"missing Enum variable {item!r}, set ANY"
        warnings.warn(msg, category=FutureWarning)
        return "ANY"
    elif isinstance(item, dict):
        return {
            key: field_signature_to_string(value) for key, value in item.items()
        }
    elif isinstance(item, list):
        return [field_signature_to_string(element) for element in item]
    else:
        return item


def build_fields_signature(
    raw_signature: str | dict[str, Any] | list[Any],
) -> str:
    """generate fields signature for docstring"""
    raw_signature = field_signature_to_string(raw_signature)
    return json.dumps(raw_signature, indent=4)


def build_ast_struct(
    schema: Type[BaseSchema],
    *,
    docstring_class_top: bool = False,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
) -> StructParser:
    """generate AST from Schema instance"""
    schema = check_schema_required_fields(schema)
    fields = schema.__get_mro_fields__()
    raw_signature = schema.__class_signature__()
    doc = (
        (schema.__doc__ or "") + "\n\n" + build_fields_signature(raw_signature)
    )
    start_parse_body: list[CallStructFunctionExpression] = []
    struct_parse_functions: list[BaseAstNode] = []
    for name, field in fields.items():
        assert_field_document_variable_types(field)

        # not allowed empty stack exprs
        if len(field.stack) == 0:
            msg = f"{schema.__name__}.{name} has not exists expressions"
            raise SyntaxError(msg)

        if css_to_xpath:
            field = convert_css_to_xpath(field)
        elif xpath_to_css:
            field = convert_xpath_to_css(field)
        match name:
            case "__PRE_VALIDATE__":
                extract_pre_validate(
                    field,
                    name,
                    start_parse_body,  # type: ignore[arg-type]
                    struct_parse_functions,  # type: ignore[arg-type]
                )
            case "__SPLIT_DOC__":
                extract_split_doc(
                    field,
                    name,
                    start_parse_body,  # type: ignore[arg-type]
                    struct_parse_functions,  # type: ignore[arg-type]
                )
            case _:
                # insert default instruction API
                unwrap_default_expr(field)
                fn = StructFieldFunction(
                    name=name,
                    body=fill_variables_stack_expr(field.stack),
                )

                struct_parse_functions.append(fn)
                if field.stack_last_ret == VariableType.NESTED:
                    start_parse_body.append(
                        CallStructFunctionExpression(
                            name=name,
                            ret_type=field.stack_last_ret,
                            fn_ref=fn,
                            nested_cls_name_ref=field.stack[-1].schema,  # type: ignore
                        )  # noqa
                    )
                else:
                    start_parse_body.append(
                        CallStructFunctionExpression(
                            name=name, ret_type=field.stack_last_ret, fn_ref=fn
                        )  # noqa
                    )

        # after fill variables and types, check corner cases
        assert_schema_dict_key_is_string(field, name, schema)
        assert_split_doc_is_list_document(field, name, schema)
        assert_ret_type_not_document(field, name, schema)

    ast_struct_parser = StructParser(
        type=schema.__SCHEMA_TYPE__,
        name=schema.__name__,
        doc=Docstring(value=doc),
        docstring_class_top=docstring_class_top,
        body=struct_parse_functions,  # type: ignore[arg-type]
    )

    return ast_struct_parser


def extract_split_doc(
    f: "BaseDocument",
    k: str,
    start_parse_body: list["BaseExpression"],
    struct_parse_functions: list["BaseAstNode"],
) -> None:
    """extract __SPLIT_DOC__ field and insert to ast"""
    assert_split_doc_ret_type_is_list_document(f)

    fn = PartDocFunction(
        # literal type
        name=k,  # type: ignore[arg-type]
        body=fill_variables_stack_expr(f.stack),
    )
    start_parse_body.append(
        CallStructFunctionExpression(
            name=k, ret_type=VariableType.LIST_DOCUMENT, fn_ref=fn
        )
    )
    struct_parse_functions.append(fn)


def extract_pre_validate(
    f: "BaseDocument",
    k: str,
    start_parse_body: list["BaseExpression"],
    struct_parse_functions: list["BaseAstNode"],
) -> None:
    """extract __PRE_VALIDATE__ field and insert to ast"""
    fn = PreValidateFunction(
        # literal
        name=k,  # type: ignore[arg-type]
        body=fill_variables_stack_expr(f.stack, ret_expr=False),
    )
    start_parse_body.append(
        CallStructFunctionExpression(
            name=k, ret_type=VariableType.NULL, fn_ref=fn
        )
    )
    struct_parse_functions.append(fn)


def build_json_struct(json_struct: Type[Json]) -> JsonStruct:
    return JsonStruct(
        name=json_struct.__name__,
        body=[
            JsonStructField(name=k, value=v)
            for k, v in json_struct.tokenize().items()
        ],
    )


def build_ast_module(
    path: str | Path,
    *,
    docstring_class_top: bool = False,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
) -> ModuleProgram:
    """build ast from python sscgen config file

    WARNING!!!
        DO NOT PASS MODULES FROM UNKNOWN SOURCE/INPUT FOR SECURITY REASONS.

        THIS FUNCTION COMPILE AND EXEC PYTHON CODE in runtime WOUT CHECKS
    """
    if css_to_xpath and xpath_to_css:
        raise AttributeError(
            "Should be chosen one variant (css_to_xpath OR xpath_to_css)"
        )
    if isinstance(path, str):
        path = Path(path)
    module = ModuleType("_")
    code = Path(path.resolve()).read_text()
    exec(code, module.__dict__)
    module_doc = Docstring(value=module.__dict__.get("__doc__") or "")

    ast_imports = ModuleImports()
    ast_json_structs = [
        build_json_struct(sc) for sc in extract_json_structs_from_module(module)
    ]

    ast_structs = [
        build_ast_struct(
            sc,
            docstring_class_top=docstring_class_top,
            xpath_to_css=xpath_to_css,
            css_to_xpath=css_to_xpath,
        )
        for sc in extract_schemas_from_module(module)
    ]
    ast_types = [st.typedef for st in ast_structs if st.typedef]

    ast_program = ModuleProgram(
        body=[
            module_doc,
            ast_imports,
        ]  # type: ignore[operator]
        + ast_json_structs
        + ast_types
        + ast_structs,
    )
    # links module
    for node in ast_program.body:
        if node.kind in (
            Docstring.kind,
            StructParser.kind,
            TypeDef.kind,
            JsonStruct.kind,
        ):
            node.parent = ast_program  # type: ignore[attr-defined]
    return ast_program
