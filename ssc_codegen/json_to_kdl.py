"""Generate sscgen JSON definitions from a JSON example."""

from __future__ import annotations

import json
import keyword
import re
from dataclasses import dataclass, field
from typing import Any


class JsonToKdlError(ValueError):
    """Raised when an example cannot be represented by JSON definitions."""


@dataclass
class _Definition:
    name: str
    fields: list[str] = field(default_factory=list)
    field_names: set[str] = field(default_factory=set)
    is_array: bool = False

    def add_field(self, name: str, definition: str) -> None:
        if name in self.field_names:
            raise JsonToKdlError(
                f"normalized field name collision in {self.name}: {name!r}"
            )
        self.field_names.add(name)
        self.fields.append(definition)


def _path(path: tuple[str, ...]) -> str:
    return "$" if not path else "$." + ".".join(path)


def _field_name(key: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]", "_", key)
    normalized = re.sub(r"_+", "_", normalized).strip("_") or "field"
    if normalized[0].isdigit() or keyword.iskeyword(normalized):
        normalized = "k_" + normalized
    return normalized


def _type_name(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    raise JsonToKdlError(f"unsupported JSON value at {_path(())}")


class _Generator:
    def __init__(self) -> None:
        self.definitions: list[_Definition] = []

    def generate(self, value: Any, name: str) -> str:
        if isinstance(value, dict):
            self._object(value, name, ())
        elif (
            isinstance(value, list)
            and value
            and all(isinstance(item, dict) for item in value)
        ):
            self._object(value, name + "Item", (), is_array=True)
        else:
            raise JsonToKdlError(
                "JSON root must be an object or a non-empty array of objects"
            )
        return (
            "\n\n".join(self._render(item) for item in self.definitions) + "\n"
        )

    def _object(
        self,
        values: dict[str, Any] | list[dict[str, Any]],
        name: str,
        path: tuple[str, ...],
        *,
        is_array: bool = False,
    ) -> str:
        definition = _Definition(name=name, is_array=is_array)
        objects = values if isinstance(values, list) else [values]
        merged: dict[str, list[Any]] = {}
        order: list[str] = []
        for obj in objects:
            for key, value in obj.items():
                if key not in merged:
                    order.append(key)
                    merged[key] = []
                merged[key].append(value)

        for key in order:
            samples = merged[key]
            field_name = _field_name(key)
            field_path = path + (key,)
            expression = self._field(samples, name, field_name, field_path)
            if field_name != key:
                code, separator, comment = expression.partition(" // ")
                expression = f'{code} "{key}"'
                if separator:
                    expression += f"{separator}{comment}"
            if len(samples) < len(objects):
                expression += " @omitempty"
            definition.add_field(field_name, expression)
        self.definitions.append(definition)
        return name

    def _field(
        self,
        samples: list[Any],
        parent_name: str,
        field_name: str,
        path: tuple[str, ...],
    ) -> str:
        if len(samples) == 1 and isinstance(samples[0], dict):
            child_name = parent_name + field_name[:1].upper() + field_name[1:]
            self._object(samples[0], child_name, path)
            return f"{field_name} {child_name}"
        if len(samples) == 1 and isinstance(samples[0], list):
            return self._array(samples[0], parent_name, field_name, path)

        types = [_type_name(item) for item in samples]
        if len(set(types)) == 1 and types[0] not in {"object", "array"}:
            suffix = " // unknown real type" if types[0] == "nil" else ""
            return f"{field_name} {types[0]}{suffix}"
        return f"{field_name} @skip // {', '.join(types)}"

    def _array(
        self,
        values: list[Any],
        parent_name: str,
        field_name: str,
        path: tuple[str, ...],
    ) -> str:
        if not values:
            return f"{field_name} (array)null @skip // empty array"
        types = [_type_name(item) for item in values]
        unique = list(dict.fromkeys(types))
        if len(unique) == 1 and unique[0] == "object":
            child_name = (
                parent_name + field_name[:1].upper() + field_name[1:] + "Item"
            )
            self._object(values, child_name, path, is_array=True)
            return f"{field_name} (array){child_name}"
        if len(unique) == 1 and unique[0] not in {"array", "object"}:
            return f"{field_name} (array){unique[0]}"
        return f"{field_name} (array)null @skip // {', '.join(unique)}"

    @staticmethod
    def _render(definition: _Definition) -> str:
        prefix = "(array)" if definition.is_array else ""
        lines = [f"{prefix}json {definition.name} {{"]
        lines.extend(f"    {item}" for item in definition.fields)
        lines.append("}")
        return "\n".join(lines)


def json_to_kdl(value: Any, *, name: str = "JsonResponse") -> str:
    """Return JSON definitions representing one JSON example."""
    return _Generator().generate(value, name)


def json_text_to_kdl(text: str, *, name: str = "JsonResponse") -> str:
    """Parse JSON text and return JSON definitions."""
    return json_to_kdl(json.loads(text), name=name)
