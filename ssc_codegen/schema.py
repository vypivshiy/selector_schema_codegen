from typing import TYPE_CHECKING, Any, Type, TypeAlias, Union, cast
from typing_extensions import assert_never
import logging


from .json_struct import json_struct_to_signature
from .tokens import StructType, TokenType, VariableType

if TYPE_CHECKING:
    from .document import BaseDocument, ClassVarDocument
    from .json_struct import Json


class MISSING_FIELD(object):  # noqa
    pass


LOGGER = logging.getLogger("ssc-gen")
_T_OPT_FIELD: TypeAlias = Union["BaseDocument", Type[MISSING_FIELD]]


RESERVED_METHODS = {
    "__PRE_VALIDATE__",
    "__SPLIT_DOC__",
    "__KEY__",
    "__VALUE__",
    "__ITEM__",
    "__START_PARSE__",
}

SIGNATURE_MAP = {
    VariableType.STRING: "String",
    VariableType.LIST_STRING: "Array<String>",
    VariableType.OPTIONAL_STRING: "String | null",
    VariableType.OPTIONAL_LIST_STRING: "Array<String> | null",
    VariableType.NULL: "null",
    VariableType.INT: "Int",
    VariableType.OPTIONAL_INT: "Int | null",
    VariableType.LIST_INT: "Array<Int>",
    VariableType.OPTIONAL_LIST_INT: "Array<Int> | null",
    VariableType.FLOAT: "Float",
    VariableType.OPTIONAL_FLOAT: "Float | null",
    VariableType.OPTIONAL_LIST_FLOAT: "Array<Float> | null",
    VariableType.LIST_FLOAT: "Array<Float>",
    VariableType.ANY: "Any",
    VariableType.BOOL: "Bool",
}


class SchemaMeta(type):
    @staticmethod
    def __fill_schema_mro(cls: Type["BaseSchema"]) -> None:
        """magic method API for helps extract parent classes.

        used in inheritance for avoid duplicate code
        """
        mro_schemas = list(
            (
                i
                for i in cls.__mro__
                # if issubclass(i, BaseSchema)
                if getattr(i, "__SCHEMA_TYPE__", False)
                and i.__SCHEMA_TYPE__ == cls.__SCHEMA_TYPE__  # type: ignore[attr-defined]
            )
        )
        mro_schemas.reverse()
        cls.__SSC_MRO__ = tuple(mro_schemas)

    @staticmethod
    def __fill_mro_fields(cls: Type["BaseSchema"]) -> None:
        # use after fill __SSC_MRO__
        assert cls.__SSC_MRO__ is not None, "required extract schemas mro first"

        mro_fields: dict[str, "BaseDocument"] = {}
        for klass in cls.__SSC_MRO__:
            if (
                klass.__SCHEMA_TYPE__
                and klass.__SCHEMA_TYPE__ != NotImplemented
            ):
                tmp_attrs = vars(klass).copy()
                for key, value in tmp_attrs.items():
                    if value == MISSING_FIELD or callable(value):
                        continue
                    elif (
                        not key.startswith("__")
                        and not key.endswith("__")
                        and getattr(value, "stack_last_ret", False)
                        and not getattr(value, "__IS_LITERAL_DOC__", False)
                    ):
                        mro_fields[key] = value
                    elif (
                        key in cls.__ALLOWED_MAGIC__
                        and getattr(value, "stack_last_ret", False)
                        and not getattr(value, "__IS_LITERAL_DOC__", False)
                    ):
                        mro_fields[key] = value
        cls.__SSC_MRO_FIELDS__ = mro_fields

    @staticmethod
    def __fill_literals(cls: Type["BaseSchema"], cls_name: str) -> None:
        assert cls.__SSC_MRO__ is not None, "required extract schemas mro first"

        mro_classvars: dict[str, "ClassVarDocument"] = {}
        for klass in cls.__SSC_MRO__:
            if (
                klass.__SCHEMA_TYPE__
                and klass.__SCHEMA_TYPE__ != NotImplemented
            ):
                tmp_attrs = vars(klass).copy()
                for key, value in tmp_attrs.items():
                    if value == MISSING_FIELD or callable(value):
                        continue
                    elif getattr(value, "__IS_LITERAL_DOC__", False):
                        value = cast("ClassVarDocument", value)
                        value.field_name = key
                        value.struct_name = cls_name
                        mro_classvars[key] = value

        cls.__SSC_MRO_CLASSVARS__ = mro_classvars

    def __new__(mcs, name, bases, namespace, **kwargs):  # type: ignore
        cls = super().__new__(mcs, name, bases, namespace)
        cls = cast(Type["BaseSchema"], cls)

        # base classes, skip
        # bases check if used (BaseSchema,) only
        if cls.__SCHEMA_TYPE__ == NotImplemented or (
            len(bases) >= 1 and bases[0].__SCHEMA_TYPE__ == NotImplemented
        ):
            return cls
        mcs.__fill_schema_mro(cls)
        mcs.__fill_mro_fields(cls)
        mcs.__fill_literals(cls, name)

        return cls


