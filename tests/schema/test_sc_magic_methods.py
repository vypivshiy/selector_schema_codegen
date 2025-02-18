from typing import Type

import pytest
from helpers import (
    schema_dict_factory,
    schema_factory,
    schema_flat_list_factory,
    schema_item_factory,
    schema_list_factory,
)

from ssc_codegen import D, DictSchema, FlatListSchema, ListSchema, R
from ssc_codegen.ast_builder import build_ast_struct
from ssc_codegen.schema import BaseSchema


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
        schema_list_factory(__SPLIT_DOC__=D()),
        schema_list_factory(__SPLIT_DOC__=D().css("a")),
        schema_list_factory(__SPLIT_DOC__=R()),
        schema_list_factory(__SPLIT_DOC__=R().split(" ")),
        schema_list_factory(__SPLIT_DOC__=R().to_int()),
        schema_list_factory(__SPLIT_DOC__=R().to_float()),
        schema_list_factory(__SPLIT_DOC__=R().split(" ").to_int()),
        schema_list_factory(__SPLIT_DOC__=R().split(" ").to_float()),
    ],
)
def test_fail_schema_split_doc_ret_type(schema: Type["BaseSchema"]) -> None:
    with pytest.raises(SyntaxError):
        build_ast_struct(schema)


@pytest.mark.parametrize(
    "schema",
    [
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("a"),
            __KEY__=D(),
            __VALUE__=D().raw(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("a"),
            __KEY__=D().raw(),
            __VALUE__=D(),
        ),
        schema_flat_list_factory(__SPLIT_DOC__=D().css_all("a"), __ITEM__=D()),
        schema_list_factory(__SPLIT_DOC__=D().css_all("a"), f1=D()),
        schema_item_factory(f1=D()),
    ],
)
def test_fail_field_empty_expr(schema: Type["BaseSchema"]) -> None:
    with pytest.raises(SyntaxError):
        build_ast_struct(schema)


@pytest.mark.parametrize(
    "schema",
    [
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css("p").text().to_int(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css("p").text().to_float(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css("p").css("a"),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css_all("p"),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css_all("p").first(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css_all("p").raw(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().css_all("p").text(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().default(None).raw(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().default(None).css("a").text(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().default(1).css("a").text().to_int(),
            __VALUE__=R(),
        ),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("p"),
            __KEY__=D().default(0.1).css("a").text().to_float(),
            __VALUE__=R(),
        ),
    ],
)
def test_fail_schema_dict_key(schema: Type["BaseSchema"]) -> None:
    with pytest.raises(TypeError):
        build_ast_struct(schema)


@pytest.mark.parametrize(
    "schema",
    [
        schema_item_factory(f1=D().css("a")),
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("a"),
            __KEY__=D().css("a").text(),
            __VALUE__=D().css("a"),
        ),
        schema_flat_list_factory(
            __SPLIT_DOC__=D().css_all("a"), __ITEM__=D().css("a")
        ),
    ],
)
def test_fail_document_value_type(schema: Type["BaseSchema"]) -> None:
    with pytest.raises(TypeError):
        build_ast_struct(schema)


@pytest.mark.parametrize(
    "schema",
    [
        schema_dict_factory(
            __SPLIT_DOC__=D().css_all("a"),
            __KEY__=D().default("ok").attr("a"),
            __VALUE__=R(),
        ),
    ],
)
def test_valid_dict_schema_key(schema: Type["BaseSchema"]) -> None:
    assert build_ast_struct(schema)
