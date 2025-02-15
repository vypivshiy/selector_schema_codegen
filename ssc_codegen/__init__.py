from .document import HTMLDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument, DefaultDocument, \
    NumericDocument, JsonDocument
from .json_struct import Json
from .schema import ItemSchema, DictSchema, ListSchema, FlatListSchema

VERSION = "0.6.1"

class __MISSING(object):
    pass

_NO_DEFAULT = __MISSING()

class Document(HTMLDocument, StringDocument, ArrayDocument, AssertDocument, DefaultDocument, NumericDocument, JsonDocument):
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    pass


def D(default_value: None | str | int | float | __MISSING =_NO_DEFAULT) -> Document:  # noqa
    """Shortcut as a Document() object

    :param default_value: .default() operator shortcut
    """
    if default_value==_NO_DEFAULT:
        return Document()
    return Document().default(value=default_value)  # type: ignore


def N() -> Nested:  # noqa
    """Shortcut as a Nested() object"""
    return Nested()


def R(default_value: None | str | int | float | __MISSING =_NO_DEFAULT) -> Document: # noqa
    """Shortcut as a Document().raw() object.
    For regex and format string operations

    :param default_value: .default() operator shortcut
    """
    if default_value==_NO_DEFAULT:
        return Document().raw()
    return Document().default(default_value).raw()  # type: ignore
