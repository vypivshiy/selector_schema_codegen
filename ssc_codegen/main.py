"""CLI for the KDL-based code generator."""

from __future__ import annotations

import enum
import traceback
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from ssc_codegen._logging import logger, setup_debug_logging

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="KDL schema codegen — generate parsers from .kdl schema files.",
)


class Target(str, enum.Enum):
    PY_BS4 = "py-bs4"
    PY_LXML = "py-lxml"
    PY_PARSEL = "py-parsel"
    PY_SLAX = "py-slax"
    JS_PURE = "js-pure"
    GO_GOQUERY = "go-goquery"


_FILE_EXTENSIONS: dict[Target, str] = {
    Target.PY_BS4: ".py",
    Target.PY_LXML: ".py",
    Target.PY_PARSEL: ".py",
    Target.PY_SLAX: ".py",
    Target.JS_PURE: ".js",
    Target.GO_GOQUERY: ".go",
}


def _get_converter(target: Target):
    if target == Target.PY_BS4:
        from ssc_codegen.converters.py_bs4 import PY_BASE_CONVERTER

        return PY_BASE_CONVERTER
    if target == Target.PY_LXML:
        from ssc_codegen.converters.py_lxml import PY_LXML_CONVERTER

        return PY_LXML_CONVERTER
    if target == Target.PY_PARSEL:
        from ssc_codegen.converters.py_parsel import PY_PARSEL_CONVERTER

        return PY_PARSEL_CONVERTER
    if target == Target.PY_SLAX:
        from ssc_codegen.converters.py_slax import PY_SLAX_CONVERTER

        return PY_SLAX_CONVERTER
    if target == Target.JS_PURE:
        from ssc_codegen.converters.js_pure import JS_CONVERTER

        return JS_CONVERTER
    if target == Target.GO_GOQUERY:
        from ssc_codegen.converters.go_goquery import GO_GOQUERY_CONVERTER

        return GO_GOQUERY_CONVERTER
    raise ValueError(f"Unknown target: {target}")


