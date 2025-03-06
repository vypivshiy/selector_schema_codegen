from .document import HTMLDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument, DefaultDocument, \
    NumericDocument, JsonDocument, BooleanDocument
from .json_struct import Json
from .schema import ItemSchema, DictSchema, ListSchema, FlatListSchema

VERSION = "0.7.4"

class __MISSING(object):
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


def D(default: None | str | int | float | __MISSING =_NO_DEFAULT) -> Document:  # noqa
    """Shortcut as a Document() object

    :param default: .default() operator shortcut
    """
    if default==_NO_DEFAULT:
        return Document()
    return Document().default(value=default)  # type: ignore


def N() -> Nested:  # noqa
    """Shortcut as a Nested() object"""
    return Nested()


def R(default: None | str | int | float | __MISSING =_NO_DEFAULT) -> Document: # noqa
    """Shortcut as a Document().raw() object.
    For regex and format string operations

    :param default: .default() operator shortcut
    """
    if default==_NO_DEFAULT:
        return Document().raw()
    return Document().default(default).raw()  # type: ignore
