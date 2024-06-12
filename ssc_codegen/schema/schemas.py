from typing import TYPE_CHECKING, Dict, List, Union

from ssc_codegen.schema.base import _T_SCHEMA_SIGNATURE, BaseSchema
from ssc_codegen.schema.constants import SchemaType
from ssc_codegen.type_state import TypeVariableState

if TYPE_CHECKING:
    from ssc_codegen.document.base import BaseDocument


class ItemSchema(BaseSchema):
    __SCHEMA_TYPE__ = SchemaType.ITEM


class ListSchema(BaseSchema):
    __SCHEMA_TYPE__ = SchemaType.LIST_ITEM
    __SPLIT_DOC__: "BaseDocument" = NotImplemented

    @classmethod
    def check(cls):
        if cls.__SPLIT_DOC__ == NotImplemented:
            raise NotImplementedError(
                "ListSchema object missing `__SPLIT_DOC__` attribute"
            )

        assert (
                cls.__SPLIT_DOC__.last_var_type is TypeVariableState.LIST_DOCUMENT
        )

    @classmethod
    def get_fields_signature(
            cls,
    ) -> Union[List[str], Dict[str, _T_SCHEMA_SIGNATURE]]:
        return [super().get_fields_signature(), "..."]  # type: ignore


class FlattenListSchema(BaseSchema):
    __SCHEMA_TYPE__ = SchemaType.LIST_FLATTEN
    __SPLIT_DOC__: "BaseDocument" = NotImplemented
    __ITEM__: "BaseDocument" = NotImplemented
    __SIGNATURE__ = ["item", "..."]

    @classmethod
    def get_fields(cls) -> Dict[str, "BaseDocument"]:
        return {
            "item": cls.__ITEM__,
            "__SPLIT_DOC__": cls.__SPLIT_DOC__
        }

    @classmethod
    def get_fields_signature(cls) -> Union[List[str], Dict[str, _T_SCHEMA_SIGNATURE]]:
        return ["item", "..."]

    @classmethod
    def check(cls) -> None:
        if cls.__ITEM__ == NotImplemented:
            raise NotImplementedError(
                "FlattenListSchema object missing __ITEM__ attribute"
            )
        if cls.__SPLIT_DOC__ == NotImplemented:
            raise NotImplementedError(
                "FlattenListSchema object missing __SPLIT_DOC__ attribute"
            )

        assert (
                cls.__SPLIT_DOC__.last_var_type == TypeVariableState.LIST_DOCUMENT
        ), "Should be return LIST_DOCUMENT type"


class DictSchema(BaseSchema):
    __SCHEMA_TYPE__ = SchemaType.DICT
    __SPLIT_DOC__: "BaseDocument" = NotImplemented
    __KEY__: "BaseDocument" = NotImplemented
    __VALUE__: "BaseDocument" = NotImplemented
    __SIGNATURE__: Dict[str, str] = NotImplemented

    @classmethod
    def check(cls):
        if cls.__SPLIT_DOC__ == NotImplemented:
            raise NotImplementedError(
                "DictSchema object missing `__SPLIT_DOC__` attribute"
            )
        if cls.__KEY__ == NotImplemented:
            raise NotImplementedError(
                "DictSchema object missing  `__KEY__` attribute"
            )
        if cls.__VALUE__ == NotImplemented:
            raise NotImplementedError(
                "DictSchema object missing  `__VALUE__` attribute"
            )

        assert (
                cls.__SPLIT_DOC__.last_var_type is TypeVariableState.LIST_DOCUMENT
        ), "Should be return type LIST_DOCUMENT"

    @classmethod
    def get_fields(cls) -> Dict[str, "BaseDocument"]:
        return {
            "key": cls.__KEY__,
            "value": cls.__VALUE__,
            "__SPLIT_DOC__": cls.__SPLIT_DOC__,
        }

    @classmethod
    def get_fields_signature(cls) -> Dict[str, _T_SCHEMA_SIGNATURE]:
        return {"K": "V", "...": "..."}
