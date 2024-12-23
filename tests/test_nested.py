import pytest
from ssc_codegen import D, N, R, ItemSchema


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
def test_nested(expr):
    pass


def test_nested_init():
    class MockParserOne_(ItemSchema):
        foo = D().text()

    class MockParserMain_(ItemSchema):
        bar = N().sub_parser(MockParserOne_)

    MockParserMain_  # noqa
