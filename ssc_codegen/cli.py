import os
import sys

from ssc_codegen.ast_builder import build_ast_module
from ssc_codegen.cli_utils import (
    ConverterLike,
    DartLIBS,
    GoLIBS,
    JsLIBS,
    PyLIBS,
    cb_check_ssc_files,
    cb_folder_out,
    create_fmt_cmd,
    import_converter,
)
from ssc_codegen.converters.tools import go_naive_fix_docstring

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


from pathlib import Path
from typing import Annotated, Callable, List, Optional

from typer import Argument, BadParameter, Option, Typer

app = Typer(no_args_is_help=True)

COMMENT_STRING = "autogenerated by ssc-gen DO NOT_EDIT"

_HELP_SSC_FILES_ARG = "ssc-gen config files"
_HELP_OUTPUT_FOLDER = "output folder"
_HELP_CORE_LIB = "core parser library"
_HELP_FILE_PREFIX = "out files prefix (<prefix>+<out>)"
_HELP_FILE_SUFFIX = "out files suffix (<out>+<suffix>)"
_HELP_FMT = "format code output"
_HELP_TO_XPATH = "convert all css queries to xpath"
_HELP_TO_CSS = "convert all xpath queries to css (works not guaranteed)"
_HELP_DEBUG_COMM_TOKENS = (
    "add debug token string in comment every generated instruction"
)


@app.command(help="Show version and exit")
def version() -> None:
    from ssc_codegen import VERSION

    print(f"ssc-gen {VERSION}")


def generate_code(
    *,
    converter: ConverterLike,
    out: Path,
    prefix: str,
    ssc_files: List[Path],
    suffix: str,
    comment_str: str,
    fmt_cmd: list[str],
    code_cb: Callable[[list[str]], str] = lambda c: "\n".join(c),
    docstring_class_top: bool = False,
    variables_patches: dict[str, str] | None = None,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
    debug_instructions: bool = False,
    debug_comment_prefix: str = "",
) -> None:
    variables_patches = variables_patches or {}
    if css_to_xpath and xpath_to_css:
        raise BadParameter("Should be passed to-xpath or to-css flag")
    if css_to_xpath:
        print("Convert ALL CSS queries to XPATH")
    elif xpath_to_css:
        print("Convert ALL XPATH queries to CSS")

    print("Generating code start")
    if debug_instructions:
        print("TOGGLE debug generated tokens")
        converter.set_debug_prefix(debug_comment_prefix)
    for file_cfg in ssc_files:
        name = file_cfg.name.split(".")[0]
        out_file = f"{prefix}{name}{suffix}"
        print(f"Make AST {file_cfg.name}...")
        ast_module = build_ast_module(
            file_cfg,
            docstring_class_top=docstring_class_top,
            css_to_xpath=css_to_xpath,
            xpath_to_css=xpath_to_css,
        )
        print(f"Convert to code {file_cfg.name}...")
        code_parts = converter.convert_program(ast_module, comment=comment_str)
        code = code_cb(code_parts)
        for k, v in variables_patches.items():
            code = code.replace(f"${k}$", v)
        out_path = out / out_file
        print(f"save {str(out_path)}")
        with open(out_path, "w") as f:
            f.write(code)
    if fmt_cmd:
        print("format code")
        for cmd in fmt_cmd:
            os.system(cmd)
    print("done")