@app.command()
def generate(
    files: Annotated[
        List[Path],
        typer.Argument(
            help="One or more .kdl schema files or directories containing .kdl files to compile.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
        ),
    ],
    target: Annotated[
        Target,
        typer.Option(
            "--target",
            "-t",
            help="Target language / library.",
            case_sensitive=False,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory. Created automatically if it does not exist.",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = Path("."),
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print full tracebacks on errors and enable DEBUG logging.",
        ),
    ] = False,
    skip_lint: Annotated[
        bool,
        typer.Option(
            "--skip-lint",
            help="Skip linting before code generation.",
        ),
    ] = False,
    css_to_xpath: Annotated[
        bool,
        typer.Option(
            "--css-to-xpath",
            help="Convert CSS selectors to XPath before code generation.",
        ),
    ] = False,
    package: Annotated[
        Optional[str],
        typer.Option(
            "--package",
            help="Package/module name for generated code. Default: output directory name.",
        ),
    ] = None,
    http_client: Annotated[
        Optional[str],
        typer.Option(
            "--http-client",
            help=(
                "HTTP client for @request codegen. "
                "Python targets: requests | httpx "
                "('httpx' emits both fetch()/async_fetch()). "
                "JS targets: fetch (default) | axios."
            ),
        ),
    ] = None,
) -> None:
    """Compile KDL schema files into parser code for the chosen target."""
    from ssc_codegen import parse_ast

    if verbose:
        setup_debug_logging()

    _PY_TARGETS = {
        Target.PY_BS4,
        Target.PY_LXML,
        Target.PY_PARSEL,
        Target.PY_SLAX,
    }
    _JS_TARGETS = {Target.JS_PURE}
    _PY_HTTP_CLIENTS = {"requests", "httpx"}
    _JS_HTTP_CLIENTS = {"fetch", "axios"}

    if http_client is not None:
        if target in _PY_TARGETS and http_client not in _PY_HTTP_CLIENTS:
            typer.echo(
                f"ERROR: Python targets accept --http-client: "
                f"{', '.join(sorted(_PY_HTTP_CLIENTS))}. Got '{http_client}'.",
                err=True,
            )
            raise typer.Exit(code=1)
        if target in _JS_TARGETS and http_client not in _JS_HTTP_CLIENTS:
            typer.echo(
                f"ERROR: JS targets accept --http-client: "
                f"{', '.join(sorted(_JS_HTTP_CLIENTS))}. Got '{http_client}'.",
                err=True,
            )
            raise typer.Exit(code=1)
        if target not in _PY_TARGETS and target not in _JS_TARGETS:
            typer.echo(
                f"ERROR: --http-client is not applicable for target '{target.value}'.",
                err=True,
            )
            raise typer.Exit(code=1)

    logger.debug(
        "generate() started: target=%s, output=%s, files=%s, skip_lint=%s",
        target,
        output,
        [str(f) for f in files],
        skip_lint,
    )

    # Collect all .kdl files from arguments (expand directories)
    kdl_files: list[Path] = []
    for path in files:
        if path.is_dir():
            # Recursively find all .kdl files in directory
            found = sorted(path.rglob("*.kdl"))
            logger.debug(
                "  directory %s: found %d .kdl file(s)", path, len(found)
            )
            kdl_files.extend(found)
        elif path.is_file():
            kdl_files.append(path)
        else:
            typer.echo(
                f"  WARNING: {path} is neither a file nor a directory, skipping",
                err=True,
            )

    if not kdl_files:
        typer.echo("No .kdl files found to process.", err=True)
        raise typer.Exit(code=1)

    logger.debug("total %d .kdl file(s) to process", len(kdl_files))

    # Lint all files first (unless --skip-lint)
    if not skip_lint:
        from ssc_codegen.linter import lint_file

        lint_errors_found = False
        for kdl_file in kdl_files:
            result = lint_file(kdl_file)
            if result.has_errors():
                lint_errors_found = True
                typer.echo(f"\n{result.format()}", err=True)

        if lint_errors_found:
            typer.echo(
                "\nLinting failed. Use --skip-lint to bypass linter.", err=True
            )
            raise typer.Exit(code=1)

        logger.debug("linting passed for all files")
    if isinstance(output, str):
        output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    ext = _FILE_EXTENSIONS[target]
    converter = _get_converter(target)

    errors: list[str] = []

    meta: dict = {"package": package or output.name}
    if http_client:
        meta["http_client"] = http_client

    for kdl_file in kdl_files:
        out_file = output / kdl_file.with_suffix(ext).name
        logger.debug("processing: %s -> %s", kdl_file, out_file)
        try:
            ast = parse_ast(path=str(kdl_file), css_to_xpath=css_to_xpath)
            logger.debug("AST built for %s", kdl_file)

            if converter.has_support_files:
                files = converter.convert_all(ast, **meta)
                for name, content in files.items():
                    target_path = out_file if name == "" else output / name
                    target_path.write_text(content, encoding="utf-8")
                    if name:
                        typer.echo(f"  -> {target_path}")
                code = files[""]
            else:
                code = converter.convert(ast, **meta)
                out_file.write_text(code, encoding="utf-8")

            logger.debug(
                "code generated for %s (%d chars)", kdl_file, len(code)
            )
            typer.echo(f"  {kdl_file} -> {out_file}")
        except Exception as exc:
            if verbose:
                typer.echo(traceback.format_exc(), err=True)
            else:
                typer.echo(f"  ERROR {kdl_file}: {exc}", err=True)
            errors.append(str(kdl_file))

    if errors:
        raise typer.Exit(code=1)


