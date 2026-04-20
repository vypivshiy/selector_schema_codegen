"""Tests for ssc_codegen.openapi — parser, converter, emitter, end-to-end."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssc_codegen.openapi.converter import (
    Endpoint,
    JsonField,
    JsonSchema,
    RequestConverter,
    SchemaConverter,
    _method_name,
    _placeholder_name,
    _to_snake,
    extract_base_url,
    topological_sort,
)
from ssc_codegen.openapi.emitter import emit_kdl
from ssc_codegen.openapi.parser import load_spec, normalize_spec, resolve_refs

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestParser:
    def test_load_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "spec.yaml"
        f.write_text("openapi: '3.0.0'\ninfo:\n  title: Test\n  version: '1.0'\n")
        spec = load_spec(f)
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Test"

    def test_load_json(self, tmp_path: Path) -> None:
        f = tmp_path / "spec.json"
        f.write_text(json.dumps({"openapi": "3.0.0", "info": {"title": "T"}}))
        spec = load_spec(f)
        assert spec["info"]["title"] == "T"

    def test_load_auto_detect_json_as_yaml(self, tmp_path: Path) -> None:
        """Valid JSON is also valid YAML, but JSON should be tried first."""
        f = tmp_path / "spec.yaml"
        f.write_text('{"openapi": "3.0.0"}')
        spec = load_spec(f)
        assert spec["openapi"] == "3.0.0"

    def test_resolve_ref(self) -> None:
        spec = {
            "components": {
                "schemas": {
                    "Pet": {"type": "object", "properties": {"name": {"type": "string"}}}
                }
            },
            "paths": {
                "/pets": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Pet"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
        }
        resolved = resolve_refs(spec)
        schema = resolved["paths"]["/pets"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert schema["type"] == "object"
        assert "name" in schema["properties"]

    def test_resolve_allof(self) -> None:
        spec = {
            "components": {
                "schemas": {
                    "Base": {"type": "object", "properties": {"id": {"type": "integer"}}},
                    "Extended": {
                        "allOf": [
                            {"$ref": "#/components/schemas/Base"},
                            {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                        ]
                    },
                }
            }
        }
        resolved = resolve_refs(spec)
        ext = resolved["components"]["schemas"]["Extended"]
        assert "id" in ext["properties"]
        assert "name" in ext["properties"]

    def test_normalize_swagger2(self) -> None:
        spec = {
            "swagger": "2.0",
            "definitions": {"Pet": {"type": "object"}},
            "responses": {"NotFound": {"description": "Not found"}},
        }
        result = normalize_spec(spec)
        assert "definitions" not in result
        assert "Pet" in result["components"]["schemas"]
        assert "NotFound" in result["components"]["responses"]


# ---------------------------------------------------------------------------
# Converter — helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    @pytest.mark.parametrize(
        ("inp", "exp"),
        [
            ("petId", "pet_id"),
            ("photoUrls", "photo_urls"),
            ("f[sorting]", "f_sorting"),
            ("f[age_ratings]", "f_age_ratings"),
            ("createdAt", "created_at"),
            ("id", "id"),
        ],
    )
    def test_to_snake(self, inp: str, exp: str) -> None:
        assert _to_snake(inp) == exp

    @pytest.mark.parametrize(
        ("inp", "exp"),
        [
            ("f[sorting]", "f_sorting"),
            ("f[age_ratings]", "f_age_ratings"),
            ("petId", "pet_id"),
        ],
    )
    def test_placeholder_name(self, inp: str, exp: str) -> None:
        assert _placeholder_name(inp) == exp

    @pytest.mark.parametrize(
        ("method", "path", "exp"),
        [
            ("get", "/pets", "get-pets"),
            ("get", "/pets/{petId}", "get-pets"),
            ("post", "/pets", "post-pets"),
            ("put", "/pets/{petId}", "put-pets"),
            ("delete", "/pets/{petId}", "delete-pets"),
            ("get", "/api/v1/catalogue", "get-api-v1-catalogue"),
        ],
    )
    def test_method_name(self, method: str, path: str, exp: str) -> None:
        assert _method_name(method, path) == exp


# ---------------------------------------------------------------------------
# SchemaConverter
# ---------------------------------------------------------------------------


class TestSchemaConverter:
    def test_basic_types(self) -> None:
        schemas = {
            "Item": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                    "price": {"type": "number"},
                    "active": {"type": "boolean"},
                },
                "required": ["name"],
            }
        }
        result = SchemaConverter().convert_schemas(schemas)
        assert len(result) == 1
        s = result[0]
        assert s.name == "Item"
        fields_by_name = {f.name: f for f in s.fields}
        assert not fields_by_name["name"].is_optional
        assert fields_by_name["count"].is_optional
        assert fields_by_name["price"].type_token == "float"

    def test_enum_comment(self) -> None:
        schemas = {
            "Item": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive"],
                    },
                },
            }
        }
        result = SchemaConverter().convert_schemas(schemas)
        f = result[0].fields[0]
        assert f.enum_comment is not None
        assert "active" in f.enum_comment

    def test_array_field(self) -> None:
        schemas = {
            "List": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            }
        }
        result = SchemaConverter().convert_schemas(schemas)
        assert result[0].fields[0].type_token == "(array)str"

    def test_ref_field(self) -> None:
        schemas = {
            "Order": {
                "type": "object",
                "properties": {
                    "pet": {"$ref": "#/components/schemas/Pet"},
                },
            },
            "Pet": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        }
        result = SchemaConverter().convert_schemas(schemas)
        by_name = {s.name: s for s in result}
        assert "Pet" in by_name["Order"].deps

    def test_alias(self) -> None:
        schemas = {
            "Item": {
                "type": "object",
                "properties": {
                    "photoUrls": {"type": "string"},
                },
            }
        }
        result = SchemaConverter().convert_schemas(schemas)
        f = result[0].fields[0]
        assert f.name == "photo_urls"
        assert f.alias == "photoUrls"

    def test_topological_sort(self) -> None:
        schemas = [
            JsonSchema(name="PetList", deps={"Pet"}),
            JsonSchema(name="Pet", deps={"Category"}),
            JsonSchema(name="Category", deps=set()),
        ]
        sorted_schemas = topological_sort(schemas)
        names = [s.name for s in sorted_schemas]
        assert names.index("Category") < names.index("Pet")
        assert names.index("Pet") < names.index("PetList")


# ---------------------------------------------------------------------------
# RequestConverter
# ---------------------------------------------------------------------------


class TestRequestConverter:
    def _make_spec(self, paths: dict) -> dict:
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "servers": [{"url": "https://api.example.com"}],
            "paths": paths,
            "components": {"schemas": {}},
        }

    def test_get_curl_format(self) -> None:
        spec = self._make_spec(
            {
                "/items": {
                    "get": {
                        "parameters": [
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            }
        )
        resolved = resolve_refs(spec)
        base_url = extract_base_url(resolved)
        eps = RequestConverter().convert_paths(resolved["paths"], base_url, {})
        assert len(eps) == 1
        assert eps[0].request.format == "curl"
        assert "limit:int?" in eps[0].request.payload

    def test_post_raw_http_format(self) -> None:
        spec = self._make_spec(
            {
                "/items": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"name": {"type": "string"}},
                                        "required": ["name"],
                                    }
                                }
                            }
                        },
                        "responses": {"201": {"description": "created"}},
                    }
                }
            }
        )
        resolved = resolve_refs(spec)
        base_url = extract_base_url(resolved)
        eps = RequestConverter().convert_paths(resolved["paths"], base_url, {})
        assert len(eps) == 1
        assert eps[0].request.format == "raw_http"
        assert "POST /items HTTP/1.1" in eps[0].request.payload
        assert '"name": "{{name:str}}"' in eps[0].request.payload

    def test_bracket_query_params(self) -> None:
        spec = self._make_spec(
            {
                "/catalogue": {
                    "get": {
                        "parameters": [
                            {
                                "name": "f[sorting]",
                                "in": "query",
                                "style": "form",
                                "explode": False,
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "f[age_ratings]",
                                "in": "query",
                                "style": "form",
                                "explode": False,
                                "schema": {"type": "array", "items": {"type": "string"}},
                            },
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            }
        )
        resolved = resolve_refs(spec)
        base_url = extract_base_url(resolved)
        eps = RequestConverter().convert_paths(resolved["paths"], base_url, {})
        payload = eps[0].request.payload
        assert "f[sorting]={{f_sorting:str?}}" in payload
        assert "f[age_ratings]={{f_age_ratings:str[]?|csv}}" in payload

    def test_path_param_placeholder(self) -> None:
        spec = self._make_spec(
            {
                "/items/{itemId}": {
                    "get": {
                        "parameters": [
                            {
                                "name": "itemId",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            }
        )
        resolved = resolve_refs(spec)
        base_url = extract_base_url(resolved)
        eps = RequestConverter().convert_paths(resolved["paths"], base_url, {})
        assert "{{item_id:int}}" in eps[0].request.payload

    def test_error_extraction(self) -> None:
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "T", "version": "1.0"},
            "servers": [{"url": "https://api.example.com"}],
            "paths": {
                "/items/{id}": {
                    "get": {
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "ok"},
                            "404": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ApiError"}
                                    }
                                }
                            },
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "ApiError": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                    }
                }
            },
        }
        # Use unresolved spec so $ref is still present for error extraction
        base_url = extract_base_url(spec)
        eps = RequestConverter().convert_paths(
            spec["paths"], base_url, spec["components"]["schemas"]
        )
        assert len(eps[0].errors) == 1
        assert eps[0].errors[0].status == 404
        assert eps[0].errors[0].schema_name == "ApiError"


# ---------------------------------------------------------------------------
# Emitter tests
# ---------------------------------------------------------------------------


class TestEmitter:
    def test_basic_emission(self) -> None:
        schemas = [
            JsonSchema(
                name="Category",
                fields=[
                    JsonField(name="id", type_token="int"),
                    JsonField(name="name", type_token="str"),
                ],
            ),
        ]
        endpoints = [
            Endpoint(
                method="get",
                path="/categories",
                request=__import__(
                    "ssc_codegen.openapi.converter",
                    fromlist=["RequestBlock"],
                ).RequestBlock(
                    name="list-categories",
                    format="curl",
                    payload="curl 'https://api.example.com/categories'",
                    doc="List all categories",
                    response_schema="Category",
                ),
            )
        ]
        text = emit_kdl("Test API", "https://api.example.com", schemas, endpoints, [])
        assert "json Category {" in text
        assert "struct TestApi type=rest" in text
        assert "name=list-categories" in text
        assert "response=Category" in text

    def test_enum_comment_in_output(self) -> None:
        schemas = [
            JsonSchema(
                name="Item",
                fields=[
                    JsonField(
                        name="status",
                        type_token="str",
                        is_optional=True,
                        enum_comment='// original: enum ["active", "inactive"]',
                    ),
                ],
            ),
        ]
        text = emit_kdl("Test", "https://api.example.com", schemas, [], [])
        assert "// original: enum" in text
        assert "status str?" in text

    def test_alias_in_output(self) -> None:
        schemas = [
            JsonSchema(
                name="Pet",
                fields=[
                    JsonField(name="photo_urls", type_token="(array)str", alias="photoUrls"),
                ],
            ),
        ]
        text = emit_kdl("Test", "https://api.example.com", schemas, [], [])
        assert 'photo_urls (array)str "photoUrls"' in text


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_petstore_yaml(self, tmp_path: Path) -> None:
        from ssc_codegen.openapi import convert_openapi

        out = tmp_path / "petstore.kdl"
        result = convert_openapi(
            FIXTURES / "petstore_openapi.yaml", output_path=out
        )
        assert out.exists()
        assert "json Category {" in result
        assert "json Pet {" in result
        assert "json ApiError {" in result
        assert "struct PetClinicApi type=rest" in result
        assert "name=get-pet" in result
        assert "name=post-pet" in result
        assert "@error 400 ApiError" in result
        assert "@error 404 ApiError" in result

    def test_anime_bracket_params(self, tmp_path: Path) -> None:
        from ssc_codegen.openapi import convert_openapi

        out = tmp_path / "anime.kdl"
        result = convert_openapi(
            FIXTURES / "anime_openapi.yaml", output_path=out
        )
        assert "f[sorting]={{f_sorting:str?}}" in result
        assert "f[age_ratings]={{f_age_ratings:str[]?|csv}}" in result
        assert "// original: enum" in result

    def test_endpoint_filter(self, tmp_path: Path) -> None:
        from ssc_codegen.openapi import convert_openapi

        out = tmp_path / "partial.kdl"
        result = convert_openapi(
            FIXTURES / "petstore_openapi.yaml",
            output_path=out,
            endpoints=[("GET", "/pet")],
        )
        assert "name=get-pet" in result
        # Other endpoints should be excluded
        assert "name=post-pet" not in result

    def test_petstore_lint_passes(self, tmp_path: Path) -> None:
        from ssc_codegen.linter import lint_string
        from ssc_codegen.openapi import convert_openapi

        result = convert_openapi(FIXTURES / "petstore_openapi.yaml")
        lint_result = lint_string(result)
        if lint_result.has_errors():
            pytest.fail(
                f"Lint errors:\n{lint_result.format()}\n\nGenerated:\n{result}"
            )

    def test_anime_lint_passes(self, tmp_path: Path) -> None:
        from ssc_codegen.linter import lint_string
        from ssc_codegen.openapi import convert_openapi

        result = convert_openapi(FIXTURES / "anime_openapi.yaml")
        lint_result = lint_string(result)
        if lint_result.has_errors():
            pytest.fail(
                f"Lint errors:\n{lint_result.format()}\n\nGenerated:\n{result}"
            )
