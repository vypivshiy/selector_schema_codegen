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
    TableConfig,
    TableMatchKey,
    TableRow,
    Text,
    TransformCall,
    TransformDef,
    TypeDef,
    Value,
)
from ssc_codegen.ast.predicate_ops import LogicNot, PredContains, PredEq
from ssc_codegen.ast.types import StructType, VariableType
from ssc_codegen.exceptions import ParseError, BuildTimeError
from ssc_codegen.parser import PARSER, parse_document


EXAMPLES = [
    Path("examples/booksToScrape.kdl"),
    Path("examples/quotesToScrape.kdl"),
    Path("examples/transformExample.kdl"),
    Path("examples/imdbcom.kdl"),
]


def _parse_example(path: str) -> object:
    return PARSER.parse(Path(path).read_text(encoding="utf-8-sig"))


def _body_of_type(nodes: list[object], cls: type):
    return [node for node in nodes if isinstance(node, cls)]


def _struct(module, name: str) -> Struct:
    return next(node for node in module.body if isinstance(node, Struct) and node.name == name)


def _json_def(module, name: str) -> JsonDef:
    return next(node for node in module.body if isinstance(node, JsonDef) and node.name == name)


def _field(struct: Struct, name: str):
    return next(node for node in struct.body if getattr(node, "name", None) == name)


def test_parse_document_decodes_literals_and_annotations():
    doc = parse_document(
        "\n".join(
            [
                'define S="abc"',
                'define R=#"raw"#',
                'define T=#true',
                'define F=#false',
                'define N=#null',
                'define I=123',
                'define X=1.25',
                'json Q {',
                '    tags (array)str',
                '}',
            ]
        )
    )

    defines = [n for n in doc.nodes if n.name == "define"]
    assert defines[0].properties == {"S": "abc"}
    assert defines[1].properties == {"R": "raw"}
    assert defines[2].properties == {"T": True}
    assert defines[3].properties == {"F": False}
    assert defines[4].properties == {"N": None}
    assert defines[5].properties == {"I": 123}
    assert defines[6].properties == {"X": 1.25}

    json_node = [n for n in doc.nodes if n.name == "json"][0]
    assert json_node.children[0].args == ["(array)str"]


def test_parse_document_raises_parse_error_on_invalid_syntax():
    with pytest.raises(ParseError, match="Invalid KDL syntax"):
        parse_document('struct Demo {\n  title {\n    css ".x"\n')


def test_parser_parses_real_examples():
    for path in EXAMPLES:
        module = PARSER.parse(path.read_text(encoding="utf-8-sig"))
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


def test_parser_builds_transform_defs_and_transform_calls():
    module = _parse_example("examples/transformExample.kdl")

    transforms = _body_of_type(module.body, TransformDef)
    assert [t.name for t in transforms] == ["to-base64", "to-list-base64", "pow2"]
    assert [t.accept for t in transforms] == [
        VariableType.STRING,
        VariableType.LIST_STRING,
        VariableType.INT,
    ]
    assert [t.ret for t in transforms] == [
        VariableType.STRING,
        VariableType.LIST_STRING,
        VariableType.INT,
    ]

    first_targets = transforms[0].body
    assert [type(t).__name__ for t in first_targets] == ["TransformTarget", "TransformTarget"]
    assert [t.lang for t in first_targets] == ["py", "js"]
    assert first_targets[0].imports == ("from base64 import b64decode",)
    assert first_targets[0].code == ("{{NXT}} = str(b64decode({{PRV}}))",)

    main = _struct(module, "Main")
    titleb64 = _field(main, "titleb64")
    urlsb64 = _field(main, "urlsb64")
    pow2_field = _field(main, "urls-len-pow2")

    assert isinstance(titleb64.body[-2], TransformCall)
    assert titleb64.body[-2].name == "to-base64"
    assert titleb64.body[-2].transform_def is transforms[0]
    assert titleb64.body[-2].accept == VariableType.STRING
    assert titleb64.body[-2].ret == VariableType.STRING

    assert isinstance(urlsb64.body[-2], TransformCall)
    assert urlsb64.body[-2].name == "to-list-base64"
    assert urlsb64.body[-2].accept == VariableType.LIST_STRING
    assert urlsb64.body[-2].ret == VariableType.LIST_STRING

    assert isinstance(pow2_field.body[-2], TransformCall)
    assert pow2_field.body[-2].name == "pow2"
    assert pow2_field.body[-2].accept == VariableType.INT
    assert pow2_field.body[-2].ret == VariableType.INT


