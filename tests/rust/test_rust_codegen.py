"""Cargo-backed smoke tests for the Rust target."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ssc_codegen.ast import MatcherEntry, MatcherListDef
from ssc_codegen.core import parse_module
from ssc_codegen.exceptions import BuildTimeError
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.rust import RustVisitor
from ssc_codegen.targets.spec import TargetSpec


pytestmark = [
    pytest.mark.skipif(
        shutil.which("cargo") is None,
        reason="Cargo toolchain not found in PATH",
    ),
    pytest.mark.toolchain,
    pytest.mark.xdist_group("cargo"),
]


_worker_id = os.environ.get("PYTEST_XDIST_WORKER")
_SHARED_TARGET_DIR = (
    Path(__file__).resolve().parents[2]
    / "target"
    / (f"test_rust_target_{_worker_id}" if _worker_id else "test_rust_target")
)


def _cargo_env() -> dict[str, str]:
    """Keep concurrent full-suite Cargo builds within CI memory limits."""
    env = os.environ.copy()
    if "CI" in env:
        env.setdefault("CARGO_BUILD_JOBS", "1")
    else:
        env.setdefault("CARGO_BUILD_JOBS", str(min(os.cpu_count() or 4, 8)))
    env.setdefault("CARGO_TARGET_DIR", str(_SHARED_TARGET_DIR))
    return env


def _write_cargo_project(root: Path) -> Path:
    """Create the common Cargo fixture layout and return its source folder."""
    source_dir = root / "src"
    source_dir.mkdir()
    (root / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_fixture"
version = "0.1.0"
edition = "2021"

[dependencies]
dom_query = "0.28"
regex = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
""",
        encoding="utf-8",
    )
    return source_dir


