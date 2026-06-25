from pathlib import Path

import pytest

from ssc_codegen.ast import (
    Assert,
    Attr,
    CssSelect,
    CssSelectAll,
    XpathSelectAll,
    Filter,
    Fmt,
    InitField,
    JsonDef,
    JsonDefField,
    Jsonify,
    Lower,
    Match,
    Nested,
    PreValidate,
    ReplMap,
    Return,
    Self,
    SplitDoc,
    StartParse,
    Struct,
    StructBase,
    StructRest,
    StructType,
    TableConfig,
    TableMatchKey,
    TableRows,
    Text,
    TypeDef,
    Value,
)
from ssc_codegen.ast.predicate_ops import LogicNot, PredContains, PredEq
from ssc_codegen.ast.types import VariableType
from ssc_codegen.core import parse_module
from kdlquery import KDL2CSTParser, KDLParseError, Severity


EXAMPLES = [
    Path("examples/booksToScrape.kdl"),
    Path("examples/quotesToScrape.kdl"),
    Path("examples/imdbcom.kdl"),
]


def _parse(src: str):
    module, diagnostics = parse_module(src)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    if errors:
        raise AssertionError("; ".join(d.message for d in errors))
    return module


def _parse_example(path: str) -> object:
    return _parse(Path(path).read_text(encoding="utf-8-sig"))


def _body_of_type(nodes: list[object], cls: type):
    return [node for node in nodes if isinstance(node, cls)]


def _struct(module, name: str) -> Struct:
    return next(
        node
        for node in module.body
        if isinstance(node, Struct) and node.name == name
    )


def _json_def(module, name: str) -> JsonDef:
    return next(
        node
        for node in module.body
        if isinstance(node, JsonDef) and node.name == name
    )


def _field(struct: Struct, name: str):
    return next(
        node for node in struct.body if getattr(node, "name", None) == name
    )


def test_parse_document_decodes_literals_and_annotations():
    doc = KDL2CSTParser().parse(
        "\n".join(
            [
                'define S="abc"',
                'define R=#"raw"#',
                "define T=#true",
                "define F=#false",
                "define N=#null",
                "define I=123",
                "define X=1.25",
                "json Q {",
                "    tags (array)str",
                "}",
            ]
        )
    )

    defines = [n for n in doc.nodes if n.name.value == "define"]
    assert (
        next(e.value.value for e in defines[0].entries if hasattr(e, "key"))
        == "abc"
    )
    assert (
        next(e.value.value for e in defines[1].entries if hasattr(e, "key"))
        == "raw"
    )
    assert (
        next(e.value.value for e in defines[2].entries if hasattr(e, "key"))
        is True
    )
    assert (
        next(e.value.value for e in defines[3].entries if hasattr(e, "key"))
        is False
    )
    assert (
        next(e.value.value for e in defines[4].entries if hasattr(e, "key"))
        is None
    )
    assert (
        next(e.value.value for e in defines[5].entries if hasattr(e, "key"))
        == 123
    )
    assert (
        next(e.value.value for e in defines[6].entries if hasattr(e, "key"))
        == 1.25
    )

    json_node = [n for n in doc.nodes if n.name.value == "json"][0]
    # CST-level: type annotation prefix "(array)" is stripped; value is "str"
    assert json_node.children[0].entries[0].value.value == "str"


def test_parse_document_raises_parse_error_on_invalid_syntax():
    with pytest.raises(KDLParseError):
        KDL2CSTParser().parse('struct Demo {\n  title {\n    css ".x"\n')


def test_parser_parses_real_examples():
    for path in EXAMPLES:
        module = _parse(path.read_text(encoding="utf-8-sig"))
        assert type(module).__name__ == "Module"
        assert len(module.body) >= 4


def test_parser_builds_expected_counts_for_quotes_example():
    module = _parse_example("examples/quotesToScrape.kdl")
    structs = _body_of_type(module.body, Struct)
    json_defs = _body_of_type(module.body, JsonDef)
    typedefs = _body_of_type(module.body, TypeDef)

    assert len(structs) == 1
    assert len(json_defs) == 2
    assert len(typedefs) == 1
    assert structs[0].name == "Main"


