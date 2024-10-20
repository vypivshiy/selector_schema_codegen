from .document import HTMLDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument
from .schema import ItemSchema, DictSchema, ListSchema, FlatListSchema


class Document(HTMLDocument, StringDocument, ArrayDocument, AssertDocument):
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    pass


def D() -> Document:  # noqa
    return Document()


def N() -> Nested:  # noqa
    return Nested()


def R() -> Document():  # noqa
    return D().raw()
