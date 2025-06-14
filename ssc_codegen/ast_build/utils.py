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
    AccUniqueListSchema,
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
        AccUniqueListSchema,
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


def _add_sys_path(abs_path: Path) -> None:
    # required for correct imports (eg: constants)
    # TODO: calculate configs dirs depth
    pathes = str(abs_path.parent), str(abs_path.parent.parent)
    for p in pathes:
        if p not in sys.path:
            sys.path.append(p)


def _is_not_dunder_obj(name: str) -> bool:
    return not name.startswith("__") and not name.endswith("___")


def _is_ssc_cls(name: str, cls: type) -> bool:
    return (
        _is_not_dunder_obj(name)
        and hasattr(cls, "__mro__")
        and BaseSchema in cls.__mro__
        and not is_template_schema_cls(cls)
    )


def exec_module_code(path: str | Path, add_sys_path: bool = True) -> ModuleType:
    # apologize, input - real python file
    if isinstance(path, str):
        path = Path(path)
    abs_path = path.resolve()
    module = ModuleType("_")

    if add_sys_path:
        _add_sys_path(abs_path)

    code = Path(abs_path).read_text()
    exec(code, module.__dict__)

    tmp_module = module.__dict__.copy()
    main_entypoint_schemas = {}
    for k, v in tmp_module.items():
        # move first schemas to end for correct order import and code generate
        if _is_ssc_cls(k, v):
            main_entypoint_schemas[k] = v
            module.__dict__.pop(k)
        # scan and import sub_schemas
        # NOTE: context will be overrided by BaseSchema-like names
        elif _is_not_dunder_obj(k) and isinstance(v, ModuleType):
            for sc in extract_schemas_from_module(v):
                if module.__dict__.get(sc.__name__):
                    LOGGER.warning(
                        "Schema `%s` already defined. `%s.%s` override it",
                        sc.__name__,
                        f"{v.__name__}.{sc.__name__}",
                    )
                module.__dict__[sc.__name__] = sc

    module.__dict__.update(main_entypoint_schemas)
    return module
