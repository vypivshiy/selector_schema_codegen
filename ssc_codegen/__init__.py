from ssc_codegen.document import HTMLDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument, DefaultDocument


class Document(HTMLDocument, StringDocument, ArrayDocument, AssertDocument, DefaultDocument):
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    pass


def D() -> Document:  # noqa
    return Document()


def N() -> Nested:  # noqa
    return Nested()


def R() -> Document():  # noqa
    return D().raw()
