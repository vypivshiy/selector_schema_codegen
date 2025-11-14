from ssc_codegen.document import DocumentElementsFilter, HTMLDocument, ClassVarDocument, StringDocument, ArrayDocument, AssertDocument, NestedDocument, \
    DefaultDocument, \
    NumericDocument, JsonDocument, BooleanDocument, DocumentFilter
from ssc_codegen.json_struct import Json
from ssc_codegen.logs import setup_logger
from ssc_codegen.schema import ItemSchema, DictSchema, ListSchema, FlatListSchema, AccUniqueListSchema

setup_logger()

VERSION = "0.13.3"


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
    """Special Common Document or Element marker manipulations"""
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    """Special Common Document or Element marker for provide Nested structure parsers"""
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


def FE() -> DocumentElementsFilter:
    """Shortcut as a DocumentElementsFilter() object"""
    return DocumentElementsFilter()


def CV(value: int | str | float | bool | None | list, self_cls_path: str | None = None, *, returns: bool = False) -> ClassVarDocument:
    """Shortcut as ClassVarDocument(value, self_cls, parse_returns) object

    pass `self_cls_path` argument if need use this var inner schema context:

    self_cls_path use case example:

```
class B(ItemSchema):
    # dont need pass class and attr names
    C = CV("test {{}}")

class A(ItemShema):
    # current impl cannot be extract class and field names
    # need pass it manually
    C1 = CV("title", "A.C1")

    title = D().css(C1).text().fmt(C)

```

    """
    return ClassVarDocument(value, self_cls_path, parse_returns=returns)