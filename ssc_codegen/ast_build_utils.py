import warnings
from types import ModuleType
from typing import Type

from ssc_codegen import FlatListSchema, ItemSchema, DictSchema, ListSchema, Json
from ssc_codegen.ast_ssc import DefaultStart, DefaultEnd
from ssc_codegen.consts import M_SPLIT_DOC, M_ITEM, M_KEY, M_VALUE
from ssc_codegen.document import BaseDocument
from ssc_codegen.schema import BaseSchema, MISSING_FIELD
from ssc_codegen.tokens import StructType, VariableType, TokenType


def _remove_non_required_attributes(
    schema: Type[BaseSchema],
    *fields: M_SPLIT_DOC | M_ITEM | M_KEY | M_VALUE | str,
) -> Type[BaseSchema]:
    """remove non-required fields in schema instance"""
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            continue
        msg = f"'{schema.__name__}.{f}' not required attribute, remove"
        warnings.warn(msg, category=SyntaxWarning)
        setattr(schema, f, MISSING_FIELD)
    return schema


def _check_required_attributes(schema: Type[BaseSchema], *fields: str) -> None:
    """helper function to check required attributes in schema. throw SyntaxError if not passed"""
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            msg = f"'{schema.__name__}' required '{f}' attribute"
            raise SyntaxError(msg)


def check_schema_required_fields(schema: Type[BaseSchema]) -> Type[BaseSchema]:
    """validate schema instance minimal required magic fields and check type

    throw SyntaxError if not passed
    """
    match schema.__SCHEMA_TYPE__:
        case StructType.ITEM:
            schema = _remove_non_required_attributes(
                schema, "__SPLIT_DOC__", "__ITEM__", "__KEY__", "__VALUE__"
            )
        case StructType.LIST:
            schema = _remove_non_required_attributes(
                schema, "__KEY__", "__VALUE__", "__ITEM__"
            )
            _check_required_attributes(schema, "__SPLIT_DOC__")
        case StructType.DICT:
            schema = _remove_non_required_attributes(schema, "__ITEM__")
            _check_required_attributes(
                schema, "__SPLIT_DOC__", "__KEY__", "__VALUE__"
            )
            # delete non required fields
            not_required_fields: list[str] = []
            for k, v in schema.__get_mro_fields__().items():
                if k not in {"__SPLIT_DOC__", "__KEY__", "__VALUE__"}:
                    msg = f"{schema.__name__}.{k} not required, remove"
                    warnings.warn(msg, category=SyntaxWarning)
                    not_required_fields.append(k)
            schema = _remove_non_required_attributes(
                schema, *not_required_fields
            )
        case StructType.FLAT_LIST:
            schema = _remove_non_required_attributes(
                schema, "__KEY__", "__VALUE__"
            )
            _check_required_attributes(schema, "__SPLIT_DOC__", "__ITEM__")

            not_required_fields: list[str] = []  # type: ignore
            for k, v in schema.__get_mro_fields__().items():
                if k not in {"__SPLIT_DOC__", "__ITEM__"}:
                    msg = f"{schema.__name__}.{k} not required, remove"
                    warnings.warn(msg, category=SyntaxWarning)
                    not_required_fields.append(k)
            schema = _remove_non_required_attributes(
                schema, *not_required_fields
            )
        case _:
            msg = f"{schema.__name__}: Unknown schema type"
            raise SyntaxError(msg)
    return schema


def is_template_schema_cls(cls: object) -> bool:
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


def extract_schemas_from_module(module: ModuleType) -> list[Type[BaseSchema]]:
    """extract Schema classes from a dynamically imported module.

    used for dynamically import and generate ast
    """
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
        and hasattr(obj, "__mro__")
        and BaseSchema in obj.__mro__
        and not is_template_schema_cls(obj)
    ]


def extract_json_structs_from_module(module: ModuleType) -> list[Type[Json]]:
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
        and hasattr(obj, "__mro__")
        and Json in obj.__mro__
        and obj != Json  # base class drop
    ]


def assert_ret_type_not_document(
    field: "BaseDocument", name: str, schema: Type[BaseSchema]
) -> None:
    if field.stack_last_ret == VariableType.DOCUMENT:
        msg = f"{schema.__name__}.{name} cannot return type {VariableType.DOCUMENT.name}"
        raise TypeError(msg)


def assert_split_doc_is_list_document(
    field: "BaseDocument", name: str, schema: Type[BaseSchema]
) -> None:
    """check return type is LIST_DOCUMENT else throw TypeError"""
    if (
        name == "__SPLIT_DOC__"
        and field.stack_last_ret != VariableType.LIST_DOCUMENT
    ):
        msg = (
            f"{schema.__name__}.{name} should be returns {VariableType.LIST_DOCUMENT.name}, "
            f"not {field.stack_last_ret.name}"
        )
        raise TypeError(msg)


def assert_schema_dict_key_is_string(
    field: "BaseDocument", name: str, schema: Type[BaseSchema]
) -> None:
    if schema.__SCHEMA_TYPE__ != StructType.DICT:
        return
    # corner case: default value is string, last return value - string
    if (
        field.stack[0].kind == TokenType.EXPR_DEFAULT_START
        and isinstance(field.stack[0].value, str)  # type: ignore
        and field.stack[-2].ret_type == VariableType.STRING
    ):
        return

    elif name == "__KEY__" and field.stack_last_ret != VariableType.STRING:  # type: ignore
        # case: default value as string
        msg = f"{schema.__name__}.__KEY__ should be STRING, not {field.stack_last_ret.name}"  # type: ignore
        raise TypeError(msg)


def unwrap_default_expr(field: "BaseDocument") -> None:
    """convert DefaultValueWrapper node to DefaultStart and DefaultEnd Nodes"""
    if field.stack and field.stack[0].kind == TokenType.EXPR_DEFAULT:
        tt_def_val = field.stack.pop(0)
        field.stack.insert(0, DefaultStart(value=tt_def_val.value))  # type: ignore
        field.stack.append(DefaultEnd(value=tt_def_val.value))  # type: ignore


def assert_split_doc_ret_type_is_list_document(f: "BaseDocument") -> None:
    """test __SPLIT_DOC__ body return type

    if ret_type != LIST_DOCUMENT - throw SyntaxError
    """
    if f.stack_last_ret != VariableType.LIST_DOCUMENT:  # noqa
        msg = f"__SPLIT_DOC__ attribute should be returns LIST_DOCUMENT, not {f.stack_last_ret.name}"  # noqa
        raise SyntaxError(msg)


def cast_ret_type_to_optional(ret_type: VariableType) -> VariableType:
    """cast type to OPTIONAL is default value is None"""
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
    return ret_type


def assert_field_document_variable_types(field: BaseDocument) -> None:
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
        # end token operation, ignore
        elif expr.kind == TokenType.EXPR_DEFAULT_END:
            continue
        elif var_cursor == VariableType.NESTED:
            raise TypeError("sub_parser not allowed next instructions")

        msg = f"'{expr.kind.name}' expected type '{expr.accept_type.name}', got '{var_cursor.name}'"
        raise TypeError(msg)