class BaseSchema(metaclass=SchemaMeta):
    __SCHEMA_TYPE__: StructType = NotImplemented

    __SIGNATURE__: dict | list | None = NotImplemented
    """manually write signature for final docstring"""

    __PRE_VALIDATE__: _T_OPT_FIELD = MISSING_FIELD
    """Optional method for pre validation input document
    
    if checks not passed - throw error
    """

    # DICT, LIST, FLAT_LIST HOOK
    __SPLIT_DOC__: _T_OPT_FIELD = MISSING_FIELD
    """ListSchema, DictSchema, FlatListSchema method for write split document to parts of elements
    """

    # FLAT LIST HOOK
    __ITEM__: _T_OPT_FIELD = MISSING_FIELD
    """FlatListSchema item method for parse items for array"""

    # DICT HOOKS
    __KEY__: _T_OPT_FIELD = MISSING_FIELD
    """DictSchema method for parse key """

    __VALUE__: _T_OPT_FIELD = MISSING_FIELD
    """DictSchema method for parse value"""

    __ALLOWED_MAGIC__ = RESERVED_METHODS

    # cache nested/json schemas (N().sub_parser(), D().jsonify())
    __NESTED_SCHEMAS__: dict[str, Type["BaseSchema"]] = {}
    __JSON_SCHEMAS__: dict[str, Type["Json"]] = {}

    # cached DSL attributes (auto filled by SchemaMeta)
    __SSC_MRO_FIELDS__: dict[str, "BaseDocument"]
    __SSC_MRO__: tuple[Type["BaseSchema"], ...]
    # old name - literals
    __SSC_MRO_CLASSVARS__: dict[str, "ClassVarDocument"]

    # retained for API backward compatibility
    @classmethod
    def __class_signature__(cls) -> dict[str, Any] | list[str | Any] | None:
        """raw API interface for represent parsed items signature

        used for auto provide docstring API
        """
        if cls.__SIGNATURE__ != NotImplemented:
            return cls.__SIGNATURE__
        return cls._fill_signature_auto()

    @classmethod
    def __field_to_signature(
        cls,
        field: "BaseDocument",
    ) -> Any:
        """convert field to signature item"""
        if field == MISSING_FIELD:
            LOGGER.warning("catch empty field, skip")
            return
        elif field.stack_last_ret in (
            VariableType.DOCUMENT,
            VariableType.LIST_DOCUMENT,
        ):
            LOGGER.warning(
                "field with type `%s` not allowed cast to signature, skip",
                field.stack_last_ret.name,
            )
            return

        if field.stack_last_ret == VariableType.NESTED:
            name = [e for e in field.stack if e.kind == TokenType.EXPR_NESTED][
                0
            ].kwargs["schema_name"]
            return cls.__NESTED_SCHEMAS__[name].__class_signature__()
        elif field.stack_last_ret == VariableType.JSON:
            name = [e for e in field.stack if e.kind == TokenType.TO_JSON][
                0
            ].kwargs["json_struct_name"]
            json_cls = cls.__JSON_SCHEMAS__[name]
            return json_struct_to_signature(json_cls)
        elif getattr(field, "__IS_LITERAL_DOC__", False):
            # if classvar returns from parse entrypoint (pre inited struct_name and field_name)
            if getattr(field, "struct_name", False) and getattr(
                field, "field_name", False
            ):
                return SIGNATURE_MAP[field.stack_last_ret]
            # else ignore classvar signature
            return
        else:
            return SIGNATURE_MAP[field.stack_last_ret]

    @classmethod
    def _fill_signature_auto(cls) -> list | dict:
        match cls.__SCHEMA_TYPE__:
            case StructType.ITEM:
                signature = {}
                for name, field in cls.__SSC_MRO_CLASSVARS__.items():
                    if field._parse_returns:
                        field_sig = cls.__field_to_signature(field)
                        signature[name] = (
                            field_sig
                            + f" (classvar {field.struct_name}.{field.field_name})"
                        )
                for name, field in cls.__SSC_MRO_FIELDS__.items():
                    if name.startswith("__") and name.endswith("__"):
                        continue
                    field_sig = cls.__field_to_signature(field)
                    signature[name] = field_sig
            case StructType.LIST:
                signature = {}
                for name, field in cls.__SSC_MRO_CLASSVARS__.items():
                    if field._parse_returns:
                        field_sig = cls.__field_to_signature(field)
                        signature[name] = field_sig + " (classvar)"
                for name, field in cls.__SSC_MRO_FIELDS__.items():
                    if name.startswith("__") and name.endswith("__"):
                        continue
                    field_sig = cls.__field_to_signature(field)
                    signature[name] = field_sig
                signature = [signature, "..."]
            case StructType.DICT:
                signature = {}
                value = cls.__field_to_signature(cls.__VALUE__)
                signature["<k>"] = value
                signature["<k_N>"] = "..."
            case StructType.FLAT_LIST:
                signature = []
                item = cls.__field_to_signature(cls.__ITEM__)
                signature.append(item)
                signature.append("...")
            case StructType.ACC_LIST:
                signature = ["String", "..."]
            case _:
                assert_never(cls.__SCHEMA_TYPE__)
        return signature

    @classmethod
    def __schema_mro__(cls) -> tuple[Type["BaseSchema"], ...]:
        """magic method API for helps extract parent classes.

        used in inheritance for avoid duplicate code
        """
        return cls.__SSC_MRO__

    @classmethod
    def __get_mro_fields__(cls) -> dict[str, "BaseDocument"]:
        """extract all fields (parent classes included)"""
        return cls.__SSC_MRO_FIELDS__

    @classmethod
    def __get_mro_literals__(cls) -> dict[str, "ClassVarDocument"]:
        return cls.__SSC_MRO_CLASSVARS__


# build-in structures
class ItemSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.ITEM


class ConfigLiteralsSchema(BaseSchema):
    # ItemSchema auto converted to it, if parse fields not defined
    __SCHEMA_TYPE__ = StructType.CONFIG_CLASSVARS


class ListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.LIST


class DictSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.DICT


class FlatListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.FLAT_LIST


class AccUniqueListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.ACC_LIST
