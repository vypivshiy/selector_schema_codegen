from typing import Type

from ssc_codegen import Document
from ssc_codegen.schema import (
    BaseSchema,
    DictSchema,
    FlatListSchema,
    ListSchema,
    ItemSchema,
)


def schema_factory(parent: Type[BaseSchema], **fields: Document) -> type:
    """helper function to create schema instance in pytest.parametrize
    :param fields: schema fields kwargs
    :param parent: parent schema class
    """
    return type("_PytestFactorySchema", (parent,), fields)


def schema_dict_factory(
    *, __SPLIT_DOC__: Document, __KEY__: Document, __VALUE__: Document
) -> type:  # noqa
    return schema_factory(
        DictSchema,
        __SPLIT_DOC__=__SPLIT_DOC__,
        __KEY__=__KEY__,
        __VALUE__=__VALUE__,
    )


def schema_flat_list_factory(
    *, __SPLIT_DOC__: Document, __ITEM__: Document
) -> type:  # noqa
    return schema_factory(
        FlatListSchema, __SPLIT_DOC__=__SPLIT_DOC__, __ITEM__=__ITEM__
    )


def schema_list_factory(*, __SPLIT_DOC__: Document, **fields: Document) -> type:  # noqa
    return schema_factory(ListSchema, __SPLIT_DOC__=__SPLIT_DOC__, **fields)


def schema_item_factory(**fields: Document) -> type:  # noqa
    return schema_factory(ItemSchema, **fields)
