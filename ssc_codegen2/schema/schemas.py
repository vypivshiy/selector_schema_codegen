from typing import TYPE_CHECKING, Dict
from ssc_codegen2.schema.base import BaseSchema, _T_SCHEMA_SIGNATURE
from ssc_codegen2.type_state import TypeVariableState

if TYPE_CHECKING:
    from ssc_codegen2.document import Document


class ItemSchema(BaseSchema):
    __SCHEMA_TYPE__ = 'Map'


class ListSchema(BaseSchema):
    __SCHEMA_TYPE__ = 'Array[Map]'
    __SPLIT_DOC__: "Document" = NotImplemented

    @classmethod
    def check(cls):
        if cls.__SPLIT_DOC__ == NotImplemented:
            raise SyntaxError("ListSchema object missing `__SPLIT_DOC__` attribute")

        assert cls.__SPLIT_DOC__.last_var_type is TypeVariableState.LIST_DOCUMENT

    @classmethod
    def get_fields_signature(cls) -> Dict[str, _T_SCHEMA_SIGNATURE]:
        return [super().get_fields_signature(), '...']


class DictSchema(BaseSchema):
    __SCHEMA_TYPE__ = 'Map'
    __SPLIT_DOC__: "Document" = NotImplemented
    __KEY__: "Document" = NotImplemented
    __VALUE__: "Document" = NotImplemented
    __DICT_SIGNATURE__: Dict[str, str] = NotImplemented

    @classmethod
    def check(cls):
        if cls.__SPLIT_DOC__ == NotImplemented:
            raise SyntaxError("DictSchema object missing `__SPLIT_DOC__` attribute")
        if cls.__KEY__ == NotImplemented:
            raise SyntaxError("DictSchema object missing  `__KEY__` attribute")
        if cls.__VALUE__ == NotImplemented:
            raise SyntaxError("DictSchema object missing  `__VALUE__` attribute")

        assert cls.__SPLIT_DOC__.last_var_type is TypeVariableState.LIST_DOCUMENT

    @classmethod
    def get_fields_signature(cls) -> Dict[str, _T_SCHEMA_SIGNATURE]:
        return {"K": "V", "...": "..."}