def test_parser_resolves_jsonify_and_nested_nodes():
    module = _parse_example("examples/imdbcom.kdl")
    search_page = _struct(module, "SearchPage")

    json_parse = _field(search_page, "json-parse")
    selector_parse = _field(search_page, "selector-parse")

    jsonify = next(
        node for node in json_parse.body if isinstance(node, Jsonify)
    )

    assert jsonify.schema_name == "Content"
    assert jsonify.path == "props.pageProps.titleResults"
    assert jsonify.accept == VariableType.STRING
    assert jsonify.ret == VariableType.JSON
    assert jsonify.is_array is False

    # nested parsing is covered on an example that actually produces Nested AST nodes
    assert selector_parse.accept == VariableType.DOCUMENT


def test_parser_builds_nested_node_for_inline_pipeline():
    module = _parse(
        """
        struct Child {
            value { css ".x"; text }
        }

        struct Main {
            child { nested Child }
        }
        """
    )
    main = _struct(module, "Main")
    child = _field(main, "child")

    nested = next(node for node in child.body if isinstance(node, Nested))
    assert nested.struct_name == "Child"
    assert nested.accept == VariableType.DOCUMENT
    assert nested.ret == VariableType.NESTED
    assert nested.is_array is False
    assert isinstance(child.body[-1], Return)


def test_parser_supports_inline_operation_chain_css_attr():
    module = _parse(
        """
        struct Main {
            url { css "a"; attr "href" }
        }
        """
    )
    main = _struct(module, "Main")
    url = _field(main, "url")

    assert isinstance(url.body[0], CssSelect)
    assert isinstance(url.body[1], Attr)
    assert isinstance(url.body[-1], Return)
    assert url.accept == VariableType.DOCUMENT
    assert url.ret == VariableType.STRING


def test_parser_supports_css_pattern_match_block():
    module = _parse(
        """
        define MAIN-TITLE=".article h1"

        struct Main {
            title {
                css {
                    MAIN-TITLE
                    "h1"
                }
                text
            }
        }
        """
    )
    main = _struct(module, "Main")
    title = _field(main, "title")

    assert isinstance(title.body[0], CssSelect)
    assert title.body[0].queries == [".article h1", "h1"]
    assert isinstance(title.body[1], Text)
    assert isinstance(title.body[-1], Return)


def test_parser_supports_xpath_all_pattern_match_block():
    module = _parse(
        """
        struct Main {
            links {
                xpath-all {
                    "//a[@href]"
                    "//area[@href]"
                }
                attr "href"
            }
        }
        """
    )
    main = _struct(module, "Main")
    links = _field(main, "links")

    assert isinstance(links.body[0], XpathSelectAll)
    assert links.body[0].queries == ["//a[@href]", "//area[@href]"]
    assert isinstance(links.body[1], Attr)
    assert isinstance(links.body[-1], Return)


def test_parser_supports_inline_raw_extractor():
    module = _parse(
        """
        struct Main {
            html { raw }
        }
        """
    )
    main = _struct(module, "Main")
    html = _field(main, "html")

    assert type(html.body[0]).__name__ == "Raw"
    assert isinstance(html.body[-1], Return)
    assert html.accept == VariableType.DOCUMENT
    assert html.ret == VariableType.STRING


def test_parser_supports_inline_nested_in_books_example():
    module = _parse_example("examples/booksToScrape.kdl")
    main_catalogue = _struct(module, "MainCatalogue")
    books = _field(main_catalogue, "books")

    nested = next(node for node in books.body if isinstance(node, Nested))
    assert nested.struct_name == "Book"
    assert nested.is_array is True
    assert books.ret == VariableType.NESTED
    assert isinstance(books.body[-1], Return)


def test_parser_supports_inline_assert_block():
    module = _parse(
        """
        struct Main {
            title { css ".title"; text; assert { contains "foo" } }
        }
        """
    )
    main = _struct(module, "Main")
    title = _field(main, "title")

    assert [type(node).__name__ for node in title.body] == [
        "CssSelect",
        "Text",
        "Assert",
        "Return",
    ]
    assert_node = next(node for node in title.body if isinstance(node, Assert))
    assert [type(node).__name__ for node in assert_node.body] == [
        "PredContains"
    ]
    assert isinstance(assert_node.body[0], PredContains)
    assert title.ret == VariableType.STRING


