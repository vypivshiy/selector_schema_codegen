from types import NoneType
from typing import Optional, List, Dict, get_args, Type, Union, Any

from ssc_codegen2.document import Document
from ssc_codegen2.type_state import TypeVariableState

# TODO: typing
_T_SCHEMA_SIGNATURE = Union[str, Dict[str, str], List[Any]]


class BaseSchema:
    # auto generate items string signature
    __SCHEMA_TYPE__: str = NotImplemented  # alias name
    __SIGNATURE__: Union[Dict, List] = NotImplemented  # optional signature implement
    __REPR_TYPE_NAMES_ALIASES__ = {
        str: "String",
        Optional[str]: "null | String",
        list: "Array[String]",
        List: "Array[String]",
        list[str]: "Array[String]",
        List[str]: "Array[String]",
        Optional[list]: "null | Array[String]",
        Optional[list[str]]: "null | Array[String]",
        Optional[List]: "null | Array[String]",
        Optional[List[str]]: "null | Array[String]",
        NoneType: "null",
        None: "null"
    }
    __ARG_TYPE_STATE_ALIAS__ = {
        TypeVariableState.LIST_STRING: "Array[String]",
        TypeVariableState.STRING: "String",
        TypeVariableState.NONE: "null"
    }

    __NON_TYPED_FIELDS__ = (
        '__SCHEMA_TYPE__',  # mark schema type
        '__PRE_VALIDATE__',  # always returns None
        '__SPLIT_DOC__',  # returns array of elements or iterator of elements (LIST_DOCUMENT)
        '__doc__'  # docstring hook
    )
    __MAGIC_METHODS_NAMES__ = (
        '__SCHEMA_TYPE__',
        '__PRE_VALIDATE__',
        '__SPLIT_DOC__',
        '__KEY__',
        '__VALUE__',
        '__doc__'
    )
    __PRE_VALIDATE__: Optional[Document] = None

    @classmethod
    def check(cls) -> None:
        pass

    @staticmethod
    def _is_implemented(value) -> bool:
        return value != NotImplemented or value != None

    @classmethod
    def get_fields(cls) -> Dict[str, Document]:
        fields = {}

        # copy dicts to avoid runtime err:
        # RuntimeError: dictionary changed size during iteration
        cls_attrs = cls.__dict__.copy()

        for k, v in cls_attrs.items():
            v: Document
            k: str

            if k in cls.__MAGIC_METHODS_NAMES__ and cls._is_implemented(v):
                fields[k] = v
            # nested schemas
            elif cls.__annotations__.get(k) and issubclass(cls.__annotations__.get(k), BaseSchema):
                fields[k] = cls.__annotations__.get(k).get_fields()
            elif k.startswith('_'):
                continue
            else:
                fields[k] = v
        return fields

    @staticmethod
    def _is_list_schema(type_):
        type_args = get_args(type_)
        return len(type_args) == 1 and issubclass(type_args[0], BaseSchema)

    @classmethod
    def get_fields_signature(cls) -> Dict[str, _T_SCHEMA_SIGNATURE]:
        signature = {}
        # copy dicts to avoid runtime err:
        # RuntimeError: dictionary changed size during iteration
        cls_annotations = cls.__annotations__.copy()

        for k, v in cls.get_fields().items():
            if type_ := cls_annotations.get(k):

                if issubclass(type_, BaseSchema):
                    type_.check()
                    if type_.__SIGNATURE__ != NotImplemented:
                        signature[k] = type_.__SIGNATURE__
                    else:
                        signature[k] = type_.get_fields_signature()
                else:
                    signature[k] = cls.__REPR_TYPE_NAMES_ALIASES__.get(type_)

            elif k not in cls.__NON_TYPED_FIELDS__:
                type_ = cls.__ARG_TYPE_STATE_ALIAS__.get(v.last_var_type, "???")
                signature[k] = type_
        return signature
