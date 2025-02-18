import pytest

from ssc_codegen.converters import convert_json_to_schema_code


@pytest.mark.parametrize(
    "raw_json, expected",
    [
        ('{"hello": "world"}', ["hello: str"]),
        ('{"a": 1, "b": 1.1, "c": null}', ["a: int", "b: float", "c: None"]),
        (
            '{"a": [1,2,3], "b": ["a", "b"], "c": [1.1,1.2,1.3]}',
            ["a: list[int]", "b: list[str]", "c: list[float]"],
        ),
        (
            '{"a": {"a1": 1, "b1": "a"}}',
            ["a: A", "a1: int", "b1: str", "class A(Json):"],
        ),
    ],
)
def test_json_converter(raw_json: str, expected: list[str]) -> None:
    code = convert_json_to_schema_code(raw_json)
    assert all(i in code for i in expected)
