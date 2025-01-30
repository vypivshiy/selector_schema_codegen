import importlib
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Protocol

from typer import BadParameter

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import BaseAstNode, ModuleProgram

CONVERTER_PATH = "ssc_codegen.converters"


class PyLIBS(StrEnum):
    BS4 = "bs4"
    PARSEL = "parsel"
    SELECTOLAX = "selectolax"
    SCRAPY = "scrapy"


class JsLIBS(StrEnum):
    PURE = "pure"


class DartLIBS(StrEnum):
    UNIVERSAL_HTML = "universal_html"


class GoLIBS(StrEnum):
    GOQUERY = "goquery"


class ConverterLike(Protocol):
    debug_instructions: bool = False
    debug_comment_prefix: str = ""

    def convert(
        self, ast_entry: "BaseAstNode", acc: list[str] | None = None
    ) -> list[str]:
        pass

    def set_debug_prefix(self, comment_prefix: str) -> None:
        pass

    def disable_debug(self) -> None:
        pass

    def convert_program(
        self, ast_program: "ModuleProgram", comment: str = ""
    ) -> list[str]:
        pass


def import_converter(converter_name: str) -> ConverterLike:
    full_import = f"{CONVERTER_PATH}.{converter_name}"
    module = importlib.import_module(full_import)
    converter_obj: ConverterLike = module.converter
    return converter_obj


# ARG cb
def cb_check_ssc_files(
    files: list[Path] | Generator[Path, None, None],
) -> list[Path]:
    tmp_files = []
    for f in files:
        if f.is_dir():
            tmp_files += cb_check_ssc_files(f.iterdir())
        elif not f.exists():
            raise BadParameter(f"'{f.name}' does not exist")
        elif not f.is_file():
            raise BadParameter(f"'{f.name}' is not file")
        # TODO: change extension???
        elif f.suffix == ".py":
            tmp_files.append(f)
    return tmp_files


def cb_folder_out(folder: Path) -> Path:
    if not folder.exists():
        folder.mkdir(exist_ok=True)
    if folder.is_file():
        raise BadParameter(f"'{folder.name}' already exists and is not a file")
    return folder


def create_fmt_cmd(
    ssc_files: list[Path],
    prefix: str,
    suffix: str,
    out: Path,
    commands: list[str],
) -> list[str]:
    comma: list[str] = []
    if not commands:
        warnings.warn("Missing cmd fmt templates")
        return comma
    for f in ssc_files:
        name = f.name.split(".")[0]
        abc_f = out / f"{prefix}{name}{suffix}"
        for cmd in commands:
            comma.append(cmd.format(str(abc_f.absolute())))
    return comma