def test_all_html_features_execute(tmp_path: Path) -> None:
    """Validate all HTML features in a single Cargo run: item, raw JSON, extensions,
    lifecycle, struct shapes (list/flat/dict/table/raw), unicode ops, JSON fragments,
    HTML functions, raw nested structs, and schema 25 functions.
    """
    root = Path(__file__).resolve().parents[2]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )

    # 1. Item parser
    s1 = """
struct Product {
    title { css "h1"; text; trim }
    price { css ".price"; text; to-int }
}
"""
    m1, d1 = parse_module(s1)
    assert not [item for item in d1 if item.severity.name == "ERROR"]
    (source_dir / "parser_item.rs").write_text(
        converter.convert(m1), encoding="utf-8"
    )

    # 2. Raw JSON parser
    s2 = """
json Product { id int; label str? from="display_label" }
(raw)struct Payload { product { jsonify Product path="data.item" } }
"""
    m2, d2 = parse_module(s2)
    assert not [item for item in d2 if item.severity.name == "ERROR"]
    (source_dir / "parser_raw_json.rs").write_text(
        converter.convert(m2), encoding="utf-8"
    )

    # 3. Extension
    s3 = """
extension Utils {
    prefix {
        sig str str
        rust { emit #"let {{out}} = format!(\"prefix-{}\", {{in}});"# }
    }
}
(raw)fn value { !Utils.prefix }
"""
    m3, d3 = parse_module(s3)
    assert not [item for item in d3 if item.severity.name == "ERROR"]
    (source_dir / "parser_extension.rs").write_text(
        converter.convert(m3), encoding="utf-8"
    )

    # 4. Lifecycle
    s4 = """
struct ChildCard {
    badge { css ".badge"; text; trim }
}
struct ParentDoc {
    @init { cached-banner { css "#banner" } }
    @pre-validate { assert { css "main" } }
    @check is-published { css ".published"; to-bool }
    title { css "h1"; text; trim }
    banner-text-before-remove { @cached-banner; text; trim }
    remove-banner { css-remove "#banner"; to-bool }
    remove-nonexistent { css-remove ".no-such-class"; to-bool }
    banner-after-remove { css "#banner"; text; fallback "gone" }
    banner-from-cache-after-remove { @cached-banner; text; trim }
    child { css ".card"; nested ChildCard }
}
"""
    m4, d4 = parse_module(s4)
    assert not [item for item in d4 if item.severity.name == "ERROR"]
    (source_dir / "parser_lifecycle.rs").write_text(
        converter.convert(m4), encoding="utf-8"
    )

    # 5. Struct shapes
    s5 = """
(list)struct ListItem {
    @split-doc { css-all "li" }
    name { text; trim }
}
(flat)struct FlatTags {
    tags { css-all ".tag"; text; trim }
}
(dict)struct DictProps {
    @split-doc { css-all ".prop" }
    @key { attr "data-key" }
    @value { text; trim }
}
(table)struct TableInfo {
    @table { css "table" }
    @rows { css-all "tr" }
    @match { css "th"; text; trim; lower }
    @value { css "td"; text; trim }
    id { match { eq "id" } }
    qty { match { eq "quantity" }; to-int; fallback 0 }
    cost { match { eq "cost" }; to-float; fallback 0.0 }
}
(raw)struct RawLines {
    @split-doc { split "\\n" }
    item { trim }
}
"""
    m5, d5 = parse_module(s5)
    assert not [item for item in d5 if item.severity.name == "ERROR"]
    (source_dir / "parser_struct_shapes.rs").write_text(
        converter.convert(m5), encoding="utf-8"
    )

    # 6. Unicode
    s6 = r"""
(raw)struct TextSuite {
    cyrillic-slice { slice 0 6 }
    emoji-slice { slice 7 9 }
    inverted-slice { slice 5 2 }
    char-len { len }
    index-emoji { index 7 }
    negative-index { index -1 }
    formatted { fmt "prefix-{{}}-suffix" }
    dollar-sub { re-sub #"(\w+)"# "$1-ok" }
    backslash-sub { re-sub #"(\w+)"# #"\1-ok"# }
    opt-field { re #"(not_found)"#; fallback #null }
    default-field { re #"(not_found)"#; fallback "recovered" }
}
"""
    m6, d6 = parse_module(s6)
    assert not [item for item in d6 if item.severity.name == "ERROR"]
    (source_dir / "parser_unicode.rs").write_text(
        converter.convert(m6), encoding="utf-8"
    )

    # 7. JSON fragment
    s7 = """
(array)json ItemRecord {
    item-id int from="nested.raw_id"
    title str
    label str?
    extra str? @omitempty
}
(raw)struct CatalogPayload {
    items { jsonify ItemRecord path="data.catalog" }
}
"""
    m7, d7 = parse_module(s7)
    assert not [item for item in d7 if item.severity.name == "ERROR"]
    (source_dir / "parser_json_fragment.rs").write_text(
        converter.convert(m7), encoding="utf-8"
    )

    # 8. HTML fn
    s8 = """
struct CardInfo { title { css "h2"; text } }
fn page_title {
    @doc "Extract the <h1> text from an HTML document."
    css "h1"; text; trim
}
fn active_links { css-all "a"; filter { attr-eq "class" "active" }; attr "href" }
fn parse_card { css ".card"; nested CardInfo }
"""
    m8, d8 = parse_module(s8)
    assert not [item for item in d8 if item.severity.name == "ERROR"]
    code8 = converter.convert(m8)
    assert "/// Extract the <h1> text from an HTML document." in code8
    (source_dir / "parser_html_fn.rs").write_text(code8, encoding="utf-8")

    # 9. Raw nested
    s9 = """
(raw)struct RawMetadata { version { re #"ver=([0-9]+\\.[0-9]+)"# } }
struct HtmlCard { heading { css "h3"; text } }
(raw)struct InnerSnippet {
    id { re #"id=(\\d+)"#; to-int }
    label { re #"name=([a-zA-Z]+)"# }
}
(raw)struct OuterEnvelope {
    snippet { nested InnerSnippet }
    card { re #"(<div class=\"card\">.*?</div>)"#; nested HtmlCard }
}
struct HtmlWithRawChild {
    meta { css "div#meta"; text; nested RawMetadata }
}
struct HtmlWithRawHtmlChild {
    card { css "div.card-wrap"; raw; nested HtmlCard }
}
"""
    m9, d9 = parse_module(s9)
    assert not [item for item in d9 if item.severity.name == "ERROR"]
    code9 = converter.convert(m9)
    assert "HtmlCardParser::new(&v" in code9
    (source_dir / "parser_raw_nested.rs").write_text(code9, encoding="utf-8")

    # 10. Schema 25 fn
    s10_path = root / "tests" / "integration" / "schemas" / "25_fn.kdl"
    m10, d10 = parse_module(
        s10_path.read_text(encoding="utf-8"), source_path=s10_path
    )
    assert not [item for item in d10 if item.severity.name == "ERROR"]
    (source_dir / "parser_fn_schema_25.rs").write_text(
        converter.convert(m10), encoding="utf-8"
    )

    (source_dir / "main.rs").write_text(
        r"""mod sscgen_runtime;
mod parser_item;
mod parser_raw_json;
mod parser_extension;
mod parser_lifecycle;
mod parser_struct_shapes;
mod parser_unicode;
mod parser_json_fragment;
mod parser_html_fn;
mod parser_raw_nested;
mod parser_fn_schema_25;

fn test_item() {
    let mut parser = parser_item::ProductParser::new("<main><h1> Widget </h1><span class=\"price\">42</span></main>").unwrap();
    let result = parser.parse().unwrap();
    assert_eq!(serde_json::to_string(&result).unwrap(), r#"{"title":"Widget","price":42}"#);
}

fn test_raw_json() {
    let mut parser = parser_raw_json::PayloadParser::new(r#"{"data":{"item":{"id":7,"display_label":"ok"}}}"#).unwrap();
    let result = parser.parse().unwrap();
    assert_eq!(serde_json::to_string(&result).unwrap(), r#"{"product":{"id":7,"label":"ok"}}"#);
}

fn test_ext() {
    assert_eq!(parser_extension::value("x").unwrap(), "prefix-x");
}

fn test_lifecycle() {
    let valid_html = "<main><div class=\"published\">Yes</div><div id=\"banner\">Important Notice</div><h1>Parent Title</h1><div class=\"card\"><span class=\"badge\">VIP</span></div></main>";
    let mut parser = parser_lifecycle::ParentDocParser::new(valid_html).expect("init should succeed");
    assert!(parser.is_published().expect("check should succeed"));
    let res1 = parser.parse().expect("first parse should succeed");
    let res2 = parser.parse().expect("second parse should succeed");
    assert_eq!(res1.title, res2.title);
    assert_eq!(res1.title, "Parent Title");
    assert_eq!(res1.banner_text_before_remove, "Important Notice");
    assert_eq!(res1.banner_after_remove, "gone");
    assert_eq!(res1.banner_from_cache_after_remove, "Important Notice");
    assert_eq!(res1.child.badge, "VIP");
    drop(parser);
    let serialized = serde_json::to_string(&res1).expect("owned result serializes after parser drop");
    assert!(serialized.contains("Parent Title"));
    let bad_html = "<main><h1>No banner</h1></main>";
    assert!(parser_lifecycle::ParentDocParser::new(bad_html).is_err());
    let no_main = "<div id=\"banner\">Notice</div><h1>Title</h1>";
    let mut bad_preval = parser_lifecycle::ParentDocParser::new(no_main).expect("init succeeds");
    assert!(bad_preval.parse().is_err());
}

fn test_shapes() {
    let html = "<ul><li>Alpha</li><li>Beta</li></ul><div class=\"tag\">rust</div><div class=\"tag\">parser</div><div class=\"tag\">rust</div><div class=\"prop\" data-key=\"color\">blue</div><div class=\"prop\" data-key=\"size\">large</div><table><tr><th>ID</th><td>XYZ-99</td></tr><tr><th>Quantity</th><td>15</td></tr><tr><th>Cost</th><td>19.95</td></tr><tr><th>Ignored</th><td>skip</td></tr></table>";
    let mut list_p = parser_struct_shapes::ListItemParser::new(html).unwrap();
    let list_res = list_p.parse().unwrap();
    assert_eq!(list_res.len(), 2);
    assert_eq!(list_res[0].name, "Alpha");
    assert_eq!(list_res[1].name, "Beta");

    let mut flat_p = parser_struct_shapes::FlatTagsParser::new(html).unwrap();
    let flat_res = flat_p.parse().unwrap();
    assert_eq!(flat_res.len(), 2);

    let mut dict_p = parser_struct_shapes::DictPropsParser::new(html).unwrap();
    let dict_res = dict_p.parse().unwrap();
    assert_eq!(dict_res.get("color").map(String::as_str), Some("blue"));
    assert_eq!(dict_res.get("size").map(String::as_str), Some("large"));

    let mut table_p = parser_struct_shapes::TableInfoParser::new(html).unwrap();
    let table_res = table_p.parse().unwrap();
    assert_eq!(table_res.get("id").and_then(|v| v.as_str()), Some("XYZ-99"));
    assert_eq!(table_res.get("qty").and_then(|v| v.as_i64()), Some(15));
    assert_eq!(table_res.get("cost").and_then(|v| v.as_f64()), Some(19.95));
    assert_eq!(table_res.get("Ignored"), None);

    let mut raw_p = parser_struct_shapes::RawLinesParser::new("first\nsecond\nthird\n").unwrap();
    let raw_res = raw_p.parse().unwrap();
    assert_eq!(raw_res.len(), 4);
}

fn test_unicode() {
    let input = "Привет 🦀 world";
    let mut p = parser_unicode::TextSuiteParser::new(input).unwrap();
    let res = p.parse().unwrap();
    assert_eq!(res.cyrillic_slice, "Привет");
    assert_eq!(res.emoji_slice, "🦀 ");
    assert_eq!(res.inverted_slice, "");
    assert_eq!(res.char_len, 14);
    assert_eq!(res.index_emoji, "🦀");
    assert_eq!(res.negative_index, "d");
    assert_eq!(res.formatted, "prefix-Привет 🦀 world-suffix");
    assert_eq!(res.dollar_sub, "Привет-ok 🦀 world-ok");
    assert_eq!(res.backslash_sub, "Привет-ok 🦀 world-ok");
    assert_eq!(res.opt_field, None);
    assert_eq!(res.default_field, "recovered");
    assert!(sscgen_runtime::index("abc", 50, "test").is_err());
    assert!(sscgen_runtime::index("abc", -50, "test").is_err());
}

fn test_json_fragment() {
    let valid_json = r#"{"data":{"catalog":[{"nested":{"raw_id":42},"title":"Gadget","label":"first","extra":"present"},{"nested":{"raw_id":43},"title":"Widget","label":null,"extra":null}]}}"#;
    let mut p = parser_json_fragment::CatalogPayloadParser::new(valid_json).unwrap();
    let res = p.parse().unwrap();
    assert_eq!(res.items.len(), 2);
    assert_eq!(res.items[0].item_id, 42);
    assert_eq!(res.items[0].title, "Gadget");
    assert_eq!(res.items[0].label.as_deref(), Some("first"));
    assert_eq!(res.items[0].extra.as_deref(), Some("present"));
    assert_eq!(res.items[1].item_id, 43);
    assert_eq!(res.items[1].title, "Widget");
    assert_eq!(res.items[1].label, None);
    assert_eq!(res.items[1].extra, None);
    let missing_json = r#"{"data":{"catalog":[{"nested":{"raw_id":99}}]}}"#;
    let mut p_bad = parser_json_fragment::CatalogPayloadParser::new(missing_json).unwrap();
    assert!(p_bad.parse().is_err());
}

fn test_html_fn() {
    let html = r#"
    <html><body>
        <h1>  Hello Rust Functions!  </h1>
        <a class="active" href="/home">Home</a>
        <a href="/about">About</a>
        <a class="active" href="/contact">Contact</a>
        <div class="card"><h2>Featured Card</h2></div>
    </body></html>"#;
    assert_eq!(parser_html_fn::page_title(html).unwrap(), "Hello Rust Functions!");
    assert_eq!(parser_html_fn::active_links(html).unwrap(), vec!["/home".to_string(), "/contact".to_string()]);
    assert_eq!(parser_html_fn::parse_card(html).unwrap().title, "Featured Card");
}

fn test_raw_nested() {
    let raw_data = "id=123;name=Rust;extra=<div class=\"card\"><h3>Card Heading</h3></div>";
    let mut envelope_parser = parser_raw_nested::OuterEnvelopeParser::new(raw_data).expect("envelope parser init");
    let envelope = envelope_parser.parse().expect("envelope parse");
    drop(envelope_parser);
    assert_eq!(envelope.snippet.id, 123);
    assert_eq!(envelope.snippet.label, "Rust");
    assert_eq!(envelope.card.heading, "Card Heading");
    let html_data = "<html><body><div id=\"meta\">ver=2.5;build=release</div></body></html>";
    let mut html_parser = parser_raw_nested::HtmlWithRawChildParser::new(html_data).expect("html parser init");
    let html_res = html_parser.parse().expect("html parse");
    drop(html_parser);
    assert_eq!(html_res.meta.version, "2.5");
    let html_data2 = "<html><body><div class=\"card-wrap\"><h3>Nested Card Heading</h3></div></body></html>";
    let mut html_raw_child_parser = parser_raw_nested::HtmlWithRawHtmlChildParser::new(html_data2).expect("html raw child parser init");
    let html_raw_child_res = html_raw_child_parser.parse().expect("html raw child parse");
    drop(html_raw_child_parser);
    assert_eq!(html_raw_child_res.card.heading, "Nested Card Heading");
}

fn test_schema_25() {
    let fn_html = "<html><body><h1>Hello World</h1><a href='/a'>A</a><a href='/b'>B</a></body></html>";
    let fn_raw = "first line\nsecond line\nthird line";
    let fn_version = "app version=1.2.3 released";
    assert_eq!(parser_fn_schema_25::page_title(fn_html).unwrap(), "Hello World");
    assert_eq!(parser_fn_schema_25::all_links(fn_html).unwrap(), vec!["/a".to_string(), "/b".to_string()]);
    assert_eq!(parser_fn_schema_25::first_line(fn_raw).unwrap(), "first line");
    assert_eq!(parser_fn_schema_25::extract_version(fn_version).unwrap(), "1.2.3");
}

fn main() {
    test_item();
    test_raw_json();
    test_ext();
    test_lifecycle();
    test_shapes();
    test_unicode();
    test_json_fragment();
    test_html_fn();
    test_raw_nested();
    test_schema_25();
    println!("ALL_HTML_FEATURES_OK");
}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["cargo", "run", "--quiet"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_cargo_env(),
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "ALL_HTML_FEATURES_OK" in result.stdout


def test_html_schema_fixtures_compile_together(tmp_path: Path) -> None:
    """Representative list/table/predicate/nested schemas share one runtime."""
    root = Path(__file__).resolve().parents[2]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    modules: list[str] = []
    for index, schema_name in enumerate(
        (
            "00_full.kdl",
            "03_filters_and_predicates.kdl",
            "04_json_and_nested.kdl",
            "05_flat.kdl",
            "06_dict.kdl",
            "07_table.kdl",
        )
    ):
        schema = root / "tests" / "integration" / "schemas" / schema_name
        module, diagnostics = parse_module(schema.read_text(encoding="utf-8"))
        assert not [
            item for item in diagnostics if item.severity.name == "ERROR"
        ]
        module_name = f"generated_{index}"
        (source_dir / f"{module_name}.rs").write_text(
            converter.convert(module), encoding="utf-8"
        )
        modules.append(module_name)
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        "\n".join(f"mod {name};" for name in modules)
        + "\nmod sscgen_runtime;"
        + "\nfn main() {}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["cargo", "check", "--quiet"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_cargo_env(),
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr

    formatted = subprocess.run(
        ["cargo", "fmt", "--", "--check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_cargo_env(),
        encoding="utf-8",
        timeout=180,
    )
    assert formatted.returncode == 0, formatted.stdout + formatted.stderr


def test_unsupported_features_diagnostics() -> None:
    """Ensure clear BuildTimeError diagnostics for unsupported DSL features."""
    converter = RustVisitor()

    # XPath select
    m1, _ = parse_module('struct X { title { xpath "//h1"; text } }')
    with pytest.raises(BuildTimeError, match="XPath"):
        converter.convert(m1)

    # XPath remove
    m2, _ = parse_module('struct X { title { xpath-remove "//script"; text } }')
    with pytest.raises(BuildTimeError, match="XPath"):
        converter.convert(m2)

    # Regex lookaround
    m5, _ = parse_module('struct X { title { css "h1"; text; re #"(?=a)b"# } }')
    with pytest.raises(BuildTimeError, match="lookaround"):
        converter.convert(m5)

    # Regex backreference
    m6, _ = parse_module(
        'struct X { title { css "h1"; text; re #"([a-z])\\1"# } }'
    )
    with pytest.raises(BuildTimeError, match="backreferences"):
        converter.convert(m6)

    # Extension without rust target
    m7, _ = parse_module(
        """
extension Ops {
    calc {
        sig int int
        py { emit "{{out}} = {{in}} * 2" }
    }
}
(raw)fn run { !Ops.calc }
"""
    )
    with pytest.raises(BuildTimeError, match="has no 'rust' target"):
        converter.convert(m7)


def test_raw_nested_rejects_document_input() -> None:
    """Invoking a (raw)struct with DOCUMENT input must be rejected with E100."""
    schema = """
(raw)struct ChildRaw {
    v { re #"v=(\\d+)"# }
}

struct ParentHtml {
    field {
        css "div"
        nested ChildRaw
    }
}
"""
    _, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert any(
        "target is a (raw)struct and requires STRING input" in d.message
        for d in errors
    )


def test_nested_rejects_list_string_input() -> None:
    """Invoking nested with a list of strings must be rejected with E100."""
    schema = """
(raw)struct ChildRaw {
    v { re #"v=(\\d+)"# }
}

(raw)struct ParentRaw {
    field {
        re-all #"v=(\\d+)"#
        nested ChildRaw
    }
}
"""
    _, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert any(
        "'nested' does not accept STRING; expected DOCUMENT" in d.message
        for d in errors
    )


def test_rust_resolver_http_client() -> None:
    """Rust target accepts reqwest as HTTP client and rejects unsupported clients."""
    profile = resolve(TargetSpec(lang="rust", http_client="reqwest"))
    assert profile.language == "rust"
    assert "reqwest" in profile.http_clients

    with pytest.raises(ResolutionError, match="Invalid HTTP client 'httpx'"):
        resolve(TargetSpec(lang="rust", http_client="httpx"))


def test_rust_method_fetch_code_generation() -> None:
    """MethodFetch generates async fetch method with query params, headers, and cookies."""
    schema = """
struct PostPage {
    @request response-path="data.content" \"\"\"
    GET /posts/{{id:int}}?tag={{tag}}&category={{cat?}} HTTP/1.1
    Host: example.com
    X-Api-Key: {{api_key}}
    Cookie: session=xyz; token={{auth_token}}
    \"\"\"

    title {
        css "h1"
        text
    }
}
"""
    module, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    converter = RustVisitor()
    code = converter.convert(module)

    assert "pub async fn fetch(" in code
    assert "client: &reqwest::Client" in code
    assert "id: i64" in code
    assert "tag: &str" in code
    assert "api_key: &str" in code
    assert "auth_token: &str" in code
    assert "cat: Option<&str>" in code
    assert "reqwest::Method::GET" in code
    assert "Self::new(body)" in code


def test_rust_method_fetch_named_and_raw() -> None:
    """MethodFetch supports custom method name and (raw)struct targets."""
    schema = """
(raw)struct ProxyList {
    @request name="custom_feed" \"\"\"
    GET /proxies/{{region}} HTTP/1.1
    Host: example.com
    \"\"\"

    items {
        split "\\n"
    }
}
"""
    module, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    converter = RustVisitor()
    code = converter.convert(module)

    assert "pub async fn fetch_custom_feed(" in code
    assert "client: &reqwest::Client" in code
    assert "region: &str" in code
    assert "Self::new(body)" in code


def test_rust_method_fetch_json_and_form_body() -> None:
    """MethodFetch supports JSON and form payloads."""
    schema = """
struct JsonPage {
    @request \"\"\"
    POST /api/items HTTP/1.1
    Host: example.com
    Content-Type: application/json

    {"query": "{{q}}", "page": 1}
    \"\"\"

    title {
        css "h1"
        text
    }
}

struct FormPage {
    @request \"\"\"
    POST /form HTTP/1.1
    Host: example.com
    Content-Type: application/x-www-form-urlencoded

    username={{user}}&role=admin
    \"\"\"

    title {
        css "h1"
        text
    }
}
"""
    module, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    converter = RustVisitor()
    code = converter.convert(module)

    assert "req = req.json(&serde_json::json!({" in code
    assert '"query": (q)' in code
    assert "req = req.form(&form_pairs);" in code


def test_rust_method_fetch_array_param_styles() -> None:
    """MethodFetch handles array parameters with csv, pipe, repeat, and bracket styles."""
    schema = """
struct SearchPage {
    @request \"\"\"
    GET /search?tags={{tags:str[]|csv}}&ids={{ids:int[]|repeat}}&pipes={{pipes:str[]?|pipe}}&brackets={{brackets:str[]|bracket}} HTTP/1.1
    Host: example.com
    \"\"\"

    title {
        css "h1"
        text
    }
}
"""
    module, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    converter = RustVisitor()
    code = converter.convert(module)

    assert "tags: &[&str]" in code
    assert "ids: &[i64]" in code
    assert "pipes: Option<&[&str]>" in code
    assert "brackets: &[&str]" in code
    assert 'join(",")' in code
    assert 'join("|")' in code
    assert '"brackets[]"' in code


def test_untyped_error_variant_holds_serde_json_value() -> None:
    """MatcherListDef with untyped error entries emits variants holding serde_json::Value."""
    schema = """
json User {
    id int
}

struct API type=rest {
    @request name=get-user response=User \"\"\"
    GET http://127.0.0.1/users/{{id:int}} HTTP/1.1
    \"\"\"
}
"""
    module_ast, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    for n in module_ast.body:
        if isinstance(n, MatcherListDef):
            n.entries.append(
                MatcherEntry(
                    status=400,
                    required_keys=[],
                    conditions={},
                    factory_name="APIErr400",
                    error_schema="",
                )
            )

    converter = RustVisitor()
    code = converter.convert(module_ast)

    assert "Err400(serde_json::Value)," in code
    assert "pub type APIErr400 = serde_json::Value;" in code
    assert "return Some(APIError::Err400(if _body_val.is_null()" in code
    assert "_body_val.clone()" in code


def test_all_rest_schemas_compile(tmp_path: Path) -> None:
    """All 17 REST schemas generate valid Rust and compile together in a single Cargo project."""
    schemas_dir = (
        Path(__file__).resolve().parents[1] / "integration" / "schemas"
    )
    schemas = [
        "08_rest_basic.kdl",
        "09_rest_void.kdl",
        "10_rest_err_404.kdl",
        "11_rest_err_404_500.kdl",
        "12_rest_err_404_keys.kdl",
        "13_rest_err_200_field.kdl",
        "14_rest_int_placeholder.kdl",
        "15_rest_query_opt.kdl",
        "16_rest_header.kdl",
        "17_rest_post.kdl",
        "20_rest_prefix_form.kdl",
        "21_rest_multi_method.kdl",
        "22_rest_response_path.kdl",
        "24_rest_form_body.kdl",
        "26_multi_rest_namespace.kdl",
        "27_rest_query_params.kdl",
        "28_rest_cookies.kdl",
    ]

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_rest_schemas"
version = "0.1.0"
edition = "2021"

[dependencies]
dom_query = "0.28"
regex = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
reqwest = { version = "0.12", default-features = false, features = ["json"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
""",
        encoding="utf-8",
    )

    converter = RustVisitor()
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )

    modules: list[str] = ["mod sscgen_runtime;"]
    for schema_file in schemas:
        schema_path = schemas_dir / schema_file
        src = schema_path.read_text(encoding="utf-8-sig")
        module_ast, diagnostics = parse_module(src, source_path=schema_path)
        errors = [d for d in diagnostics if d.severity.name == "ERROR"]
        assert not errors, f"Lint errors in {schema_file}: {errors}"

        mod_name = f"rest_{schema_file.split('_')[0]}"
        (source_dir / f"{mod_name}.rs").write_text(
            converter.convert(module_ast), encoding="utf-8"
        )
        modules.append(f"mod {mod_name};")

    modules.append("fn main() {}")
    (source_dir / "main.rs").write_text("\n".join(modules), encoding="utf-8")

    result = subprocess.run(
        ["cargo", "check", "--quiet"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_cargo_env(),
        timeout=180,
    )
    assert result.returncode == 0, result.stderr


def test_all_rest_and_fetch_execute(tmp_path: Path) -> None:
    """Execute all async REST endpoints and HTML fetch parsers in a single Cargo run:
    HTML fetch with params, HTML fetch with JSON response-path envelope, REST client
    with typed/untyped errors & status(), conditional errors, and void endpoints.
    """
    source_dir = _write_cargo_project(tmp_path)
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_all_rest"
version = "0.1.0"
edition = "2021"

[dependencies]
dom_query = "0.28"
regex = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
reqwest = { version = "0.12", default-features = false, features = ["json"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
""",
        encoding="utf-8",
    )
    converter = RustVisitor()
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )

    # 1. HTML fetch
    s1 = """
struct PostPage {
    @request \"\"\"
    curl http://127.0.0.1:{{port:int}}/posts?tag={{tag}}
    \"\"\"
    title { css "h1"; text }
}
"""
    m1, d1 = parse_module(s1)
    assert not [item for item in d1 if item.severity.name == "ERROR"]
    (source_dir / "p_fetch.rs").write_text(
        converter.convert(m1), encoding="utf-8"
    )

    # 2. HTML fetch envelope
    s2 = """
struct JsonEnvelopePage {
    @request response-path="data.markup" \"\"\"
    curl http://127.0.0.1:{{port:int}}/envelope
    \"\"\"
    heading { css "h2"; text }
}
"""
    m2, d2 = parse_module(s2)
    assert not [item for item in d2 if item.severity.name == "ERROR"]
    (source_dir / "p_fetch_envelope.rs").write_text(
        converter.convert(m2), encoding="utf-8"
    )

    # 3. REST endpoint
    s3 = """
json User { id int; name str }
json Err { code int; message str }
struct API type=rest {
    @error 404 Err
    @request name=get-user response=User \"\"\"
    GET http://127.0.0.1:{{port:int}}/users/{{id:int}} HTTP/1.1
    \"\"\"
}
"""
    m3, d3 = parse_module(s3)
    assert not [item for item in d3 if item.severity.name == "ERROR"]
    for n in m3.body:
        if isinstance(n, MatcherListDef):
            n.entries.insert(
                0,
                MatcherEntry(
                    status=400,
                    required_keys=[],
                    conditions={},
                    factory_name="APIErr400",
                    error_schema="",
                ),
            )
    code3 = converter.convert(m3)
    assert "Err400(serde_json::Value)" in code3
    (source_dir / "p_rest_endpoint.rs").write_text(code3, encoding="utf-8")

    # 4. REST conditional error matching
    s4 = """
json Err { error str; detail str }
json User { id int; name str }
struct API type=rest {
    @error 404 Err error detail
    @request response=User \"\"\"
    GET http://127.0.0.1:{{port:int}}/items/{{id:int}} HTTP/1.1
    \"\"\"
}
"""
    m4, d4 = parse_module(s4)
    assert not [item for item in d4 if item.severity.name == "ERROR"]
    (source_dir / "p_rest_cond.rs").write_text(
        converter.convert(m4), encoding="utf-8"
    )

    # 5. REST void endpoint and response-path
    s5 = """
json User { id int; name str }
struct ApiVoid type=rest {
    @request \"\"\"
    POST http://127.0.0.1:{{port:int}}/ping HTTP/1.1
    \"\"\"
}
struct ApiUser type=rest {
    @request response=User response-path="data.user" \"\"\"
    GET http://127.0.0.1:{{port:int}}/me HTTP/1.1
    \"\"\"
}
"""
    m5, d5 = parse_module(s5)
    assert not [item for item in d5 if item.severity.name == "ERROR"]
    (source_dir / "p_rest_void_path.rs").write_text(
        converter.convert(m5), encoding="utf-8"
    )

    (source_dir / "main.rs").write_text(
        r"""mod sscgen_runtime;
mod p_fetch;
mod p_fetch_envelope;
mod p_rest_endpoint;
mod p_rest_cond;
mod p_rest_void_path;

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

async fn test_fetch(client: &reqwest::Client) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 1024];
            let _ = stream.read(&mut buf);
            let body = "<html><body><h1>Fetched Title</h1></body></html>";
            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(), body
            );
            stream.write_all(response.as_bytes()).unwrap();
            break;
        }
    });
    let mut parser = p_fetch::PostPageParser::fetch(client, port as i64, "rust").await.unwrap();
    let result = parser.parse().unwrap();
    assert_eq!(serde_json::to_string(&result).unwrap(), r#"{"title":"Fetched Title"}"#);
}