def test_parser_supports_inline_match_block():
    module = _parse(
        """
        struct Main type=table {
            @table { css "table" }
            @rows { css-all "tr" }
            @match { css "th"; text }
            @value { css "td"; text }
            row-name { match { eq "Name" } }
        }
        """
    )
    main = _struct(module, "Main")
    row_name = _field(main, "row-name")

    assert [type(node).__name__ for node in row_name.body] == [
        "Match",
        "Return",
    ]
    match_node = row_name.body[0]
    assert isinstance(match_node, Match)
    assert [type(node).__name__ for node in match_node.body] == ["PredEq"]
    assert isinstance(match_node.body[0], PredEq)
    assert row_name.ret == VariableType.STRING


def test_parser_supports_inline_filter_not_block():
    module = _parse(
        """
        struct Main {
            links { css-all "a"; attr href; filter { not { contains "utm" } } }
        }
        """
    )
    main = _struct(module, "Main")
    links = _field(main, "links")

    assert [type(node).__name__ for node in links.body] == [
        "CssSelectAll",
        "Attr",
        "Filter",
        "Return",
    ]
    assert isinstance(links.body[0], CssSelectAll)
    filter_node = next(node for node in links.body if isinstance(node, Filter))
    assert [type(node).__name__ for node in filter_node.body] == ["LogicNot"]
    assert isinstance(filter_node.body[0], LogicNot)
    assert [type(node).__name__ for node in filter_node.body[0].body] == [
        "PredContains"
    ]
    assert isinstance(filter_node.body[0].body[0], PredContains)
    assert links.ret == VariableType.STRING
    assert links.is_array


def test_parser_resolves_json_definition_field_shapes():
    module = _parse_example("examples/imdbcom.kdl")
    results = _json_def(module, "Results")
    content = _json_def(module, "Content")

    results_fields = {field.name: field for field in results.body}
    content_fields = {field.name: field for field in content.body}

    assert (
        results_fields["titlePosterImageModel"].ret_type_info.ref
        == "TitlePosterImageModel"
    )
    assert (
        results_fields["titlePosterImageModel"].ret_type_info.is_array is False
    )
    assert results_fields["topCredits"].ret_type_info.is_array is True
    assert results_fields["topCredits"].ret_type_info.ref is None
    assert results_fields["seriesId"].ret_type_info.is_optional is True
    assert results_fields["seriesSeasonText"].ret_type_info.is_optional is True

    assert content_fields["results"].ret_type_info.is_array is True
    assert content_fields["results"].ret_type_info.ref == "Results"
    assert content_fields["hasExactMatches"].ret_type_info.is_optional is False


def test_parser_handles_table_struct_special_nodes_and_field_types():
    module = _parse_example("examples/booksToScrape.kdl")
    product_info = _struct(module, "ProductInfo")

    assert (
        isinstance(product_info, Struct)
        and product_info.type == StructType.TABLE
    )

    table_cfg = next(
        node for node in product_info.body if isinstance(node, TableConfig)
    )
    table_rows = next(
        node for node in product_info.body if isinstance(node, TableRows)
    )
    table_match = next(
        node for node in product_info.body if isinstance(node, TableMatchKey)
    )
    value_node = next(
        node for node in product_info.body if isinstance(node, Value)
    )
    pre_validate = next(
        node for node in product_info.body if isinstance(node, PreValidate)
    )
    start_parse = product_info.body[-1]
    number_reviews = _field(product_info, "number-of-reviews")

    assert isinstance(start_parse, StartParse)
    assert start_parse.use_pre_validate is True
    assert start_parse.use_split_doc is False
    assert (
        isinstance(product_info, Struct)
        and product_info.type == StructType.TABLE
    )
    assert isinstance(table_cfg, TableConfig)
    assert isinstance(table_rows, TableRows)
    assert isinstance(table_match, TableMatchKey)

    assert value_node.ret == VariableType.STRING
    assert isinstance(pre_validate.body[0], Assert)
    assert type(number_reviews.body[0]).__name__ == "Fallback"
    assert isinstance(number_reviews.body[0].body[0], Match)
    assert isinstance(number_reviews.body[-1], Return)
    assert number_reviews.ret == VariableType.INT


