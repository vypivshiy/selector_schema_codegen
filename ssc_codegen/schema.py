from typing import TYPE_CHECKING, Any, Type, TypeAlias, Union

from .consts import RESERVED_METHODS
from .json_struct import json_struct_to_signature
from .tokens import StructType, TokenType, VariableType

if TYPE_CHECKING:
    from .document import BaseDocument


class MISSING_FIELD(object):  # noqa
    pass


EXCLUDE_KEY = object()

_T_OPT_FIELD: TypeAlias = Union["BaseDocument", Type[MISSING_FIELD]]


class BaseSchema:
    __SCHEMA_TYPE__: StructType = NotImplemented

    __SIGNATURE__: dict | list = NotImplemented
    """manually write signature attribute"""

    __PRE_VALIDATE__: _T_OPT_FIELD = MISSING_FIELD

    # DICT, LIST, FLAT_LIST HOOK
    __SPLIT_DOC__: _T_OPT_FIELD = MISSING_FIELD

    # FLAT LIST HOOK
    __ITEM__: _T_OPT_FIELD = MISSING_FIELD

    # DICT HOOKS
    __KEY__: _T_OPT_FIELD = MISSING_FIELD
    __VALUE__: _T_OPT_FIELD = MISSING_FIELD

    __EXCLUDE_SIGNATURE__: _T_OPT_FIELD = MISSING_FIELD

    __ALLOWED_MAGIC__ = RESERVED_METHODS

    @staticmethod
    def _get_nested_signature(field: "BaseDocument") -> "BaseSchema":
        return [e for e in field.stack if e.kind == TokenType.EXPR_NESTED][
            0
        ].schema_cls  # type: ignore

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
            nested_class = cls._get_nested_signature(field)
            signature[key] = nested_class.__class_signature__()
        elif field.stack_last_ret == VariableType.JSON:
            signature[key] = json_struct_to_signature(field.stack[-1].value)  # noqa
        else:
            signature[key] = field.stack_last_ret

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
            nested_class = cls._get_nested_signature(field)
            signature.append(nested_class.__class_signature__())
        elif field.stack_last_ret == VariableType.JSON:
            signature[k] = json_struct_to_signature(v.stack[-1].value)  # noqa
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
    def __get_mro_fields__(cls) -> dict[str, "BaseDocument"]:
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
        fields = {}
        for k, v in cls__dict__.items():
            if k in cls.__ALLOWED_MAGIC__ and v != MISSING_FIELD:
                fields[k] = v
            elif k.startswith("_"):
                continue
            # only fields-like accept, ignore callable
            elif not callable(v):
                fields[k] = v
        return fields


# build-in structures
class ItemSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.ITEM


class ListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.LIST


class DictSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.DICT


class FlatListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.FLAT_LIST
