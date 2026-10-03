"""Generate sscgen JSON definitions from a JSON example."""

from __future__ import annotations

import json
import keyword
import re
from typing import Any

from ssc_codegen.naming import to_pascal_case


class JsonToKdlError(ValueError):
    """Raised when an example cannot be represented by JSON definitions."""


def _path(path: tuple[str, ...]) -> str:
    return "$" if not path else "$." + ".".join(path)


_RESERVED_FIELD_NAMES = frozenset({"true", "false", "null", "inf", "nan"})


def _field_name(key: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]", "_", key)
    normalized = re.sub(r"_+", "_", normalized).strip("_") or "field"
    if (
        normalized[0].isdigit()
        or keyword.iskeyword(normalized)
        or normalized in _RESERVED_FIELD_NAMES
    ):
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
        self.used_model_names: set[str] = set()

    def _resolve_item_model_name(
        self, field_name: str, ancestors: list[str]
    ) -> str:
        candidate = to_pascal_case(field_name) + "Item"
        if candidate not in self.used_model_names:
            self.used_model_names.add(candidate)
            return candidate

        for i in range(len(ancestors) - 1, -1, -1):
            prefix = "".join(to_pascal_case(a) for a in ancestors[i:])
            candidate = f"{prefix}{to_pascal_case(field_name)}Item"
            if candidate not in self.used_model_names:
                self.used_model_names.add(candidate)
                return candidate

        base_candidate = candidate
        suffix = 2
        while True:
            candidate = f"{base_candidate}{suffix}"
            if candidate not in self.used_model_names:
                self.used_model_names.add(candidate)
                return candidate
            suffix += 1

    def generate(self, value: Any, name: str) -> str:
        if isinstance(value, dict):
            self.used_model_names = {name}
            header = f"json {name} {{"
            body_lines = self._render_object_fields(
                value, indent_level=1, scope_name=name, ancestors=[]
            )
        elif (
            isinstance(value, list)
            and value
            and all(isinstance(item, dict) for item in value)
        ):
            item_name = name + "Item"
            self.used_model_names = {item_name, name}
            header = f"(array)json {item_name} {{"
            body_lines = self._render_object_fields(
                value, indent_level=1, scope_name=item_name, ancestors=[]
            )
        else:
            raise JsonToKdlError(
                "JSON root must be an object or a non-empty array of objects"
            )

        if not body_lines:
            return f"{header}\n}}\n"

        body_text = "\n".join(body_lines)
        return f"{header}\n{body_text}\n}}\n"

    def _render_object_fields(
        self,
        values: dict[str, Any] | list[dict[str, Any]],
        indent_level: int,
        scope_name: str,
        ancestors: list[str] | None = None,
    ) -> list[str]:
        if ancestors is None:
            ancestors = []
        objects = values if isinstance(values, list) else [values]
        merged: dict[str, list[Any]] = {}
        order: list[str] = []
        for obj in objects:
            for key, val in obj.items():
                if key not in merged:
                    order.append(key)
                    merged[key] = []
                merged[key].append(val)

        seen_field_names: set[str] = set()
        lines: list[str] = []
        indent = " " * (indent_level * 4)

        for key in order:
            samples = merged[key]
            field_name = _field_name(key)
            if field_name in seen_field_names:
                raise JsonToKdlError(
                    f"normalized field name collision in {scope_name}: {field_name!r}"
                )
            seen_field_names.add(field_name)

            from_part = f" from={json.dumps(key)}" if field_name != key else ""
            is_omitempty = len(samples) < len(objects)
            omitempty_part = " @omitempty" if is_omitempty else ""

            # 1. Single or merged nested dictionaries
            if all(isinstance(s, dict) for s in samples):
                if all(not s for s in samples):
                    # Empty object safety: emit @skip without child block
                    lines.append(
                        f"{indent}{field_name} @skip{from_part}{omitempty_part} // empty object"
                    )
                else:
                    lines.append(
                        f"{indent}{field_name}{from_part}{omitempty_part} {{"
                    )
                    child_lines = self._render_object_fields(
                        samples,
                        indent_level=indent_level + 1,
                        scope_name=field_name,
                        ancestors=ancestors + [field_name],
                    )
                    lines.extend(child_lines)
                    lines.append(f"{indent}}}")

            # 2. Arrays
            elif len(samples) == 1 and isinstance(samples[0], list):
                sample_list = samples[0]
                if not sample_list:
                    lines.append(
                        f"{indent}{field_name} (array)null @skip{from_part}{omitempty_part} // empty array"
                    )
                else:
                    types = [_type_name(item) for item in sample_list]
                    unique = list(dict.fromkeys(types))
                    if len(unique) == 1 and unique[0] == "object":
                        if all(
                            isinstance(x, dict) and not x for x in sample_list
                        ):
                            lines.append(
                                f"{indent}{field_name} (array)null @skip{from_part}{omitempty_part} // empty object"
                            )
                        else:
                            item_model_name = self._resolve_item_model_name(
                                field_name, ancestors
                            )
                            lines.append(
                                f"{indent}{field_name} (array){item_model_name}{from_part}{omitempty_part} {{"
                            )
                            child_lines = self._render_object_fields(
                                sample_list,
                                indent_level=indent_level + 1,
                                scope_name=item_model_name,
                                ancestors=ancestors + [field_name],
                            )
                            lines.extend(child_lines)
                            lines.append(f"{indent}}}")
                    elif len(unique) == 1 and unique[0] not in {
                        "array",
                        "object",
                        "nil",
                    }:
                        lines.append(
                            f"{indent}{field_name} (array){unique[0]}{from_part}{omitempty_part}"
                        )
                    else:
                        types_comment = ", ".join(unique)
                        lines.append(
                            f"{indent}{field_name} (array)null @skip{from_part}{omitempty_part} // {types_comment}"
                        )

            # 3. Primitive scalars, nulls, and heterogeneous samples
            else:
                types = [_type_name(item) for item in samples]
                if len(set(types)) == 1 and types[0] not in {
                    "object",
                    "array",
                }:
                    if types[0] == "nil":
                        lines.append(
                            f"{indent}{field_name} nil{from_part}{omitempty_part} // unknown real type"
                        )
                    else:
                        lines.append(
                            f"{indent}{field_name} {types[0]}{from_part}{omitempty_part}"
                        )
                else:
                    types_comment = ", ".join(types)
                    lines.append(
                        f"{indent}{field_name} @skip{from_part}{omitempty_part} // {types_comment}"
                    )

        return lines


def json_to_kdl(value: Any, *, name: str = "JsonResponse") -> str:
    """Return JSON definitions representing one JSON example."""
    return _Generator().generate(value, name)


def json_text_to_kdl(text: str, *, name: str = "JsonResponse") -> str:
    """Parse JSON text and return JSON definitions."""
    return json_to_kdl(json.loads(text), name=name)
