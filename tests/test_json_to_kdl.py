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


def test_json_to_kdl_inline_array_of_objects() -> None:
    data = {
        "users": [{"id": 1, "username": "alice", "active": True}],
        "settings": {
            "options": [{"key": "theme", "value": "dark"}],
        },
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    users (array)UsersItem {\n"
        "        id int\n"
        "        username str\n"
        "        active bool\n"
        "    }\n"
        "    settings {\n"
        "        options (array)OptionsItem {\n"
        "            key str\n"
        "            value str\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "UsersItem" in defs
    assert "OptionsItem" in defs
    assert "JsonResponseSettings" in defs
    assert "JsonResponse" in defs

    users_def = defs["UsersItem"]
    assert getattr(users_def, "is_array", False) is False
    assert [f.name for f in users_def.body] == ["id", "username", "active"]

    options_def = defs["OptionsItem"]
    assert getattr(options_def, "is_array", False) is False
    assert [f.name for f in options_def.body] == ["key", "value"]

    settings_def = defs["JsonResponseSettings"]
    assert settings_def.body[0].name == "options"
    assert settings_def.body[0].ret_type_info.is_array is True
    assert settings_def.body[0].ret_type_info.ref == "OptionsItem"

    root_def = defs["JsonResponse"]
    assert root_def.body[0].name == "users"
    assert root_def.body[0].ret_type_info.is_array is True
    assert root_def.body[0].ret_type_info.ref == "UsersItem"
    assert root_def.body[1].name == "settings"
    assert root_def.body[1].ret_type_info.is_array is False
    assert root_def.body[1].ret_type_info.ref == "JsonResponseSettings"


def test_json_to_kdl_inline_array_with_aliasing_and_omitempty() -> None:
    data = {
        "user-items": [
            {"item-id": 10, "label": "first"},
            {"item-id": 20},
        ]
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        '    user_items (array)UserItemsItem from="user-items" {\n'
        '        item_id int from="item-id"\n'
        "        label str @omitempty\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    item_def = defs["UserItemsItem"]
    assert item_def.body[0].name == "item_id"
    assert item_def.body[0].alias == "item-id"
    assert item_def.body[0].ret_type_info.omitempty is False
    assert item_def.body[1].name == "label"
    assert item_def.body[1].ret_type_info.omitempty is True

    root_def = defs["JsonResponse"]
    assert root_def.body[0].name == "user_items"
    assert root_def.body[0].alias == "user-items"
    assert root_def.body[0].ret_type_info.is_array is True
    assert root_def.body[0].ret_type_info.ref == "UserItemsItem"


def test_json_to_kdl_collision_disambiguation_with_ancestors() -> None:
    data = {
        "order": {
            "items": [{"id": 1}],
        },
        "profile": {
            "items": [{"name": "a"}],
        },
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    order {\n"
        "        items (array)ItemsItem {\n"
        "            id int\n"
        "        }\n"
        "    }\n"
        "    profile {\n"
        "        items (array)ProfileItemsItem {\n"
        "            name str\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "ItemsItem" in defs
    assert "ProfileItemsItem" in defs
    assert "JsonResponseOrder" in defs
    assert "JsonResponseProfile" in defs
    assert "JsonResponse" in defs

    assert defs["JsonResponseOrder"].body[0].ret_type_info.ref == "ItemsItem"
    assert (
        defs["JsonResponseProfile"].body[0].ret_type_info.ref
        == "ProfileItemsItem"
    )


def test_json_to_kdl_collision_disambiguation_multi_level_ancestors() -> None:
    data = {
        "company": {
            "order": {
                "items": [{"id": 1}],
            }
        },
        "store": {
            "order": {
                "items": [{"sku": "SKU-1"}],
            }
        },
        "warehouse": {
            "order": {
                "items": [{"qty": 50}],
            }
        },
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    company {\n"
        "        order {\n"
        "            items (array)ItemsItem {\n"
        "                id int\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    store {\n"
        "        order {\n"
        "            items (array)OrderItemsItem {\n"
        "                sku str\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    warehouse {\n"
        "        order {\n"
        "            items (array)WarehouseOrderItemsItem {\n"
        "                qty int\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "ItemsItem" in defs
    assert "OrderItemsItem" in defs
    assert "WarehouseOrderItemsItem" in defs


def test_json_to_kdl_collision_numeric_suffix_when_ancestor_collides() -> None:
    data = {
        "items": [{"id": 1}],
        "profile_items": [{"id": 2}],
        "profile": {
            "items": [{"name": "a"}],
        },
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    items (array)ItemsItem {\n"
        "        id int\n"
        "    }\n"
        "    profile_items (array)ProfileItemsItem {\n"
        "        id int\n"
        "    }\n"
        "    profile {\n"
        "        items (array)ProfileItemsItem2 {\n"
        "            name str\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "ItemsItem" in defs
    assert "ProfileItemsItem" in defs
    assert "ProfileItemsItem2" in defs
    assert "JsonResponseProfile" in defs
    assert "JsonResponse" in defs


def test_json_to_kdl_top_level_array_collision_with_root_schema() -> None:
    data = [{"json_response": [{"id": 1}]}]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    json_response (array)JsonResponseItem2 {\n"
        "        id int\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "JsonResponseItem" in defs
    assert "JsonResponseItem2" in defs
    assert defs["JsonResponseItem"].is_array is True
    assert defs["JsonResponseItem2"].is_array is False


def test_json_to_kdl_top_level_object_collision_with_root_name() -> None:
    data = {"custom": [{"id": 1}]}
    source = json_to_kdl(data, name="CustomItem")
    expected = (
        "json CustomItem {\n"
        "    custom (array)CustomItem2 {\n"
        "        id int\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "CustomItem" in defs
    assert "CustomItem2" in defs


def test_json_to_kdl_deep_array_hierarchies() -> None:
    data = {
        "departments": [
            {
                "name": "Engineering",
                "teams": [
                    {
                        "name": "Backend",
                        "members": [
                            {
                                "name": "Alice",
                                "active": True,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    source = json_to_kdl(data)
    expected = (
        "json JsonResponse {\n"
        "    departments (array)DepartmentsItem {\n"
        "        name str\n"
        "        teams (array)TeamsItem {\n"
        "            name str\n"
        "            members (array)MembersItem {\n"
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
    assert "MembersItem" in defs
    assert "TeamsItem" in defs
    assert "DepartmentsItem" in defs
    assert "JsonResponse" in defs

    members_def = defs["MembersItem"]
    assert [f.name for f in members_def.body] == ["name", "active"]

    teams_def = defs["TeamsItem"]
    assert teams_def.body[0].name == "name"
    assert teams_def.body[1].name == "members"
    assert teams_def.body[1].ret_type_info.is_array is True
    assert teams_def.body[1].ret_type_info.ref == "MembersItem"

    depts_def = defs["DepartmentsItem"]
    assert depts_def.body[0].name == "name"
    assert depts_def.body[1].name == "teams"
    assert depts_def.body[1].ret_type_info.is_array is True
    assert depts_def.body[1].ret_type_info.ref == "TeamsItem"

    root_def = defs["JsonResponse"]
    assert root_def.body[0].name == "departments"
    assert root_def.body[0].ret_type_info.is_array is True
    assert root_def.body[0].ret_type_info.ref == "DepartmentsItem"


def test_json_to_kdl_multi_sample_arrays_different_keys_omitempty() -> None:
    data = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "age": 30},
        {"id": 3, "name": "Charlie", "email": "c@example.com"},
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    id int\n"
        "    name str @omitempty\n"
        "    age int @omitempty\n"
        "    email str @omitempty\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    item_fields = {f.name: f for f in defs["JsonResponseItem"].body}
    assert item_fields["id"].ret_type_info.omitempty is False
    assert item_fields["name"].ret_type_info.omitempty is True
    assert item_fields["age"].ret_type_info.omitempty is True
    assert item_fields["email"].ret_type_info.omitempty is True


def test_json_to_kdl_recursive_nested_objects_merging_with_omitempty() -> None:
    data = [
        {
            "user": {
                "id": 1,
                "profile": {
                    "first_name": "Alice",
                    "city": "London",
                },
            }
        },
        {
            "user": {
                "id": 2,
                "profile": {
                    "first_name": "Bob",
                    "country": "UK",
                },
            }
        },
        {
            "user": {
                "id": 3,
                "profile": {
                    "first_name": "Charlie",
                },
            }
        },
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    user {\n"
        "        id int\n"
        "        profile {\n"
        "            first_name str\n"
        "            city str @omitempty\n"
        "            country str @omitempty\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    profile_fields = {
        f.name: f for f in defs["JsonResponseItemUserProfile"].body
    }
    assert profile_fields["first_name"].ret_type_info.omitempty is False
    assert profile_fields["city"].ret_type_info.omitempty is True
    assert profile_fields["country"].ret_type_info.omitempty is True


def test_json_to_kdl_recursive_nested_objects_partial_child_blocks() -> None:
    data = [
        {
            "user": {
                "profile": {"display_name": "Alice", "avatar": "a.png"},
            }
        },
        {
            "user": {
                "profile": {"display_name": "Bob"},
            }
        },
        {
            "user": {},
        },
        {},
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    user @omitempty {\n"
        "        profile @omitempty {\n"
        "            display_name str\n"
        "            avatar str @omitempty\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    item_fields = {f.name: f for f in defs["JsonResponseItem"].body}
    assert item_fields["user"].ret_type_info.omitempty is True

    user_fields = {f.name: f for f in defs["JsonResponseItemUser"].body}
    assert user_fields["profile"].ret_type_info.omitempty is True

    profile_fields = {
        f.name: f for f in defs["JsonResponseItemUserProfile"].body
    }
    assert profile_fields["display_name"].ret_type_info.omitempty is False
    assert profile_fields["avatar"].ret_type_info.omitempty is True


def test_json_to_kdl_nested_arrays_across_multiple_parent_samples() -> None:
    data = [
        {
            "id": 1,
            "tags": ["python", "kdl"],
            "orders": [
                {"sku": "A1", "price": 10},
            ],
        },
        {
            "id": 2,
            "tags": ["rust"],
            "orders": [
                {"sku": "B2", "price": 20, "discount": 5},
                {"sku": "B3", "price": 30},
            ],
        },
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    id int\n"
        "    tags (array)str\n"
        "    orders (array)OrdersItem {\n"
        "        sku str\n"
        "        price int\n"
        "        discount int @omitempty\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "OrdersItem" in defs
    orders_fields = {f.name: f for f in defs["OrdersItem"].body}
    assert orders_fields["sku"].ret_type_info.omitempty is False
    assert orders_fields["price"].ret_type_info.omitempty is False
    assert orders_fields["discount"].ret_type_info.omitempty is True


def test_json_to_kdl_deep_nested_arrays_across_multiple_parent_samples() -> (
    None
):
    data = [
        {
            "company": "Acme",
            "departments": [
                {
                    "name": "Engineering",
                    "teams": [
                        {"lead": "Alice", "size": 10},
                    ],
                }
            ],
        },
        {
            "company": "Globex",
            "departments": [
                {
                    "name": "Design",
                    "budget": 20000,
                    "teams": [
                        {"lead": "Bob", "remote": True},
                        {"lead": "Charlie", "size": 5},
                    ],
                },
                {
                    "name": "Sales",
                    "teams": [
                        {"lead": "David"},
                    ],
                },
            ],
        },
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    company str\n"
        "    departments (array)DepartmentsItem {\n"
        "        name str\n"
        "        teams (array)TeamsItem {\n"
        "            lead str\n"
        "            size int @omitempty\n"
        "            remote bool @omitempty\n"
        "        }\n"
        "        budget int @omitempty\n"
        "    }\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    assert "DepartmentsItem" in defs
    assert "TeamsItem" in defs

    teams_fields = {f.name: f for f in defs["TeamsItem"].body}
    assert teams_fields["lead"].ret_type_info.omitempty is False
    assert teams_fields["size"].ret_type_info.omitempty is True
    assert teams_fields["remote"].ret_type_info.omitempty is True

    depts_fields = {f.name: f for f in defs["DepartmentsItem"].body}
    assert depts_fields["name"].ret_type_info.omitempty is False
    assert depts_fields["teams"].ret_type_info.omitempty is False
    assert depts_fields["budget"].ret_type_info.omitempty is True


def test_json_to_kdl_heterogeneous_types_fallback_to_skip() -> None:
    data = [
        {
            "scalar_mix": 42,
            "obj_or_scalar": {"foo": "bar"},
            "obj_or_arr": {"key": 1},
            "arr_or_scalar": ["item"],
        },
        {
            "scalar_mix": "forty-two",
            "obj_or_scalar": "plain text",
            "obj_or_arr": [1, 2],
            "arr_or_scalar": 100,
        },
    ]
    source = json_to_kdl(data)
    expected = (
        "(array)json JsonResponseItem {\n"
        "    scalar_mix @skip // int, str\n"
        "    obj_or_scalar @skip // object, str\n"
        "    obj_or_arr @skip // object, array\n"
        "    arr_or_scalar @skip // array, int\n"
        "}\n"
    )
    assert source == expected

    module, diags = parse_module(source)
    assert not any(d.severity.name == "ERROR" for d in diags)

    defs = {node.name: node for node in module.body if hasattr(node, "name")}
    fields = {f.name: f for f in defs["JsonResponseItem"].body}
    for f_name in [
        "scalar_mix",
        "obj_or_scalar",
        "obj_or_arr",
        "arr_or_scalar",
    ]:
        assert fields[f_name].ret_type_info.skip is True

    # Heterogeneous items within an array field across samples
    arr_data = [
        {"arr_mix": ["str_val"], "obj_arr_mix": [{"id": 1}]},
        {"arr_mix": [999], "obj_arr_mix": ["string_item"]},
    ]
    arr_source = json_to_kdl(arr_data)
    assert "arr_mix (array)null @skip // str, int" in arr_source
    assert "obj_arr_mix (array)null @skip // object, str" in arr_source


def test_json_to_kdl_empty_objects_merging_and_optionality() -> None:
    # 1. All samples empty dict
    all_empty = [{"meta": {}}, {"meta": {}}]
    src_all_empty = json_to_kdl(all_empty)
    assert src_all_empty == (
        "(array)json JsonResponseItem {\n    meta @skip // empty object\n}\n"
    )
    _, diags = parse_module(src_all_empty)
    assert not any(d.severity.name == "ERROR" for d in diags)

    # 2. Some empty, some non-empty -> merged and marked @omitempty
    some_empty = [{"meta": {}}, {"meta": {"version": 1}}]
    src_some_empty = json_to_kdl(some_empty)
    assert src_some_empty == (
        "(array)json JsonResponseItem {\n"
        "    meta {\n"
        "        version int @omitempty\n"
        "    }\n"
        "}\n"
    )
    _, diags = parse_module(src_some_empty)
    assert not any(d.severity.name == "ERROR" for d in diags)

    # 3. Some empty, some non-empty, some missing -> meta gets @omitempty, version gets @omitempty
    mixed_meta = [{"meta": {}}, {"meta": {"version": 1}}, {}]
    src_mixed_meta = json_to_kdl(mixed_meta)
    assert src_mixed_meta == (
        "(array)json JsonResponseItem {\n"
        "    meta @omitempty {\n"
        "        version int @omitempty\n"
        "    }\n"
        "}\n"
    )
    _, diags = parse_module(src_mixed_meta)
    assert not any(d.severity.name == "ERROR" for d in diags)

    # 4. Array of empty objects across all samples
    arr_empty_objs = [{"items": [{}]}, {"items": [{}]}]
    src_arr_empty = json_to_kdl(arr_empty_objs)
    assert src_arr_empty == (
        "(array)json JsonResponseItem {\n"
        "    items (array)null @skip // empty object\n"
        "}\n"
    )

    # 5. Array with empty object and populated object
    arr_mixed_objs = [{"items": [{}]}, {"items": [{"id": 1}]}]
    src_arr_mixed = json_to_kdl(arr_mixed_objs)
    assert src_arr_mixed == (
        "(array)json JsonResponseItem {\n"
        "    items (array)ItemsItem {\n"
        "        id int @omitempty\n"
        "    }\n"
        "}\n"
    )
    _, diags = parse_module(src_arr_mixed)
    assert not any(d.severity.name == "ERROR" for d in diags)


def test_json_to_kdl_empty_and_populated_arrays_merging() -> None:
    # 1. Some empty array samples, some populated
    data_populated = [{"tags": []}, {"tags": ["a", "b"]}]
    source_pop = json_to_kdl(data_populated)
    assert source_pop == (
        "(array)json JsonResponseItem {\n    tags (array)str\n}\n"
    )
    _, diags = parse_module(source_pop)
    assert not any(d.severity.name == "ERROR" for d in diags)

    # 2. All empty array samples
    data_all_empty = [{"tags": []}, {"tags": []}]
    source_empty = json_to_kdl(data_all_empty)
    assert source_empty == (
        "(array)json JsonResponseItem {\n"
        "    tags (array)null @skip // empty array\n"
        "}\n"
    )

    # 3. Empty array in some samples, missing in other
    data_empty_missing = [{"tags": []}, {}]
    source_empty_missing = json_to_kdl(data_empty_missing)
    assert source_empty_missing == (
        "(array)json JsonResponseItem {\n"
        "    tags (array)null @skip @omitempty // empty array\n"
        "}\n"
    )

    # 4. Populated array in some, missing in other
    data_pop_missing = [{"tags": ["a"]}, {}]
    source_pop_missing = json_to_kdl(data_pop_missing)
    assert source_pop_missing == (
        "(array)json JsonResponseItem {\n    tags (array)str @omitempty\n}\n"
    )
    _, diags = parse_module(source_pop_missing)
    assert not any(d.severity.name == "ERROR" for d in diags)
