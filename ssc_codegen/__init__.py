from .document import HTMLDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument, DefaultDocument
from .schema import ItemSchema, DictSchema, ListSchema, FlatListSchema

VERSION = "0.4.0"


class Document(HTMLDocument, StringDocument, ArrayDocument, AssertDocument, DefaultDocument):
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    pass


def D() -> Document:  # noqa
    """Shortcut as a Document() object"""
    return Document()


def N() -> Nested:  # noqa
    """Shortcut as a Nested() object"""
    return Nested()


def R() -> Document: # noqa
    """Shortcut as a Document().raw() object.
    For regex and format string operations
    """
    return D().raw()
