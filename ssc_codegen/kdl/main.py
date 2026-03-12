"""CLI for the KDL-based code generator."""

from __future__ import annotations

import enum
import traceback
from pathlib import Path
from typing import Annotated, List

import typer

from ssc_codegen.kdl._logging import logger, setup_debug_logging

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="KDL schema codegen — generate parsers from .kdl schema files.",
)


class Target(str, enum.Enum):
    PY_BS4 = "py-bs4"
    PY_LXML = "py-lxml"
    JS_PURE = "js-pure"


_FILE_EXTENSIONS: dict[Target, str] = {
    Target.PY_BS4: ".py",
    Target.PY_LXML: ".py",
    Target.JS_PURE: ".js",
}


def _get_converter(target: Target):
    if target == Target.PY_BS4:
        from ssc_codegen.kdl.converters.py_bs4 import PY_BASE_CONVERTER
        return PY_BASE_CONVERTER
    if target == Target.PY_LXML:
        from ssc_codegen.kdl.converters.py_lxml import PY_LXML_CONVERTER
        return PY_LXML_CONVERTER
    if target == Target.JS_PURE:
        from ssc_codegen.kdl.converters.js_pure import JS_CONVERTER
        return JS_CONVERTER
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
            "--target", "-t",
            help="Target language / library.",
            case_sensitive=False,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output", "-o",
            help="Output directory. Created automatically if it does not exist.",
            file_okay=False,
            dir_okay=True,
            writable=True,
        ),
    ] = Path("."),
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
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
) -> None:
    """Compile KDL schema files into parser code for the chosen target."""
    from ssc_codegen.kdl import parse_ast

    if verbose:
        setup_debug_logging()

    logger.debug(
        "generate() started: target=%s, output=%s, files=%s, skip_lint=%s",
        target, output, [str(f) for f in files], skip_lint,
    )

    # Collect all .kdl files from arguments (expand directories)
    kdl_files: list[Path] = []
    for path in files:
        if path.is_dir():
            # Recursively find all .kdl files in directory
            found = sorted(path.rglob("*.kdl"))
            logger.debug("  directory %s: found %d .kdl file(s)", path, len(found))
            kdl_files.extend(found)
        elif path.is_file():
            kdl_files.append(path)
        else:
            typer.echo(f"  WARNING: {path} is neither a file nor a directory, skipping", err=True)

    if not kdl_files:
        typer.echo("No .kdl files found to process.", err=True)
        raise typer.Exit(code=1)

    logger.debug("total %d .kdl file(s) to process", len(kdl_files))

    # Lint all files first (unless --skip-lint)
    if not skip_lint:
        from ssc_codegen.kdl.linter import lint_file
        
        lint_errors_found = False
        for kdl_file in kdl_files:
            result = lint_file(kdl_file)
            if result.has_errors():
                lint_errors_found = True
                typer.echo(f"\n{result.format()}", err=True)
        
        if lint_errors_found:
            typer.echo("\nLinting failed. Use --skip-lint to bypass linter.", err=True)
            raise typer.Exit(code=1)
        
        logger.debug("linting passed for all files")
    if isinstance(output, str):
        output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    ext = _FILE_EXTENSIONS[target]
    converter = _get_converter(target)

    errors: list[str] = []

    for kdl_file in kdl_files:
        out_file = output / kdl_file.with_suffix(ext).name
        logger.debug("processing: %s -> %s", kdl_file, out_file)
        try:
            ast = parse_ast(path=str(kdl_file))
            logger.debug("AST built for %s", kdl_file)
            code = converter.convert(ast)
            logger.debug("code generated for %s (%d chars)", kdl_file, len(code))
            out_file.write_text(code, encoding="utf-8")
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
            "--verbose", "-v",
            help="Enable DEBUG logging.",
        ),
    ] = False,
) -> None:
    """Check KDL schema files for errors without generating code."""
    from ssc_codegen.kdl.linter import lint_file
    
    if verbose:
        setup_debug_logging()
    
    logger.debug("check() started: files=%s, format=%s", [str(f) for f in files], fmt)
    
    # Collect all .kdl files from arguments (expand directories)
    kdl_files: list[Path] = []
    for path in files:
        if path.is_dir():
            found = sorted(path.rglob("*.kdl"))
            logger.debug("  directory %s: found %d .kdl file(s)", path, len(found))
            kdl_files.extend(found)
        elif path.is_file():
            kdl_files.append(path)
        else:
            typer.echo(f"  WARNING: {path} is neither a file nor a directory, skipping", err=True)
    
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
            typer.echo(f"\nFound {total_errors} error(s) in {len(kdl_files)} file(s).", err=True)
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
