from typing import Type

import pytest

from ssc_codegen import D, DictSchema, Document, FlatListSchema, ListSchema, R
from ssc_codegen.ast_builder import build_ast_struct
from ssc_codegen.schema import BaseSchema, ItemSchema


def schema_factory(parent: Type[BaseSchema], **fields: Document) -> type:
    return type("_PytestFactorySchema", (parent,), fields)


@pytest.mark.parametrize(
    "schema",
    [
        # missing magic fields cases
        schema_factory(DictSchema),
        schema_factory(DictSchema, __SPLIT_DOC__=D()),
        schema_factory(DictSchema, __SPLIT_DOC__=D(), __KEY__=D()),
        schema_factory(DictSchema, __SPLIT_DOC__=D(), __VALUE__=D()),
        schema_factory(DictSchema, __KEY__=D()),
        schema_factory(DictSchema, __VALUE__=D()),
        schema_factory(ListSchema),
        schema_factory(FlatListSchema),
        schema_factory(FlatListSchema, __SPLIT_DOC__=D()),
        schema_factory(FlatListSchema, __ITEM__=D()),
    ],
)
def test_fail_schema_config(schema: Type[BaseSchema]) -> None:
    with pytest.raises(SyntaxError):
        build_ast_struct(schema)


@pytest.mark.parametrize(
    "schema",
    [
        schema_factory(ListSchema, __SPLIT_DOC__=D()),
        schema_factory(ListSchema, __SPLIT_DOC__=D().css("a")),
        schema_factory(ListSchema, __SPLIT_DOC__=R()),
        schema_factory(ListSchema, __SPLIT_DOC__=R().split(" ")),
        schema_factory(ListSchema, __SPLIT_DOC__=R().to_int()),
        schema_factory(ListSchema, __SPLIT_DOC__=R().to_float()),
        schema_factory(ListSchema, __SPLIT_DOC__=R().split(" ").to_int()),
        schema_factory(ListSchema, __SPLIT_DOC__=R().split(" ").to_float()),
    ],
)
def test_fail_schema_split_doc_ret_type(schema: Type["BaseSchema"]) -> None:
    with pytest.raises(SyntaxError):
        build_ast_struct(schema)


@pytest.mark.parametrize(
    "schema",
    [
        schema_factory(
            DictSchema,
            __SPLIT_DOC__=D().css_all("a"),
            __KEY__=D(),
            __VALUE__=D().raw(),
        ),
        schema_factory(
            DictSchema,
            __SPLIT_DOC__=D().css_all("a"),
            __KEY__=D().raw(),
            __VALUE__=D(),
        ),
        schema_factory(
            FlatListSchema, __SPLIT_DOC__=D().css_all("a"), __ITEM__=D()
        ),
        schema_factory(ListSchema, __SPLIT_DOC__=D().css_all("a"), f1=D()),
        schema_factory(ItemSchema, f1=D()),
    ],
)
def test_fail_field_empty_expr(schema: Type["BaseSchema"]) -> None:
    with pytest.raises(SyntaxError):
        build_ast_struct(schema)
