import pytest
from ssc_codegen.generation.runtime import (
    SscJsonPathError,
    SscJsonFieldMissingError,
    ssc_resolve_dotpath,
    ssc_json_project,
)
from ssc_codegen.core import parse_module
from ssc_codegen.targets.python import PY_BS4_CONVERTER


def test_ssc_resolve_dotpath_valid():
    data = {
        "user": {
            "name": "Alice",
            "badges": [{"icon": "star"}, {"icon": "shield"}],
        }
    }
    assert ssc_resolve_dotpath(data, "user.name", is_optional=False) == "Alice"
    assert (
        ssc_resolve_dotpath(data, "user.badges.0.icon", is_optional=False)
        == "star"
    )
    assert (
        ssc_resolve_dotpath(data, "user.badges.1.icon", is_optional=False)
        == "shield"
    )


def test_ssc_resolve_dotpath_errors():
    data = {"user": {"name": "Alice", "tags": "not-a-list"}}

    # Missing key
    with pytest.raises(
        SscJsonPathError, match="Missing key 'age' in path 'user.age'"
    ):
        ssc_resolve_dotpath(data, "user.age", is_optional=False)
    assert ssc_resolve_dotpath(data, "user.age", is_optional=True) is None

    # Expected list
    with pytest.raises(
        SscJsonPathError,
        match="Expected list for index '0' in path 'user.tags.0'",
    ):
        ssc_resolve_dotpath(data, "user.tags.0", is_optional=False)
    assert ssc_resolve_dotpath(data, "user.tags.0", is_optional=True) is None

    # Index out of bounds
    data_list = {"items": ["only_one"]}
    with pytest.raises(SscJsonPathError, match="Index 5 out of bounds"):
        ssc_resolve_dotpath(data_list, "items.5", is_optional=False)
    assert ssc_resolve_dotpath(data_list, "items.5", is_optional=True) is None

    # Traverse on null
    data_null = {"profile": None}
    with pytest.raises(
        SscJsonPathError,
        match="Cannot traverse segment 'avatar' on null object",
    ):
        ssc_resolve_dotpath(data_null, "profile.avatar.url", is_optional=False)
    assert (
        ssc_resolve_dotpath(data_null, "profile.avatar.url", is_optional=True)
        is None
    )


def test_ssc_json_project_strict_allowlist():
    data = {
        "id": "u1",
        "display_name": "Alice",
        "unmodeled_secret": "drop_me",
        "profile": {
            "avatar": {"url": "https://example.com/a.png", "width": 100},
        },
        "badges": [{"icon": "gold", "level": 99}],
        "extra_info": 12345,
    }

    # Descriptors format: canonical_name: (wire_path, is_optional, is_omitempty, nested_desc)
    descriptors = {
        "id": ("id", False, False, None),
        "name": ("display_name", False, False, None),
        "avatar_url": ("profile.avatar.url", True, False, None),
        "top_badge": ("badges.0.icon", True, False, None),
        "legacy_id": ("meta.legacy_id", False, True, None),
    }

    projected = ssc_json_project(data, descriptors)
    assert projected == {
        "id": "u1",
        "name": "Alice",
        "avatar_url": "https://example.com/a.png",
        "top_badge": "gold",
    }
    assert "unmodeled_secret" not in projected
    assert "extra_info" not in projected
    assert "legacy_id" not in projected


def test_ssc_json_project_missing_required_fields():
    data = {"display_name": "Alice"}
    descriptors = {
        "id": ("id", False, False, None),
        "name": ("display_name", False, False, None),
    }
    with pytest.raises(
        SscJsonFieldMissingError, match="Required JSON field 'id'"
    ):
        ssc_json_project(data, descriptors)


def test_ssc_json_project_null_on_non_nullable():
    data = {"id": None, "display_name": "Alice"}
    descriptors = {
        "id": ("id", False, False, None),
        "name": ("display_name", False, False, None),
    }
    with pytest.raises(
        SscJsonFieldMissingError,
        match="Field 'id' is null, but 'id' is not nullable",
    ):
        ssc_json_project(data, descriptors)

    # Required field via dot-path with explicit null on wire
    data_dot_null = {"profile": {"avatar": {"url": None}}}
    descriptors_dot = {
        "avatar_url": ("profile.avatar.url", False, False, None),
    }
    with pytest.raises(
        SscJsonFieldMissingError,
        match="Field 'profile.avatar.url' is null, but 'avatar_url' is not nullable",
    ):
        ssc_json_project(data_dot_null, descriptors_dot)


def test_ssc_json_project_nested_schema():
    geo_desc = {
        "latitude": ("lat", False, False, None),
        "longitude": ("lng", False, False, None),
    }
    user_desc = {
        "name": ("name", False, False, None),
        "location": ("geo", True, False, geo_desc),
    }

    data_with_geo = {
        "name": "Bob",
        "geo": {"lat": 12.34, "lng": 56.78, "extra": "drop"},
        "extra_parent": True,
    }
    res = ssc_json_project(data_with_geo, user_desc)
    assert res == {
        "name": "Bob",
        "location": {"latitude": 12.34, "longitude": 56.78},
    }


def test_end_to_end_python_codegen_and_execution():
    src = """
json GeoLocation {
    latitude float from="lat"
    longitude float from="lng"
}

json AuthorDetail {
    author_name str from="dc:creator"
    location GeoLocation?
}

json CatalogItem {
    item_id int from="@id"
    author AuthorDetail
    top_score int from="rating_scores.0"
    missing_note str? from="meta.notes.0.text"
    omitted_val int @omitempty from="not_found.key"
}

(raw)struct Scraper {
    items {
        jsonify CatalogItem
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)

    code = PY_BS4_CONVERTER.convert(module)
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)

    input_json = """
    {
        "@id": 42,
        "dc:creator": "Alice",
        "author": {
            "dc:creator": "Alice Author",
            "extra_author_field": "ignore_me",
            "location": {
                "lat": 10.5,
                "lng": 20.5,
                "altitude": 100
            }
        },
        "rating_scores": [5, 4, 3],
        "secret_token": "xyz123"
    }
    """
    scraper_cls = ns["Scraper"]
    result = scraper_cls(input_json).parse()

    assert result["items"]["item_id"] == 42
    assert result["items"]["author"]["author_name"] == "Alice Author"
    assert result["items"]["author"]["location"] == {
        "latitude": 10.5,
        "longitude": 20.5,
    }
    assert result["items"]["top_score"] == 5
    assert result["items"]["missing_note"] is None
    assert "omitted_val" not in result["items"]
    assert "secret_token" not in result["items"]