@app.command()
def check(
    files: Annotated[
        List[Path],
        typer.Argument(
            help="One or more .kdl schema files or directories containing .kdl files to check.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
        ),
    ],
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'text' (human-readable) or 'json' (for LLM pipelines).",
        ),
    ] = "text",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable DEBUG logging.",
        ),
    ] = False,
) -> None:
    """Check KDL schema files for errors without generating code."""
    from ssc_codegen.linter import lint_file

    if verbose:
        setup_debug_logging()

    logger.debug(
        "check() started: files=%s, format=%s", [str(f) for f in files], fmt
    )

    # Collect all .kdl files from arguments (expand directories)
    kdl_files: list[Path] = []
    for path in files:
        if path.is_dir():
            found = sorted(path.rglob("*.kdl"))
            logger.debug(
                "  directory %s: found %d .kdl file(s)", path, len(found)
            )
            kdl_files.extend(found)
        elif path.is_file():
            kdl_files.append(path)
        else:
            typer.echo(
                f"  WARNING: {path} is neither a file nor a directory, skipping",
                err=True,
            )

    if not kdl_files:
        typer.echo("No .kdl files found to check.", err=True)
        raise typer.Exit(code=1)

    logger.debug("total %d .kdl file(s) to check", len(kdl_files))

    # Check all files
    all_results = []
    total_errors = 0

    for kdl_file in kdl_files:
        result = lint_file(kdl_file)
        all_results.append(result)

        if result.has_errors():
            total_errors += result.error_count
            if fmt == "text":
                typer.echo(result.format(style="text"), err=True)

    if total_errors > 0:
        if fmt == "text":
            typer.echo(
                f"\nFound {total_errors} error(s) in {len(kdl_files)} file(s).",
                err=True,
            )
        else:
            # JSON: output all errors from all files
            import json

            all_errors_json = []
            for result in all_results:
                if result.has_errors():
                    all_errors_json.extend([e.to_dict() for e in result.errors])
            typer.echo(json.dumps(all_errors_json, indent=2))
        raise typer.Exit(code=1)

    # Success
    if fmt == "text":
        typer.echo(f"✓ All {len(kdl_files)} file(s) passed linting.")
    else:
        # JSON: empty array means no errors
        typer.echo("[]")


class _PyTarget(str, enum.Enum):
    """Python-only targets for the run command."""

    PY_BS4 = "py-bs4"
    PY_LXML = "py-lxml"
    PY_PARSEL = "py-parsel"
    PY_SLAX = "py-slax"


