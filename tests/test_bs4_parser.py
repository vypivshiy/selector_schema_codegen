"""Tests for configurable BS4 parser engine (--bs4-parser)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ssc_codegen.core import parse_module
from ssc_codegen.main import app
from ssc_codegen.targets.python.visitor import PythonVisitor
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.spec import TargetSpec

runner = CliRunner()

_ARTICLE_KDL = """
struct Article {
    title {
        css "h1"
        text
    }
}
"""

_FN_KDL = """
fn extract_heading {
    css "h1"
    text
}

(raw)fn clean_text {
    trim
}
"""


class TestTargetSpecAndResolution:
    def test_bs4_parser_defaults_to_none_on_spec(self) -> None:
        spec = TargetSpec(lang="python")
        assert spec.bs4_parser is None

    def test_resolve_python_defaults_to_lxml(self) -> None:
        profile = resolve(TargetSpec(lang="python"))
        converter = profile.create_converter()
        assert isinstance(converter, PythonVisitor)
        assert converter.bs4_parser == "lxml"

    @pytest.mark.parametrize("parser", ["lxml", "html.parser", "html5lib"])
    def test_resolve_python_with_valid_bs4_parsers(self, parser: str) -> None:
        profile = resolve(TargetSpec(lang="python", bs4_parser=parser))
        converter = profile.create_converter()
        assert isinstance(converter, PythonVisitor)
        assert converter.bs4_parser == parser

    def test_resolve_python_rejects_invalid_bs4_parser(self) -> None:
        with pytest.raises(
            ResolutionError, match=r"Invalid --bs4-parser 'invalid'"
        ):
            resolve(TargetSpec(lang="python", bs4_parser="invalid"))

    @pytest.mark.parametrize("lib", ["lxml", "parsel", "slax"])
    def test_resolve_python_rejects_bs4_parser_for_non_bs4_lib(
        self, lib: str
    ) -> None:
        with pytest.raises(
            ResolutionError,
            match=rf"--bs4-parser is only applicable when --lib is bs4, not '{lib}'\.",
        ):
            resolve(
                TargetSpec(lang="python", lib=lib, bs4_parser="html.parser")
            )

    @pytest.mark.parametrize("lang", ["javascript", "js", "go", "rust"])
    def test_resolve_rejects_bs4_parser_for_non_python_languages(
        self, lang: str
    ) -> None:
        with pytest.raises(
            ResolutionError, match=r"--bs4-parser is not applicable"
        ):
            resolve(TargetSpec(lang=lang, bs4_parser="html.parser"))


class TestBs4ParserCodegen:
    @pytest.mark.parametrize("parser", ["lxml", "html.parser", "html5lib"])
    def test_bs4_codegen_imports_literal_and_emits_constant(
        self, parser: str
    ) -> None:
        module, diags = parse_module(_ARTICLE_KDL)
        assert not diags
        profile = resolve(TargetSpec(lang="python", bs4_parser=parser))
        converter = profile.create_converter()
        code = converter.convert(module)

        assert "from typing import Literal" in code
        assert (
            f'BS4_FEATURES: Literal["html.parser", "lxml", "html5lib"] = {parser!r}'
            in code
        )

    def test_bs4_struct_init_signature_and_body(self) -> None:
        module, diags = parse_module(_ARTICLE_KDL)
        assert not diags
        profile = resolve(TargetSpec(lang="python", bs4_parser="html.parser"))
        converter = profile.create_converter()
        code = converter.convert(module)

        expected_sig = (
            "def __init__(self, document: Union[str, BeautifulSoup, Tag], *, "
            'features: Literal["html.parser", "lxml", "html5lib"] = BS4_FEATURES) -> None:'
        )
        assert expected_sig in code
        assert "self._doc = BeautifulSoup(document, features=features)" in code

    def test_bs4_fn_and_raw_fn_signatures(self) -> None:
        module, diags = parse_module(_FN_KDL)
        assert not diags
        profile = resolve(TargetSpec(lang="python", bs4_parser="html.parser"))
        converter = profile.create_converter()
        code = converter.convert(module)

        expected_fn_sig = (
            "def extract_heading(document: str, *, "
            'features: Literal["html.parser", "lxml", "html5lib"] = BS4_FEATURES) -> str:'
        )
        assert expected_fn_sig in code
        assert "v = BeautifulSoup(document, features=features)" in code

        expected_raw_fn_sig = "def clean_text(document: str) -> str:"
        assert expected_raw_fn_sig in code
        assert "features" not in expected_raw_fn_sig


class TestBs4ParserRuntimeExecution:
    def test_struct_runtime_execution_with_default_and_override(self) -> None:
        module, diags = parse_module(_ARTICLE_KDL)
        assert not diags
        profile = resolve(TargetSpec(lang="python", bs4_parser="html.parser"))
        converter = profile.create_converter()
        code = converter.convert(module)

        ns: dict[str, Any] = {}
        exec(compile(code, "generated.py", "exec"), ns)  # noqa: S102
        article_cls = ns["Article"]

        html = "<html><body><h1>Scraped Title</h1></body></html>"

        # Default instantiation uses BS4_FEATURES ('html.parser')
        res_default = article_cls(html).parse()
        assert res_default == {"title": "Scraped Title"}

        # Dynamic override via features keyword argument
        res_lxml = article_cls(html, features="lxml").parse()
        assert res_lxml == {"title": "Scraped Title"}

        res_html_parser = article_cls(html, features="html.parser").parse()
        assert res_html_parser == {"title": "Scraped Title"}

    def test_fn_runtime_execution_with_default_and_override(self) -> None:
        module, diags = parse_module(_FN_KDL)
        assert not diags
        profile = resolve(TargetSpec(lang="python", bs4_parser="html.parser"))
        converter = profile.create_converter()
        code = converter.convert(module)

        ns: dict[str, Any] = {}
        exec(compile(code, "generated.py", "exec"), ns)  # noqa: S102
        extract_heading = ns["extract_heading"]
        clean_text = ns["clean_text"]

        html = "<html><body><h1>Function Title</h1></body></html>"

        assert extract_heading(html) == "Function Title"
        assert extract_heading(html, features="lxml") == "Function Title"
        assert extract_heading(html, features="html.parser") == "Function Title"

        assert clean_text("  hello  ") == "hello"


class TestBs4ParserCli:
    def test_cli_generate_accepts_bs4_parser(self, tmp_path: Path) -> None:
        schema = tmp_path / "schema.kdl"
        schema.write_text(_ARTICLE_KDL, encoding="utf-8")
        out_dir = tmp_path / "out"

        result = runner.invoke(
            app,
            [
                "generate",
                "python",
                str(schema),
                "-o",
                str(out_dir),
                "--bs4-parser",
                "html.parser",
            ],
        )
        assert result.exit_code == 0, result.output
        out_py = (out_dir / "schema.py").read_text(encoding="utf-8")
        assert (
            'BS4_FEATURES: Literal["html.parser", "lxml", "html5lib"] = \'html.parser\''
            in out_py
        )

    def test_cli_generate_rejects_bs4_parser_with_lxml(
        self, tmp_path: Path
    ) -> None:
        schema = tmp_path / "schema.kdl"
        schema.write_text(_ARTICLE_KDL, encoding="utf-8")
        out_dir = tmp_path / "out"

        result = runner.invoke(
            app,
            [
                "generate",
                "python",
                str(schema),
                "-o",
                str(out_dir),
                "-L",
                "lxml",
                "--bs4-parser",
                "html.parser",
            ],
        )
        assert result.exit_code == 1
        assert (
            "--bs4-parser is only applicable when --lib is bs4" in result.output
        )

    def test_cli_generate_rejects_invalid_bs4_parser(
        self, tmp_path: Path
    ) -> None:
        schema = tmp_path / "schema.kdl"
        schema.write_text(_ARTICLE_KDL, encoding="utf-8")
        out_dir = tmp_path / "out"

        result = runner.invoke(
            app,
            [
                "generate",
                "python",
                str(schema),
                "-o",
                str(out_dir),
                "--bs4-parser",
                "invalid",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid --bs4-parser 'invalid'" in result.output

    def test_cli_run_supports_bs4_parser(self, tmp_path: Path) -> None:
        schema = tmp_path / "schema.kdl"
        schema.write_text(_ARTICLE_KDL, encoding="utf-8")
        html_file = tmp_path / "page.html"
        html_file.write_text("<h1>Run Title</h1>", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "run",
                f"{schema}:Article",
                "--bs4-parser",
                "html.parser",
                "-i",
                str(html_file),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data == {"title": "Run Title"}

    def test_cli_run_rejects_bs4_parser_with_lxml(self, tmp_path: Path) -> None:
        schema = tmp_path / "schema.kdl"
        schema.write_text(_ARTICLE_KDL, encoding="utf-8")
        html_file = tmp_path / "page.html"
        html_file.write_text("<h1>Run Title</h1>", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "run",
                f"{schema}:Article",
                "-L",
                "lxml",
                "--bs4-parser",
                "html.parser",
                "-i",
                str(html_file),
            ],
        )
        assert result.exit_code == 1
        assert (
            "--bs4-parser is only applicable when --lib is bs4" in result.output
        )
