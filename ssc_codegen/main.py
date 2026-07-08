"""CLI for the KDL-based code generator."""

from __future__ import annotations

import enum
import traceback
from pathlib import Path
from typing import Annotated, List, Literal, Optional

import typer

from ssc_codegen._logging import logger, setup_debug_logging
from ssc_codegen.core import parse_module, format_diagnostics, ReadDiagnostic
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.spec import TargetSpec


app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="KDL schema codegen — generate parsers from .kdl schema files.",
)


class Lang(str, enum.Enum):
    PYTHON = "python"
    JS = "js"


class HtmlLib(str, enum.Enum):
    BS4 = "bs4"
    LXML = "lxml"
    PARSEL = "parsel"
    SLAX = "slax"


class FmtType(str, enum.Enum):
    TEXT = "text"
    JSON = "json"


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
    lang: Annotated[
        Lang,
        typer.Option(
            "--lang",
            "-l",
            help="Target language backend.",
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
    lib: Annotated[
        Optional[HtmlLib],
        typer.Option(
            "--lib",
            "-L",
            help="HTML parsing library (Python only). Default: bs4.",
        ),
    ] = None,
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
                "Python: httpx (default) | aiohttp | requests. "
                "JS: fetch (default) | axios."
            ),
        ),
    ] = None,
    separate_runtime: Annotated[
        bool,
        typer.Option(
            "--separate-runtime",
            "-R",
            help="Extract helper functions into a separate runtime module.",
        ),
    ] = False,
    runtime_name: Annotated[
        Optional[str],
        typer.Option(
            "--runtime-name",
            "-rn",
            help="Runtime module name (default: sscgen_runtime).",
        ),
    ] = None,
    fmt: Annotated[
        FmtType,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'text' (human-readable) or 'json' (for LLM pipelines).",
        ),
    ] = FmtType.TEXT,
) -> None:
    """Compile KDL schema files into parser code for the chosen target."""

    if verbose:
        setup_debug_logging()

    try:
        profile = resolve(
            TargetSpec(
                lang=lang.value,
                lib=lib.value if lib else None,
                http_client=http_client,
                separate_runtime=separate_runtime,
            )
        )
    except ResolutionError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1)

    logger.debug(
        "generate() started: lang=%s, lib=%s, output=%s, files=%s, skip_lint=%s",
        lang,
        lib,
        output,
        [str(f) for f in files],
        skip_lint,
    )

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
        typer.echo("No .kdl files found to process.", err=True)
        raise typer.Exit(code=1)

    logger.debug("total %d .kdl file(s) to process", len(kdl_files))

    if isinstance(output, str):
        output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    ext = profile.file_extension
    converter = profile.create_converter()

    errors: list[str] = []

    meta: dict = {"package": package or output.name}
    if http_client:
        meta["http_client"] = http_client

    if separate_runtime:
        from ssc_codegen.generation.runtime import register_runtime_file

        _runtime_name = runtime_name or "sscgen_runtime"
        meta["runtime_module"] = _runtime_name
        generate_runtime = register_runtime_file(
            converter,
            _runtime_name,
            include_fallback=profile.runtime_include_fallback,
        )

    from ssc_codegen.ast import Module

    parsed: list[tuple[Path, Module]] = []
    for kdl_file in kdl_files:
        try:
            ast, err = parse_module(
                kdl_file.read_text(encoding="utf-8"), source_path=kdl_file
            )
            if not skip_lint:
                lint_output = format_diagnostics(
                    err, filepath=kdl_file, fmt=fmt.value
                )
                if lint_output:
                    typer.echo(lint_output, err=True)
                    errors.append(lint_output)
                    continue
            logger.debug("AST built for %s", kdl_file)
            parsed.append((kdl_file, ast))
        except Exception as exc:
            if verbose:
                typer.echo(f"ERROR {kdl_file}:", err=True)
                typer.echo(traceback.format_exc(), err=True)
            else:
                typer.echo(f"  ERROR {kdl_file}: {exc}", err=True)
            errors.append(str(kdl_file))

    if separate_runtime and parsed:
        runtime_path = output / f"{_runtime_name}.py"
        runtime_path.write_text(
            generate_runtime([ast for _, ast in parsed]),
            encoding="utf-8",
        )
        typer.echo(f"  -> {runtime_path}")

    for kdl_file, ast in parsed:
        out_file = output / kdl_file.with_suffix(ext).name
        logger.debug("processing: %s -> %s", kdl_file, out_file)
        try:
            code = converter.convert(ast, **meta)
            out_file.write_text(code, encoding="utf-8")
            logger.debug(
                "code generated for %s (%d chars)", kdl_file, len(code)
            )
            typer.echo(f"  {kdl_file} -> {out_file}")
        except Exception as exc:
            if verbose:
                typer.echo(f"ERROR {kdl_file}:", err=True)
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
        FmtType,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'text' (human-readable) or 'json' (for LLM pipelines).",
        ),
    ] = FmtType.TEXT,
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

    if verbose:
        setup_debug_logging()

    logger.debug(
        "check() started: files=%s, format=%s", [str(f) for f in files], fmt
    )

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

    all_results: list[ReadDiagnostic] = []
    total_errors = 0

    for kdl_file in kdl_files:
        try:
            _, errs = parse_module(
                kdl_file.read_text(encoding="utf-8"), source_path=kdl_file
            )
        except Exception as exc:
            if verbose:
                typer.echo(f"ERROR {kdl_file}:", err=True)
                typer.echo(traceback.format_exc(), err=True)
            else:
                typer.echo(f"  ERROR {kdl_file}: {exc}", err=True)
            total_errors += 1
            continue
        all_results.extend(errs)

        if errs:
            total_errors += len(errs)
            output = format_diagnostics(errs, filepath=kdl_file, fmt=fmt.value)
            if output:
                typer.echo(output, err=True)

    if total_errors > 0:
        if fmt == FmtType.TEXT:
            typer.echo(
                f"\nFound {total_errors} error(s) in {len(kdl_files)} file(s).",
                err=True,
            )
        raise typer.Exit(code=1)
    if fmt == FmtType.TEXT:
        typer.echo(f"All {len(kdl_files)} file(s) passed linting.")
    else:
        typer.echo("[]")


