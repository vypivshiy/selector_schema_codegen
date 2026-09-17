"""Cargo-backed smoke tests for the Rust target."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ssc_codegen.core import parse_module
from ssc_codegen.exceptions import BuildTimeError
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.rust import RustVisitor
from ssc_codegen.targets.spec import TargetSpec


pytestmark = pytest.mark.skipif(
    shutil.which("cargo") is None,
    reason="Cargo toolchain not found in PATH",
)


_SHARED_TARGET_DIR = (
    Path(__file__).resolve().parents[2] / "target" / "test_rust_target"
)


def _cargo_env() -> dict[str, str]:
    """Keep concurrent full-suite Cargo builds within CI memory limits."""
    env = os.environ.copy()
    env.setdefault("CARGO_BUILD_JOBS", "1")
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


def test_generated_item_parser_compiles_and_runs(tmp_path: Path) -> None:
    """A generated CSS/text/cast parser is valid Rust and returns owned data."""
    schema = """
struct Product {
    title {
        css "h1"
        text
        trim
    }
    price {
        css ".price"
        text
        to-int
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_smoke"
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
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

fn main() {
    let mut parser = parser::ProductParser::new(
        "<main><h1> Widget </h1><span class=\\\"price\\\">42</span></main>",
    ).unwrap();
    let result = parser.parse().unwrap();
    println!(\"{}\", serde_json::to_string(&result).unwrap());
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
    assert result.stdout.strip() == '{"title":"Widget","price":42}'


def test_generated_raw_json_parser_compiles_and_runs(tmp_path: Path) -> None:
    """Raw parsers select an envelope fragment and decode a typed model."""
    schema = """
json Product {
    id int
    label str? from="display_label"
}

(raw)struct Payload {
    product {
        jsonify Product path="data.item"
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_json_smoke"
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
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

fn main() {
    let mut parser = parser::PayloadParser::new(
        r#"{\"data\":{\"item\":{\"id\":7,\"display_label\":\"ok\"}}}"#,
    ).unwrap();
    let result = parser.parse().unwrap();
    println!(\"{}\", serde_json::to_string(&result).unwrap());
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
    assert result.stdout.strip() == '{"product":{"id":7,"label":"ok"}}'


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


def test_rust_extension_is_emitted_and_runs(tmp_path: Path) -> None:
    """Rust extension emit templates participate in the fallible pipeline."""
    schema = """
extension Utils {
    prefix {
        sig str str
        rust { emit #"let {{out}} = format!(\"prefix-{}\", {{in}});"# }
    }
}

(raw)fn value {
    !Utils.prefix
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod parser;
mod sscgen_runtime;

fn main() {
    println!(\"{}\", parser::value(\"x\").unwrap());
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "prefix-x"


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


def test_lifecycle_precomputed_init_and_detached_dom_nodes(
    tmp_path: Path,
) -> None:
    """Validate fallible init, repeatable parse, checks, detached nodes and ownership."""
    schema = """
struct ChildCard {
    badge {
        css ".badge"
        text
        trim
    }
}

struct ParentDoc {
    @init {
        cached-banner {
            css "#banner"
        }
    }

    @pre-validate {
        assert {
            css "main"
        }
    }

    @check is-published {
        css ".published"
        to-bool
    }

    title {
        css "h1"
        text
        trim
    }

    banner-text-before-remove {
        @cached-banner
        text
        trim
    }

    remove-banner {
        css-remove "#banner"
        to-bool
    }

    remove-nonexistent {
        css-remove ".no-such-class"
        to-bool
    }

    banner-after-remove {
        css "#banner"
        text
        fallback "gone"
    }

    banner-from-cache-after-remove {
        @cached-banner
        text
        trim
    }

    child {
        css ".card"
        nested ChildCard
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let valid_html = "<main><div class=\"published\">Yes</div><div id=\"banner\">Important Notice</div><h1>Parent Title</h1><div class=\"card\"><span class=\"badge\">VIP</span></div></main>";

    // 1. Successful initialization and check method
    let mut parser = parser::ParentDocParser::new(valid_html).expect("init should succeed");
    assert!(parser.is_published().expect("check should succeed"));

    // 2. Repeatable parse execution
    let res1 = parser.parse().expect("first parse should succeed");
    let res2 = parser.parse().expect("second parse should succeed");
    assert_eq!(res1.title, res2.title);
    assert_eq!(res1.title, "Parent Title");
    assert_eq!(res1.banner_text_before_remove, "Important Notice");
    assert_eq!(res1.banner_after_remove, "gone");
    assert_eq!(res1.banner_from_cache_after_remove, "Important Notice");
    assert_eq!(res1.child.badge, "VIP");

    // 3. Extracted output outlives dropped parser instance
    drop(parser);
    let serialized = serde_json::to_string(&res1).expect("owned result serializes after parser drop");
    assert!(serialized.contains("Parent Title"));

    // 4. Missing init field fails early in constructor
    let bad_html = "<main><h1>No banner</h1></main>";
    let init_err = parser::ParentDocParser::new(bad_html);
    assert!(init_err.is_err(), "missing init selector must fail constructor");

    // 5. Pre-validate assertion failure aborts parse
    let no_main_html = "<div id=\"banner\">Notice</div><h1>Title</h1>";
    let mut bad_preval = parser::ParentDocParser::new(no_main_html).expect("init succeeds");
    let parse_err = bad_preval.parse();
    assert!(parse_err.is_err(), "failing pre-validation must abort parse");

    println!("LIFECYCLE_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "LIFECYCLE_OK" in result.stdout


def test_all_struct_shapes_execute(tmp_path: Path) -> None:
    """Validate list, flat, dict, table, and raw split-doc struct shapes."""
    schema = """
(list)struct ListItem {
    @split-doc {
        css-all "li"
    }
    name {
        text
        trim
    }
}

(flat)struct FlatTags {
    tags {
        css-all ".tag"
        text
        trim
    }
}

(dict)struct DictProps {
    @split-doc {
        css-all ".prop"
    }
    @key {
        attr "data-key"
    }
    @value {
        text
        trim
    }
}

(table)struct TableInfo {
    @table {
        css "table"
    }
    @rows {
        css-all "tr"
    }
    @match {
        css "th"
        text
        trim
        lower
    }
    @value {
        css "td"
        text
        trim
    }

    id {
        match {
            eq "id"
        }
    }

    qty {
        match {
            eq "quantity"
        }
        to-int
        fallback 0
    }

    cost {
        match {
            eq "cost"
        }
        to-float
        fallback 0.0
    }
}

(raw)struct RawLines {
    @split-doc {
        split "\\n"
    }
    item {
        trim
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let html = "<ul><li>Alpha</li><li>Beta</li></ul><div class=\"tag\">rust</div><div class=\"tag\">parser</div><div class=\"tag\">rust</div><div class=\"prop\" data-key=\"color\">blue</div><div class=\"prop\" data-key=\"size\">large</div><table><tr><th>ID</th><td>XYZ-99</td></tr><tr><th>Quantity</th><td>15</td></tr><tr><th>Cost</th><td>19.95</td></tr><tr><th>Ignored</th><td>skip</td></tr></table>";

    // List struct
    let mut list_p = parser::ListItemParser::new(html).unwrap();
    let list_res = list_p.parse().unwrap();
    assert_eq!(list_res.len(), 2);
    assert_eq!(list_res[0].name, "Alpha");
    assert_eq!(list_res[1].name, "Beta");

    // Flat struct
    let mut flat_p = parser::FlatTagsParser::new(html).unwrap();
    let flat_res = flat_p.parse().unwrap();
    assert_eq!(flat_res.len(), 2);
    assert!(flat_res.contains(&"rust".to_string()));
    assert!(flat_res.contains(&"parser".to_string()));

    // Dict struct
    let mut dict_p = parser::DictPropsParser::new(html).unwrap();
    let dict_res = dict_p.parse().unwrap();
    assert_eq!(dict_res.get("color").map(String::as_str), Some("blue"));
    assert_eq!(dict_res.get("size").map(String::as_str), Some("large"));

    // Table struct
    let mut table_p = parser::TableInfoParser::new(html).unwrap();
    let table_res = table_p.parse().unwrap();
    assert_eq!(table_res.get("id").and_then(|v| v.as_str()), Some("XYZ-99"));
    assert_eq!(table_res.get("qty").and_then(|v| v.as_i64()), Some(15));
    assert_eq!(table_res.get("cost").and_then(|v| v.as_f64()), Some(19.95));
    assert_eq!(table_res.get("Ignored"), None);

    // Raw struct with split-doc
    let mut raw_p = parser::RawLinesParser::new("first\nsecond\nthird\n").unwrap();
    let raw_res = raw_p.parse().unwrap();
    assert_eq!(raw_res.len(), 4);
    assert_eq!(raw_res[0].item, "first");
    assert_eq!(raw_res[1].item, "second");
    assert_eq!(raw_res[2].item, "third");

    println!("SHAPES_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "SHAPES_OK" in result.stdout


def test_unicode_string_slice_index_fmt_and_fallback(tmp_path: Path) -> None:
    """Validate Unicode scalar chars(), index bounds, fmt, backreferences, and fallback."""
    schema = r"""
(raw)struct TextSuite {
    cyrillic-slice {
        slice 0 6
    }
    emoji-slice {
        slice 7 9
    }
    inverted-slice {
        slice 5 2
    }
    char-len {
        len
    }
    index-emoji {
        index 7
    }
    negative-index {
        index -1
    }
    formatted {
        fmt "prefix-{{}}-suffix"
    }
    dollar-sub {
        re-sub #"(\w+)"# "$1-ok"
    }
    backslash-sub {
        re-sub #"(\w+)"# #"\1-ok"#
    }
    opt-field {
        re #"(not_found)"#
        fallback #null
    }
    default-field {
        re #"(not_found)"#
        fallback "recovered"
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let input = "Привет 🦀 world";
    let mut p = parser::TextSuiteParser::new(input).unwrap();
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

    // Index out of bounds error
    assert!(sscgen_runtime::index("abc", 50, "test").is_err());
    assert!(sscgen_runtime::index("abc", -50, "test").is_err());

    println!("UNICODE_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "UNICODE_OK" in result.stdout


def test_json_fragment_first_and_array_schema_execute(tmp_path: Path) -> None:
    """Validate fragment-first JSON array decoding, dot-path aliases, omitempty, and required error."""
    schema = """
(array)json ItemRecord {
    item-id int from="nested.raw_id"
    title str
    label str?
    extra str? @omitempty
}

(raw)struct CatalogPayload {
    items {
        jsonify ItemRecord path="data.catalog"
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]
    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let valid_json = r#"{"data":{"catalog":[{"nested":{"raw_id":42},"title":"Gadget","label":"first","extra":"present"},{"nested":{"raw_id":43},"title":"Widget","label":null,"extra":null}]}}"#;
    let mut p = parser::CatalogPayloadParser::new(valid_json).unwrap();
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

    // Serialization skips omitempty field
    let s0 = serde_json::to_string(&res.items[0]).unwrap();
    let s1 = serde_json::to_string(&res.items[1]).unwrap();
    assert!(s0.contains("\"extra\":\"present\""));
    assert!(!s1.contains("\"extra\""), "omitempty field must be skipped when None: {}", s1);

    // Missing required field produces SscError
    let missing_json = r#"{"data":{"catalog":[{"nested":{"raw_id":99}}]}}"#; // missing title
    let mut p_bad = parser::CatalogPayloadParser::new(missing_json).unwrap();
    let parse_err = p_bad.parse();
    assert!(parse_err.is_err(), "missing required title must fail");

    println!("JSON_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "JSON_OK" in result.stdout


def test_html_fn_compiles_and_runs(tmp_path: Path) -> None:
    """Non-raw HTML fn parses input into dom_query::Document and evaluates pipelines."""
    schema = """
struct CardInfo {
    title {
        css "h2"
        text
    }
}

fn page_title {
    @doc "Extract the <h1> text from an HTML document."
    css "h1"
    text
    trim
}

fn active_links {
    css-all "a"
    filter {
        attr-eq "class" "active"
    }
    attr "href"
}

fn parse_card {
    css ".card"
    nested CardInfo
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]

    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let html = r#"
    <html>
        <body>
            <h1>  Hello Rust Functions!  </h1>
            <a class="active" href="/home">Home</a>
            <a href="/about">About</a>
            <a class="active" href="/contact">Contact</a>
            <div class="card">
                <h2>Featured Card</h2>
            </div>
        </body>
    </html>
    "#;

    let title = parser::page_title(html).expect("page_title should succeed");
    assert_eq!(title, "Hello Rust Functions!");

    let links = parser::active_links(html).expect("active_links should succeed");
    assert_eq!(links, vec!["/home".to_string(), "/contact".to_string()]);

    let card = parser::parse_card(html).expect("parse_card should succeed");
    assert_eq!(card.title, "Featured Card");

    println!("HTML_FN_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "HTML_FN_OK" in result.stdout


def test_raw_nested_compiles_and_runs(tmp_path: Path) -> None:
    """Raw struct nested invocations support raw-to-raw, raw-to-html, and html-to-raw pipelines."""
    schema = """
(raw)struct RawMetadata {
    version {
        re #"ver=([0-9]+\\.[0-9]+)"#
    }
}

struct HtmlCard {
    heading {
        css "h3"
        text
    }
}

(raw)struct InnerSnippet {
    id {
        re #"id=(\\d+)"#
        to-int
    }
    label {
        re #"name=([a-zA-Z]+)"#
    }
}

(raw)struct OuterEnvelope {
    snippet {
        nested InnerSnippet
    }
    card {
        re #"(<div class=\"card\">.*?</div>)"#
        nested HtmlCard
    }
}

struct HtmlWithRawChild {
    meta {
        css "div#meta"
        text
        nested RawMetadata
    }
}
"""
    module, diagnostics = parse_module(schema)
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]

    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let raw_data = "id=123;name=Rust;extra=<div class=\"card\"><h3>Card Heading</h3></div>";
    let mut envelope_parser = parser::OuterEnvelopeParser::new(raw_data).expect("envelope parser init");
    let envelope = envelope_parser.parse().expect("envelope parse");
    // Verify memory safety: parsed child types outlive parser drop
    drop(envelope_parser);
    assert_eq!(envelope.snippet.id, 123);
    assert_eq!(envelope.snippet.label, "Rust");
    assert_eq!(envelope.card.heading, "Card Heading");
    let s = serde_json::to_string(&envelope.snippet).expect("snippet serializes independently");
    assert!(s.contains("\"id\":123"));

    let html_data = "<html><body><div id=\"meta\">ver=2.5;build=release</div></body></html>";
    let mut html_parser = parser::HtmlWithRawChildParser::new(html_data).expect("html parser init");
    let html_res = html_parser.parse().expect("html parse");
    drop(html_parser);
    assert_eq!(html_res.meta.version, "2.5");

    println!("RAW_NESTED_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "RAW_NESTED_OK" in result.stdout


def test_fn_schema_25_compiles_and_runs(tmp_path: Path) -> None:
    """Full 25_fn.kdl schema with HTML and raw functions runs successfully."""
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "integration"
        / "schemas"
        / "25_fn.kdl"
    )
    module, diagnostics = parse_module(
        schema_path.read_text(encoding="utf-8"), source_path=schema_path
    )
    assert not [item for item in diagnostics if item.severity.name == "ERROR"]

    source_dir = _write_cargo_project(tmp_path)
    converter = RustVisitor()
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        r"""mod parser;
mod sscgen_runtime;

fn main() {
    let fn_html = "<html><body><h1>Hello World</h1><a href='/a'>A</a><a href='/b'>B</a></body></html>";
    let fn_raw = "first line\nsecond line\nthird line";
    let fn_version = "app version=1.2.3 released";

    let title = parser::page_title(fn_html).unwrap();
    assert_eq!(title, "Hello World");

    let links = parser::all_links(fn_html).unwrap();
    assert_eq!(links, vec!["/a".to_string(), "/b".to_string()]);

    let first = parser::first_line(fn_raw).unwrap();
    assert_eq!(first, "first line");

    let ver = parser::extract_version(fn_version).unwrap();
    assert_eq!(ver, "1.2.3");

    println!("SCHEMA_25_OK");
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
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "SCHEMA_25_OK" in result.stdout


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


def test_html_fetch_compiles_and_runs(tmp_path: Path) -> None:
    """HTML parser with @request compiles and executes async fetch via reqwest."""
    schema = """
struct PostPage {
    @request \"\"\"
    curl http://127.0.0.1:{{port:int}}/posts?tag={{tag}}
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

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_fetch"
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
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

#[tokio::main]
async fn main() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();

    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 1024];
            let _ = stream.read(&mut buf);
            let body = "<html><body><h1>Fetched Title</h1></body></html>";
            let response = format!(
                "HTTP/1.1 200 OK\\r\\nContent-Type: text/html\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                body.len(),
                body
            );
            stream.write_all(response.as_bytes()).unwrap();
            break;
        }
    });

    let client = reqwest::Client::new();
    let mut parser = parser::PostPageParser::fetch(&client, port as i64, "rust").await.unwrap();
    let result = parser.parse().unwrap();
    println!("{}", serde_json::to_string(&result).unwrap());
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
    assert result.stdout.strip() == '{"title":"Fetched Title"}'


def test_html_fetch_response_path_compiles_and_runs(tmp_path: Path) -> None:
    """HTML parser with @request response-path extracts HTML from JSON envelope."""
    schema = """
struct JsonEnvelopePage {
    @request response-path="data.markup" \"\"\"
    curl http://127.0.0.1:{{port:int}}/envelope
    \"\"\"

    heading {
        css "h2"
        text
    }
}
"""
    module, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_fetch_envelope"
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
    (source_dir / "parser.rs").write_text(
        converter.convert(module), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

#[tokio::main]
async fn main() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();

    thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut buf = [0u8; 1024];
            let _ = stream.read(&mut buf);
            let body = r#"{"data":{"markup":"<div><h2>Inner Heading</h2></div>"}}"#;
            let response = format!(
                "HTTP/1.1 200 OK\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                body.len(),
                body
            );
            stream.write_all(response.as_bytes()).unwrap();
            break;
        }
    });

    let client = reqwest::Client::new();
    let mut parser = parser::JsonEnvelopePageParser::fetch(&client, port as i64).await.unwrap();
    let result = parser.parse().unwrap();
    println!("{}", serde_json::to_string(&result).unwrap());
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
    assert result.stdout.strip() == '{"heading":"Inner Heading"}'


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


def test_rest_endpoint_execution(tmp_path: Path) -> None:
    """REST client executes requests, matches typed errors, handles unknown status, and exposes err.status()."""
    schema = """
json User {
    id int
    name str
}

json Err {
    code int
    message str
}

struct API type=rest {
    @error 404 Err
    @request name=get-user response=User \"\"\"
    GET http://127.0.0.1:{{port:int}}/users/{{id:int}} HTTP/1.1
    \"\"\"
}
"""
    module_ast, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_rest_exec"
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
    (source_dir / "parser.rs").write_text(
        converter.convert(module_ast), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

#[tokio::main]
async fn main() {
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
                let resp = format!(
                    "HTTP/1.1 200 OK\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/users/2") {
                let body = r#"{"code":404,"message":"user not found"}"#;
                let resp = format!(
                    "HTTP/1.1 404 Not Found\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/users/3") {
                let body = r#"{"detail":"bad gateway"}"#;
                let resp = format!(
                    "HTTP/1.1 502 Bad Gateway\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes());
            }
        }
    });

    let client = reqwest::Client::new();

    // 1. Success response via typed aliases
    let user_res: parser::GetUserResult = parser::API::get_user(&client, port as i64, 1).await;
    let user = user_res.unwrap();
    assert_eq!(user.id, 1);
    assert_eq!(user.name, "Alice");

    let api_res: parser::APIGetUserResult = parser::API::get_user(&client, port as i64, 1).await;
    assert_eq!(api_res.unwrap().id, 1);

    // 2. Typed error response (@error 404)
    match parser::API::get_user(&client, port as i64, 2).await {
        Err(parser::APIError::Err404(err)) => {
            assert_eq!(err.code, 404);
            assert_eq!(err.message, "user not found");
        }
        other => panic!("expected Err404, got {:?}", other),
    }

    // 3. Unknown error response (HTTP 502)
    match parser::API::get_user(&client, port as i64, 3).await {
        Err(err) => {
            assert_eq!(err.status(), Some(502));
            match err {
                parser::APIError::Unknown(status, val) => {
                    assert_eq!(status, 502);
                    assert_eq!(val["detail"], "bad gateway");
                }
                other => panic!("expected Unknown, got {:?}", other),
            }
        }
        other => panic!("expected Err, got {:?}", other),
    }

    println!("REST_EXEC_OK");
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
    assert "REST_EXEC_OK" in result.stdout


def test_rest_condition_matching_execution(tmp_path: Path) -> None:
    """REST client matches conditional @error rules and distinguishes matched vs unmatched status."""
    schema = """
json Err {
    error str
    detail str
}

json User {
    id int
    name str
}

struct API type=rest {
    @error 404 Err error detail
    @request response=User \"\"\"
    GET http://127.0.0.1:{{port:int}}/items/{{id:int}} HTTP/1.1
    \"\"\"
}
"""
    module_ast, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_rest_cond"
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
    (source_dir / "parser.rs").write_text(
        converter.convert(module_ast), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

#[tokio::main]
async fn main() {
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
                let resp = format!(
                    "HTTP/1.1 404 Not Found\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/items/2") {
                let body = r#"{"error":"NOT_FOUND"}"#;
                let resp = format!(
                    "HTTP/1.1 404 Not Found\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes());
            }
        }
    });

    let client = reqwest::Client::new();

    // 1. Matched conditional error
    match parser::API::fetch(&client, port as i64, 1).await {
        Err(parser::APIError::Err404ErrorDetail(e)) => {
            assert_eq!(e.error, "NOT_FOUND");
            assert_eq!(e.detail, "item 1 missing");
        }
        other => panic!("expected Err404ErrorDetail, got {:?}", other),
    }

    // 2. Unmatched condition on 404 -> falls back to Unknown
    match parser::API::fetch(&client, port as i64, 2).await {
        Err(parser::APIError::Unknown(404, val)) => {
            assert_eq!(val["error"], "NOT_FOUND");
        }
        other => panic!("expected Unknown(404), got {:?}", other),
    }

    println!("REST_COND_OK");
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
    assert "REST_COND_OK" in result.stdout


def test_rest_void_and_response_path_execution(tmp_path: Path) -> None:
    """REST void endpoint returns Ok(()) and response-path extracts nested model."""
    schema = """
json User {
    id int
    name str
}

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
    module_ast, diagnostics = parse_module(schema)
    errors = [d for d in diagnostics if d.severity.name == "ERROR"]
    assert not errors

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (tmp_path / "Cargo.toml").write_text(
        """[package]
name = "sscgen_rust_rest_void_path"
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
    (source_dir / "parser.rs").write_text(
        converter.convert(module_ast), encoding="utf-8"
    )
    (source_dir / "sscgen_runtime.rs").write_text(
        converter.emit_runtime(), encoding="utf-8"
    )
    (source_dir / "main.rs").write_text(
        """mod sscgen_runtime;
mod parser;

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

#[tokio::main]
async fn main() {
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
                let resp = "HTTP/1.1 200 OK\\r\\nContent-Length: 0\\r\\nConnection: close\\r\\n\\r\\n";
                let _ = stream.write_all(resp.as_bytes());
            } else if req_str.contains("/me") {
                let body = r#"{"data":{"user":{"id":42,"name":"Bob"}}}"#;
                let resp = format!(
                    "HTTP/1.1 200 OK\\r\\nContent-Type: application/json\\r\\nContent-Length: {}\\r\\nConnection: close\\r\\n\\r\\n{}",
                    body.len(), body
                );
                let _ = stream.write_all(resp.as_bytes());
            }
        }
    });

    let client = reqwest::Client::new();

    // 1. Void endpoint returns Ok(())
    let void_res = parser::ApiVoid::fetch(&client, port as i64).await;
    assert!(void_res.is_ok());

    // 2. response-path extracts nested UserJson
    let user = parser::ApiUser::fetch(&client, port as i64).await.unwrap();
    assert_eq!(user.id, 42);
    assert_eq!(user.name, "Bob");

    // 3. Transport error when targeting closed port
    let dead_res = parser::ApiVoid::fetch(&client, 1).await;
    match dead_res {
        Err(parser::ApiVoidError::Transport(e)) => {
            assert!(e.is_connect());
        }
        other => panic!("expected Transport error, got {:?}", other),
    }

    println!("REST_VOID_PATH_OK");
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
    assert "REST_VOID_PATH_OK" in result.stdout
