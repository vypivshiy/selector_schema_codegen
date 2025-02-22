import json
import os
import pprint
import sys
import warnings
from ichrome.exceptions import ChromeRuntimeError
import typer

from ssc_codegen.ast_builder import build_ast_module
from ssc_codegen.cli.cli_utils import (
    ConverterLike,
    create_fmt_cmd,
    import_converter,
    raw_json_check_keys,
    suggest_class_name,
)
from ssc_codegen.cli.code_callbacks import (
    CB_PY_CODE,
    CB_DART_CODE,
    CB_GO_CODE,
    CB_JS_CODE,
)
from ssc_codegen.cli.runtime_parse_runners import (
    assert_cls_target,
    parse_from_html_file,
    print_json_output,
    parse_from_http_request,
    parse_from_chrome,
)
from .consts import (
    PyLIBS,
    JsLIBS,
    DartLIBS,
    GoLIBS,
    COMMENT_STRING,
    HELP_OUTPUT_FOLDER,
    HELP_CORE_LIB,
    HELP_FILE_PREFIX,
    HELP_FILE_SUFFIX,
    HELP_FMT,
    HELP_TO_XPATH,
    HELP_TO_CSS,
    HELP_DEBUG_COMM_TOKENS,
    CMD_VERSION,
    CMD_PY,
    CMD_JS,
    CMD_DART,
    CMD_GO,
    CMD_JSON_GEN,
    DEFAULT_UA,
)
from ..converters.json_to_schema import convert_json_to_schema_code
from .cli_callbacks import cb_check_ssc_files, cb_folder_out


from pathlib import Path
from typing import Annotated, Callable, List, Optional

from typer import Argument, BadParameter, Option, Typer

app = Typer(no_args_is_help=True)


@app.command(help=CMD_VERSION)
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
    """universal generate code entrypoint"""
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


@app.command("py", help=CMD_PY)
def gen_py(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        PyLIBS, Option("--lib", "-i", help=HELP_CORE_LIB)
    ] = PyLIBS.BS4,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=HELP_FILE_SUFFIX)
    ] = ".py",
    fmt: Annotated[bool, Option(help=HELP_FMT, is_flag=True)] = True,
    to_xpath: Annotated[bool, Option(help=HELP_TO_XPATH, is_flag=True)] = False,
    to_css: Annotated[bool, Option(help=HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[
        bool, Option(help=HELP_DEBUG_COMM_TOKENS, is_flag=True)
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
        code_cb=CB_PY_CODE,
    )


@app.command("js", help=CMD_JS)
def gen_js(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        JsLIBS, Option("--lib", "-i", help=HELP_CORE_LIB)
    ] = JsLIBS.PURE,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=HELP_FILE_SUFFIX)
    ] = ".js",
    fmt: Annotated[bool, Option(help=HELP_FMT, is_flag=True)] = True,
    to_xpath: Annotated[bool, Option(help=HELP_TO_XPATH, is_flag=True)] = False,
    to_css: Annotated[bool, Option(help=HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[
        bool, Option(help=HELP_DEBUG_COMM_TOKENS, is_flag=True)
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
        code_cb=CB_JS_CODE,
    )


@app.command("dart", help=CMD_DART)
def gen_dart(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        DartLIBS, Option("--lib", "-i", help=HELP_CORE_LIB)
    ] = DartLIBS.UNIVERSAL_HTML,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=HELP_FILE_SUFFIX)
    ] = ".dart",
    fmt: Annotated[bool, Option(help=HELP_FMT, is_flag=True)] = True,
    to_xpath: Annotated[bool, Option(help=HELP_TO_XPATH, is_flag=True)] = False,
    to_css: Annotated[bool, Option(help=HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[
        bool, Option(help=HELP_DEBUG_COMM_TOKENS, is_flag=True)
    ] = False,
) -> None:
    converter = import_converter(f"dart_{lib.value}")
    if fmt:
        commands = ["dart format {}"]
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
        code_cb=CB_DART_CODE,
        docstring_class_top=True,
        xpath_to_css=to_css,
        css_to_xpath=to_xpath,
        debug_instructions=debug,
        debug_comment_prefix="// ",
    )


