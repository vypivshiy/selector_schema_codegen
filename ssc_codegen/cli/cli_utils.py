import importlib
import re
import warnings
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol
import difflib

from typer import BadParameter

from .consts import CONVERTERS_PATH

if TYPE_CHECKING:
    from ssc_codegen.ast_ssc import BaseAstNode, ModuleProgram


RE_JSON_KEYS_CHECK = re.compile(r'(?<=")([\d\W][^"]*)(?="\s*:)')


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
    """import converter module in runtime"""
    full_import = f"{CONVERTERS_PATH}.{converter_name}"
    module = importlib.import_module(full_import)
    converter_obj: ConverterLike = module.converter
    return converter_obj


def create_fmt_cmd(
    ssc_files: list[Path],
    prefix: str,
    suffix: str,
    out: Path,
    commands: list[str],
) -> list[str]:
    """insert generated schemas paths to shell command template"""
    comma: list[str] = []
    if not commands:
        warnings.warn("Missing cmd fmt templates", category=Warning)
        return comma
    for f in ssc_files:
        name = f.name.split(".")[0]
        abc_f = out / f"{prefix}{name}{suffix}"
        comma.extend(cmd.format(str(abc_f.absolute())) for cmd in commands)
    return comma


def raw_json_check_keys(jsn: str) -> None:
    """check raw json keys by regular expression.
    all keys shold be starts symbol as [_a-zA-Z]

    raise BadParameter if json key is invalid
    """
    # TODO: check all bad chars keys
    if results := RE_JSON_KEYS_CHECK.findall(jsn):
        for r in results:
            warnings.warn(f"bad json key: {r}", category=Warning)
        all_keys = ", ".join(f"`{k}`" for k in results)
        raise BadParameter(
            f"bad json keys count: {len(results)}, keys: {all_keys}"
        )


def suggest_class_name(module: ModuleType, target_class_name: str) -> str:
    """try to suggest correct class name"""
    class_names = [
        name for name in dir(module) if isinstance(getattr(module, name), type)
    ]

    return difflib.get_close_matches(
        target_class_name, class_names, n=3, cutoff=0.6
    )[0]
