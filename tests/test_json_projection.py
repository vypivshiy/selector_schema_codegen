import pytest
from ssc_codegen.generation.runtime import (
    SscJsonPathError,
    SscJsonFieldMissingError,
    SscJsonSchemaError,
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


def test_top_level_dict_json_codegen_and_execution():
    src = """
(dict)json Translations {
    @key int
    @value (array)str
}

(raw)struct Scraper {
    translations {
        jsonify Translations
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    assert "TranslationsJson = Dict[int, List[str]]" in code
    assert (
        "_translations_JSON_DESCRIPTORS = {'__dict__': True, '__value__': None}"
        in code
    )
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = '{"1": ["jap", "eng"], "10": ["rus"]}'
    res = ns["Scraper"](payload).parse()
    assert res["translations"] == {"1": ["jap", "eng"], "10": ["rus"]}


def test_top_level_dict_json_with_schema_ref():
    src = """
json Episode {
    id int
    title str from="episode_title"
}

(dict)json EpisodeMap {
    @key str
    @value Episode
}

(raw)struct Scraper {
    episodes {
        jsonify EpisodeMap
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    assert "EpisodeMapJson = Dict[str, EpisodeJson]" in code
    assert (
        "_episode_map_JSON_DESCRIPTORS = {'__dict__': True, '__value__': {'id': ('id', False, False, None), 'title': ('episode_title', False, False, None)}}"
        in code
    )
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = """{
        "ep_1": {"id": 1, "episode_title": "Pilot", "extra": "drop"},
        "ep_2": {"id": 2, "episode_title": "Finale", "extra": "drop"}
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["episodes"] == {
        "ep_1": {"id": 1, "title": "Pilot"},
        "ep_2": {"id": 2, "title": "Finale"},
    }


def test_inline_dict_field_codegen_and_execution():
    src = """
json AnimeInfo {
    id int
    translations (dict) {
        @key str
        @value (array)str
    }
}

(raw)struct Scraper {
    anime {
        jsonify AnimeInfo
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    assert "'translations': Dict[str, List[str]]" in code
    assert (
        "'translations': ('translations', False, False, {'__dict__': True, '__value__': None})"
        in code
    )
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = """{
        "id": 123,
        "translations": {
            "1": ["jap", "eng"],
            "2": ["rus"]
        }
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["anime"]["id"] == 123
    assert res["anime"]["translations"] == {
        "1": ["jap", "eng"],
        "2": ["rus"],
    }


def test_inline_anonymous_object_block():
    src = """
json AnimeResponse {
    id str
    material_data {
        anime_title str
        year int
    }
}

(raw)struct Scraper {
    anime {
        jsonify AnimeResponse
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    assert "AnimeResponseMaterialDataJson = TypedDict" in code
    assert "'material_data': AnimeResponseMaterialDataJson" in code
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = """{
        "id": "a1",
        "material_data": {
            "anime_title": "Steins;Gate",
            "year": 2011,
            "extra_field": "drop"
        }
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["anime"]["id"] == "a1"
    assert res["anime"]["material_data"] == {
        "anime_title": "Steins;Gate",
        "year": 2011,
    }


def test_inline_explicitly_named_object_block():
    src = """
json AnimeResponse {
    id str
    franchise Franchise {
        id str
        name str from="franchise_name"
    }
}

(raw)struct Scraper {
    anime {
        jsonify AnimeResponse
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    assert 'FranchiseJson = TypedDict("FranchiseJson"' in code
    assert "'franchise': FranchiseJson" in code
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = """{
        "id": "a2",
        "franchise": {
            "id": "f1",
            "franchise_name": "Science Adventure",
            "ignored": 999
        }
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["anime"]["id"] == "a2"
    assert res["anime"]["franchise"] == {
        "id": "f1",
        "name": "Science Adventure",
    }


def test_inline_explicitly_named_array_block():
    src = """
json AnimeResponse {
    id str
    links (array)Links {
        id int
        relation str
    }
}

(raw)struct Scraper {
    anime {
        jsonify AnimeResponse
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    assert 'LinksJson = TypedDict("LinksJson"' in code
    assert "'links': List[LinksJson]" in code
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = """{
        "id": "a3",
        "links": [
            {"id": 10, "relation": "prequel", "junk": 1},
            {"id": 11, "relation": "sequel", "junk": 2}
        ]
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["anime"]["id"] == "a3"
    assert res["anime"]["links"] == [
        {"id": 10, "relation": "prequel"},
        {"id": 11, "relation": "sequel"},
    ]


def test_end_to_end_combined_dict_and_inline_schemas():
    src = """
json Episode {
    id int
    title str from="ep_title"
}

(dict)json EpisodeMap {
    @key int
    @value Episode
}

json AnimeComplete {
    id str
    franchise Franchise {
        id str
    }
    links (array)Links {
        id int
        relation str
    }
    material_data {
        anime_title str
        year int
    }
    translations (dict) {
        @key str
        @value (array)str
    }
    episodes EpisodeMap?
}

(raw)struct Scraper {
    anime {
        jsonify AnimeComplete
    }
}
"""
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    code = PY_BS4_CONVERTER.convert(module)
    ns = {}
    exec(compile(code, "<test>", "exec"), ns)
    payload = """{
        "id": "c1",
        "franchise": {"id": "fr1", "extra": 1},
        "links": [{"id": 1, "relation": "spin_off", "other": 2}],
        "material_data": {"anime_title": "Fullmetal Alchemist", "year": 2009},
        "translations": {"1": ["jap", "eng"]},
        "episodes": {
            "1": {"id": 101, "ep_title": "To Challenge the Sun", "skip": 0}
        }
    }"""
    res = ns["Scraper"](payload).parse()
    anime = res["anime"]
    assert anime["id"] == "c1"
    assert anime["franchise"] == {"id": "fr1"}
    assert anime["links"] == [{"id": 1, "relation": "spin_off"}]
    assert anime["material_data"] == {
        "anime_title": "Fullmetal Alchemist",
        "year": 2009,
    }
    assert anime["translations"] == {"1": ["jap", "eng"]}
    assert anime["episodes"] == {
        "1": {"id": 101, "title": "To Challenge the Sun"}
    }


def test_ssc_json_schema_error_on_non_dict_payload():
    # 1. Direct ssc_json_project unit tests
    dict_desc = {"__dict__": True, "__value__": None}
    with pytest.raises(SscJsonSchemaError, match="Expected dict, got list"):
        ssc_json_project(["item1", "item2"], dict_desc)
    with pytest.raises(SscJsonSchemaError, match="Expected dict, got int"):
        ssc_json_project(12345, dict_desc)
    with pytest.raises(SscJsonSchemaError, match="Expected dict, got str"):
        ssc_json_project("string_payload", dict_desc)

    # 2. Top-level dict schema execution error
    top_src = """
(dict)json Translations {
    @key int
    @value (array)str
}

(raw)struct TopScraper {
    data {
        jsonify Translations
    }
}
"""
    m_top, _ = parse_module(top_src)
    code_top = PY_BS4_CONVERTER.convert(m_top)
    ns_top = {}
    exec(compile(code_top, "<test>", "exec"), ns_top)
    ErrTop = ns_top["SscJsonSchemaError"]
    with pytest.raises(ErrTop, match="Expected dict, got list"):
        ns_top["TopScraper"]("[1, 2, 3]").parse()

    # 3. Inline dict field execution error
    inline_src = """
json MediaItem {
    id int
    translations (dict) {
        @key str
        @value (array)str
    }
}

(raw)struct InlineScraper {
    item {
        jsonify MediaItem
    }
}
"""
    m_inline, _ = parse_module(inline_src)
    code_inline = PY_BS4_CONVERTER.convert(m_inline)
    ns_inline = {}
    exec(compile(code_inline, "<test>", "exec"), ns_inline)
    ErrInline = ns_inline["SscJsonSchemaError"]
    with pytest.raises(ErrInline, match="Expected dict, got list"):
        ns_inline["InlineScraper"](
            '{"id": 1, "translations": ["not", "a", "dict"]}'
        ).parse()
