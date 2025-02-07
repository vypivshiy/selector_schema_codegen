from typing import Type

import pytest
from helpers import schema_item_factory

from ssc_codegen import D
from ssc_codegen.ast_builder import build_ast_struct
from ssc_codegen.schema import BaseSchema


@pytest.mark.parametrize(
    "schema",
    [
        schema_item_factory(f=D().default(0).raw()),
        schema_item_factory(f=D().default(0.1).raw()),
        schema_item_factory(f=D().default("a").raw().to_int()),
        schema_item_factory(f=D().default("a").raw().to_float()),
        schema_item_factory(f=D().default(1).raw().to_float()),
        schema_item_factory(f=D().default(0.1).raw().to_int()),
    ],
)
def test_invalid_default(schema: Type["BaseSchema"]) -> None:
    # TODO: replace exception as TypeError
    with pytest.raises(TypeError):
        build_ast_struct(schema)