async fn test_fetch_envelope(client: &reqwest::Client) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 1024];
            let _ = stream.read(&mut buf);
            let body = r#"{"data":{"markup":"<div><h2>Inner Heading</h2></div>"}}"#;
            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(), body
            );
            stream.write_all(response.as_bytes()).unwrap();
            break;
        }
    });
    let mut parser = p_fetch_envelope::JsonEnvelopePageParser::fetch(client, port as i64).await.unwrap();
    let result = parser.parse().unwrap();
    assert_eq!(serde_json::to_string(&result).unwrap(), r#"{"heading":"Inner Heading"}"#);
}

async fn test_rest_endpoint(client: &reqwest::Client) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 2048];
            let n = match stream.read(&mut buf) {
                Ok(n) if n > 0 => n,
                _ => continue,
            };
            let req_str = String::from_utf8_lossy(&buf[..n]);
            if req_str.contains("/users/1") {
                let body = r#"{"id":1,"name":"Alice"}"#;
                let resp = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/users/2") {
                let body = r#"{"code":404,"message":"user not found"}"#;
                let resp = format!("HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/users/3") {
                let body = r#"{"detail":"bad gateway"}"#;
                let resp = format!("HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/users/4") {
                let body = r#"{"bad_input":true,"detail":"missing field"}"#;
                let resp = format!("HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            }
        }
    });

    let user_res: p_rest_endpoint::GetUserResult = p_rest_endpoint::API::get_user(client, port as i64, 1).await;
    let user = user_res.unwrap();
    assert_eq!(user.id, 1);
    assert_eq!(user.name, "Alice");

    let api_res: p_rest_endpoint::APIGetUserResult = p_rest_endpoint::API::get_user(client, port as i64, 1).await;
    assert_eq!(api_res.unwrap().id, 1);

    match p_rest_endpoint::API::get_user(client, port as i64, 2).await {
        Err(p_rest_endpoint::APIError::Err404(err)) => {
            assert_eq!(err.code, 404);
            assert_eq!(err.message, "user not found");
        }
        other => panic!("expected Err404, got {:?}", other),
    }

    match p_rest_endpoint::API::get_user(client, port as i64, 3).await {
        Err(err) => {
            assert_eq!(err.status(), Some(502));
            match err {
                p_rest_endpoint::APIError::Unknown(status, val) => {
                    assert_eq!(status, 502);
                    assert_eq!(val["detail"], "bad gateway");
                }
                other => panic!("expected Unknown, got {:?}", other),
            }
        }
        other => panic!("expected Err, got {:?}", other),
    }

    match p_rest_endpoint::API::get_user(client, port as i64, 4).await {
        Err(err) => {
            assert_eq!(err.status(), Some(400));
            match err {
                p_rest_endpoint::APIError::Err400(val) => {
                    assert_eq!(val["bad_input"], true);
                    assert_eq!(val["detail"], "missing field");
                }
                other => panic!("expected Err400, got {:?}", other),
            }
        }
        other => panic!("expected Err, got {:?}", other),
    }

    let closed_port_err = p_rest_endpoint::API::get_user(client, 1, 99).await.unwrap_err();
    assert_eq!(closed_port_err.status(), None);
}

