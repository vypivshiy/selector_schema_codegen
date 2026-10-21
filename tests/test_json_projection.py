import re
import traceback

import pytest

from ssc_codegen.core import parse_module
from ssc_codegen.generation.runtime import (
    SscJsonFieldMissingError,
    SscJsonPathError,
    SscJsonSchemaError,
    ssc_resolve_dotpath,
)
from ssc_codegen.targets.python import PY_BS4_CONVERTER


def _compile_and_exec(src: str) -> tuple[str, dict]:
    module, diags = parse_module(src)
    errors = [d for d in diags if d.severity.name == "ERROR"]
    assert not errors, f"Unexpected lint errors: {errors}"
    code = PY_BS4_CONVERTER.convert(module)
    ns: dict = {}
    exec(compile(code, "<test>", "exec"), ns)
    return code, ns


def test_ssc_resolve_dotpath_valid():
    data = {
        "user": {
            "name": "Alice",
            "badges": [{"icon": "star"}, {"icon": "shield"}],
        },
        "os.version": "1.2.3",
        "a\\b": "backslash_val",
        "#": "hash_key_val",
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
    assert (
        ssc_resolve_dotpath(data, r"os\.version", is_optional=False) == "1.2.3"
    )
    assert (
        ssc_resolve_dotpath(data, r"a\\b", is_optional=False) == "backslash_val"
    )
    assert (
        ssc_resolve_dotpath(data, r"\#", is_optional=False) == "hash_key_val"
    )
    assert (
        ssc_resolve_dotpath(data, "user.badges.#", is_optional=False) == 2
    )
    assert ssc_resolve_dotpath(
        data, "user.badges.#.icon", is_optional=False
    ) == ["star", "shield"]


def test_ssc_resolve_dotpath_errors():
    data = {"user": {"name": "Alice", "tags": "not-a-list"}}

    # Missing key
    with pytest.raises(
        SscJsonPathError,
        match=r"User\.age: Missing key 'age' in path 'user\.age'",
    ):
        ssc_resolve_dotpath(
            data, "user.age", is_optional=False, target="User.age"
        )
    assert ssc_resolve_dotpath(data, "user.age", is_optional=True) is None

    # Expected list for index
    with pytest.raises(
        SscJsonPathError,
        match=r"User\.tag: Expected list for index '0' in path 'user\.tags\.0'",
    ):
        ssc_resolve_dotpath(
            data, "user.tags.0", is_optional=False, target="User.tag"
        )
    assert ssc_resolve_dotpath(data, "user.tags.0", is_optional=True) is None

    # Expected list for '#'
    with pytest.raises(
        SscJsonPathError,
        match=r"User\.tag_count: Expected list for '#' in path 'user\.tags\.#'",
    ):
        ssc_resolve_dotpath(
            data, "user.tags.#", is_optional=False, target="User.tag_count"
        )
    assert ssc_resolve_dotpath(data, "user.tags.#", is_optional=True) is None

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


def test_strict_allowlist_and_field_modifiers_projection():
    src = """
json UserProfile {
    id str
    name str from="display_name"
    avatar_url str? from="profile.avatar.url"
    top_badge str? from="badges.0.icon"
    legacy_id int @omitempty from="meta.legacy_id"
}

(raw)struct Scraper {
    user {
        jsonify UserProfile
    }
}
"""
    code, ns = _compile_and_exec(src)
    assert "def _project_user_profile(data: Any) -> UserProfileJson:" in code
    assert "JSON_DESCRIPTOR_" not in code
    assert "ssc_json_project" not in code
    assert "ssc_remap_json_keys" not in code

    payload = """{
        "id": "u1",
        "display_name": "Alice",
        "unmodeled_secret": "drop_me",
        "profile": {
            "avatar": {"url": "https://example.com/a.png", "width": 100}
        },
        "badges": [{"icon": "gold", "level": 99}],
        "extra_info": 12345
    }"""
    projected = ns["Scraper"](payload).parse()["user"]
    assert projected == {
        "id": "u1",
        "name": "Alice",
        "avatar_url": "https://example.com/a.png",
        "top_badge": "gold",
    }
    assert "unmodeled_secret" not in projected
    assert "extra_info" not in projected
    assert "legacy_id" not in projected


def test_missing_required_and_null_non_nullable_errors_include_schema_field():
    src = """
json UserAccount {
    id str
    name str from="display_name"
    avatar_url str from="profile.avatar.url"
}

(raw)struct Scraper {
    user {
        jsonify UserAccount
    }
}
"""
    _, ns = _compile_and_exec(src)
    ErrMissing = ns["SscJsonFieldMissingError"]

    with pytest.raises(
        ErrMissing,
        match=r"UserAccount\.id: Required JSON field 'id' \(mapped to 'id'\) is missing",
    ):
        ns["Scraper"](
            '{"display_name": "Alice", "profile": {"avatar": {"url": "http://x"}}}'
        ).parse()

    with pytest.raises(
        ErrMissing,
        match=r"UserAccount\.id: Field 'id' is null, but 'id' is not nullable",
    ):
        ns["Scraper"](
            '{"id": null, "display_name": "Alice", "profile": {"avatar": {"url": "http://x"}}}'
        ).parse()

    with pytest.raises(
        ErrMissing,
        match=r"UserAccount\.avatar_url: Field 'profile\.avatar\.url' is null, but 'avatar_url' is not nullable",
    ):
        ns["Scraper"](
            '{"id": "1", "display_name": "Alice", "profile": {"avatar": {"url": null}}}'
        ).parse()


def test_nested_projector_call_stack_and_qualified_error_context():
    src = """
json Preroll {
    vast_url str from="url"
    skip_offset int
}

json Vast {
    preroll Preroll
}

json CdnVideoHubResponse {
    vast Vast
}

(raw)struct PlayerScraper {
    hub {
        jsonify CdnVideoHubResponse
    }
}
"""
    code, ns = _compile_and_exec(src)
    assert "def _project_preroll(data: Any) -> PrerollJson:" in code
    assert "def _project_vast(data: Any) -> VastJson:" in code
    assert (
        "def _project_cdn_video_hub_response(data: Any) -> CdnVideoHubResponseJson:"
        in code
    )

    ErrMissing = ns["SscJsonFieldMissingError"]
    bad_payload = '{"vast": {"preroll": {"url": "https://ads.example/v.xml"}}}'

    with pytest.raises(ErrMissing) as exc_info:
        ns["PlayerScraper"](bad_payload).parse()

    assert "Preroll.skip_offset" in str(exc_info.value)
    assert (
        "Required JSON field 'skip_offset' (mapped to 'skip_offset') is missing"
        in str(exc_info.value)
    )

    frame_names = [
        frame.name for frame in traceback.extract_tb(exc_info.value.__traceback__)
    ]
    assert "_project_cdn_video_hub_response" in frame_names
    assert "_project_vast" in frame_names
    assert "_project_preroll" in frame_names
    assert (
        frame_names.index("_project_cdn_video_hub_response")
        < frame_names.index("_project_vast")
        < frame_names.index("_project_preroll")
    )


def test_gjson_escaped_dots_array_length_and_projection_end_to_end():
    src = r"""
json ReleaseInfo {
    os_version str from="os\\.version"
    nested_dot str from="meta.build\\.number"
    backslash_key str from="a\\\\b"
    tag_names (array)str from="tags.#.name"
    tag_count int from="tags.#"
    missing_count int? from="missing_arr.#"
    missing_proj (array)str? from="missing_arr.#.name"
}

(raw)struct ReleaseScraper {
    info {
        jsonify ReleaseInfo path="payload\\.data"
    }
}
"""
    code, ns = _compile_and_exec(src)
    # Direct key with escaped dot should be unescaped at compile time for O(1) lookup
    assert (
        "ssc_json_req(_d, 'os.version', 'ReleaseInfo.os_version')"
        in code
    )
    assert (
        "ssc_json_req(_d, 'a\\\\b', 'ReleaseInfo.backslash_key')"
        in code
    )

    payload = r"""{
        "payload.data": {
            "os.version": "24.04",
            "meta": {"build.number": "b-900"},
            "a\\b": "slash-ok",
            "tags": [
                {"name": "action", "id": 1},
                {"id": 2},
                {"name": null, "id": 3},
                {"name": "sci-fi", "id": 4}
            ]
        }
    }"""
    res = ns["ReleaseScraper"](payload).parse()["info"]
    assert res == {
        "os_version": "24.04",
        "nested_dot": "b-900",
        "backslash_key": "slash-ok",
        "tag_names": ["action", "sci-fi"],
        "tag_count": 4,
        "missing_count": None,
        "missing_proj": None,
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
    code, ns = _compile_and_exec(src)
    assert "def _project_geo_location(data: Any) -> GeoLocationJson:" in code
    assert "def _project_author_detail(data: Any) -> AuthorDetailJson:" in code
    assert "def _project_catalog_item(data: Any) -> CatalogItemJson:" in code
    assert "_project_geo_location(_v)" in code
    assert "_project_author_detail(" in code
    assert "_project_catalog_item(json.loads(v))" in code
    assert "JSON_DESCRIPTOR_" not in code
    assert "ssc_json_project" not in code

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
    code, ns = _compile_and_exec(src)
    assert "TranslationsJson = Dict[int, List[str]]" in code
    assert "def _project_translations(data: Any) -> TranslationsJson:" in code
    assert "JSON_DESCRIPTOR_" not in code
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
    code, ns = _compile_and_exec(src)
    assert "EpisodeMapJson = Dict[str, EpisodeJson]" in code
    assert "def _project_episode(data: Any) -> EpisodeJson:" in code
    assert "def _project_episode_map(data: Any) -> EpisodeMapJson:" in code
    assert "_project_episode(_v)" in code
    assert "JSON_DESCRIPTOR_" not in code
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
    code, ns = _compile_and_exec(src)
    assert "'translations': Dict[str, List[str]]" in code
    assert "def _project_anime_info(data: Any) -> AnimeInfoJson:" in code
    assert "ssc_expect_dict(" in code
    assert "JSON_DESCRIPTOR_" not in code
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
    code, ns = _compile_and_exec(src)
    assert "AnimeResponseMaterialDataJson = TypedDict" in code
    assert "'material_data': AnimeResponseMaterialDataJson" in code
    assert "def _project_anime_response_material_data(" in code
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
    code, ns = _compile_and_exec(src)
    assert 'FranchiseJson = TypedDict("FranchiseJson"' in code
    assert "'franchise': FranchiseJson" in code
    assert "def _project_franchise(data: Any) -> FranchiseJson:" in code
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
    code, ns = _compile_and_exec(src)
    assert 'LinksJson = TypedDict("LinksJson"' in code
    assert "'links': List[LinksJson]" in code
    assert "def _project_links(data: Any) -> LinksJson:" in code
    assert "def _project_anime_response(data: Any) -> AnimeResponseJson:" in code
    assert "[_project_links(_x) for _x in ssc_expect_list(" in code
    assert "_project_anime_response(json.loads(v))" in code
    assert "JSON_DESCRIPTOR_" not in code
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
    _, ns = _compile_and_exec(src)
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


def test_ssc_json_schema_error_on_invalid_container_shapes():
    # 1. Object schema receiving non-dict (None, list, int, str, bool)
    obj_src = """
json User {
    id int
}

(raw)struct ObjScraper {
    user {
        jsonify User
    }
}
"""
    _, ns_obj = _compile_and_exec(obj_src)
    ErrObj = ns_obj["SscJsonSchemaError"]
    for raw_json, expected_type in [
        ("null", "NoneType"),
        ("[1, 2]", "list"),
        ("12345", "int"),
        ('"string_payload"', "str"),
        ("true", "bool"),
    ]:
        with pytest.raises(
            ErrObj, match=f"User: Expected dict, got {expected_type}"
        ):
            ns_obj["ObjScraper"](raw_json).parse()

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
    _, ns_top = _compile_and_exec(top_src)
    ErrTop = ns_top["SscJsonSchemaError"]
    with pytest.raises(
        ErrTop, match="Translations: Expected dict, got list"
    ):
        ns_top["TopScraper"]("[1, 2, 3]").parse()
    with pytest.raises(
        ErrTop, match="Translations: Expected dict, got NoneType"
    ):
        ns_top["TopScraper"]("null").parse()
    with pytest.raises(
        ErrTop, match="Translations: Expected list, got str"
    ):
        ns_top["TopScraper"]('{"1": "not_a_list"}').parse()

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
    _, ns_inline = _compile_and_exec(inline_src)
    ErrInline = ns_inline["SscJsonSchemaError"]
    with pytest.raises(
        ErrInline, match=r"MediaItem\.translations: Expected dict, got list"
    ):
        ns_inline["InlineScraper"](
            '{"id": 1, "translations": ["not", "a", "dict"]}'
        ).parse()
    with pytest.raises(
        ErrInline, match=r"MediaItem\.translations: Expected list, got int"
    ):
        ns_inline["InlineScraper"](
            '{"id": 1, "translations": {"en": 123}}'
        ).parse()

    # 4. Top-level array schema receiving non-list or non-dict element
    arr_src = """
(array)json ItemList {
    id int
}

(raw)struct ArrScraper {
    items {
        jsonify ItemList
    }
}
"""
    _, ns_arr = _compile_and_exec(arr_src)
    ErrArr = ns_arr["SscJsonSchemaError"]
    with pytest.raises(
        ErrArr, match="ItemList: Expected list, got dict"
    ):
        ns_arr["ArrScraper"]('{"id": 1}').parse()
    with pytest.raises(
        ErrArr, match="ItemList: Expected dict, got str"
    ):
        ns_arr["ArrScraper"]('["not_a_dict"]').parse()


def test_anime_response_nested_dict_hierarchy_runtime_projection():
    src = """
json AnimeResponse {
    translations (dict)Translation {
        @key str
        @value TranslationValue {
            episodes (dict)EpisodeMap {
                @key int
                @value EpisodeValue {
                    link str
                    screenshots @skip
                }
            }
            is_active bool
            season int
            type str
            viewers int
            watch_seconds int
        }
    }
}

(raw)struct Scraper {
    anime {
        jsonify AnimeResponse
    }
}
"""
    code, ns = _compile_and_exec(src)

    # 1. Verify topological dependency order of emitted TypedDicts
    ep_pos = code.find('EpisodeValueJson = TypedDict("EpisodeValueJson"')
    tr_pos = code.find(
        'TranslationValueJson = TypedDict("TranslationValueJson"'
    )
    an_pos = code.find('AnimeResponseJson = TypedDict("AnimeResponseJson"')
    assert ep_pos != -1, "EpisodeValueJson must be defined"
    assert tr_pos != -1, "TranslationValueJson must be defined"
    assert an_pos != -1, "AnimeResponseJson must be defined"
    assert ep_pos < tr_pos < an_pos, (
        "Hoisted schemas must be emitted in post-order dependency sequence"
    )

    # 2. Verify generated projector functions
    assert "def _project_episode_value(data: Any) -> EpisodeValueJson:" in code
    assert (
        "def _project_translation_value(data: Any) -> TranslationValueJson:"
        in code
    )
    assert (
        "def _project_anime_response(data: Any) -> AnimeResponseJson:" in code
    )
    assert "_project_episode_value(_dv)" in code
    assert "_project_translation_value(_dv)" in code
    assert "JSON_DESCRIPTOR_" not in code

    # 3. Execute projection against realistic nested dictionary payload
    payload = """{
        "translations": {
            "sub_ru": {
                "is_active": true,
                "season": 1,
                "type": "sub",
                "viewers": 1500,
                "watch_seconds": 142000,
                "unmodeled_field": "drop_me",
                "episodes": {
                    "1": {
                        "link": "https://stream.example/ep1.mp4",
                        "screenshots": ["s1.png", "s2.png"],
                        "fps": 60
                    },
                    "2": {
                        "link": "https://stream.example/ep2.mp4",
                        "screenshots": ["s3.png"],
                        "fps": 60
                    }
                }
            },
            "dub_en": {
                "is_active": false,
                "season": 2,
                "type": "dub",
                "viewers": 300,
                "watch_seconds": 25000,
                "episodes": {
                    "10": {
                        "link": "https://stream.example/ep10.mp4",
                        "screenshots": []
                    }
                }
            }
        },
        "extra_root_prop": 999
    }"""
    res = ns["Scraper"](payload).parse()
    anime = res["anime"]
    assert "extra_root_prop" not in anime
    assert set(anime["translations"].keys()) == {"sub_ru", "dub_en"}

    sub_ru = anime["translations"]["sub_ru"]
    assert "unmodeled_field" not in sub_ru
    assert sub_ru["is_active"] is True
    assert sub_ru["season"] == 1
    assert sub_ru["type"] == "sub"
    assert sub_ru["viewers"] == 1500
    assert sub_ru["watch_seconds"] == 142000
    assert sub_ru["episodes"] == {
        "1": {"link": "https://stream.example/ep1.mp4"},
        "2": {"link": "https://stream.example/ep2.mp4"},
    }
    assert "screenshots" not in sub_ru["episodes"]["1"]
    assert "fps" not in sub_ru["episodes"]["1"]

    dub_en = anime["translations"]["dub_en"]
    assert dub_en["is_active"] is False
    assert dub_en["season"] == 2
    assert dub_en["type"] == "dub"
    assert dub_en["viewers"] == 300
    assert dub_en["watch_seconds"] == 25000
    assert dub_en["episodes"] == {
        "10": {"link": "https://stream.example/ep10.mp4"},
    }


def test_inline_dict_value_modifiers_runtime_projection():
    src = """
json StreamCatalog {
    channels (dict) {
        @key str
        @value {
            display_title str from="channel_title"
            backup_stream str? from="backup.url"
            featured bool @omitempty from="meta.is_featured"
            notes str?
            internal_debug @skip
            bitrates (dict) {
                @key int
                @value {
                    endpoint str from="stream_endpoint"
                    codec str?
                    extra_tag @skip
                }
            }
        }
    }
}

(raw)struct Scraper {
    catalog {
        jsonify StreamCatalog
    }
}
"""
    _, ns = _compile_and_exec(src)

    payload = """{
        "channels": {
            "ch_main": {
                "channel_title": "Main Channel",
                "backup": {"url": "https://backup.example/stream"},
                "meta": {"is_featured": true},
                "notes": null,
                "internal_debug": "secret_token",
                "unmodeled_attr": 42,
                "bitrates": {
                    "1080": {
                        "stream_endpoint": "https://cdn.example/1080p",
                        "codec": "h264",
                        "extra_tag": "discard"
                    },
                    "720": {
                        "stream_endpoint": "https://cdn.example/720p",
                        "codec": null
                    }
                }
            },
            "ch_alt": {
                "channel_title": "Alternative Channel",
                "notes": "Community stream",
                "bitrates": {}
            }
        }
    }"""
    res = ns["Scraper"](payload).parse()
    channels = res["catalog"]["channels"]

    ch_main = channels["ch_main"]
    assert ch_main["display_title"] == "Main Channel"
    assert ch_main["backup_stream"] == "https://backup.example/stream"
    assert ch_main["featured"] is True
    assert ch_main["notes"] is None
    assert "internal_debug" not in ch_main
    assert "unmodeled_attr" not in ch_main
    assert ch_main["bitrates"] == {
        "1080": {
            "endpoint": "https://cdn.example/1080p",
            "codec": "h264",
        },
        "720": {
            "endpoint": "https://cdn.example/720p",
            "codec": None,
        },
    }
    assert "extra_tag" not in ch_main["bitrates"]["1080"]

    ch_alt = channels["ch_alt"]
    assert ch_alt["display_title"] == "Alternative Channel"
    assert ch_alt["backup_stream"] is None
    assert "featured" not in ch_alt
    assert ch_alt["notes"] == "Community stream"
    assert ch_alt["bitrates"] == {}

    # Validation errors on invalid payloads
    missing_required_payload = """{
        "channels": {
            "bad": {
                "backup": {"url": "http://x"},
                "bitrates": {}
            }
        }
    }"""
    Err = ns["SscJsonFieldMissingError"]
    with pytest.raises(
        Err,
        match=re.escape(
            "StreamCatalogChannelsValue.display_title: Required JSON field 'channel_title' (mapped to 'display_title') is missing"
        ),
    ):
        ns["Scraper"](missing_required_payload).parse()

    null_non_nullable_payload = """{
        "channels": {
            "bad": {
                "channel_title": null,
                "bitrates": {}
            }
        }
    }"""
    with pytest.raises(
        Err,
        match=re.escape(
            "StreamCatalogChannelsValue.display_title: Field 'channel_title' is null, but 'display_title' is not nullable"
        ),
    ):
        ns["Scraper"](null_non_nullable_payload).parse()


def test_top_level_dict_json_with_inline_value_block_projection():
    src = """
(dict)json Translations {
    @key str
    @value {
        title str from="wire_name"
        active bool
        description str?
        badge str @omitempty from="meta.badge"
        raw_token @skip
    }
}

(raw)struct Scraper {
    translations {
        jsonify Translations
    }
}
"""
    code, ns = _compile_and_exec(src)
    assert code.find(
        'TranslationsValueJson = TypedDict("TranslationsValueJson"'
    ) < code.find("TranslationsJson = Dict[str, TranslationsValueJson]")
    assert (
        "def _project_translations_value(data: Any) -> TranslationsValueJson:"
        in code
    )
    assert "def _project_translations(data: Any) -> TranslationsJson:" in code
    assert "_project_translations_value(_v)" in code
    assert "JSON_DESCRIPTOR_" not in code

    payload = """{
        "en": {
            "wire_name": "English",
            "active": true,
            "description": null,
            "raw_token": "secret_abc",
            "extra_field": 123
        },
        "ja": {
            "wire_name": "Japanese",
            "active": false,
            "description": "Original sound",
            "meta": {"badge": "original"}
        }
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["translations"] == {
        "en": {
            "title": "English",
            "active": True,
            "description": None,
        },
        "ja": {
            "title": "Japanese",
            "active": False,
            "description": "Original sound",
            "badge": "original",
        },
    }


def test_inline_dict_array_value_block_projection():
    src = """
json PlaylistLibrary {
    categories (dict) {
        @key str
        @value (array)PlaylistItem {
            track_id int from="id"
            title str
            lossless bool?
            discarded_blob @skip
        }
    }
}

(raw)struct Scraper {
    library {
        jsonify PlaylistLibrary
    }
}
"""
    code, ns = _compile_and_exec(src)
    assert 'PlaylistItemJson = TypedDict("PlaylistItemJson"' in code
    assert "'categories': Dict[str, List[PlaylistItemJson]]" in code
    assert "def _project_playlist_item(data: Any) -> PlaylistItemJson:" in code
    assert (
        "def _project_playlist_library(data: Any) -> PlaylistLibraryJson:"
        in code
    )
    assert "[_project_playlist_item(_x) for _x in ssc_expect_list(" in code
    assert "_project_playlist_library(json.loads(v))" in code
    assert "JSON_DESCRIPTOR_" not in code

    payload = """{
        "categories": {
            "rock": [
                {"id": 1, "title": "Song A", "lossless": true, "discarded_blob": "xxx", "meta": 1},
                {"id": 2, "title": "Song B", "lossless": null}
            ],
            "jazz": []
        }
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["library"]["categories"] == {
        "rock": [
            {"track_id": 1, "title": "Song A", "lossless": True},
            {"track_id": 2, "title": "Song B", "lossless": None},
        ],
        "jazz": [],
    }


def test_nested_dict_value_null_entry_projection():
    src = """
json MediaHub {
    seasons (dict) {
        @key str
        @value {
            season_num int
            episodes (dict) {
                @key int
                @value {
                    link str
                }
            }
        }
    }
}

(raw)struct Scraper {
    hub {
        jsonify MediaHub
    }
}
"""
    _, ns = _compile_and_exec(src)

    payload = """{
        "seasons": {
            "s1": {
                "season_num": 1,
                "episodes": {
                    "1": {"link": "https://stream.example/1"}
                }
            },
            "s2": null
        }
    }"""
    res = ns["Scraper"](payload).parse()
    assert res["hub"]["seasons"] == {
        "s1": {
            "season_num": 1,
            "episodes": {
                "1": {"link": "https://stream.example/1"},
            },
        },
        "s2": None,
    }