@app.command("go", help=CMD_GO)
def gen_go(
    ssc_files: Annotated[
        List[Path],
        Argument(help="ssc-gen config files", callback=cb_check_ssc_files),
    ],
    out: Annotated[
        Path,
        Option("--out", "-o", help=HELP_OUTPUT_FOLDER, callback=cb_folder_out),
    ],
    lib: Annotated[
        GoLIBS, Option("--lib", "-i", help=HELP_CORE_LIB)
    ] = GoLIBS.GOQUERY,
    prefix: Annotated[
        str, Option("--prefix", "-p", help=HELP_FILE_PREFIX)
    ] = "",
    suffix: Annotated[
        str, Option("--suffix", "-s", help=HELP_FILE_SUFFIX)
    ] = ".go",
    fmt: Annotated[bool, Option(help=HELP_FMT, is_flag=True)] = True,
    package: Annotated[
        Optional[str],
        Option(help="package name (default - get output folder name)"),
    ] = None,
    to_xpath: Annotated[bool, Option(help=HELP_TO_XPATH, is_flag=True)] = False,
    to_css: Annotated[bool, Option(help=HELP_TO_CSS, is_flag=True)] = False,
    debug: Annotated[bool, Option(help=HELP_DEBUG_COMM_TOKENS)] = False,
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
        # todo: better API for code callbacks
        code_cb=CB_GO_CODE,
        docstring_class_top=True,
        variables_patches={"PACKAGE": package or out.name},
        xpath_to_css=to_css,
        css_to_xpath=to_xpath,
        debug_instructions=debug,
        debug_comment_prefix="// ",
    )


@app.command(
    "json-gen",
    help=CMD_JSON_GEN,
)
def json_to_schema(
    out: Annotated[
        Path,
        Option("--out", "-o", help="output filename"),
    ],
    jsn_file: Annotated[
        typer.FileText,
        Argument(
            help="json file or stdin. json entrypoint should be starts as dict(map) object"
        ),
        # https://github.com/fastapi/typer/issues/345#issuecomment-2124380470
    ] = sys.stdin,  # type: ignore[assignment]
    entrypoint_name: Annotated[
        str,
        Option("--name", "-n", help="first struct name entrypoint"),
    ] = "Content",
) -> None:
    if isinstance(jsn_file, Path):
        jsn_text = jsn_file.read_text(encoding="utf-8").strip()
    else:
        jsn_text = jsn_file.read().strip()

    raw_json_check_keys(jsn_text)
    jsn = json.loads(jsn_text)
    if not isinstance(jsn, dict) and not isinstance(jsn[0], dict):
        msg = f"Expected dict but got {type(jsn).__name__}"
        raise typer.BadParameter(msg)

    code = convert_json_to_schema_code(jsn, entrypoint_name)
    out.write_text(
        "# json-struct: Autogenerated by ssc-gen\n"
        + "from ssc_codegen import Json\n"
        + code
    )


@app.command(
    "parse-from-file", help="runtime convert schema to python and parse html"
)
def parse_from_file(
    source: Annotated[Path, Argument(help="html file input")],
    cls_target: Annotated[
        str, Option("-t", "--target", help="class parser entrypoint")
    ],
    out: Annotated[
        Optional[Path],
        Option(
            "--out",
            "-o",
            help="output filename. if not passed - print parsed result",
        ),
    ] = None,
) -> None:
    from ssc_codegen.compiler import Compiler
    from ssc_codegen.converters.py_parsel import converter

    cls_target, schema_config = _validate_parser_target(cls_target)

    compiler = Compiler.from_file(schema_config, converter=converter)
    if not assert_cls_target(compiler, cls_target):
        suggest = suggest_class_name(compiler._module, cls_target)  # noqa
        msg = f"{schema_config.name} not contains {cls_target} class. Did you mean `{suggest}`?"
        raise typer.BadParameter(msg)
    if not source.exists():
        raise typer.BadParameter(f"`{source}` does not exist")
    elif source.is_dir():
        raise typer.BadParameter(
            f"`{source}` should be a html file, not directory"
        )
    result = parse_from_html_file(source, compiler, cls_target)
    if out:
        if isinstance(result, str):
            result = json.loads(result)
        json.dump(result, out, indent=2)
    else:
        print_json_output(result)