@app.command()
def run(
    schema: Annotated[
        str,
        typer.Argument(
            help="Schema target in format 'path/to/schema.kdl:StructName'.",
        ),
    ],
    target: Annotated[
        _PyTarget,
        typer.Option(
            "--target",
            "-t",
            help="Target library for execution.",
            case_sensitive=False,
        ),
    ] = _PyTarget.PY_BS4,
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input",
            "-i",
            help="HTML input file. If omitted, reads from stdin.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print generated code to stderr and enable DEBUG logging.",
        ),
    ] = False,
    css_to_xpath: Annotated[
        bool,
        typer.Option(
            "--css-to-xpath",
            help="Convert CSS selectors to XPath before execution.",
        ),
    ] = False,
) -> None:
    """Run a KDL schema struct against HTML input and output JSON.

    \b
    Examples:
        cat page.html | ssc-kdl run examples/booksToScrape.kdl:MainCatalogue
        ssc-kdl run schema.kdl:Product -i page.html
        ssc-kdl run schema.kdl:Product -t py-lxml < page.html
    """
    import json
    import sys

    from ssc_codegen import parse_ast
    from ssc_codegen.ast import Struct
    from ssc_codegen.converters.helpers import to_pascal_case

    if verbose:
        setup_debug_logging()

    # Parse schema:StructName
    if ":" not in schema:
        typer.echo(
            "ERROR: schema argument must be in format 'path/to/schema.kdl:StructName'",
            err=True,
        )
        raise typer.Exit(code=1)

    file_part, struct_name = schema.rsplit(":", 1)
    kdl_path = Path(file_part)
    if not kdl_path.is_file():
        typer.echo(f"ERROR: file not found: {kdl_path}", err=True)
        raise typer.Exit(code=1)

    # Build AST
    try:
        module_ast = parse_ast(path=str(kdl_path), css_to_xpath=css_to_xpath)
    except Exception as exc:
        if verbose:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"ERROR: failed to parse {kdl_path}: {exc}", err=True)
        raise typer.Exit(code=1)

    # Verify struct exists
    structs = [n for n in module_ast.body if isinstance(n, Struct)]
    struct_names = [s.name for s in structs]
    if struct_name not in struct_names:
        typer.echo(
            f"ERROR: struct '{struct_name}' not found in {kdl_path}. "
            f"Available: {', '.join(struct_names)}",
            err=True,
        )
        raise typer.Exit(code=1)

    class_name = to_pascal_case(struct_name)

    # Generate code
    converter = _get_converter(Target(target.value))
    code = converter.convert(module_ast)

    if verbose:
        typer.echo("--- generated code ---", err=True)
        typer.echo(code, err=True)
        typer.echo("--- end generated code ---", err=True)

    # Read HTML
    if input_file is not None:
        html = input_file.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            typer.echo(
                "Reading HTML from stdin (Ctrl+D to end, or use -i <file>)...",
                err=True,
            )
        html = sys.stdin.read()

    if not html.strip():
        typer.echo("ERROR: empty HTML input", err=True)
        raise typer.Exit(code=1)

    # Execute generated code
    namespace: dict = {}
    try:
        exec(code, namespace)  # noqa: S102
    except Exception as exc:
        if verbose:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(
                f"ERROR: failed to execute generated code: {exc}", err=True
            )
        raise typer.Exit(code=1)

    cls = namespace.get(class_name)
    if cls is None:
        typer.echo(
            f"ERROR: class '{class_name}' not found in generated code.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        result = cls(html).parse()
    except Exception as exc:
        if verbose:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"ERROR: parsing failed: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def health(
    schema: Annotated[
        str,
        typer.Argument(
            help="Schema target in format 'path/to/schema.kdl:StructName'.",
        ),
    ],
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input",
            "-i",
            help="HTML input file. If omitted, reads from stdin.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'text' (human-readable) or 'json' (for LLM pipelines).",
        ),
    ] = "text",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable DEBUG logging.",
        ),
    ] = False,
    css_to_xpath: Annotated[
        bool,
        typer.Option(
            "--css-to-xpath",
            help="Convert CSS selectors to XPath before checking.",
        ),
    ] = False,
) -> None:
    """Check that all selectors in a struct match elements in the given HTML.

    \b
    Examples:
        cat page.html | ssc-kdl health examples/booksToScrape.kdl:MainCatalogue
        ssc-kdl health schema.kdl:Product -i page.html
        ssc-kdl health schema.kdl:Product -f json < page.html
    """
    import sys

    from ssc_codegen import parse_ast
    from ssc_codegen.ast import Struct
    from ssc_codegen.health import check_struct_health

    if verbose:
        setup_debug_logging()

    # Parse schema:StructName
    if ":" not in schema:
        typer.echo(
            "ERROR: schema argument must be in format 'path/to/schema.kdl:StructName'",
            err=True,
        )
        raise typer.Exit(code=1)

    file_part, struct_name = schema.rsplit(":", 1)
    kdl_path = Path(file_part)
    if not kdl_path.is_file():
        typer.echo(f"ERROR: file not found: {kdl_path}", err=True)
        raise typer.Exit(code=1)

    # Build AST
    try:
        module_ast = parse_ast(path=str(kdl_path), css_to_xpath=css_to_xpath)
    except Exception as exc:
        if verbose:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"ERROR: failed to parse {kdl_path}: {exc}", err=True)
        raise typer.Exit(code=1)

    # Find struct
    structs = [n for n in module_ast.body if isinstance(n, Struct)]
    struct_names = [s.name for s in structs]
    if struct_name not in struct_names:
        typer.echo(
            f"ERROR: struct '{struct_name}' not found in {kdl_path}. "
            f"Available: {', '.join(struct_names)}",
            err=True,
        )
        raise typer.Exit(code=1)

    target_struct = next(s for s in structs if s.name == struct_name)

    # Read HTML
    if input_file is not None:
        html = input_file.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            typer.echo(
                "Reading HTML from stdin (Ctrl+D to end, or use -i <file>)...",
                err=True,
            )
        html = sys.stdin.read()

    if not html.strip():
        typer.echo("ERROR: empty HTML input", err=True)
        raise typer.Exit(code=1)

    # Run health check
    result = check_struct_health(target_struct, html, module=module_ast)
    typer.echo(result.format(fmt=fmt))

    if result.has_failures():
        raise typer.Exit(code=1)


