# TODO refactoring
import importlib
import pathlib
import subprocess
import sys
import types
import warnings
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Annotated as A  # type: ignore
from typing import List, Optional

import typer

from ssc_codegen.converters.generator import CodeGenerator
from ssc_codegen.schema import (
    BaseSchema,
    DictSchema,
    FlattenListSchema,
    ItemSchema,
    ListSchema,
)

DEFAULT_PATH = Path.cwd() / Path("src") / Path("ssc_gen")


class Converters(str, Enum):
    PY_BS4 = "py.bs4"
    PY_PARSEL = "py.parsel"
    PY_SLAX = "py.selectolax"
    PY_SCRAPY = "py.scrapy"
    DART = "dart"


# detect from converters
FORMAT_EXTENSIONS = {
    **{k: 'py' for k in ['py_bs4', 'py_parsel', 'py_selectolax', 'py_scrapy']},
    'dart': 'dart'
}

FORMATTERS_CLI = {
    'py': 'black {}',
    'dart': 'dart format {}'
}


def _is_template_cls(cls: object) -> bool:
    return any(
        cls == base_cls
        for base_cls in (
            FlattenListSchema,
            ItemSchema,
            DictSchema,
            ListSchema,
            BaseSchema,
        )
    )


def extract_schemas(module: ModuleType) -> List[BaseSchema]:
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
        and hasattr(obj, "__mro__")
        and BaseSchema in obj.__mro__
        and not _is_template_cls(obj)
    ]


def _version_cb() -> None:
    from ssc_codegen import __version__

    print("ssc-gen", __version__)
    typer.Abort()


def import_from_file(path: Path) -> ModuleType:
    module = ModuleType("mod")
    code = pathlib.Path(path.resolve()).read_text()
    exec(code, module.__dict__)
    return module


def main(
    configs: A[list[str], typer.Argument(help="ssc-codegen config files or path folder with configs")],
    converter: A[
        Converters,
        typer.Option(
            "-c", "--converter", help="code converter", show_default=False
        ),
    ],
    output_folder: A[
        Path,
        typer.Option(
            "-o",
            "--output",
            help="folder output. Default get current working directory and create src/ssc_gen path",
            show_default=False,
        ),
    ] = DEFAULT_PATH,
    css_to_xpath: A[
        bool,
        typer.Option(
            "--to-xpath",
            help="convert css queries to xpath (works not guaranteed)",
        ),
    ] = False,
    xpath_to_css: A[
        bool, typer.Option("--to-css", help="convert xpath queries to css")
    ] = False,
    xpath_prefix: A[
        str, typer.Option(help="xpath prefix (for --to-xpath argument)")
    ] = "descendant-or-self::",
    no_format: A[
        bool, typer.Option("--skip-format", help="skip format code")
    ] = False,
    file_prefix: A[
        Optional[str],
        typer.Option(
            "-p",
            "--prefix",
            help="file prefix for config output",
            show_default=False,
        ),
    ] = None,
    file_suffix: A[
        Optional[str],
        typer.Option(
            "-s",
            "--suffix",
            help="file suffix for config output",
            show_default=False,
        ),
    ] = None,
    version: A[
        Optional[bool],
        typer.Option(
            "--version", help="print version and exit", callback=_version_cb
        ),
    ] = None,
) -> None:
    if version:
        exit(0)
    _check_css_and_xpath_args(css_to_xpath, xpath_to_css)
    file_prefix, file_suffix = file_prefix or "", file_suffix or ""
    print("Start generate code")
    output_folder.mkdir(exist_ok=True, parents=True)

    print(f"Start parse {len(configs)} schemas")
    converter = converter.value.replace(".", "_")
    converter_module = importlib.import_module(
        f"ssc_codegen.converters.{converter}"
    )
    codegen: CodeGenerator = converter_module.code_generator
    print("Load code generator")
    parse_configs = _get_files_configs(configs)
    for config in parse_configs:
        schemas = _extarct_schemas_classes(config, css_to_xpath, xpath_prefix, xpath_to_css)

        ext = FORMAT_EXTENSIONS[str(converter)]
        base_module_name = f"baseStruct.{ext}"
        _save_base_class(base_module_name, codegen, output_folder)

        # TODO detect extension
        # path issue
        config = str(config).rstrip(".py").split("/")[-1].split("\\")[-1]
        parser_module_name = (
            f"{file_prefix}{config}{file_suffix}.{ext}"
            if converter.startswith("py_")
            else f"{file_prefix}{config}{file_suffix}.dart"
        )

        codes = _generate_code(codegen, schemas)
        _save_generated_code(codes, output_folder, parser_module_name)

    if not no_format:
        # TODO detect extension
        fmt_cmd = FORMATTERS_CLI.get(ext)
        if not fmt_cmd:
            warnings.warn('Not founded required code formatter', stacklevel=1, category=RuntimeWarning)
        subprocess.Popen(fmt_cmd.format(output_folder.resolve()), shell=True)

    print("Done! 😇😛")
    exit(0)


def _extarct_schemas_classes(config, css_to_xpath, xpath_prefix, xpath_to_css):
    module = import_from_file(Path.cwd() / config)
    schemas = extract_schemas(module)
    if css_to_xpath:
        _convert_css_to_xpath(schemas, xpath_prefix)
    elif xpath_to_css:
        _convert_xpath_to_css(schemas)
    return schemas


def _convert_xpath_to_css(schemas):
    for s in schemas:
        for f in s.get_fields().values():
            f.convert_xpath_to_css()  # type: ignore


def _convert_css_to_xpath(schemas, xpath_prefix):
    for s in schemas:
        for f in s.get_fields().values():
            f.convert_css_to_xpath(xpath_prefix)  # type: ignore


def _save_generated_code(codes, output_folder, parser_module_name):
    output_file = output_folder / Path(parser_module_name)
    with open(output_file, "w") as file:
        file.write("\n".join(codes))


def _generate_code(codegen, schemas):
    codes = [codegen.generate_base_imports(), codegen.generate_required_imports()]
    codes.extend(codegen.generate_code(*schemas))  # type: ignore
    return codes


def _save_base_class(base_module_name, codegen, output_folder):
    base_module_output = output_folder / Path(base_module_name)
    with open(base_module_output, "w") as file:
        file.write(codegen.generate_base_class())


def _get_files_configs(configs):
    parse_configs: List[Path] = []
    for cfg in configs:
        cfg = cfg.rstrip('*')
        p = Path(cfg)
        if p.is_dir():
            parse_configs.extend(i for i in p.iterdir() if not i.name.startswith('_') and i.suffix == '.py')
        elif p.suffix == '.py':
            parse_configs.append(p)
    return parse_configs


def _check_css_and_xpath_args(css_to_xpath, xpath_to_css):
    if css_to_xpath and xpath_to_css:
        print("ERROR! Should be passed --to-css OR --to-xpath", file=sys.stderr)
        raise typer.Abort()


def script_entry_point() -> None:
    typer.run(main)


if __name__ == "__main__":
    script_entry_point()