@app.command(
    "parse-from-url",
    help="runtime convert schema to python and parse from http response",
)
def parse_from_url(
    url: Annotated[str, Argument(help="http(s) url")],
    cls_target: Annotated[
        str,
        Option(
            "-t",
            "--target",
            help="ssc-gen config file and class parser entrypoint. file and class name sep by `:` char ",
        ),
    ],
    out: Annotated[
        Optional[Path],
        Option(
            "--out",
            "-o",
            help="output filename. if not passed - print parsed result",
        ),
    ] = None,
    # TODO: cookie files arg and other useful http options
    user_agent: Annotated[
        str, Option("-ua", "--user-agent", help="user agent for web request")
    ] = DEFAULT_UA,
    follow_redirects: Annotated[
        bool, Option("-fr", "--follow-redirects", help="follow redirects")
    ] = True,
) -> None:
    from ssc_codegen.compiler import Compiler
    from ssc_codegen.converters.py_parsel import converter

    cls_target, schema_config = _validate_parser_target(cls_target)

    compiler = Compiler.from_file(schema_config, converter=converter)
    if not assert_cls_target(compiler, cls_target):
        suggest = suggest_class_name(compiler._module, cls_target)  # noqa
        msg = f"{schema_config.name} not contains {cls_target} class. Did you mean `{suggest}`?"
        raise typer.BadParameter(msg)
    if not url.startswith("http"):
        raise typer.BadParameter(f"`{url}` not a http url")
    result = parse_from_http_request(
        url,
        compiler,
        cls_target,
        headers={"user-agent": user_agent},
        follow_redirects=follow_redirects,
    )
    if out:
        if isinstance(result, str):
            result = json.loads(result)
        json.dump(result, out, indent=2)
    else:
        print_json_output(result)


@app.command(
    "parse-from-chrome",
    help="runtime convert schema to js and parse from chrome browser",
)
def parse_from_chrome_(
    url: Annotated[str, Argument(help="http(s) url")],
    cls_target: Annotated[
        str, Option("-t", "--target", help="class parser entrypoint")
    ],
    out: Annotated[
        Optional[Path],
        Option(
            "--out",
            "-o",
            help="output filename. if not passed - print parsed result",
        ),
    ] = None,
    timeout: Annotated[
        int, Option("-ti", "--timeout", help="load page timeout in seconds")
    ] = 10,
    host: Annotated[str, Option("--host", help="cdp host")] = "localhost",
    port: Annotated[int, Option("--port", help="cdp port")] = 9992,
    headless: Annotated[
        bool, Option("-hl", "--headless", help="headless mode")
    ] = False,
    chrome_path: Annotated[
        Optional[str],
        Option("-sc", "--system-chrome", help="chrome binary path"),
    ] = None,
    chrome_options: Annotated[
        str,
        Option(
            "-co",
            "--options",
            help="extra chrome options (one line, sep by comma `,`",
        ),
    ] = "",
) -> None:
    from ssc_codegen.converters.js_pure import converter as js_converter
    import asyncio
    from ssc_codegen.compiler import Compiler
    from ssc_codegen.converters.py_parsel import converter

    cls_target, schema_config = _validate_parser_target(cls_target)

    compiler = Compiler.from_file(schema_config, converter=converter)
    if not assert_cls_target(compiler, cls_target):
        suggest = suggest_class_name(compiler._module, cls_target)  # noqa
        msg = f"{schema_config.name} not contains {cls_target} class. Did you mean `{suggest}`?"
        raise typer.BadParameter(msg)
    if not assert_cls_target(compiler, cls_target):
        suggest = suggest_class_name(compiler._module, cls_target)  # noqa
        msg = f"{schema_config.name} not contains {cls_target} class. Did you mean `{suggest}`?"
        raise typer.BadParameter(msg)
    if not url.startswith("http"):
        raise typer.BadParameter(f"`{url}` not a http url")

    ast = build_ast_module(schema_config, docstring_class_top=True)  # type: ignore
    code_parts = js_converter.convert_program(ast)
    code = CB_JS_CODE(code_parts)
    code += f"; JSON.stringify((new {cls_target}(document).parse()))"

    chrome_opt = chrome_options.split(",") if chrome_options else []
    try:
        result = asyncio.run(
            parse_from_chrome(
                url=url,
                js_code=code,
                page_load_timeout=timeout,
                chrome_path=chrome_path,
                host=host,
                port=port,
                headless=headless,
                chrome_options=chrome_opt,
            )
        )
    except ChromeRuntimeError as e:
        msg = f"{e} try manually provide chrome executable path"
        warnings.warn(msg, category=Warning)
        exit(1)
    try:
        if isinstance(result, str):
            result = json.loads(result)
        result = json.dumps(result, indent=2)
        if out:
            out.write_text(result)
        else:
            print(result)
    except Exception as e:
        print("parse json error", e)
        pprint.pprint(result, sort_dicts=False)


def _validate_parser_target(cls_target: str) -> tuple[str, Path]:
    try:
        schema_config, cls_target = cls_target.split(":", 1)
        schema_config = Path(schema_config)  # type: ignore

    except ValueError as e:
        raise typer.BadParameter(
            "-t --target option missing parser class name after `:` char"
        ) from e
    return cls_target, schema_config  # type: ignore


def main() -> None:
    app()


if __name__ == "__main__":
    app()
