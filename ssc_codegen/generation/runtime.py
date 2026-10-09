"""Assembly of the separate runtime module file (``--separate-runtime`` / ``-R``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ssc_codegen.ast as a
from ssc_codegen.targets.python.http_libs.base import HttpLibStrategy
from ssc_codegen.targets.python.http_libs.httpx import HttpxStrategy
from ssc_codegen.traversal.utils import module_has_rest

_BASE_UTILITY_LINES: list[str] = [
    "_RE_HEX_ENTITY = re.compile(r'&#x([0-9a-fA-F]+);')",
    "_RE_UNICODE_ENTITY = re.compile(r'\\\\u([0-9a-fA-F]{4})')",
    "_RE_BYTES_ENTITY = re.compile(r'\\\\x([0-9a-fA-F]{2})')",
    "_RE_CHARS_MAP = {'\\\\b': '\\b', '\\\\f': '\\f', '\\\\n': '\\n', '\\\\r': '\\r', '\\\\t': '\\t'}",
    "",
    "class SscAssertionError(Exception):",
    "    pass",
    "",
    "class SscRegexError(Exception):",
    "    pass",
    "",
    "def std_assert(cond: bool, msg: str = '') -> None:",
    "    if not cond:",
    "        raise SscAssertionError(msg or 'ssc-gen assertion failed')",
    "",
    "def std_re_search(pattern: str, value: str, msg: str = '') -> str:",
    "    m = re.search(pattern, value)",
    "    if m is None:",
    "        raise SscRegexError(msg or 'ssc-gen re-match failed')",
    "    return m[1]",
    "",
    "def std_repl_map(s: str, rmap: Dict[str, str]) -> str:",
    "    for k, v in rmap.items():",
    "        s = s.replace(k, v)",
    "    return s",
    "",
    "def std_normalize_text(text: str) -> str:",
    "    return ' '.join(text.split()) if text else \"\"",
    "",
    "class UnmatchedTableRow:",
    "    pass",
    "",
    "def std_unescape_text(text: str) -> str:",
    "    s = ssc_html_unescape(text)",
    "    s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
    "    s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
    "    s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
    "    for ch, r in _RE_CHARS_MAP.items():",
    "        s = s.replace(ch, r)",
    "    return s",
    "",
    "if sys.version_info >= (3, 9):",
    "    def std_rm_prefix(s: str, p: str) -> str:",
    "        return s.removeprefix(p)",
    "",
    "    def std_rm_suffix(s: str, p: str) -> str:",
    "        return s.removesuffix(p)",
    "",
    "else:",
    "    def std_rm_prefix(s: str, p: str) -> str:",
    "        return s[len(p):] if s.startswith(p) else s",
    "",
    "    def std_rm_suffix(s: str, p: str) -> str:",
    "        return s[:-(len(p))] if s.endswith(p) else s",
    "",
    "",
    "UNMATCHED_TABLE_ROW = UnmatchedTableRow()",
    "",
    "class SscJsonError(Exception):",
    "    pass",
    "",
    "class SscJsonPathError(SscJsonError):",
    "    pass",
    "",
    "class SscJsonFieldMissingError(SscJsonError):",
    "    pass",
    "",
    "class SscJsonSchemaError(SscJsonError):",
    "    pass",
    "",
    "def ssc_resolve_dotpath(data: Any, path: str, is_optional: bool) -> Any:",
    "    current = data",
    "    for seg in path.split('.'):",
    "        if current is None:",
    "            if is_optional:",
    "                return None",
    "            raise SscJsonPathError(f\"Cannot traverse segment '{seg}' on null object in path '{path}'\")",
    "        if seg.isdigit():",
    "            idx = int(seg)",
    "            if not isinstance(current, list):",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"Expected list for index '{idx}' in path '{path}', got {type(current).__name__}\")",
    "            if not (0 <= idx < len(current)):",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"Index {idx} out of bounds (len={len(current)}) in path '{path}'\")",
    "            current = current[idx]",
    "        elif isinstance(current, dict):",
    "            if seg not in current:",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"Missing key '{seg}' in path '{path}'\")",
    "            current = current[seg]",
    "        else:",
    "            if is_optional:",
    "                return None",
    "            raise SscJsonPathError(f\"Cannot access key '{seg}' on non-dict {type(current).__name__} in path '{path}'\")",
    "    return current",
    "",
    "def ssc_json_project(data: Any, field_descriptors: Any) -> Any:",
    "    if isinstance(field_descriptors, dict) and field_descriptors.get('__dict__'):",
    "        if not isinstance(data, dict):",
    '            raise SscJsonSchemaError(f"Expected dict, got {type(data).__name__}")',
    "        val_desc = field_descriptors.get('__value__')",
    "        if val_desc is None:",
    "            return data",
    "        if isinstance(val_desc, list) and val_desc:",
    "            return {k: [ssc_json_project(x, val_desc[0]) for x in v if x is not None] if isinstance(v, list) else (ssc_json_project(v, val_desc[0]) if v is not None else None) for k, v in data.items()}",
    "        return {k: (ssc_json_project(v, val_desc) if v is not None else None) for k, v in data.items()}",
    "    if isinstance(data, list):",
    "        return [ssc_json_project(item, field_descriptors) for item in data]",
    "    if not isinstance(data, dict):",
    "        return data",
    "    result: Dict[str, Any] = {}",
    "    for canonical_name, (wire_path, is_optional, is_omitempty, nested_desc) in field_descriptors.items():",
    "        if '.' in wire_path or wire_path.isdigit():",
    "            val = ssc_resolve_dotpath(data, wire_path, is_optional=is_optional or is_omitempty)",
    "        else:",
    "            if wire_path not in data:",
    "                if is_omitempty or is_optional:",
    "                    val = None",
    "                else:",
    "                    raise SscJsonFieldMissingError(f\"Required JSON field '{wire_path}' (mapped to '{canonical_name}') is missing\")",
    "            else:",
    "                val = data[wire_path]",
    "        if val is None:",
    "            if is_omitempty:",
    "                continue",
    "            if not is_optional:",
    "                raise SscJsonFieldMissingError(f\"Field '{wire_path}' is null, but '{canonical_name}' is not nullable\")",
    "            result[canonical_name] = None",
    "            continue",
    "        if nested_desc is not None:",
    "            if isinstance(nested_desc, dict) and nested_desc.get('__dict__'):",
    "                val = ssc_json_project(val, nested_desc)",
    "            elif isinstance(nested_desc, list) and nested_desc:",
    "                val = [ssc_json_project(x, nested_desc[0]) for x in val if x is not None] if isinstance(val, list) else ssc_json_project(val, nested_desc[0])",
    "            else:",
    "                val = ssc_json_project(val, nested_desc)",
    "        result[canonical_name] = val",
    "    return result",
    "",
    "def ssc_remap_json_keys(value: Any, mapping: Dict[str, Any]) -> Any:",
    "    if isinstance(value, list):",
    "        return [ssc_remap_json_keys(item, mapping) for item in value]",
    "    if not isinstance(value, dict):",
    "        return value",
    "    result: Dict[str, Any] = {}",
    "    for source, spec in mapping.items():",
    "        if source not in value:",
    "            continue",
    "        output, nested = (spec, None)",
    "        if isinstance(spec, tuple):",
    "            output, nested = spec",
    "        item = value[source]",
    "        if isinstance(nested, list) and nested:",
    "            item = [ssc_remap_json_keys(x, nested[0]) for x in item]",
    "        elif isinstance(nested, dict):",
    "            item = ssc_remap_json_keys(item, nested)",
    "        result[output] = item",
    "    return result",
]


class SscJsonError(Exception):
    """Base exception for runtime JSON projection and dotpath resolution failures."""


class SscJsonPathError(SscJsonError):
    """Raised when traversal of a dot-separated path fails on invalid types or out-of-bounds indices."""


class SscJsonFieldMissingError(SscJsonError):
    """Raised when a non-optional required JSON field is absent in input data."""


class SscJsonSchemaError(SscJsonError):
    """Raised when input JSON does not match schema structure (e.g. expected dict but got non-dict)."""


def ssc_resolve_dotpath(data: Any, path: str, is_optional: bool) -> Any:
    """Traverse a dot-separated query path over nested dicts and lists.

    Args:
        data: Root JSON-compatible data structure (dict, list, or primitive).
        path: Dot-separated path string (e.g. ``"data.users.0.name"``).
        is_optional: If `True`, returns `None` upon encountering a missing key,
            null parent, or out-of-bounds index instead of raising an error.

    Returns:
        The extracted value at the target path, or `None` if optional and missing.

    Raises:
        SscJsonPathError: If path traversal fails and `is_optional` is `False`.
    """
    current = data
    for seg in path.split("."):
        if current is None:
            if is_optional:
                return None
            raise SscJsonPathError(
                f"Cannot traverse segment '{seg}' on null object in path '{path}'"
            )
        if seg.isdigit():
            idx = int(seg)
            if not isinstance(current, list):
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"Expected list for index '{idx}' in path '{path}', got {type(current).__name__}"
                )
            if not (0 <= idx < len(current)):
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"Index {idx} out of bounds (len={len(current)}) in path '{path}'"
                )
            current = current[idx]
        elif isinstance(current, dict):
            if seg not in current:
                if is_optional:
                    return None
                raise SscJsonPathError(f"Missing key '{seg}' in path '{path}'")
            current = current[seg]
        else:
            if is_optional:
                return None
            raise SscJsonPathError(
                f"Cannot access key '{seg}' on non-dict {type(current).__name__} in path '{path}'"
            )
    return current


def ssc_json_project(data: Any, field_descriptors: Any) -> Any:
    """Project raw JSON dictionary or list into a validated canonical schema dict.

    Applies strict field allowlisting, alias path resolution, nullability checks,
    and recursive nested schema projections.

    Args:
        data: The input JSON data (dict or list of dicts).
        field_descriptors: Mapping of canonical field names to a tuple of
            ``(wire_path, is_optional, is_omitempty, nested_descriptors)``, or
            dict descriptor ``{"__dict__": True, "__value__": val_desc}``.

    Returns:
        Projected dictionary with canonical keys, or list of projected dictionaries.

    Raises:
        SscJsonFieldMissingError: If a required field is missing or null.
        SscJsonPathError: If path resolution fails for a required field.
        SscJsonSchemaError: If schema structure is violated (e.g. non-dict passed to dict schema).
    """
    if isinstance(field_descriptors, dict) and field_descriptors.get(
        "__dict__"
    ):
        if not isinstance(data, dict):
            raise SscJsonSchemaError(
                f"Expected dict, got {type(data).__name__}"
            )
        val_desc = field_descriptors.get("__value__")
        if val_desc is None:
            return data
        if isinstance(val_desc, list) and val_desc:
            return {
                k: (
                    [
                        ssc_json_project(x, val_desc[0])
                        for x in v
                        if x is not None
                    ]
                    if isinstance(v, list)
                    else (
                        ssc_json_project(v, val_desc[0])
                        if v is not None
                        else None
                    )
                )
                for k, v in data.items()
            }
        return {
            k: (ssc_json_project(v, val_desc) if v is not None else None)
            for k, v in data.items()
        }

    if isinstance(data, list):
        return [ssc_json_project(item, field_descriptors) for item in data]
    if not isinstance(data, dict):
        return data
    result: dict[str, Any] = {}
    for canonical_name, (
        wire_path,
        is_optional,
        is_omitempty,
        nested_desc,
    ) in field_descriptors.items():
        if "." in wire_path or wire_path.isdigit():
            val = ssc_resolve_dotpath(
                data, wire_path, is_optional=is_optional or is_omitempty
            )
        else:
            if wire_path not in data:
                if is_omitempty or is_optional:
                    val = None
                else:
                    raise SscJsonFieldMissingError(
                        f"Required JSON field '{wire_path}' (mapped to '{canonical_name}') is missing"
                    )
            else:
                val = data[wire_path]
        if val is None:
            if is_omitempty:
                continue
            if not is_optional:
                raise SscJsonFieldMissingError(
                    f"Field '{wire_path}' is null, but '{canonical_name}' is not nullable"
                )
            result[canonical_name] = None
            continue
        if nested_desc is not None:
            if isinstance(nested_desc, dict) and nested_desc.get("__dict__"):
                val = ssc_json_project(val, nested_desc)
            elif isinstance(nested_desc, list) and nested_desc:
                val = (
                    [
                        ssc_json_project(x, nested_desc[0])
                        for x in val
                        if x is not None
                    ]
                    if isinstance(val, list)
                    else ssc_json_project(val, nested_desc[0])
                )
            else:
                val = ssc_json_project(val, nested_desc)
        result[canonical_name] = val
    return result


def _extension_runtime_defs(
    modules: list[a.Module],
) -> dict[str, tuple[list[str], str]]:
    """Extract and aggregate runtime helper definitions from extension calls across modules.

    Args:
        modules: List of AST `Module` instances to scan.

    Returns:
        Dictionary mapping helper names to tuples of ``(import_lines, source_code)``.

    Raises:
        ValueError: If conflicting definitions are encountered for the same helper name.
    """
    definitions: dict[str, tuple[list[str], str]] = {}

    def walk(node: a.Node) -> None:
        if isinstance(node, a.ExtensionCall) and node.definition is not None:
            target = node.definition.targets.get("py")
            if target is not None:
                for helper in target.helpers:
                    value = (
                        [item.value for item in helper.imports],
                        helper.source,
                    )
                    previous = definitions.get(helper.name)
                    if previous is not None and previous != value:
                        raise ValueError(
                            f"conflicting runtime helper definition: {helper.name}"
                        )
                    definitions.setdefault(helper.name, value)
        for child in node.body:
            walk(child)

    for module in modules:
        walk(module)
    return definitions


def runtime_module_content(
    module: a.Module,
    *,
    http_strategy: HttpLibStrategy | None = None,
    extension_defs: dict[str, tuple[list[str], str]] | None = None,
) -> str:
    """Generate the full Python source text for the separate runtime module file.

    Emits base string/regex/HTML unescape utilities, JSON dotpath/projection helpers,
    REST runtime definitions (Result types `Ok`/`Err`, error dispatch, transport call
    handlers), and custom extension runtime helpers.

    Args:
        module: Representative AST `Module` to check for REST structures or utilities.
        http_strategy: The HTTP library strategy (e.g. `HttpxStrategy`, `AioHttpStrategy`,
            or `RequestsStrategy`). Controls the transport exception handling and
            matching library import in `ssc_rest_call`. Defaults to `HttpxStrategy`.
        extension_defs: Optional pre-collected dictionary of extension helpers.

    Returns:
        Complete Python source code string for the runtime module.
    """
    strategy = http_strategy or HttpxStrategy()
    lines: list[str] = [
        "# autogenerated runtime helpers — do not edit",
        "from __future__ import annotations",
        "import re",
        "import sys",
        "from typing import Any, Callable, Dict, Generic, List, Literal, Mapping, Optional, Tuple, TypeVar, Union",
        "from html import unescape as ssc_html_unescape",
    ]
    has_rest = module_has_rest(module)
    if has_rest:
        lines.extend(
            [
                "from dataclasses import dataclass, field",
                strategy.import_line,
            ]
        )
    if extension_defs:
        for imports, _code in extension_defs.values():
            for import_line in imports:
                if import_line not in lines:
                    lines.append(import_line)
    lines.append("")
    lines.append("")
    lines.extend(_BASE_UTILITY_LINES)
    lines.append("")
    if has_rest:
        lines.extend(strategy.rest_runtime_lines(http_io="both"))
    if extension_defs:
        for _imports, code in extension_defs.values():
            lines.append("")
            lines.extend(code.strip("\n").splitlines())
    return "\n".join(lines)


def register_runtime_file(
    converter: Any,
    runtime_name: str = "sscgen_runtime",
    *,
    include_fallback: bool = False,
    http_strategy: HttpLibStrategy | None = None,
) -> Callable[[list[a.Module]], str]:
    """Register a runtime module file generator on the given converter instance.

    Wires a file hook for ``<runtime_name>.py`` that generates runtime helpers
    when ``--separate-runtime`` (`-R`) is requested.

    Args:
        converter: Target converter object exposing a ``.file()`` decorator hook.
        runtime_name: Module filename without extension (default: ``"sscgen_runtime"``).
        include_fallback: If `True`, includes fallback empty HTML document constants.
        http_strategy: The canonical HTTP transport strategy to apply across parser
            and runtime code generation. Defaults to `HttpxStrategy`.

    Returns:
        A callable taking a list of `Module` ASTs and returning the full runtime source.
    """

    # Normalize callers that don't pass http_strategy.
    if http_strategy is None:
        http_strategy = HttpxStrategy()

    def _apply_fallback(content: str) -> str:
        if not include_fallback:
            return content
        return content.replace(
            "_RE_HEX_ENTITY",
            'FALLBACK_HTML_STR = "<html><body></body></html>"\n\n_RE_HEX_ENTITY',
            1,
        )

    @converter.file(f"{runtime_name}.py")
    def _runtime_provider(module_ast: a.Module, meta):
        strat = http_strategy
        if (
            meta
            and meta.get("http_client")
            and hasattr(converter, "http_strategy_for")
        ):
            strat = converter.http_strategy_for(meta.get("http_client"))
        return _apply_fallback(
            runtime_module_content(
                module_ast,
                http_strategy=strat,
                extension_defs=_extension_runtime_defs([module_ast]),
            )
        )

    def _generate_runtime(modules: list[a.Module]) -> str:
        ref = next(
            (m for m in modules if module_has_rest(m)),
            modules[0],
        )
        return _apply_fallback(
            runtime_module_content(
                ref,
                http_strategy=http_strategy,
                extension_defs=_extension_runtime_defs(modules),
            )
        )

    return _generate_runtime
