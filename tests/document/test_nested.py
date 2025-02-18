import pytest
from ssc_codegen import D, N, ItemSchema
from ssc_codegen.document import BaseDocument


class MockParserOne(ItemSchema):
    foo = D().text()


class MockParserMain(ItemSchema):
    bar: MockParserOne = N().sub_parser(MockParserOne)


@pytest.mark.parametrize(
    "expr",
    [
        N().sub_parser(MockParserOne),
        N().css("a").sub_parser(MockParserMain),
        N().xpath("//a").sub_parser(MockParserMain),
    ],
)
def test_nested(expr: BaseDocument) -> None:
    assert True


def test_nested_init() -> None:
    class MockParserOne(ItemSchema):
        foo = D().text()

    class MockParserMain(ItemSchema):
        bar = N().sub_parser(MockParserOne)

    MockParserMain  # noqa
