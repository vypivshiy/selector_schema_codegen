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
