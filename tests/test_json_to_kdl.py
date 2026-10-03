import json
import pytest
from typer.testing import CliRunner

from ssc_codegen.ast.types import VariableType
from ssc_codegen.core import parse_module
from ssc_codegen.json_to_kdl import (
    JsonToKdlError,
    json_to_kdl,
    json_text_to_kdl,
)
from ssc_codegen.main import app


def test_json_to_kdl_generates_nested_definitions() -> None:
    source = json_to_kdl(
        {
            "user": {"id": 1, "profile": {"display-name": "Ann"}},
            "tags": ["one", "two"],
        }
    )

    expected = (
        "json JsonResponse {\n"
        "    user {\n"
        "        id int\n"
        "        profile {\n"
        '            display_name str from="display-name"\n'
        "        }\n"
        "    }\n"
        "    tags (array)str\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "JsonResponseUserProfile" in defs
    assert "JsonResponseUser" in defs
    assert "JsonResponse" in defs

    profile_def = defs["JsonResponseUserProfile"]
    assert len(profile_def.body) == 1
    assert profile_def.body[0].name == "display_name"
    assert profile_def.body[0].alias == "display-name"
    assert profile_def.body[0].ret_type_info.base == VariableType.STRING

    user_def = defs["JsonResponseUser"]
    assert len(user_def.body) == 2
    assert user_def.body[0].name == "id"
    assert user_def.body[0].ret_type_info.base == VariableType.INT
    assert user_def.body[1].name == "profile"
    assert user_def.body[1].ret_type_info.ref == "JsonResponseUserProfile"

    root_def = defs["JsonResponse"]
    assert len(root_def.body) == 2
    assert root_def.body[0].name == "user"
    assert root_def.body[0].ret_type_info.ref == "JsonResponseUser"
    assert root_def.body[1].name == "tags"
    assert root_def.body[1].ret_type_info.is_array is True
    assert root_def.body[1].ret_type_info.base == VariableType.STRING


def test_json_to_kdl_marks_unknown_arrays() -> None:
    source = json_to_kdl({"tags": [1, "x"], "empty": [], "value": None})

    assert "tags (array)null @skip // int, str" in source
    assert "empty (array)null @skip // empty array" in source
    assert "value nil // unknown real type" in source


def test_json_to_kdl_root_array_uses_item_schema() -> None:
    source = json_to_kdl([{"id": 1}])

    assert source == "(array)json JsonResponseItem {\n    id int\n}\n"
    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "JsonResponseItem" in defs
    item_def = defs["JsonResponseItem"]
    assert getattr(item_def, "is_array", False) is True
    assert len(item_def.body) == 1
    assert item_def.body[0].name == "id"


def test_json_to_kdl_anonymous_inline_deep_nesting() -> None:
    data = {
        "company": {
            "department": {
                "lead": {
                    "name": "Alice",
                    "active": True,
                }
            }
        }
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    company {\n"
        "        department {\n"
        "            lead {\n"
        "                name str\n"
        "                active bool\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "JsonResponseCompanyDepartmentLead" in defs
    assert "JsonResponseCompanyDepartment" in defs
    assert "JsonResponseCompany" in defs
    assert "JsonResponse" in defs


def test_json_to_kdl_canonical_from_remapping() -> None:
    data = {
        "kebab-case": "val1",
        "@context": "https://schema.org",
        "123_num": 42,
        "class": "keyword",
        "for": "keyword",
        "null": 0,
        "nested-obj": {
            "inner-field": "inner_val",
        },
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        '    kebab_case str from="kebab-case"\n'
        '    context str from="@context"\n'
        '    k_123_num int from="123_num"\n'
        '    k_class str from="class"\n'
        '    k_for str from="for"\n'
        '    k_null int from="null"\n'
        '    nested_obj from="nested-obj" {\n'
        '        inner_field str from="inner-field"\n'
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    root_fields = {f.name: f for f in defs["JsonResponse"].body}
    assert root_fields["kebab_case"].alias == "kebab-case"
    assert root_fields["context"].alias == "@context"
    assert root_fields["k_123_num"].alias == "123_num"
    assert root_fields["k_class"].alias == "class"
    assert root_fields["k_for"].alias == "for"
    assert root_fields["k_null"].alias == "null"
    assert root_fields["nested_obj"].alias == "nested-obj"

    nested_def = defs["JsonResponseNestedObj"]
    assert nested_def.body[0].name == "inner_field"
    assert nested_def.body[0].alias == "inner-field"


def test_json_to_kdl_empty_objects_emitted_as_skip_scalar() -> None:
    data = {
        "empty": {},
        "empty-remapped": {},
        "nested": {
            "inner_empty": {},
        },
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    empty @skip // empty object\n"
        '    empty_remapped @skip from="empty-remapped" // empty object\n'
        "    nested {\n"
        "        inner_empty @skip // empty object\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    # Must parse with 0 errors and no E001/E002 diagnostics
    module, diags = parse_module(source)
    errors = [d for d in diags if d.severity.name == "ERROR"]
    assert not errors

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    root_fields = {f.name: f for f in defs["JsonResponse"].body}
    assert root_fields["empty"].ret_type_info.skip is True
    assert root_fields["empty_remapped"].ret_type_info.skip is True
    assert root_fields["empty_remapped"].alias == "empty-remapped"

    nested_fields = {f.name: f for f in defs["JsonResponseNested"].body}
    assert nested_fields["inner_empty"].ret_type_info.skip is True


def test_json_to_kdl_empty_root_object() -> None:
    source = json_to_kdl({})
    assert source == "json JsonResponse {\n}\n"

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)


def test_json_to_kdl_custom_root_name() -> None:
    source = json_to_kdl({"name": "foo"}, name="CustomModel")
    assert source == "json CustomModel {\n    name str\n}\n"

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    source_arr = json_to_kdl([{"name": "foo"}], name="Catalog")
    assert source_arr == "(array)json CatalogItem {\n    name str\n}\n"

    module_arr, diags_arr = parse_module(source_arr)
    assert not any(d.severity.name == "ERROR" for d in diags_arr)


def test_json_to_kdl_primitive_arrays_all_types() -> None:
    data = {
        "strings": ["a", "b"],
        "ints": [1, 2],
        "floats": [1.5, 2.5],
        "bools": [True, False],
        "remap-list": ["x"],
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    strings (array)str\n"
        "    ints (array)int\n"
        "    floats (array)float\n"
        "    bools (array)bool\n"
        '    remap_list (array)str from="remap-list"\n'
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)


def test_json_to_kdl_null_values() -> None:
    data = {
        "normal_nil": None,
        "raw-nil": None,
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    normal_nil nil // unknown real type\n"
        '    raw_nil nil from="raw-nil" // unknown real type\n'
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)


def test_json_to_kdl_root_array_with_omitempty() -> None:
    data = [
        {"id": 1, "extra": "foo", "empty-sub": {}},
        {"id": 2},
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    id int\n"
        "    extra str @omitempty\n"
        '    empty_sub @skip from="empty-sub" @omitempty // empty object\n'
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    item_fields = {f.name: f for f in defs["JsonResponseItem"].body}
    assert item_fields["id"].ret_type_info.omitempty is False
    assert item_fields["extra"].ret_type_info.omitempty is True
    assert item_fields["empty_sub"].ret_type_info.omitempty is True
    assert item_fields["empty_sub"].ret_type_info.skip is True
    assert item_fields["empty_sub"].alias == "empty-sub"


def test_json_to_kdl_collision_in_same_scope_raises() -> None:
    data = {
        "foo_bar": 1,
        "foo-bar": 2,
    }
    with pytest.raises(
        JsonToKdlError,
        match="normalized field name collision in JsonResponse: 'foo_bar'",
    ):
        json_to_kdl(data)


def test_json_to_kdl_invalid_roots_raise() -> None:
    for invalid in [[], [1, 2], "scalar", 123, None]:
        with pytest.raises(
            JsonToKdlError,
            match="JSON root must be an object or a non-empty array of objects",
        ):
            json_to_kdl(invalid)


def test_json_text_to_kdl_convenience_function() -> None:
    raw_text = '{"name": "Alice", "age": 30}'
    source = json_text_to_kdl(raw_text)
    assert source == "json JsonResponse {\n    name str\n    age int\n}\n"

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)


def test_json_to_kdl_cli_writes_and_requires_confirmation(tmp_path) -> None:
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.kdl"
    input_file.write_text(json.dumps({"id": 1}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app, ["json-to-kdl", str(input_file), "-o", str(output_file)]
    )
    assert result.exit_code == 0, result.output
    assert "id int" in output_file.read_text(encoding="utf-8")

    result = runner.invoke(
        app,
        ["json-to-kdl", str(input_file), "-o", str(output_file)],
        input="n\n",
    )
    assert result.exit_code == 0
    assert "Output not written." in result.output