def test_parser_inlines_define_blocks_and_resolves_init_references():
    module = _parse(
        """
        define COMMON {
            trim
            lower
        }

        struct Main {
            @init {
                seed {
                    css title
                    text
                }
            }

            inline-define {
                css title
                text
                COMMON
            }

            from-init {
                @seed
                fmt "Hello {{}}"
            }
        }
        """
    )
    main = _struct(module, "Main")

    init_field = next(
        node
        for node in main.init.body
        if isinstance(node, InitField) and node.name == "seed"
    )
    inline_define = _field(main, "inline-define")
    from_init = _field(main, "from-init")

    assert [type(node).__name__ for node in init_field.body] == [
        "CssSelect",
        "Text",
        "Return",
    ]
    assert init_field.ret == VariableType.STRING

    assert [type(node).__name__ for node in inline_define.body] == [
        "CssSelect",
        "Text",
        "Trim",
        "Lower",
        "Return",
    ]
    assert isinstance(inline_define.body[0], CssSelect)
    assert isinstance(inline_define.body[1], Text)
    assert isinstance(inline_define.body[3], Lower)
    assert inline_define.ret == VariableType.STRING

    assert isinstance(from_init.body[0], Self)
    assert from_init.body[0].name == "seed"
    assert from_init.body[0].ret == VariableType.STRING
    assert isinstance(from_init.body[1], Fmt)
    assert isinstance(from_init.body[-1], Return)
    assert from_init.ret == VariableType.STRING


def test_parser_rejects_legacy_self_syntax():
    _, diagnostics = parse_module(
        """
        struct Main {
            @init {
                seed {
                    text
                }
            }

            from-init {
                self seed
                fmt "Hello {{}}"
            }
        }
        """
    )
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert errors
    assert "no longer supported" in errors[0].message


def test_parser_expands_repl_map_define_and_adds_return():
    module = _parse_example("examples/booksToScrape.kdl")
    book = _struct(module, "Book")
    rating = _field(book, "rating")

    repl = next(node for node in rating.body if isinstance(node, ReplMap))
    assert repl.replacements["One"] == "1"
    assert repl.replacements["Five"] == "5"
    assert rating.ret == VariableType.INT
    assert isinstance(rating.body[-1], Return)


def test_parser_preserves_split_doc_and_start_parse_flags():
    module = _parse_example("examples/booksToScrape.kdl")
    book = _struct(module, "Book")
    start_parse = book.body[-1]

    assert isinstance(
        next(node for node in book.body if isinstance(node, SplitDoc)), SplitDoc
    )
    assert isinstance(start_parse, StartParse)
    assert start_parse.use_split_doc is True
    assert start_parse.use_pre_validate is True
    assert {field.name for field in start_parse.fields} == {
        "name",
        "image-url",
        "rating",
        "price",
        "url",
    }


# ── json linter tests ──────────────────────────────────────────────────────────


def _lint_errors(src: str) -> list[str]:
    _, diagnostics = parse_module(src)
    return [d.message for d in diagnostics if d.severity == Severity.ERROR]


def _lint_warnings(src: str) -> list[str]:
    _, diagnostics = parse_module(src)
    return [d.message for d in diagnostics if d.severity == Severity.WARNING]


def test_json_lint_empty_name():
    errs = _lint_errors("json { x str }")
    assert any("'json' requires a name" in e for e in errs)


def test_json_lint_duplicate_name():
    errs = _lint_errors("json Foo { x str }\njson Foo { y int }")
    assert any("duplicate json definition 'Foo'" in e for e in errs)


def test_json_lint_empty_path_property():
    errs = _lint_errors('json Foo path="" { x str }')
    assert any("'path' property must be a non-empty string" in e for e in errs)


def test_json_lint_valid_array_and_path():
    errs = _lint_errors('(array)json Foo path="data.items" { x str }')
    assert len(errs) == 0


