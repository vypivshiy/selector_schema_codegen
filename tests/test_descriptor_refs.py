from dataclasses import FrozenInstanceError

import pytest

from ssc_codegen.ast import JsonDef
from ssc_codegen.core import parse_module
from ssc_codegen.naming import json_descriptor_var_name
from ssc_codegen.traversal.utils import (
    DescriptorRef,
    json_def_descriptors,
)


def _get_json_defs(src: str) -> dict[str, JsonDef]:
    module, diags = parse_module(src)
    assert not any(d.severity.name == "ERROR" for d in diags)
    return {n.name: n for n in module.body if isinstance(n, JsonDef)}


def test_json_descriptor_var_name_canonical():
    assert json_descriptor_var_name("Episode") == "JSON_DESCRIPTOR_EPISODE"
    assert (
        json_descriptor_var_name("CatalogReleasesResponse")
        == "JSON_DESCRIPTOR_CATALOG_RELEASES_RESPONSE"
    )
    assert (
        json_descriptor_var_name("catalog_releases_response")
        == "JSON_DESCRIPTOR_CATALOG_RELEASES_RESPONSE"
    )
    assert (
        json_descriptor_var_name("catalog-releases-response")
        == "JSON_DESCRIPTOR_CATALOG_RELEASES_RESPONSE"
    )
    assert (
        json_descriptor_var_name("userProfile")
        == "JSON_DESCRIPTOR_USER_PROFILE"
    )
    assert (
        json_descriptor_var_name("_private_schema")
        == "JSON_DESCRIPTOR_PRIVATE_SCHEMA"
    )
    assert json_descriptor_var_name("__internal") == "JSON_DESCRIPTOR_INTERNAL"
    assert (
        json_descriptor_var_name("Item2Release")
        == "JSON_DESCRIPTOR_ITEM2_RELEASE"
    )


def test_descriptor_ref_dataclass_properties():
    ref = DescriptorRef("Episode")
    assert ref.schema_name == "Episode"
    assert ref == DescriptorRef("Episode")
    assert hash(ref) == hash(DescriptorRef("Episode"))
    assert ref != DescriptorRef("Other")

    with pytest.raises(FrozenInstanceError):
        ref.schema_name = "Modified"  # type: ignore[misc]


def test_descriptors_primitive_leaf_schema():
    src = """
json GeoLocation {
    latitude float from="lat"
    longitude float from="lng"
    accuracy int?
}
"""
    defs = _get_json_defs(src)
    desc = json_def_descriptors(defs["GeoLocation"], defs)

    assert desc == {
        "latitude": ("lat", False, False, None),
        "longitude": ("lng", False, False, None),
        "accuracy": ("accuracy", True, False, None),
    }


def test_descriptors_single_nested_schema_ref():
    src = """
json Author {
    id int
    name str
}

json Book {
    id int
    title str
    author Author
}
"""
    defs = _get_json_defs(src)
    book_desc = json_def_descriptors(defs["Book"], defs)

    assert book_desc["id"] == ("id", False, False, None)
    assert book_desc["title"] == ("title", False, False, None)

    # author must be DescriptorRef, NOT an inlined dict
    wire_path, is_opt, is_omit, nested = book_desc["author"]
    assert wire_path == "author"
    assert is_opt is False
    assert is_omit is False
    assert isinstance(nested, DescriptorRef)
    assert nested == DescriptorRef("Author")
    assert nested.schema_name == "Author"


def test_descriptors_array_of_schema_ref():
    src = """
json Genre {
    name str
}

json Release {
    id int
    genres (array)Genre
}
"""
    defs = _get_json_defs(src)
    release_desc = json_def_descriptors(defs["Release"], defs)

    wire_path, is_opt, is_omit, nested = release_desc["genres"]
    assert wire_path == "genres"
    assert is_opt is False
    assert is_omit is False
    assert isinstance(nested, list)
    assert len(nested) == 1
    assert isinstance(nested[0], DescriptorRef)
    assert nested[0] == DescriptorRef("Genre")


