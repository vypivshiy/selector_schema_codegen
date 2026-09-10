"""Cargo-backed smoke tests for the Rust target."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ssc_codegen.core import parse_module
from ssc_codegen.targets.rust import RustVisitor


pytestmark = pytest.mark.skipif(
    shutil.which("cargo") is None,
    reason="Cargo toolchain not found in PATH",
)


def _cargo_env() -> dict[str, str]:
    """Keep concurrent full-suite Cargo builds within CI memory limits."""
    env = os.environ.copy()
    env["CARGO_BUILD_JOBS"] = "1"
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
