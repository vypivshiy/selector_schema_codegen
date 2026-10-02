import json

from typer.testing import CliRunner

from ssc_codegen.main import app


runner = CliRunner()


def test_generate_rejects_duplicate_output_names(tmp_path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for directory in (left, right):
        (directory / "same.kdl").write_text(
            "(raw)fn value { trim }\n", encoding="utf-8"
        )
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "generate",
            "python",
            str(left / "same.kdl"),
            str(right / "same.kdl"),
            "-o",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "output collision" in result.output
    assert not output.exists()


def test_generate_rejects_runtime_schema_collision(tmp_path) -> None:
    schema = tmp_path / "sscgen_runtime.kdl"
    schema.write_text("(raw)fn value { trim }\n", encoding="utf-8")
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        ["generate", "python", str(schema), "-o", str(output), "-R"],
    )

    assert result.exit_code == 1
    assert "Python runtime" in result.output
    assert not output.exists()


def test_generate_go_defaults_to_main_package(tmp_path) -> None:
    schema = tmp_path / "value.kdl"
    schema.write_text("(raw)fn value { trim }\n", encoding="utf-8")
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        ["generate", "go", str(schema), "-o", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "package main" in (output / "value.go").read_text(encoding="utf-8")
    assert "package main" in (output / "sscgen_runtime.go").read_text(
        encoding="utf-8"
    )


def test_generate_go_rejects_invalid_package_before_writing(tmp_path) -> None:
    schema = tmp_path / "value.kdl"
    schema.write_text("(raw)fn value { trim }\n", encoding="utf-8")
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "generate",
            "go",
            str(schema),
            "-o",
            str(output),
            "--package",
            "bad-name",
        ],
    )

    assert result.exit_code == 1
    assert "invalid Go package" in result.output
    assert not output.exists()


def test_generate_rust_writes_parser_and_shared_runtime(tmp_path) -> None:
    schema = tmp_path / "value.kdl"
    schema.write_text("(raw)fn value { trim }\n", encoding="utf-8")
    output = tmp_path / "out"

    result = runner.invoke(
        app, ["generate", "rust", str(schema), "-o", str(output)]
    )

    assert result.exit_code == 0, result.output
    assert (output / "value.rs").exists()
    assert (output / "sscgen_runtime.rs").exists()
    assert "super::sscgen_runtime" in (output / "value.rs").read_text(
        encoding="utf-8"
    )