async fn test_rest_cond(client: &reqwest::Client) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 2048];
            let n = match stream.read(&mut buf) {
                Ok(n) if n > 0 => n,
                _ => continue,
            };
            let req_str = String::from_utf8_lossy(&buf[..n]);
            if req_str.contains("/items/1") {
                let body = r#"{"error":"NOT_FOUND","detail":"item 1 missing"}"#;
                let resp = format!("HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/items/2") {
                let body = r#"{"error":"NOT_FOUND"}"#;
                let resp = format!("HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            }
        }
    });

    match p_rest_cond::API::fetch(client, port as i64, 1).await {
        Err(p_rest_cond::APIError::Err404ErrorDetail(e)) => {
            assert_eq!(e.error, "NOT_FOUND");
            assert_eq!(e.detail, "item 1 missing");
        }
        other => panic!("expected Err404ErrorDetail, got {:?}", other),
    }

    match p_rest_cond::API::fetch(client, port as i64, 2).await {
        Err(p_rest_cond::APIError::Unknown(404, val)) => {
            assert_eq!(val["error"], "NOT_FOUND");
        }
        other => panic!("expected Unknown(404), got {:?}", other),
    }
}

async fn test_rest_void_path(client: &reqwest::Client) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 2048];
            let n = match stream.read(&mut buf) {
                Ok(n) if n > 0 => n,
                _ => continue,
            };
            let req_str = String::from_utf8_lossy(&buf[..n]);
            if req_str.contains("/ping") {
                let resp = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/me") {
                let body = r#"{"data":{"user":{"id":42,"name":"Bob"}}}"#;
                let resp = format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}", body.len(), body);
                let _ = stream.write_all(resp.as_bytes());
            }
        }
    });

    let void_res = p_rest_void_path::ApiVoid::fetch(client, port as i64).await;
    assert!(void_res.is_ok());

    let user = p_rest_void_path::ApiUser::fetch(client, port as i64).await.unwrap();
    assert_eq!(user.id, 42);
    assert_eq!(user.name, "Bob");

    let dead_res = p_rest_void_path::ApiVoid::fetch(client, 1).await;
    match dead_res {
        Err(p_rest_void_path::ApiVoidError::Transport(e)) => {
            assert!(e.is_connect());
        }
        other => panic!("expected Transport error, got {:?}", other),
    }
}

#[tokio::main]
async fn main() {
    let client = reqwest::Client::new();
    test_fetch(&client).await;
    test_fetch_envelope(&client).await;
    test_rest_endpoint(&client).await;
    test_rest_cond(&client).await;
    test_rest_void_path(&client).await;
    println!("ALL_REST_PASSED");
}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["cargo", "run", "--quiet"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_cargo_env(),
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "ALL_REST_PASSED" in result.stdout
