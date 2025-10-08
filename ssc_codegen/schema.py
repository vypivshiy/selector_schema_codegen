from typing import TYPE_CHECKING, Any, Type, TypeAlias, Union


from .json_struct import json_struct_to_signature
from .tokens import StructType, TokenType, VariableType

if TYPE_CHECKING:
    from .document import BaseDocument, ClassVarDocument
    from .json_struct import Json


class MISSING_FIELD(object):  # noqa
    pass


EXCLUDE_KEY = object()
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


class BaseSchema:
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

    __EXCLUDE_SIGNATURE__: _T_OPT_FIELD = MISSING_FIELD

    __ALLOWED_MAGIC__ = RESERVED_METHODS

    __NESTED_SCHEMAS__: dict[str, Type["BaseSchema"]] = {}
    __JSON_SCHEMAS__: dict[str, Type["Json"]] = {}

    @classmethod
    def __class_signature__(cls) -> dict[str, Any] | list[str | Any]:
        """raw API interface for represent parsed items signature

        used for auto provide docstring API
        """
        if cls.__SIGNATURE__ != NotImplemented:
            return cls.__SIGNATURE__

        match cls.__SCHEMA_TYPE__:
            case StructType.FLAT_LIST:
                signature = cls._get_flat_list_signature()
            case StructType.DICT:
                signature = cls._get_dict_signature()
            case StructType.LIST:
                signature = cls._get_list_signature()
            case StructType.ITEM:
                signature = cls._get_item_signature()

            case StructType.ACC_LIST:
                signature = [VariableType.STRING, "..."]
            case _:
                # code unreached
                raise TypeError("Unknown schema type")
        return signature

    @classmethod
    def _get_list_signature(cls):  # type: ignore
        signature = {}
        for k, v in cls.__get_mro_fields__().items():
            if k in cls.__ALLOWED_MAGIC__:
                continue
            cls._field_to_signature(k, signature, v)
        return [signature, "..."]

    @classmethod
    def _field_to_signature(
        cls, key: str, signature: dict[str, Any], field: "BaseDocument"
    ) -> None:
        """convert field to signature item"""
        if field.stack_last_ret == VariableType.NESTED:
            name = [e for e in field.stack if e.kind == TokenType.EXPR_NESTED][
                0
            ].kwargs["schema_name"]
            signature[key] = cls.__NESTED_SCHEMAS__[name].__class_signature__()
        elif field.stack_last_ret == VariableType.JSON:
            name = [e for e in field.stack if e.kind == TokenType.TO_JSON][
                0
            ].kwargs["json_struct_name"]
            json_cls = cls.__JSON_SCHEMAS__[name]
            signature[key] = json_struct_to_signature(json_cls)
        elif getattr(field, "__IS_LITERAL_DOC__", False):
            # if classvar returns from parse entrypoint (pre inited struct_name and field_name)
            if getattr(field, "struct_name", False) and getattr(
                field, "field_name", False
            ):
                signature[key] = SIGNATURE_MAP[field.stack_last_ret]
            # else ignore classvar signature
            return
        else:
            signature[key] = SIGNATURE_MAP[field.stack_last_ret]

    @classmethod
    def _get_item_signature(cls):  # type: ignore
        signature = {}
        for k, v in cls.__get_mro_fields__().items():
            if k in cls.__ALLOWED_MAGIC__:
                continue
            cls._field_to_signature(k, signature, v)
        return signature

    @classmethod
    def _get_dict_signature(cls):  # type: ignore
        signature = {}
        # _field_k always string
        field_v = cls.__VALUE__
        cls._field_to_signature("<K>", signature, field_v)
        signature["<KN>"] = "..."
        return signature

    @classmethod
    def _get_flat_list_signature(cls):  # type: ignore
        signature = []
        field = cls.__ITEM__
        if field.stack_last_ret == VariableType.NESTED:
            name = [e for e in field.stack if e.kind == TokenType.EXPR_NESTED][
                0
            ].kwargs["schema_name"]
            nested_class = cls.__NESTED_SCHEMAS__[name].__class_signature__()
            signature.append(nested_class)
        elif field.stack_last_ret == VariableType.JSON:
            signature["__item__"] = json_struct_to_signature(
                field.stack[-1].value
            )
        else:
            signature.append(field.stack_last_ret)
        signature.append("...")
        return signature

    @classmethod
    def __schema_mro__(cls) -> tuple[Type["BaseSchema"], ...]:
        """magic method API for helps extract parent classes.

        used in inheritance for avoid duplicate code
        """
        return tuple(
            (
                i
                for i in cls.__mro__
                if issubclass(i, BaseSchema)
                and i.__SCHEMA_TYPE__ == cls.__SCHEMA_TYPE__
            )
        )

    @classmethod
    def __get_mro_annotations__(cls) -> dict[str, Type]:
        """extract all annotations (parent classes included)"""
        cls__annotations__: dict[str, Type] = {}
        fields = cls.__get_mro_fields__()
        for kls in cls.__schema_mro__():
            if kls.__annotations__:
                for k, v in kls.__annotations__.items():
                    if (
                        not cls__annotations__.get(k)
                        and fields.get(k) != MISSING_FIELD
                    ):
                        cls__annotations__[k] = v
                    elif (
                        k in cls.__ALLOWED_MAGIC__
                        and fields.get(k) != MISSING_FIELD
                        and not cls__annotations__.get(k)
                    ):
                        cls__annotations__[k] = v
        return cls__annotations__

    @classmethod
    def _get_ssc_deep_documents(cls) -> dict[str, Union["BaseDocument", str]]:
        """extract all fields (parent classes included)"""
        cls__dict__: dict[str, "BaseDocument"] = {}
        for klass in cls.__schema_mro__():
            # copy __dict__ to avoid runtime err:
            # RuntimeError: dictionary changed size during iteration
            tmp_attrs = vars(klass).copy()
            for k, v in tmp_attrs.items():
                # if not set docstring - get from parent class
                if (
                    k == "__doc__"
                    and not cls.__doc__
                    and not cls__dict__.get("__doc__")
                ):
                    cls__dict__[k] = v
                elif cls__dict__.get(k):
                    continue
                cls__dict__[k] = v
        return cls__dict__

    @classmethod
    def __get_mro_fields__(cls) -> dict[str, "BaseDocument"]:
        """extract all fields (parent classes included)"""
        cls__dict__ = cls._get_ssc_deep_documents()
        fields = {}
        for k, v in cls__dict__.items():
            # handle magic fields `__SPLIT_DOC__`, `__PRE_VALIDATE__` etc
            if k in cls.__ALLOWED_MAGIC__ and v != MISSING_FIELD:
                fields[k] = v
            # ignore other hidden fields
            elif k.startswith("_"):
                continue
            # 1. only fields-like accept, ignore callables
            # 2. ignore literals
            elif not callable(v) and not getattr(
                v, "__IS_LITERAL_DOC__", False
            ):
                fields[k] = v
        return fields

    @classmethod
    def __get_mro_literals__(cls) -> dict[str, "ClassVarDocument"]:
        cls__dict = cls._get_ssc_deep_documents()
        fields = {}
        for k, v in cls__dict.items():
            if k.startswith("_"):
                continue
            if isinstance(v, str):
                continue
            if (
                v
                and not callable(v)
                and getattr(v, "__IS_LITERAL_DOC__", False)
            ):
                fields[k] = v
        return fields

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # HACK: for set LiteralDocument values in inheirended subclasses
        class_name = cls.__name__
        for attr_name, attr_value in cls.__dict__.items():
            if getattr(attr_value, "__IS_LITERAL_DOC__", False):
                attr_value.struct_name = class_name
                attr_value.field_name = attr_name
                setattr(cls, attr_name, attr_value)


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
