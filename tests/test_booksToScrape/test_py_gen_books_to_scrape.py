from pathlib import Path

from ssc_codegen.compiler import Compiler
import json
from ssc_codegen.converters.py_bs4 import CONVERTER as BS4_CONVERTER
from ssc_codegen.converters.py_parsel import CONVERTER as PARSEL_CONVERTER
from ssc_codegen.converters.py_selectolax import CONVERTER as SLAX_CONVERTER
from ssc_codegen.converters.py_base import BasePyCodeConverter
import pytest

_TEST_DIR = Path(__file__).parent
_SCHEMA_INPUT = _TEST_DIR / "bts_schema.py"
_HTML_DOC_INDEX = _TEST_DIR / "bts_index.html"
_HTML_DOC_BOOK = _TEST_DIR / "bts_book.html"
_JSON_DOC_INDEX_OUT = _TEST_DIR / "bts_index_out.json"
_JSON_BOOK_OUT = _TEST_DIR / "bts_book_out.json"


@pytest.mark.parametrize(
    "schema_path,doc_path,converter,json_out,cls_target",
    [
        (
            _SCHEMA_INPUT,
            _HTML_DOC_INDEX,
            BS4_CONVERTER,
            _JSON_DOC_INDEX_OUT,
            "MainCatalogue",
        ),
        (
            _SCHEMA_INPUT,
            _HTML_DOC_INDEX,
            PARSEL_CONVERTER,
            _JSON_DOC_INDEX_OUT,
            "MainCatalogue",
        ),
        (
            _SCHEMA_INPUT,
            _HTML_DOC_INDEX,
            SLAX_CONVERTER,
            _JSON_DOC_INDEX_OUT,
            "MainCatalogue",
        ),
        (
            _SCHEMA_INPUT,
            _HTML_DOC_BOOK,
            BS4_CONVERTER,
            _JSON_BOOK_OUT,
            "ProductDescription",
        ),
        (
            _SCHEMA_INPUT,
            _HTML_DOC_BOOK,
            PARSEL_CONVERTER,
            _JSON_BOOK_OUT,
            "ProductDescription",
        ),
        (
            _SCHEMA_INPUT,
            _HTML_DOC_BOOK,
            SLAX_CONVERTER,
            _JSON_BOOK_OUT,
            "ProductDescription",
        ),
    ],
)
def test_parse_books_to_scrape(
    schema_path: Path,
    doc_path: Path,
    converter: BasePyCodeConverter,
    json_out: Path,
    cls_target: str,
) -> None:
    comp = Compiler.from_file(schema_path, converter=converter)
    document = Path(doc_path).read_text()
    result = comp.run_parse(cls_target, document)

    expected = json.loads(json_out.read_text())
    assert result == expected
