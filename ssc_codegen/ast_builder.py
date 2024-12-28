import json
import warnings
from pathlib import Path
from types import ModuleType
from typing import Type, Any

from .ast_ssc import (
    ModuleProgram,
    ModuleImports,
    Variable,
    StructParser,
    Docstring,
    StructFieldFunction,
    PartDocFunction,
    PreValidateFunction,
    ReturnExpression,
    NoReturnExpression,
    CallStructFunctionExpression,
    BaseExpression,
    TypeDef, DefaultStart, DefaultEnd,
)
from .consts import M_SPLIT_DOC, M_VALUE, M_KEY, M_ITEM, SIGNATURE_MAP
from .document import BaseDocument
from .document_utlis import convert_css_to_xpath, convert_xpath_to_css
from .schema import (
    BaseSchema,
    MISSING_FIELD,
    ItemSchema,
    DictSchema,
    ListSchema,
    FlatListSchema,
)
from .tokens import VariableType, StructType, TokenType


def _is_template_cls(cls: object) -> bool:
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
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
           and hasattr(obj, "__mro__")
           and BaseSchema in obj.__mro__
           and not _is_template_cls(obj)
    ]


def check_field_expr(field: BaseDocument):
    """validate correct type expression"""
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
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            continue
        msg = f"'{schema.__name__}' not required {f} attribute, remove"
        warnings.warn(msg, category=SyntaxWarning)
        setattr(schema, f, MISSING_FIELD)
    return schema


def _check_required_attributes(schema: Type[BaseSchema], *fields: str) -> None:
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            msg = f"'{schema.__name__}' required '{f}' attribute"
            raise SyntaxError(msg)


def check_schema(schema: Type[BaseSchema]) -> Type[BaseSchema]:
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
    tmp_stack = stack.copy()
    ret_type = tmp_stack[-1].ret_type
    first_expr = tmp_stack[0]
    if first_expr.kind == TokenType.EXPR_DEFAULT_START:
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
            case t if t in (VariableType.NULL, VariableType.ANY, VariableType.NESTED):
                pass
            case _:
                raise TypeError(f"Unknown variable return type: {ret_type.name} {ret_type.name}")

    expr_count = len(tmp_stack)
    for i, expr in enumerate(tmp_stack):
        expr.variable = Variable(num=i, count=expr_count, type=expr.accept_type)

    if ret_expr:
        var = Variable(num=expr_count - 1, count=expr_count, type=ret_type)
        if first_expr.kind == TokenType.EXPR_DEFAULT_START:
            # before TokenType.EXPR_DEFAULT_END push expr

            tmp_stack.insert(len(tmp_stack) - 1,
                             ReturnExpression(variable=var, ret_type=ret_type)
                             )
        else:
            tmp_stack.append(
                ReturnExpression(variable=var, ret_type=ret_type)
            )
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


def replace_enum_values(item):
    """
    Recursively replaces Enum values with their underlying values.
    Ignores strings and traverses dicts and lists.
    """
    if isinstance(item, VariableType):
        return SIGNATURE_MAP.get(item)
    elif isinstance(item, dict):
        return {key: replace_enum_values(value) for key, value in item.items()}
    elif isinstance(item, list):
        return [replace_enum_values(element) for element in item]
    else:
        return item


def build_fields_signature(raw_signature: Any) -> str:
    raw_signature = replace_enum_values(raw_signature)
    return json.dumps(raw_signature, indent=4)


def build_ast_struct(
        schema: Type[BaseSchema],
        *,
        docstring_class_top: bool = False,
        css_to_xpath: bool = False,
        xpath_to_css: bool = False,
) -> StructParser:
    schema = check_schema(schema)
    fields = schema.__get_mro_fields__()
    raw_signature = schema.__class_signature__()
    doc = ((schema.__doc__ or "")
           + "\n\n"
           + build_fields_signature(raw_signature)
           )
    start_parse_body: list[CallStructFunctionExpression] = []
    struct_parse_functions = []
    for k, f in fields.items():
        check_field_expr(f)
        if css_to_xpath:
            f = convert_css_to_xpath(f)
        elif xpath_to_css:
            f = convert_xpath_to_css(f)
        match k:
            case "__PRE_VALIDATE__":
                fn = PreValidateFunction(
                    name=k,  # noqa
                    body=_fill_stack_variables(f.stack, ret_expr=False),
                )
                start_parse_body.append(
                    CallStructFunctionExpression(
                        name=k, ret_type=VariableType.NULL, fn_ref=fn
                    )
                )
                struct_parse_functions.append(fn)
            case "__SPLIT_DOC__":
                _check_split_doc(f)
                fn = PartDocFunction(
                    name=k,  # noqa
                    body=_fill_stack_variables(f.stack),
                )
                start_parse_body.append(
                    CallStructFunctionExpression(
                        name=k, ret_type=VariableType.LIST_DOCUMENT, fn_ref=fn
                    )
                )
                struct_parse_functions.append(fn)
            case _:
                # insert default instruction API
                if f.stack[0].kind == TokenType.EXPR_DEFAULT:
                    tt_def_val = f.stack.pop(0)
                    f.stack.insert(0,
                                   DefaultStart(value=tt_def_val.value))
                    f.stack.append(
                        DefaultEnd(value=tt_def_val.value)
                    )

                fn = StructFieldFunction(
                    name=k,
                    body=_fill_stack_variables(f.stack),
                )
                if fn.default:
                    fn.default.parent = fn

                struct_parse_functions.append(fn)
                if f.stack_last_ret == VariableType.NESTED:
                    start_parse_body.append(
                        CallStructFunctionExpression(
                            name=k,
                            ret_type=f.stack_last_ret,
                            fn_ref=fn,
                            nested_cls_name_ref=f.stack[-1].schema,
                        )  # noqa
                    )
                else:
                    start_parse_body.append(
                        CallStructFunctionExpression(
                            name=k, ret_type=f.stack_last_ret, fn_ref=fn
                        )  # noqa
                    )
    # fixme: start_parse_body DEAD CODE?
    ast_struct_parser = StructParser(
        type=schema.__SCHEMA_TYPE__,
        name=schema.__name__,
        doc=Docstring(value=doc),
        docstring_class_top=docstring_class_top,
        body=struct_parse_functions,
    )

    return ast_struct_parser


def _check_split_doc(f):
    if f.stack_last_ret != VariableType.LIST_DOCUMENT:  # noqa
        msg = f"__SPLIT_DOC__ attribute should be returns LIST_DOCUMENT, not {f.stack_last_ret.name}"  # noqa
        raise SyntaxError(msg)


def build_ast_module(
        path: str | Path[str],
        *,
        docstring_class_top: bool = False,
        css_to_xpath: bool = False,
        xpath_to_css: bool = False,
) -> ModuleProgram:
    if css_to_xpath and xpath_to_css:
        raise AttributeError("Should be chosen one variant (css_to_xpath OR xpath_to_css)")
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
        body=[module_doc, ast_imports] + ast_types + ast_structs,
    )
    # links module
    for node in ast_program.body:
        if node.kind in (Docstring.kind, StructParser.kind, TypeDef.kind):
            node.parent = ast_program
    return ast_program