def test_json_lint_duplicate_fields():
    errs = _lint_errors("json Foo { x str\nx int }")
    assert any("duplicate json field 'x'" in e for e in errs)


def test_json_lint_field_missing_type():
    errs = _lint_errors("json Foo { x }")
    assert any("requires a type" in e for e in errs)


def test_json_lint_field_skip_without_type():
    errs = _lint_errors("json Foo { x @skip }")
    assert len(errs) == 0


def test_json_lint_unknown_modifier():
    errs = _lint_errors("json Foo { x str @invalid }")
    assert any("unknown json field modifier '@invalid'" in e for e in errs)


def test_json_lint_undefined_ref():
    errs = _lint_errors("json A { x NonExistent }")
    assert any(
        "references undefined json definition 'NonExistent'" in e for e in errs
    )


def test_json_lint_valid_ref():
    errs = _lint_errors("json A { x str }\njson B { y A }")
    assert len(errs) == 0


def test_json_lint_circular_ref():
    errs = _lint_errors("json A { x B }\njson B { y A }")
    assert any("circular reference" in e for e in errs)


def test_json_lint_optional_suffix_ok():
    errs = _lint_errors("json Foo { x str? }")
    assert len(errs) == 0


def test_json_lint_optional_modifier_now_error():
    """@optional was removed; it should produce an unknown modifier error."""
    errs = _lint_errors("json Foo { x str @optional }")
    assert any("unknown json field modifier '@optional'" in e for e in errs)


def test_json_lint_omitempty_modifier_ok():
    errs = _lint_errors("json Foo { x str @omitempty }")
    assert len(errs) == 0


# ── REST cross-ref linter tests ───────────────────────────────────────────────


def test_rest_response_undefined_json():
    errs = _lint_errors(
        "struct API type=rest {\n"
        '    @request response=Product """\n'
        "    GET /items HTTP/1.1\n"
        "    Host: x.com\n"
        '    """\n'
        "}\n"
    )
    assert any(
        "references undefined json definition 'Product'" in e for e in errs
    )


def test_rest_error_undefined_json():
    errs = _lint_errors("struct API type=rest {\n    @error 404 NotFound\n}\n")
    assert any(
        "references undefined json definition 'NotFound'" in e for e in errs
    )


def test_rest_response_valid_json():
    errs = _lint_errors(
        "json Product { id int }\n"
        "struct API type=rest {\n"
        '    @request response=Product """\n'
        "    GET /items HTTP/1.1\n"
        "    Host: x.com\n"
        '    """\n'
        "}\n"
    )
    assert not any("references undefined" in e for e in errs)


def test_rest_error_valid_json():
    errs = _lint_errors(
        "json Err { code int }\nstruct API type=rest {\n    @error 404 Err\n}\n"
    )
    assert not any("references undefined" in e for e in errs)


def test_rest_response_empty_ok():
    errs = _lint_errors(
        "struct API type=rest {\n"
        '    @request """\n'
        "    GET /items HTTP/1.1\n"
        "    Host: x.com\n"
        '    """\n'
        "}\n"
    )
    assert not any("references undefined" in e for e in errs)


# ── Block define expansion in json ────────────────────────────────────────────


def test_json_define_expansion_basic():
    """Block define children expand as json fields."""
    module = _parse(
        "define CORE {\n"
        "    id int\n"
        "    name str\n"
        "}\n"
        "json Foo {\n"
        "    CORE\n"
        "    extra bool\n"
        "}\n"
    )
    foo = _json_def(module, "Foo")
    fields = {f.name: f for f in foo.body if isinstance(f, JsonDefField)}
    assert "id" in fields
    assert "name" in fields
    assert "extra" in fields
    assert fields["id"].ret == VariableType.INT
    assert fields["name"].ret == VariableType.STRING
    assert fields["extra"].ret == VariableType.BOOL