def test_descriptors_inline_dict_with_schema_ref():
    src = """
json Episode {
    id int
    title str
}

json Catalog {
    id int
    episodes (dict) {
        @key str
        @value Episode
    }
}
"""
    defs = _get_json_defs(src)
    catalog_desc = json_def_descriptors(defs["Catalog"], defs)

    wire_path, is_opt, is_omit, nested = catalog_desc["episodes"]
    assert wire_path == "episodes"
    assert is_opt is False
    assert is_omit is False
    assert nested == {"__dict__": True, "__value__": DescriptorRef("Episode")}


def test_descriptors_inline_dict_with_array_of_schema_ref():
    src = """
json Episode {
    id int
    title str
}

json Series {
    id int
    seasons (dict) {
        @key str
        @value (array)Episode
    }
}
"""
    defs = _get_json_defs(src)
    series_desc = json_def_descriptors(defs["Series"], defs)

    wire_path, _is_opt, _is_omit, nested = series_desc["seasons"]
    assert wire_path == "seasons"
    assert nested == {"__dict__": True, "__value__": [DescriptorRef("Episode")]}


def test_descriptors_top_level_dict_with_schema_ref():
    src = """
json Episode {
    id int
    title str
}

(dict)json EpisodeMap {
    @key str
    @value Episode
}
"""
    defs = _get_json_defs(src)
    desc = json_def_descriptors(defs["EpisodeMap"], defs)

    assert desc == {"__dict__": True, "__value__": DescriptorRef("Episode")}


def test_descriptors_top_level_dict_with_array_schema_ref():
    src = """
json Episode {
    id int
    title str
}

(dict)json SeasonMap {
    @key int
    @value (array)Episode
}
"""
    defs = _get_json_defs(src)
    desc = json_def_descriptors(defs["SeasonMap"], defs)

    assert desc == {"__dict__": True, "__value__": [DescriptorRef("Episode")]}


def test_descriptors_top_level_dict_primitive():
    src = """
(dict)json Translations {
    @key str
    @value (array)str
}
"""
    defs = _get_json_defs(src)
    desc = json_def_descriptors(defs["Translations"], defs)

    assert desc == {"__dict__": True, "__value__": None}


def test_descriptors_skip_and_modifiers():
    src = """
json Item {
    id int
    internal_token str @skip
    custom_name str from="wire_name"
    optional_tag str?
    omitted_count int @omitempty
}
"""
    defs = _get_json_defs(src)
    desc = json_def_descriptors(defs["Item"], defs)

    assert "internal_token" not in desc
    assert desc["custom_name"] == ("wire_name", False, False, None)
    assert desc["optional_tag"] == ("optional_tag", True, False, None)
    assert desc["omitted_count"] == ("omitted_count", False, True, None)


def test_descriptors_no_inline_dictionary_duplication():
    src = """
json Image {
    url str
}

json Poster {
    image Image
}

json Catalog {
    poster Poster
    all_images (array)Image
}
"""
    defs = _get_json_defs(src)
    catalog_desc = json_def_descriptors(defs["Catalog"], defs)

    # Verify that catalog_desc references Poster via DescriptorRef,
    # NOT inlining Image descriptors inside Poster
    poster_ref = catalog_desc["poster"][3]
    assert isinstance(poster_ref, DescriptorRef)
    assert poster_ref.schema_name == "Poster"

    images_ref = catalog_desc["all_images"][3]
    assert isinstance(images_ref, list)
    assert isinstance(images_ref[0], DescriptorRef)
    assert images_ref[0].schema_name == "Image"


def test_descriptors_without_definitions_map():
    src = """
json Author {
    id int
}

json Genre {
    id int
}

json Book {
    id int
    author Author
    genres (array)Genre
}
"""
    defs = _get_json_defs(src)
    # Calling json_def_descriptors without definitions mapping should still emit DescriptorRef
    desc = json_def_descriptors(defs["Book"])

    assert desc["author"][3] == DescriptorRef("Author")
    assert desc["genres"][3] == [DescriptorRef("Genre")]