@app.command()
def run(
    schema: Annotated[
        str,
        typer.Argument(
            help="Schema target in format 'path/to/schema.kdl:StructName'.",
        ),
    ],
    lang: Annotated[
        Lang,
        typer.Option(
            "--lang",
            "-l",
            help="Target language.",
            case_sensitive=False,
        ),
    ] = Lang.PYTHON,
    lib: Annotated[
        Optional[HtmlLib],
        typer.Option(
            "--lib",
            "-L",
            help="HTML parsing library (Python only). Default: bs4.",
        ),
    ] = None,
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
    fmt: Annotated[
        FmtType,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'text' (human-readable) or 'json' (for LLM pipelines).",
        ),
    ] = FmtType.TEXT,
) -> None:
    """Run a KDL schema struct against HTML input and output JSON.

    \b
    Examples:
        cat page.html | ssc-gen run examples/booksToScrape.kdl:MainCatalogue
        ssc-gen run schema.kdl:Product -i page.html
        ssc-gen run schema.kdl:Product -l python -L lxml < page.html
    """
    import json
    import sys

    from ssc_codegen.ast import StructBase
    from ssc_codegen.naming import to_pascal_case

    if verbose:
        setup_debug_logging()

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

    try:
        module_ast, errs = parse_module(
            kdl_path.read_text(encoding="utf-8"), source_path=kdl_path
        )
        if errs:
            output = format_diagnostics(errs, filepath=kdl_path, fmt=fmt.value)
            if output:
                typer.echo(output, err=True)
            raise typer.Exit(1)

    except Exception as exc:
        if verbose:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"ERROR: failed to parse {kdl_path}: {exc}", err=True)
        raise typer.Exit(code=1)

    structs = [n for n in module_ast.body if isinstance(n, StructBase)]
    struct_names = [s.name for s in structs]
    if struct_name not in struct_names:
        typer.echo(
            f"ERROR: struct '{struct_name}' not found in {kdl_path}. "
            f"Available: {', '.join(struct_names)}",
            err=True,
        )
        raise typer.Exit(code=1)

    class_name = to_pascal_case(struct_name)

    try:
        profile = resolve(
            TargetSpec(
                lang=lang.value,
                lib=lib.value if lib else None,
            )
        )
    except ResolutionError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1)

    converter = profile.create_converter()
    code = converter.convert(module_ast)

    if verbose:
        typer.echo("--- generated code ---", err=True)
        typer.echo(code, err=True)
        typer.echo("--- end generated code ---", err=True)

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
        Literal["text", "json"],
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
    """Check that all selectors in a struct match elements in the given HTML.

    \b
    Examples:
        cat page.html | ssc-gen health examples/booksToScrape.kdl:MainCatalogue
        ssc-gen health schema.kdl:Product -i page.html
        ssc-gen health schema.kdl:Product -f json < page.html
    """
    import sys

    from ssc_codegen import parse_module
    from ssc_codegen.ast import StructBase
    from ssc_codegen.health import check_struct_health

    if verbose:
        setup_debug_logging()

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

    try:
        module_ast, _ = parse_module(
            kdl_path.read_text(encoding="utf-8"), source_path=kdl_path
        )
    except Exception as exc:
        if verbose:
            typer.echo(traceback.format_exc(), err=True)
        else:
            typer.echo(f"ERROR: failed to parse {kdl_path}: {exc}", err=True)
        raise typer.Exit(code=1)

    structs = [n for n in module_ast.body if isinstance(n, StructBase)]
    struct_names = [s.name for s in structs]
    if struct_name not in struct_names:
        typer.echo(
            f"ERROR: struct '{struct_name}' not found in {kdl_path}. "
            f"Available: {', '.join(struct_names)}",
            err=True,
        )
        raise typer.Exit(code=1)

    target_struct = next(s for s in structs if s.name == struct_name)

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

    result = check_struct_health(target_struct, html, module=module_ast)
    typer.echo(result.format(fmt=fmt))

    if result.has_failures():
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
