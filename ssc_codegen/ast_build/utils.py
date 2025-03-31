import json
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Type

from ssc_codegen import Json
from ssc_codegen.consts import SIGNATURE_MAP
from ssc_codegen.schema import (
    BaseSchema,
    ListSchema,
    DictSchema,
    ItemSchema,
    FlatListSchema,
)
from ssc_codegen.tokens import VariableType

LOGGER = logging.getLogger("ssc_gen")


def field_signature_to_string(
    item: str | dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any] | str:
    """
    Recursively replaces Enum values with their underlying values.
    Ignores strings and traverses dicts and lists.
    """
    if isinstance(item, VariableType):
        if var_type := SIGNATURE_MAP.get(item):
            return var_type
        LOGGER.warning("signature gen missing variable %s, set Any", repr(item))
        return "Any"
    elif isinstance(item, dict):
        return {
            key: field_signature_to_string(value) for key, value in item.items()
        }
    elif isinstance(item, list):
        return [field_signature_to_string(element) for element in item]
    else:
        return item


def generate_docstring_signature(
    ssc_signature: str | dict[str, Any] | list[Any] | Type[BaseSchema],
) -> str:
    """generate fields signature from schema"""
    if issubclass(ssc_signature, BaseSchema):  # type: ignore
        ssc_signature = ssc_signature.__class_signature__()  # type: ignore
    ssc_signature = field_signature_to_string(ssc_signature)  # type: ignore
    return json.dumps(ssc_signature, indent=4)


def is_template_schema_cls(cls: object) -> bool:
    """return true if class is not BaseSchema instance. used for dynamically import config and generate ast"""
    return cls in (
        FlatListSchema,
        ItemSchema,
        DictSchema,
        ListSchema,
        BaseSchema,
    )


def extract_schemas_from_module(module: ModuleType) -> list[Type[BaseSchema]]:
    """extract Schema classes from a dynamically imported module.

    used for dynamically import and generate ast
    """
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
        and hasattr(obj, "__mro__")
        and BaseSchema in obj.__mro__
        and not is_template_schema_cls(obj)  # base classes drop
    ]


def extract_json_structs_from_module(module: ModuleType) -> list[Type[Json]]:
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
        and hasattr(obj, "__mro__")
        and Json in obj.__mro__
        and obj != Json  # base class drop
    ]


def exec_module_code(path: str | Path, add_sys_path: bool = True) -> ModuleType:
    # apologize, input - real python file
    if isinstance(path, str):
        path = Path(path)
    module = ModuleType("_")
    abs_path = path.resolve()
    # required for correct imports (eg: constants)
    # TODO: calculate configs dirs depth
    if add_sys_path and str(abs_path.parent) not in sys.path:
        sys.path.append(str(abs_path.parent))

    if add_sys_path and str(abs_path.parent.parent) not in sys.path:
        sys.path.append(str(abs_path.parent.parent))

    code = Path(abs_path).read_text()
    exec(code, module.__dict__)
    return module