@app.command("py", help="generate python modules")
def gen_py(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=_HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        PyLIBS, Option("--lib", "-i", help=_HELP_CORE_LIB)
    ] = PyLIBS.BS4,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=_HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=_HELP_FILE_SUFFIX)
    ] = ".py",
    fmt: Annotated[bool, Option(help=_HELP_FMT, is_flag=True)] = True,
    to_xpath: Annotated[
        bool, Option(help=_HELP_TO_XPATH, is_flag=True)
    ] = False,
    to_css: Annotated[bool, Option(help=_HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[
        bool, Option(help=_HELP_DEBUG_COMM_TOKENS, is_flag=True)
    ] = False,
) -> None:
    converter = import_converter(f"py_{lib.value}")
    if fmt:
        commands = ["ruff format {}", "ruff check {} --fix"]
        fmt_cmd = create_fmt_cmd(ssc_files, prefix, suffix, out, commands)
    else:
        fmt_cmd = []
    generate_code(
        converter=converter,
        out=out,
        prefix=prefix,
        ssc_files=ssc_files,
        suffix=suffix,
        comment_str=f"# {COMMENT_STRING}",
        fmt_cmd=fmt_cmd,
        xpath_to_css=to_css,
        css_to_xpath=to_xpath,
        debug_instructions=debug,
        debug_comment_prefix="# ",
    )


@app.command("js", help="generate javascript modules (unstable)")
def gen_js(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=_HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        JsLIBS, Option("--lib", "-i", help=_HELP_CORE_LIB)
    ] = JsLIBS.PURE,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=_HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=_HELP_FILE_SUFFIX)
    ] = ".js",
    fmt: Annotated[bool, Option(help=_HELP_FMT, is_flag=True)] = True,
    to_xpath: Annotated[
        bool, Option(help=_HELP_TO_XPATH, is_flag=True)
    ] = False,
    to_css: Annotated[bool, Option(help=_HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[
        bool, Option(help=_HELP_DEBUG_COMM_TOKENS, is_flag=True)
    ] = False,
) -> None:
    converter = import_converter(f"js_{lib.value}")
    if fmt:
        # TODO: js formatters
        commands: list[str] = []
        fmt_cmd = create_fmt_cmd(ssc_files, prefix, suffix, out, commands)
    else:
        fmt_cmd = []
    generate_code(
        converter=converter,
        out=out,
        prefix=prefix,
        ssc_files=ssc_files,
        suffix=suffix,
        comment_str=f"// {COMMENT_STRING}",
        fmt_cmd=fmt_cmd,
        docstring_class_top=True,
        xpath_to_css=to_css,
        css_to_xpath=to_xpath,
        debug_instructions=debug,
        debug_comment_prefix="// ",
    )


@app.command("dart", help="generate dart modules (BROKEN)")
def gen_dart(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=_HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        DartLIBS, Option("--lib", "-i", help=_HELP_CORE_LIB)
    ] = DartLIBS.UNIVERSAL_HTML,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=_HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=_HELP_FILE_SUFFIX)
    ] = ".dart",
    fmt: Annotated[bool, Option(help=_HELP_FMT, is_flag=True)] = True,
    to_xpath: Annotated[
        bool, Option(help=_HELP_TO_XPATH, is_flag=True)
    ] = False,
    to_css: Annotated[bool, Option(help=_HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[
        bool, Option(help=_HELP_DEBUG_COMM_TOKENS, is_flag=True)
    ] = False,
) -> None:
    converter = import_converter(f"dart_{lib.value}")
    if fmt:
        commands = ["dart format {}", "dart fix {}"]
        fmt_cmd = create_fmt_cmd(ssc_files, prefix, suffix, out, commands)
    else:
        fmt_cmd = []
    generate_code(
        converter=converter,
        out=out,
        prefix=prefix,
        ssc_files=ssc_files,
        suffix=suffix,
        comment_str=f"// {COMMENT_STRING}",
        fmt_cmd=fmt_cmd,
        code_cb=go_naive_fix_docstring,
        docstring_class_top=True,
        xpath_to_css=to_css,
        css_to_xpath=to_xpath,
        debug_instructions=debug,
        debug_comment_prefix="// ",
    )


@app.command("go", help="generate golang modules (BROKEN)")
def gen_go(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=_HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        GoLIBS, Option("--lib", "-i", help=_HELP_CORE_LIB)
    ] = GoLIBS.GOQUERY,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=_HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=_HELP_FILE_SUFFIX)
    ] = ".go",
    fmt: Annotated[bool, Option(help=_HELP_FMT, is_flag=True)] = True,
    package: Annotated[
        Optional[str],
        Option(help="package name (default - get output folder name)"),
    ] = None,
    to_xpath: Annotated[
        bool, Option(help=_HELP_TO_XPATH, is_flag=True)
    ] = False,
    to_css: Annotated[bool, Option(help=_HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[bool, Option(help=_HELP_DEBUG_COMM_TOKENS)] = False,
) -> None:
    converter = import_converter(f"go_{lib.value}")
    if fmt:
        commands = ["gofmt -w {}"]
        fmt_cmd = create_fmt_cmd(ssc_files, prefix, suffix, out, commands)
    else:
        fmt_cmd = []
    generate_code(
        converter=converter,
        out=out,
        prefix=prefix,
        ssc_files=ssc_files,
        suffix=suffix,
        comment_str=f"// {COMMENT_STRING}",
        fmt_cmd=fmt_cmd,
        code_cb=go_naive_fix_docstring,
        docstring_class_top=True,
        variables_patches={"PACKAGE": package or out.name},
        xpath_to_css=to_css,
        css_to_xpath=to_xpath,
        debug_instructions=debug,
        debug_comment_prefix="// ",
    )


def main() -> None:
    app()


if __name__ == "__main__":
    app()
