import json
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any, Type

from .ast_ssc import (
    BaseAstNode,
    BaseExpression,
    CallStructFunctionExpression,
    DefaultEnd,
    DefaultStart,
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
)
from .consts import M_ITEM, M_KEY, M_SPLIT_DOC, M_VALUE, SIGNATURE_MAP
from .document import BaseDocument
from .document_utlis import convert_css_to_xpath, convert_xpath_to_css
from .schema import (
    MISSING_FIELD,
    BaseSchema,
    DictSchema,
    FlatListSchema,
    ItemSchema,
    ListSchema,
)
from .tokens import StructType, TokenType, VariableType


def _is_template_cls(cls: object) -> bool:
    """return true if class is not BaseSchema instance. used for dynamically import config and generate ast"""
    return any(
        cls == base_cls
        for base_cls in (
            FlatListSchema,
            ItemSchema,
            DictSchema,
            ListSchema,
            BaseSchema,
        )
    )


def _extract_schemas(module: ModuleType) -> list[Type[BaseSchema]]:
    """extract Schema classes from a dynamically imported module.

    used for dynamically import and generate ast
    """
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
        and hasattr(obj, "__mro__")
        and BaseSchema in obj.__mro__
        and not _is_template_cls(obj)
    ]


def check_field_expr(field: BaseDocument) -> None:
    """validate correct type expressions pass.

    raise TypeError if not passed
    """
    var_cursor = VariableType.DOCUMENT
    for expr in field.stack:
        if var_cursor == expr.accept_type:
            var_cursor = expr.ret_type
            continue
        # this type always first (naive, used in DEFAULT and RETURN expr)
        elif expr.accept_type == VariableType.ANY:
            var_cursor = VariableType.DOCUMENT
            continue
        elif var_cursor == VariableType.NESTED:
            raise TypeError("sub_parser not allowed next instructions")

        msg = f"'{expr.kind.name}' expected type '{expr.accept_type.name}', got '{var_cursor.name}'"
        raise TypeError(msg)


def _patch_non_required_attributes(
    schema: Type[BaseSchema],
    *fields: M_SPLIT_DOC | M_ITEM | M_KEY | M_VALUE | str,
) -> Type[BaseSchema]:
    """remove non-required fields in schema instance"""
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            continue
        msg = f"'{schema.__name__}' not required {f} attribute, remove"
        warnings.warn(msg, category=SyntaxWarning)
        setattr(schema, f, MISSING_FIELD)
    return schema


def _check_required_attributes(schema: Type[BaseSchema], *fields: str) -> None:
    """helper function to check required attributes in schema. throw SyntaxError if not passed"""
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            msg = f"'{schema.__name__}' required '{f}' attribute"
            raise SyntaxError(msg)


def check_schema(schema: Type[BaseSchema]) -> Type[BaseSchema]:
    """validate schema instance minimal required magic fields and check type

    throw SyntaxError if not passed
    """
    match schema.__SCHEMA_TYPE__:
        case StructType.ITEM:
            schema = _patch_non_required_attributes(
                schema, "__SPLIT_DOC__", "__ITEM__", "__KEY__", "__VALUE__"
            )
        case StructType.LIST:
            schema = _patch_non_required_attributes(
                schema, "__KEY__", "__VALUE__", "__ITEM__"
            )
            _check_required_attributes(schema, "__SPLIT_DOC__")
        case StructType.DICT:
            schema = _patch_non_required_attributes(schema, "__ITEM__")
            _check_required_attributes(
                schema, "__SPLIT_DOC__", "__KEY__", "__VALUE__"
            )
        case StructType.FLAT_LIST:
            schema = _patch_non_required_attributes(
                schema, "__KEY__", "__VALUE__"
            )
            _check_required_attributes(schema, "__SPLIT_DOC__", "__ITEM__")
        case _:
            raise SyntaxError("Unknown schema type")
    return schema


def _fill_stack_variables(
    stack: list[BaseExpression], *, ret_expr: bool = True
) -> list[BaseExpression]:
    """insert variables to field stack of expressions"""
    tmp_stack = stack.copy()
    ret_type = tmp_stack[-1].ret_type
    first_expr = tmp_stack[0]
    if first_expr.kind == TokenType.EXPR_DEFAULT_START:
        # last token - TT.DefaultEnd
        ret_type = tmp_stack[-2].ret_type
        # used for convert return type
        if first_expr.value == None:  # type: ignore[attr-defined]
            match ret_type:
                case VariableType.STRING:
                    ret_type = VariableType.OPTIONAL_STRING
                case VariableType.LIST_STRING:
                    ret_type = VariableType.OPTIONAL_LIST_STRING
                case VariableType.INT:
                    ret_type = VariableType.OPTIONAL_INT
                case VariableType.LIST_INT:
                    ret_type = VariableType.OPTIONAL_LIST_INT
                case VariableType.FLOAT:
                    ret_type = VariableType.OPTIONAL_FLOAT
                case VariableType.LIST_FLOAT:
                    ret_type = VariableType.OPTIONAL_LIST_FLOAT
                # ignore cast
                case t if t in (
                    VariableType.NULL,
                    VariableType.ANY,
                    VariableType.NESTED,
                ):
                    pass
                case _:
                    raise TypeError(
                        f"Unknown variable return type: {ret_type.name} {ret_type.name}"
                    )

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