def test_generate_rust_supports_rest_schema(tmp_path) -> None:
    schema = tmp_path / "api.kdl"
    schema.write_text(
        """json User { id int; name str }
struct Api type=rest {
    @request response=User \"\"\"
    GET /users HTTP/1.1
    Host: api.example.com
    \"\"\"
}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["generate", "rust", str(schema), "-o", str(tmp_path / "out")]
    )

    assert result.exit_code == 0
    out_file = tmp_path / "out" / "api.rs"
    assert out_file.exists()
    assert "pub struct Api;" in out_file.read_text(encoding="utf-8")


def test_check_json_is_single_document_for_multiple_files(tmp_path) -> None:
    files = []
    for name in ("one", "two"):
        path = tmp_path / f"{name}.kdl"
        path.write_text(f"unknown-{name}\n", encoding="utf-8")
        files.append(path)

    result = runner.invoke(
        app,
        ["check", *(str(path) for path in files), "-f", "json"],
    )

    assert result.exit_code == 1
    diagnostics = json.loads(result.stdout)
    assert len(diagnostics) == 2
    assert {item["path"] for item in diagnostics} == {
        str(path) for path in files
    }


def test_health_stops_on_schema_diagnostics(tmp_path) -> None:
    schema = tmp_path / "invalid.kdl"
    schema.write_text(
        'unknown\nstruct Broken { title { css "h1"; text } }\n',
        encoding="utf-8",
    )
    html = tmp_path / "page.html"
    html.write_text("<h1>ok</h1>", encoding="utf-8")

    result = runner.invoke(
        app,
        ["health", f"{schema}:Broken", "-i", str(html)],
    )

    assert result.exit_code == 1
    assert "Unknown node: unknown" in result.output


def test_generate_skips_extension_only_file(tmp_path) -> None:
    extensions = tmp_path / "extensions.kdl"
    extensions.write_text(
        "extension Utils { value { sig T str; py { emit #\"{{out}} = 'x'\"# } } }\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        ["generate", "python", str(extensions), "-o", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert not output.exists()


def test_extension_library_contributes_to_consumer_runtime(tmp_path) -> None:
    extensions = tmp_path / "sscgen_runtime.kdl"
    extensions.write_text(
        r'''
extension Utils {
    value {
        sig T str
        py {
            import "from uuid import uuid4"
            helper make_value {
                source #"""
                    def make_value(value: str) -> str:
                        return value
                    """#
            }
            emit #"{{out}} = make_value(str(uuid4()))"#
        }
    }
}
''',
        encoding="utf-8",
    )
    schema = tmp_path / "schema.kdl"
    schema.write_text(
        'import "./sscgen_runtime.kdl" { (extension)Utils }\n'
        "(raw)fn value { !Utils.value }\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "generate",
            "python",
            str(tmp_path),
            "-o",
            str(output),
            "-R",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (output / "sscgen_runtime.kdl.py").exists()
    generated = (output / "schema.py").read_text(encoding="utf-8")
    runtime = (output / "sscgen_runtime.py").read_text(encoding="utf-8")
    assert "from uuid import uuid4" in generated
    assert "from .sscgen_runtime import make_value" in generated
    assert "def make_value" in runtime


def test_check_with_target_filter(tmp_path) -> None:
    # 'self' produces '_parse_self' in Python (valid), but 'self' in Rust (invalid)
    schema = tmp_path / "schema.kdl"
    schema.write_text(
        'struct Data { self { css "h1"; text } }\n', encoding="utf-8"
    )

    # check with all targets should fail on Rust
    res_all = runner.invoke(app, ["check", str(schema)])
    assert res_all.exit_code == 1
    assert "rust identifier" in res_all.output

    # check targeting python specifically should pass
    res_py = runner.invoke(app, ["check", str(schema), "-t", "python"])
    assert res_py.exit_code == 0, res_py.output

    # check targeting rust specifically should fail on 'self'
    res_rust = runner.invoke(app, ["check", str(schema), "-t", "rust"])
    assert res_rust.exit_code == 1
    assert "rust identifier" in res_rust.output


def test_generate_python_with_shared_placeholders_and_keywords(
    tmp_path,
) -> None:
    schema = tmp_path / "api.kdl"
    schema.write_text(
        "struct Data {\n"
        '    ref { css "a"; text }\n'
        '    type { css "b"; text }\n'
        "}\n\n"
        "(rest)struct Api {\n"
        '    @request name=list_items """\n'
        "        GET /items?page={{page:int?}}&limit={{limit:int?}}&pub={{pub}} HTTP/1.1\n"
        "        Host: example.com\n"
        '        """\n'
        '    @request name=get_item """\n'
        "        GET /items/{{id:int}}?limit={{limit:int?}} HTTP/1.1\n"
        "        Host: example.com\n"
        '        """\n'
        "}\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    result = runner.invoke(
        app,
        ["generate", "python", str(schema), "-o", str(output)],
    )
    assert result.exit_code == 0, result.output
    generated = (output / "api.py").read_text(encoding="utf-8")
    assert "def _parse_ref(" in generated
    assert "def _parse_type(" in generated
    assert "def list_items(" in generated
    assert "pub: str" in generated
    assert "def get_item(" in generated


def test_generate_rust_with_raw_identifiers(tmp_path) -> None:
    schema = tmp_path / "schema.kdl"
    schema.write_text(
        "struct Data {\n"
        '    ref { css "a"; text }\n'
        '    type { css "b"; text }\n'
        "}\n\n"
        "(rest)struct Api {\n"
        '    @request name=get """\n'
        "        GET /?pub={{pub}} HTTP/1.1\n"
        "        Host: example.com\n"
        '        """\n'
        "}\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    result = runner.invoke(
        app,
        ["generate", "rust", str(schema), "-o", str(output)],
    )
    assert result.exit_code == 0, result.output
    generated = (output / "schema.rs").read_text(encoding="utf-8")
    assert "pub r#ref: String," in generated
    assert "pub r#type: String," in generated
    assert "r#pub: &str" in generated


def test_health_and_run_use_python_target_validation(tmp_path) -> None:
    schema = tmp_path / "schema.kdl"
    schema.write_text(
        'struct Item {\n    self { css "h1"; text }\n}\n',
        encoding="utf-8",
    )
    html = tmp_path / "page.html"
    html.write_text("<h1>Hello</h1>", encoding="utf-8")

    health_res = runner.invoke(
        app, ["health", f"{schema}:Item", "-i", str(html)]
    )
    assert health_res.exit_code == 0, health_res.output

    run_res = runner.invoke(app, ["run", f"{schema}:Item", "-i", str(html)])
    assert run_res.exit_code == 0, run_res.output
    assert '"self": "Hello"' in run_res.output
