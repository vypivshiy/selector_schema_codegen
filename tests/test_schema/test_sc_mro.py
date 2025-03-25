from ssc_codegen import ItemSchema, R
import pytest


class _Parent(ItemSchema):
    parent_f1 = R()
    parent_f2 = R()
    parent_f3 = R()


class _Child1(_Parent):
    child1_f1 = R()
    child1_f2 = R()


class _Child2(_Child1):
    child2_f1 = R()
    child2_f2 = R()


@pytest.mark.parametrize(
    "instance,fields",
    [
        (_Parent, {"parent_f1", "parent_f2", "parent_f3"}),
        (
            _Child1,
            {"child1_f1", "child1_f2"}
            | {"parent_f1", "parent_f2", "parent_f3"},
        ),
        (
            _Child2,
            {"child2_f1", "child2_f2"}
            | {"child1_f1", "child1_f2"}
            | {"parent_f1", "parent_f2", "parent_f3"},
        ),
    ],
)
def test_schema_mro(instance, fields) -> None:  # type: ignore
    assert all(instance.__class_signature__().get(f) for f in fields)  # type: ignore
