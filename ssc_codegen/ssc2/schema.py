from typing import TYPE_CHECKING, TypeAlias, Union, Type, Any

from .tokens import StructType

if TYPE_CHECKING:
    from .document import BaseDocument


class MISSING_FIELD(object):  # type: ignore
    pass


EXCLUDE_KEY = object()

_T_OPT_FIELD: TypeAlias = Union["BaseDocument", MISSING_FIELD]


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

    __ALLOWED_MAGIC__ = {
        "__PRE_VALIDATE__",
        "__SPLIT_DOC__",
        "__ITEM__",
        "__KEY__",
        "__VALUE__",
        "__ITEM__"
    }

    @classmethod
    def __schema_mro__(cls) -> tuple[Type["BaseSchema"], ...]:
        return tuple((i for i in cls.__mro__ if issubclass(i, BaseSchema) and i.__SCHEMA_TYPE__ == cls.__SCHEMA_TYPE__))

    @classmethod
    def __get_mro_annotations__(cls) -> dict[str, Any]:
        """extract all annotations (parent classes included)"""
        cls__annotations = {}
        fields = cls.__get_mro_fields__()
        for kls in cls.__schema_mro__():
            if kls.__annotations__:
                for k, v in kls.__annotations__.items():
                    if not cls__annotations.get(k) and fields.get(k) != MISSING_FIELD:
                        cls__annotations[k] = v
                    elif k in cls.__ALLOWED_MAGIC__ and fields.get(k) != MISSING_FIELD and not cls__annotations.get(k):
                        cls__annotations[k] = v
        return cls__annotations

    @classmethod
    def __get_mro_fields__(cls) -> dict[str, "BaseDocument"]:
        """extract all fields (parent classes included)"""
        cls__dict__ = {}
        for klass in cls.__schema_mro__():
            # copy __dict__ to avoid runtime err:
            # RuntimeError: dictionary changed size during iteration
            tmp_attrs = vars(klass).copy()
            for k, v in tmp_attrs.items():
                # if not set docstring - get from parent class
                if k == '__doc__' and not cls.__doc__ and not cls__dict__.get('__doc__'):
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
            # only fields-like accept
            elif not callable(v):
                fields[k] = v
        return fields


class ItemSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.ITEM


class ListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.LIST


class DictSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.DICT


class FlatListSchema(BaseSchema):
    __SCHEMA_TYPE__ = StructType.FLAT_LIST