def test_parser_resolves_jsonify_and_nested_nodes():
    module = _parse_example("examples/imdbcom.kdl")
    search_page = _struct(module, "SearchPage")

    json_parse = _field(search_page, "json-parse")
    selector_parse = _field(search_page, "selector-parse")

    jsonify = next(node for node in json_parse.body if isinstance(node, Jsonify))

    assert jsonify.schema_name == "Content"
    assert jsonify.path == "props.pageProps.titleResults"
    assert jsonify.accept == VariableType.STRING
    assert jsonify.ret == VariableType.JSON
    assert jsonify.is_array is False

    # nested parsing is covered on an example that actually produces Nested AST nodes
    assert selector_parse.accept == VariableType.DOCUMENT


def test_parser_builds_nested_node_for_inline_pipeline():
    module = PARSER.parse(
        '''
        struct Child {
            value { css ".x"; text }
        }

        struct Main {
            child { nested Child }
        }
        '''
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
    module = PARSER.parse(
        '''
        struct Main {
            url { css "a"; attr "href" }
        }
        '''
    )
    main = _struct(module, "Main")
    url = _field(main, "url")

    assert isinstance(url.body[0], CssSelect)
    assert isinstance(url.body[1], Attr)
    assert isinstance(url.body[-1], Return)
    assert url.accept == VariableType.DOCUMENT
    assert url.ret == VariableType.STRING


def test_parser_supports_css_pattern_match_block():
    module = PARSER.parse(
        '''
        define MAIN_TITLE=".article h1"

        struct Main {
            title {
                css {
                    MAIN_TITLE
                    "h1"
                }
                text
            }
        }
        '''
    )
    main = _struct(module, "Main")
    title = _field(main, "title")

    assert isinstance(title.body[0], CssSelect)
    assert title.body[0].query == ""
    assert title.body[0].queries == [".article h1", "h1"]
    assert isinstance(title.body[1], Text)
    assert isinstance(title.body[-1], Return)


def test_parser_supports_xpath_all_pattern_match_block():
    module = PARSER.parse(
        '''
        struct Main {
            links {
                xpath-all {
                    "//a[@href]"
                    "//area[@href]"
                }
                attr "href"
            }
        }
        '''
    )
    main = _struct(module, "Main")
    links = _field(main, "links")

    assert isinstance(links.body[0], XpathSelectAll)
    assert links.body[0].query == ""
    assert links.body[0].queries == ["//a[@href]", "//area[@href]"]
    assert isinstance(links.body[1], Attr)
    assert isinstance(links.body[-1], Return)



def test_parser_supports_inline_raw_extractor():
    module = PARSER.parse(
        '''
        struct Main {
            html { raw }
        }
        '''
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
    module = PARSER.parse(
        '''
        struct Main {
            title { css ".title"; text; assert { contains "foo" } }
        }
        '''
    )
    main = _struct(module, "Main")
    title = _field(main, "title")

    assert [type(node).__name__ for node in title.body] == ["CssSelect", "Text", "Assert", "Return"]
    assert_node = next(node for node in title.body if isinstance(node, Assert))
    assert [type(node).__name__ for node in assert_node.body] == ["PredContains"]
    assert isinstance(assert_node.body[0], PredContains)
    assert title.ret == VariableType.STRING



def test_parser_supports_inline_match_block():
    module = PARSER.parse(
        '''
        struct Main type=table {
            @table { css "table" }
            @rows { css-all "tr" }
            @match { css "th"; text }
            @value { css "td"; text }
            row-name { match { eq "Name" } }
        }
        '''
    )
    main = _struct(module, "Main")
    row_name = _field(main, "row-name")

    assert [type(node).__name__ for node in row_name.body] == ["Match", "Return"]
    match_node = row_name.body[0]
    assert isinstance(match_node, Match)
    assert [type(node).__name__ for node in match_node.body] == ["PredEq"]
    assert isinstance(match_node.body[0], PredEq)
    assert row_name.ret == VariableType.STRING



def test_parser_supports_inline_filter_not_block():
    module = PARSER.parse(
        '''
        struct Main {
            links { css-all "a"; attr href; filter { not { contains "utm" } } }
        }
        '''
    )
    main = _struct(module, "Main")
    links = _field(main, "links")

    assert [type(node).__name__ for node in links.body] == ["CssSelectAll", "Attr", "Filter", "Return"]
    assert isinstance(links.body[0], CssSelectAll)
    filter_node = next(node for node in links.body if isinstance(node, Filter))
    assert [type(node).__name__ for node in filter_node.body] == ["LogicNot"]
    assert isinstance(filter_node.body[0], LogicNot)
    assert [type(node).__name__ for node in filter_node.body[0].body] == ["PredContains"]
    assert isinstance(filter_node.body[0].body[0], PredContains)
    assert links.ret == VariableType.LIST_STRING



def test_parser_resolves_json_definition_field_shapes():
    module = _parse_example("examples/imdbcom.kdl")
    results = _json_def(module, "Results")
    content = _json_def(module, "Content")

    results_fields = {field.name: field for field in results.body}
    content_fields = {field.name: field for field in content.body}

    assert results_fields["titlePosterImageModel"].ref_name == "TitlePosterImageModel"
    assert results_fields["titlePosterImageModel"].is_array is False
    assert results_fields["topCredits"].is_array is True
    assert results_fields["topCredits"].ref_name == ""
    assert results_fields["seriesId"].is_optional is True
    assert results_fields["seriesSeasonText"].is_optional is True

    assert content_fields["results"].is_array is True
    assert content_fields["results"].ref_name == "Results"
    assert content_fields["hasExactMatches"].is_optional is False


def test_parser_handles_table_struct_special_nodes_and_field_types():
    module = _parse_example("examples/booksToScrape.kdl")
    product_info = _struct(module, "ProductInfo")

    assert product_info.struct_type == StructType.TABLE

    table_cfg = next(node for node in product_info.body if isinstance(node, TableConfig))
    table_rows = next(node for node in product_info.body if isinstance(node, TableRow))
    table_match = next(node for node in product_info.body if isinstance(node, TableMatchKey))
    value_node = next(node for node in product_info.body if isinstance(node, Value))
    pre_validate = next(node for node in product_info.body if isinstance(node, PreValidate))
    start_parse = product_info.body[-1]
    number_reviews = _field(product_info, "number-of-reviews")

    assert isinstance(start_parse, StartParse)
    assert start_parse.use_pre_validate is True
    assert start_parse.use_split_doc is False
    assert start_parse.fields_table == (table_cfg, table_rows, table_match)

    assert value_node.ret == VariableType.STRING
    assert isinstance(pre_validate.body[0], Assert)
    assert type(number_reviews.body[0]).__name__ == "FallbackStart"
    assert isinstance(number_reviews.body[1], Match)
    assert number_reviews.accept == VariableType.STRING
    assert isinstance(number_reviews.body[-1], Return)
    assert number_reviews.ret == VariableType.INT


def test_parser_inlines_define_blocks_and_resolves_init_references():
    module = PARSER.parse(
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

    init_field = next(node for node in main.init.body if isinstance(node, InitField) and node.name == "seed")
    inline_define = _field(main, "inline-define")
    from_init = _field(main, "from-init")

    assert [type(node).__name__ for node in init_field.body] == ["CssSelect", "Text", "Return"]
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
    with pytest.raises(BuildTimeError, match="no longer supported"):
        PARSER.parse(
            """
            struct Main {
                @init {
                    seed {
                        text
                    }
                }

                from-init {
                    self seed
                    fmt \"Hello {{}}\"
                }
            }
            """
        )


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

    assert isinstance(next(node for node in book.body if isinstance(node, SplitDoc)), SplitDoc)
    assert isinstance(start_parse, StartParse)
    assert start_parse.use_split_doc is True
    assert start_parse.use_pre_validate is True
    assert {field.name for field in start_parse.fields} == {"name", "image-url", "rating", "price"}
