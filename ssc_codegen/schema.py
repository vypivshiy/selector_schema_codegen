from typing import TYPE_CHECKING, TypeAlias, Union, Type, Any

from .tokens import StructType, VariableType, TokenType
from .consts import RESERVED_METHODS, SIGNATURE_MAP
from ssc_codegen.schema import BaseSchema

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
    __NESTED_CLASSES__: dict[str, BaseSchema] = {}

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
    def _get_nested_signature(field: 'BaseDocument') -> 'BaseSchema':
        return [e for e in field.stack if e.kind == TokenType.EXPR_NESTED][0].schema_cls  # noqa

    @classmethod
    def __class_signature__(cls):
        if cls.__SIGNATURE__ != NotImplemented:
            return cls.__SIGNATURE__
        if cls.__SCHEMA_TYPE__ == StructType.FLAT_LIST:
            signature = cls._get_flat_list_signature()
        elif cls.__SCHEMA_TYPE__ == StructType.DICT:
            signature = cls._get_dict_signature()
        elif cls.__SCHEMA_TYPE__ == StructType.ITEM:
            signature = cls._get_item_signature()
        elif cls.__SCHEMA_TYPE__ == StructType.LIST:
            signature = cls._get_list_signature()
        else:
            # code unreached
            raise TypeError('Unknown schema type')
        return signature

    @classmethod
    def _get_list_signature(cls):
        signature = {}
        for k, v in cls.__get_mro_fields__().items():
            if k in cls.__ALLOWED_MAGIC__:
                continue

            if v.stack_last_ret == VariableType.NESTED:
                nested_class = cls._get_nested_signature(v)
                signature[k] = nested_class.__class_signature__()
            else:
                signature[k] = v.stack_last_ret
        signature = [signature, '...']
        return signature

    @classmethod
    def _get_item_signature(cls):
        signature = {}
        for k, v in cls.__get_mro_fields__().items():
            if k in cls.__ALLOWED_MAGIC__:
                continue

            if v.stack_last_ret == VariableType.NESTED:
                nested_class = cls._get_nested_signature(v)
                signature[k] = nested_class.__class_signature__()
            else:
                signature[k] = v.stack_last_ret
        return signature

    @classmethod
    def _get_dict_signature(cls):
        signature = {}
        field_k, field_v = cls.__KEY__, cls.__VALUE__
        if field_v.stack_last_ret == VariableType.NESTED:
            nested_class = [e for e in field.stack if e.kind == TokenType.EXPR_NESTED][0].schema_cls  # noqa
            signature["<K>"] = nested_class.__class_signature__()
        else:
            signature['<K>'] = field_v.stack_last_ret
        signature['<KN>'] = '...'
        return signature

    @classmethod
    def _get_flat_list_signature(cls):
        signature = []
        field = cls.__ITEM__
        if field.stack_last_ret == VariableType.NESTED:
            nested_class = cls._get_nested_signature(field)
            signature.append(nested_class.__class_signature__())
        else:
            signature.append(field.stack_last_ret)
        signature.append('...')
        return signature

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
