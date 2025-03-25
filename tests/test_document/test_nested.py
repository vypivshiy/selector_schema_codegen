import pytest
from ssc_codegen import D, N, ItemSchema
from ssc_codegen.document import BaseDocument


class MockParserOne(ItemSchema):
    foo = D().text()


class MockParserMain(ItemSchema):
    bar = N().sub_parser(MockParserOne)


@pytest.mark.parametrize(
    "_",
    [
        N().sub_parser(MockParserOne),
        N().css("a").sub_parser(MockParserMain),
        N().xpath("//a").sub_parser(MockParserMain),
    ],
)
def test_nested(_: BaseDocument) -> None:
    assert True


def test_nested_init() -> None:
    class MockParserOne2(ItemSchema):
        foo = D().text()

    class MockParserMain2(MockParserOne2):
        bar = N().sub_parser(MockParserOne)

    fields = MockParserMain2.__get_mro_fields__()
    assert fields.get("foo")
