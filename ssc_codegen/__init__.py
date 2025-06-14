from ssc_codegen.document import HTMLDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument, \
    DefaultDocument, \
    NumericDocument, JsonDocument, BooleanDocument, DocumentFilter
from ssc_codegen.json_struct import Json
from ssc_codegen.logs import setup_logger
from ssc_codegen.schema import ItemSchema, DictSchema, ListSchema, FlatListSchema, AccUniqueListSchema

setup_logger()

VERSION = "0.9.9"


class __MISSING(object):
    """special marker for mark is not passed default value"""
    pass


_NO_DEFAULT = __MISSING()


class Document(
    HTMLDocument,
    StringDocument,
    ArrayDocument,
    AssertDocument,
    DefaultDocument,
    NumericDocument,
    JsonDocument,
    BooleanDocument
):
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    pass


def D(default: None | str | int | float | list | __MISSING = _NO_DEFAULT) -> Document:  # noqa
    """Shortcut as a Document() object

    :param default: .default() operator shortcut
    """
    if default == _NO_DEFAULT:
        return Document()
    return Document().default(value=default)  # type: ignore


def N() -> Nested:  # noqa
    """Shortcut as a Nested() object"""
    return Nested()


def R(default: None | str | int | float | list | __MISSING = _NO_DEFAULT) -> Document:  # noqa
    """Shortcut as a Document().raw() object.
    For regex and format string operations

    :param default: .default() operator shortcut
    """
    if default == _NO_DEFAULT:
        return Document().raw()
    return Document().default(default).raw()  # type: ignore


def F() -> DocumentFilter:
    """Shortcut as a DocumentFilter() object"""
    return DocumentFilter()