@app.command()
def shell(
    schema: Annotated[
        str | None,
        typer.Argument(
            help="Schema target in format 'path/to/schema.kdl:StructName'. "
            "If omitted, starts empty REPL.",
        ),
    ] = None,
    target: Annotated[
        _PyTarget,
        typer.Option(
            "--target",
            "-t",
            help="Python backend for the REPL.",
            case_sensitive=False,
        ),
    ] = _PyTarget.PY_BS4,
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input",
            "-i",
            help="HTML input file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option(
            "--url",
            help="URL to fetch HTML from.",
        ),
    ] = None,
    http_client: Annotated[
        str | None,
        typer.Option(
            "--http-client",
            help="HTTP client for REST structs: httpx (default) or requests.",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print generated code and enable DEBUG logging.",
        ),
    ] = False,
    css_to_xpath: Annotated[
        bool,
        typer.Option(
            "--css-to-xpath",
            help="Convert CSS selectors to XPath.",
        ),
    ] = False,
) -> None:
    """Launch an interactive REPL shell for testing KDL schema parsers.

    \b
    Examples:
        ssc-gen shell examples/booksToScrape.kdl:Book --url https://books.toscrape.com/
        ssc-gen shell schema.kdl:Product -i page.html -t py-lxml
        ssc-gen shell examples/restApiLike.kdl:DummyJsonApi --http-client httpx
        ssc-gen shell
    """
    from ssc_codegen.repl import Repl, ReplState

    if verbose:
        setup_debug_logging()

    state = ReplState(
        target=target.value,
        http_client=http_client or "httpx",
        verbose=verbose,
        css_to_xpath=css_to_xpath,
    )

    if input_file is not None:
        state.html = input_file.read_text(encoding="utf-8")

    if schema is not None:
        if ":" in schema:
            path_part, struct_name = schema.rsplit(":", 1)
            kdl_path = Path(path_part)
        else:
            kdl_path = Path(schema)
            struct_name = ""
        if not kdl_path.is_file():
            typer.echo(f"ERROR: file not found: {kdl_path}", err=True)
            raise typer.Exit(code=1)
        from ssc_codegen import parse_ast
        from ssc_codegen.ast import Struct as StructNode

        try:
            state.module_ast = parse_ast(
                path=str(kdl_path), css_to_xpath=css_to_xpath
            )
        except Exception as exc:
            if verbose:
                typer.echo(traceback.format_exc(), err=True)
            else:
                typer.echo(
                    f"ERROR: failed to parse {kdl_path}: {exc}", err=True
                )
            raise typer.Exit(code=1)

        state.schema_path = kdl_path
        state.kdl_source = kdl_path.read_text(encoding="utf-8-sig")

        structs = [
            n for n in state.module_ast.body if isinstance(n, StructNode)
        ]
        if not struct_name:
            if structs:
                struct_name = structs[0].name
        struct_names = [s.name for s in structs]
        if struct_name and struct_name not in struct_names:
            typer.echo(
                f"ERROR: struct '{struct_name}' not found. "
                f"Available: {', '.join(struct_names)}",
                err=True,
            )
            raise typer.Exit(code=1)
        state.struct_name = struct_name

    if url is not None and not state.html:
        try:
            from ssc_codegen.repl import _fetch_html

            state.html = _fetch_html(url)
        except Exception as exc:
            typer.echo(f"ERROR fetching URL: {exc}", err=True)
            raise typer.Exit(code=1)

    repl = Repl(state)
    repl.cmdloop()


@app.command(
    name="openapi-to-ssc",
    help="Experimental converter swagger openapi 3.0 to kdl DSL",
)
def openapi_to_ssc(
    spec: Annotated[
        Path,
        typer.Argument(
            help="OpenAPI/Swagger spec file (YAML or JSON).",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output .kdl file path.",
            file_okay=True,
            dir_okay=False,
            writable=True,
        ),
    ],
    endpoints: Annotated[
        Optional[str],
        typer.Option(
            "--endpoints",
            "-e",
            help="Comma-separated endpoint filter: 'GET /pets,POST /pets'.",
        ),
    ] = None,
    skip_lint: Annotated[
        bool,
        typer.Option(
            "--skip-lint",
            help="Skip lint validation of generated .kdl.",
        ),
    ] = False,
) -> None:
    """Convert an OpenAPI/Swagger spec (YAML/JSON) to a KDL REST schema file."""
    from ssc_codegen.openapi import convert_openapi

    endpoint_filter: list[tuple[str, str]] | None = None
    if endpoints:
        endpoint_filter = []
        for pair in endpoints.split(","):
            parts = pair.strip().split(None, 1)
            if len(parts) == 2:
                endpoint_filter.append((parts[0].upper(), parts[1]))
            else:
                typer.echo(
                    f"WARNING: invalid endpoint filter '{pair}', skipping",
                    err=True,
                )

    try:
        text = convert_openapi(
            spec_path=spec,
            output_path=output,
            endpoints=endpoint_filter,
        )
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"  {spec} -> {output}")

    if not skip_lint:
        from ssc_codegen.linter import lint_file

        result = lint_file(output)
        if result.has_errors():
            typer.echo(result.format(style="text"), err=True)
            raise typer.Exit(code=1)
        typer.echo("  Lint passed.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