# TODO: better typing?
def replace_enum_values(item: Any) -> dict[str, Any] | list[Any] | str:
    """
    Recursively replaces Enum values with their underlying values.
    Ignores strings and traverses dicts and lists.
    """
    if isinstance(item, VariableType):
        if var_type := SIGNATURE_MAP.get(item):
            return var_type
        msg = f"missing Enum variable {item.name}, set ANY"
        warnings.warn(msg, category=FutureWarning)
        return "ANY"
    elif isinstance(item, dict):
        return {key: replace_enum_values(value) for key, value in item.items()}
    elif isinstance(item, list):
        return [replace_enum_values(element) for element in item]
    else:
        return item


def build_fields_signature(raw_signature: Any) -> str:
    """generate fields signature for docstring"""
    raw_signature = replace_enum_values(raw_signature)
    return json.dumps(raw_signature, indent=4)


def build_ast_struct(
    schema: Type[BaseSchema],
    *,
    docstring_class_top: bool = False,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
) -> StructParser:
    """generate AST from Schema instance"""
    schema = check_schema(schema)
    fields = schema.__get_mro_fields__()
    raw_signature = schema.__class_signature__()
    doc = (
        (schema.__doc__ or "") + "\n\n" + build_fields_signature(raw_signature)
    )
    start_parse_body: list[CallStructFunctionExpression] = []
    struct_parse_functions: list[BaseAstNode] = []
    for name, field in fields.items():
        check_field_expr(field)
        if css_to_xpath:
            field = convert_css_to_xpath(field)
        elif xpath_to_css:
            field = convert_xpath_to_css(field)
        match name:
            case "__PRE_VALIDATE__":
                extract_pre_validate(
                    field,
                    name,
                    start_parse_body,
                    struct_parse_functions,  # type: ignore[arg-type]
                )
            case "__SPLIT_DOC__":
                extract_split_doc(
                    field,
                    name,
                    start_parse_body,
                    struct_parse_functions,  # type: ignore[arg-type]
                )
            case _:
                # insert default instruction API
                extract_default_expr(field)
                fn = StructFieldFunction(
                    name=name,
                    body=_fill_stack_variables(field.stack),
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
    # fixme: start_parse_body DEAD CODE?
    ast_struct_parser = StructParser(
        type=schema.__SCHEMA_TYPE__,
        name=schema.__name__,
        doc=Docstring(value=doc),
        docstring_class_top=docstring_class_top,
        body=struct_parse_functions,  # type: ignore[arg-type]
    )

    return ast_struct_parser


def extract_default_expr(field: "BaseDocument") -> None:
    """convert DefaultValueWrapper node to DefaultStart and DefaultEnd Nodes"""
    if field.stack[0].kind == TokenType.EXPR_DEFAULT:
        tt_def_val = field.stack.pop(0)
        field.stack.insert(0, DefaultStart(value=tt_def_val.value))  # type: ignore
        field.stack.append(DefaultEnd(value=tt_def_val.value))  # type: ignore


def extract_split_doc(
    f: "BaseDocument",
    k: str,
    start_parse_body: list["BaseExpression"],
    struct_parse_functions: list["BaseAstNode"],
) -> None:
    """extract __SPLIT_DOC__ field and insert to ast"""
    _check_split_doc(f)

    fn = PartDocFunction(
        # literal type
        name=k,  # type: ignore[arg-type]
        body=_fill_stack_variables(f.stack),
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
        body=_fill_stack_variables(f.stack, ret_expr=False),
    )
    start_parse_body.append(
        CallStructFunctionExpression(
            name=k, ret_type=VariableType.NULL, fn_ref=fn
        )
    )
    struct_parse_functions.append(fn)


def _check_split_doc(f: "BaseDocument") -> None:
    """test __SPLIT_DOC__ body return type

    if ret_type != LIST_DOCUMENT - throw SyntaxError
    """
    if f.stack_last_ret != VariableType.LIST_DOCUMENT:  # noqa
        msg = f"__SPLIT_DOC__ attribute should be returns LIST_DOCUMENT, not {f.stack_last_ret.name}"  # noqa
        raise SyntaxError(msg)


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

        THIS FUNCTION COMPILE AND EXEC PYTHON CODE WOUT CHECKS
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
    ast_structs = [
        build_ast_struct(
            sc,
            docstring_class_top=docstring_class_top,
            xpath_to_css=xpath_to_css,
            css_to_xpath=css_to_xpath,
        )
        for sc in _extract_schemas(module)
    ]
    ast_types = [st.typedef for st in ast_structs if st.typedef]

    ast_program = ModuleProgram(
        body=[module_doc, ast_imports] + ast_types + ast_structs,  # type: ignore[operator]
    )
    # links module
    for node in ast_program.body:
        if node.kind in (Docstring.kind, StructParser.kind, TypeDef.kind):
            node.parent = ast_program  # type: ignore[attr-defined]
    return ast_program
