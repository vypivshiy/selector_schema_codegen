# TODO refactoring
import importlib
import pathlib
import subprocess
import sys
import types
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
    PY_BS4 = ("py.bs4",)
    PY_PARSEL = "py.parsel"
    PY_SLAX = "py.selectolax"
    PY_SCRAPY = "py.scrapy"
    DART = "dart"


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
    module = ModuleType('mod')
    code = pathlib.Path(path.resolve()).read_text()
    exec(code, module.__dict__)
    return module

def main(
    configs: A[list[str], typer.Argument(help="ssc-codegen config files")],
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
    version: A[
        Optional[bool],
        typer.Option(
            "--version", help="print version and exit", callback=_version_cb
        ),
    ] = None,
) -> None:
    if css_to_xpath and xpath_to_css:
        print("ERROR! Should be passed --to-css OR --to-xpath", file=sys.stderr)
        raise typer.Abort()

    print("Start generate code")
    output_folder.mkdir(exist_ok=True, parents=True)

    print(f"Start parse {len(configs)} schemas")
    converter = converter.value.replace(".", "_")
    converter_module = importlib.import_module(
        f"ssc_codegen.converters.{converter}"
    )
    codegen: CodeGenerator = converter_module.code_generator
    print("Load code generator")

    for config in configs:
        module = import_from_file(Path.cwd() / Path(config))
        # module = importlib.import_module(config)
        schemas = extract_schemas(module)
        if css_to_xpath:
            for s in schemas:
                for f in s.get_fields().values():
                    # Document object
                    f.convert_css_to_xpath(xpath_prefix)  # type: ignore
        elif xpath_to_css:
            for s in schemas:
                for f in s.get_fields().values():
                    # Document object
                    f.convert_xpath_to_css()  # type: ignore

        # TODO detect extension
        base_module_name = (
            "baseStruct.py"
            if str(converter).startswith("py_")
            else "baseStruct.dart"
        )
        base_module_output = output_folder / Path(base_module_name)
        with open(base_module_output, "w") as file:
            file.write(codegen.generate_base_class())

        # TODO detect extension
        # path issue
        config = config.rstrip('.py').split('/')[-1].split('\\')[-1]
        parser_module_name = (
            f"{config}.py" if converter.startswith("py_") else f"{config}.dart"
        )

        codes = [codegen.generate_imports()]
        codes.extend(codegen.generate_code(*schemas))  # type: ignore
        output_file = output_folder / Path(parser_module_name)
        with open(output_file, "w") as file:
            file.write("\n".join(codes))

    if not no_format:
        # TODO detect extension
        if converter == "dart":
            subprocess.Popen(
                f"dart format {output_folder.resolve()}", shell=True
            )
        else:
            subprocess.Popen(f"black {output_folder.resolve()}", shell=True)

    print("Done.")
    exit(0)


def script_entry_point() -> None:
    typer.run(main)


if __name__ == "__main__":
    script_entry_point()
