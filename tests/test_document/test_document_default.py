from ssc_codegen import D
from ssc_codegen.schema import BaseSchema
from ssc_codegen.document import BaseDocument
from ssc_codegen.static_checker import _DEFAULT_CB_DOCUMENTS  # noqa

import pytest


@pytest.mark.parametrize(
    "doc",
    [
        D().default("").raw(),
        D().default(1).raw().to_int(),
        D().default(0.1).raw().to_float(),
        D().default(0).raw().to_int(),
        D().default(0.0).raw().to_float(),
        D().default(True).raw().to_bool(),
        D().default(False).raw().to_bool(),
        D().default(None).raw(),
        D().default([]).raw().split(" "),
        D().default([]).raw().split(" ").to_int(),
        D().default([]).raw().split(" ").to_float(),
    ],
)
def test_default_document(doc: BaseDocument) -> None:
    result = all(cb(BaseSchema, "_", doc) for cb in _DEFAULT_CB_DOCUMENTS)
    assert result