def test_json_define_expansion_multiple_jsons():
    """Same define expands in multiple json schemas."""
    module = _parse(
        "define BASE {\n"
        "    id int\n"
        "    title str\n"
        "}\n"
        "json Summary {\n"
        "    BASE\n"
        "}\n"
        "json Detail {\n"
        "    BASE\n"
        "    description str?\n"
        "}\n"
    )
    summary = _json_def(module, "Summary")
    detail = _json_def(module, "Detail")
    assert [f.name for f in summary.body if isinstance(f, JsonDefField)] == [
        "id",
        "title",
    ]
    assert [f.name for f in detail.body if isinstance(f, JsonDefField)] == [
        "id",
        "title",
        "description",
    ]


def test_json_define_expansion_lint_ok():
    """Define expansion passes lint with no errors."""
    errs = _lint_errors(
        "define F {\n    x int\n    y str\n}\njson A {\n    F\n    z bool\n}\n"
    )
    assert len(errs) == 0


def test_json_define_expansion_duplicate_field():
    """Duplicate field across define and direct field is caught."""
    errs = _lint_errors(
        "define F {\n    x int\n}\njson A {\n    F\n    x str\n}\n"
    )
    assert any("duplicate json field 'x'" in e for e in errs)


def test_json_define_expansion_ref_in_define():
    """Define fields can reference other json schemas."""
    module = _parse(
        "define ITEM {\n"
        "    id int\n"
        "    tag Tag\n"
        "}\n"
        "json Tag {\n"
        "    name str\n"
        "}\n"
        "json Item {\n"
        "    ITEM\n"
        "}\n"
    )
    item = _json_def(module, "Item")
    tag_field = next(
        f for f in item.body if isinstance(f, JsonDefField) and f.name == "tag"
    )
    assert tag_field.ret_type_info.ref == "Tag"
    assert tag_field.ret == VariableType.JSON


def test_json_define_expansion_bare_name_without_define_is_field():
    """A bare name that's NOT a define gets a 'requires a type' error."""
    errs = _lint_errors("json A {\n    mystery\n}\n")
    assert any("requires a type" in e for e in errs)


# ── JSON field type / modifier / jsonify / REST form tests (file-based) ───────

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(*parts: str) -> str:
    return (_FIXTURES.joinpath(*parts)).read_text(encoding="utf-8-sig")


def _json_field(module, json_name: str, field_name: str) -> JsonDefField:
    jdef = _json_def(module, json_name)
    return next(
        f
        for f in jdef.body
        if isinstance(f, JsonDefField) and f.name == field_name
    )


class TestJsonFieldTypes:
    def test_str_field(self):
        m = _parse(_load_fixture("json_types", "str.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret == VariableType.STRING
        assert f.is_array is False
        assert f.ret_type_info.is_optional is False

    def test_int_field(self):
        m = _parse(_load_fixture("json_types", "int.kdl"))
        assert _json_field(m, "F", "x").ret == VariableType.INT

    def test_float_field(self):
        m = _parse(_load_fixture("json_types", "float.kdl"))
        assert _json_field(m, "F", "x").ret == VariableType.FLOAT

    def test_bool_field(self):
        m = _parse(_load_fixture("json_types", "bool.kdl"))
        assert _json_field(m, "F", "x").ret == VariableType.BOOL

    def test_null_field(self):
        m = _parse(_load_fixture("json_types", "null.kdl"))
        assert _json_field(m, "F", "x").ret == VariableType.NULL

    def test_array_str(self):
        m = _parse(_load_fixture("json_types", "array_str.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret == VariableType.STRING
        assert f.ret_type_info.is_array is True

    def test_array_int(self):
        m = _parse(_load_fixture("json_types", "array_int.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret == VariableType.INT
        assert f.ret_type_info.is_array is True

    def test_optional_suffix(self):
        m = _parse(_load_fixture("json_types", "optional.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret_type_info.is_optional is True
        assert f.ret == VariableType.STRING

    def test_ref_field(self):
        m = _parse(_load_fixture("json_types", "ref_field.kdl"))
        f = _json_field(m, "B", "ref")
        assert f.ret_type_info.ref == "A"
        assert f.ret == VariableType.JSON

    def test_array_ref(self):
        m = _parse(_load_fixture("json_types", "array_ref.kdl"))
        f = _json_field(m, "B", "items")
        assert f.ret_type_info.ref == "A"
        assert f.ret_type_info.is_array is True


class TestJsonFieldModifiers:
    def test_omitempty(self):
        m = _parse(_load_fixture("json_modifiers", "omitempty.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret_type_info.omitempty is True
        assert f.ret_type_info.skip is False

    def test_skip(self):
        m = _parse(_load_fixture("json_modifiers", "skip.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret_type_info.skip is True

    def test_skip_without_type_infers_str(self):
        m = _parse(_load_fixture("json_modifiers", "skip_no_type.kdl"))
        f = _json_field(m, "F", "x")
        assert f.ret_type_info.skip is True
        assert f.ret == VariableType.STRING

    def test_alias(self):
        m = _parse(_load_fixture("json_modifiers", "alias.kdl"))
        f = _json_field(m, "F", "x")
        assert f.alias == "original-key"

    def test_alias_with_ref(self):
        m = _parse(_load_fixture("json_modifiers", "alias_ref.kdl"))
        f = _json_field(m, "B", "x")
        assert f.alias == "orig-ref"
        assert f.ret_type_info.ref == "A"

    def test_unknown_modifier_errors(self):
        errs = _lint_errors(
            _load_fixture("json_modifiers", "bogus_modifier.kdl")
        )
        assert any("unknown json field modifier '@bogus'" in e for e in errs)

    def test_optional_modifier_is_error(self):
        errs = _lint_errors(
            _load_fixture("json_modifiers", "optional_modifier.kdl")
        )
        assert any("unknown json field modifier '@optional'" in e for e in errs)


class TestJsonDefPathProperty:
    def test_path_stored(self):
        m = _parse(_load_fixture("json_def_path", "with_path.kdl"))
        assert _json_def(m, "F").path == "data.items"

    def test_is_array_default_false(self):
        m = _parse(_load_fixture("json_def_path", "plain.kdl"))
        assert _json_def(m, "F").is_array is False

    def test_is_array_prefix(self):
        m = _parse(_load_fixture("json_def_path", "array.kdl"))
        assert _json_def(m, "F").is_array is True

    def test_array_with_path_ok(self):
        errs = _lint_errors(
            _load_fixture("json_def_path", "array_with_path.kdl")
        )
        assert not errs


class TestJsonifyAst:
    def _jsonify_node(self, *fixture_parts: str) -> Jsonify:
        module = _parse(_load_fixture(*fixture_parts))
        struct = _struct(module, "M")
        field = _field(struct, "f")
        return next(n for n in field.body if isinstance(n, Jsonify))

    def test_no_path(self):
        j = self._jsonify_node("jsonify", "no_path.kdl")
        assert j.schema_name == "Q"
        assert j.path == ""
        assert j.is_array is False

    def test_with_path(self):
        j = self._jsonify_node("jsonify", "with_path.kdl")
        assert j.path == "0.x"

    def test_array_def_is_array(self):
        j = self._jsonify_node("jsonify", "array_def.kdl")
        assert j.is_array is True

    def test_undefined_schema_errors(self):
        errs = _lint_errors(_load_fixture("jsonify", "undefined_schema.kdl"))
        assert any("not found" in e.lower() for e in errs)


class TestRestStructForms:
    def test_prefix_form_creates_struct_rest(self):
        m = _parse(_load_fixture("rest_forms", "prefix.kdl"))
        s = next(n for n in m.body if isinstance(n, StructBase))
        assert isinstance(s, StructRest)

    def test_property_form_creates_struct_rest(self):
        m = _parse(_load_fixture("rest_forms", "property.kdl"))
        s = next(n for n in m.body if isinstance(n, StructBase))
        assert isinstance(s, StructRest)

    def test_both_forms_same_request_count(self):
        m_prefix = _parse(_load_fixture("rest_forms", "prefix.kdl"))
        m_prop = _parse(_load_fixture("rest_forms", "property.kdl"))
        s_prefix = next(n for n in m_prefix.body if isinstance(n, StructRest))
        s_prop = next(n for n in m_prop.body if isinstance(n, StructRest))
        assert len(s_prefix.request_configs) == len(s_prop.request_configs)
