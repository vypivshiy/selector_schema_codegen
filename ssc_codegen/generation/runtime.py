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
    "def ssc_expect_dict(data: Any, target: str = '') -> Dict[str, Any]:",
    "    if not isinstance(data, dict):",
    "        prefix = f'{target}: ' if target else ''",
    '        raise SscJsonSchemaError(f"{prefix}Expected dict, got {type(data).__name__}")',
    "    return data",
    "",
    "def ssc_expect_list(data: Any, target: str = '') -> List[Any]:",
    "    if not isinstance(data, list):",
    "        prefix = f'{target}: ' if target else ''",
    '        raise SscJsonSchemaError(f"{prefix}Expected list, got {type(data).__name__}")',
    "    return data",
    "",
    "def ssc_resolve_dotpath(data: Any, path: str, is_optional: bool = False, target: str = '') -> Any:",
    "    prefix = f'{target}: ' if target else ''",
    "    raw_segs: List[str] = []",
    "    buf: List[str] = []",
    "    i = 0",
    "    n = len(path)",
    "    while i < n:",
    "        ch = path[i]",
    "        if ch == '\\\\' and i + 1 < n:",
    "            buf.append(ch)",
    "            buf.append(path[i + 1])",
    "            i += 2",
    "        elif ch == '.':",
    "            raw_segs.append(''.join(buf))",
    "            buf = []",
    "            i += 1",
    "        else:",
    "            buf.append(ch)",
    "            i += 1",
    "    raw_segs.append(''.join(buf))",
    "    current = data",
    "    for idx_seg, raw_seg in enumerate(raw_segs):",
    "        if raw_seg == '#':",
    "            if current is None:",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"{prefix}Cannot traverse segment '#' on null object in path '{path}'\")",
    "            if not isinstance(current, list):",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"{prefix}Expected list for '#' in path '{path}', got {type(current).__name__}\")",
    "            if idx_seg == len(raw_segs) - 1:",
    "                return len(current)",
    "            subpath = '.'.join(raw_segs[idx_seg + 1:])",
    "            out: List[Any] = []",
    "            for item in current:",
    "                v = ssc_resolve_dotpath(item, subpath, is_optional=True, target=target)",
    "                if v is not None:",
    "                    out.append(v)",
    "            return out",
    "        has_escape = '\\\\' in raw_seg",
    "        if has_escape:",
    "            seg_chars: List[str] = []",
    "            j = 0",
    "            m = len(raw_seg)",
    "            while j < m:",
    "                if raw_seg[j] == '\\\\' and j + 1 < m:",
    "                    seg_chars.append(raw_seg[j + 1])",
    "                    j += 2",
    "                else:",
    "                    seg_chars.append(raw_seg[j])",
    "                    j += 1",
    "            seg = ''.join(seg_chars)",
    "        else:",
    "            seg = raw_seg",
    "        if current is None:",
    "            if is_optional:",
    "                return None",
    "            raise SscJsonPathError(f\"{prefix}Cannot traverse segment '{seg}' on null object in path '{path}'\")",
    "        if not has_escape and seg.isdigit():",
    "            idx = int(seg)",
    "            if not isinstance(current, list):",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"{prefix}Expected list for index '{idx}' in path '{path}', got {type(current).__name__}\")",
    "            if not (0 <= idx < len(current)):",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"{prefix}Index {idx} out of bounds (len={len(current)}) in path '{path}'\")",
    "            current = current[idx]",
    "        elif isinstance(current, dict):",
    "            if seg not in current:",
    "                if is_optional:",
    "                    return None",
    "                raise SscJsonPathError(f\"{prefix}Missing key '{seg}' in path '{path}'\")",
    "            current = current[seg]",
    "        else:",
    "            if is_optional:",
    "                return None",
    "            raise SscJsonPathError(f\"{prefix}Cannot access key '{seg}' on non-dict {type(current).__name__} in path '{path}'\")",
    "    return current",
    "",
    "def ssc_json_req(data: Dict[str, Any], key: str, target: str = '', field: str = '') -> Any:",
    "    fname = field or (target.rsplit('.', 1)[-1] if '.' in target else key)",
    "    qual = target if (not target or '.' in target) else f'{target}.{fname}'",
    "    prefix = f'{qual}: ' if qual else ''",
    "    if key not in data:",
    "        raise SscJsonFieldMissingError(f\"{prefix}Required JSON field '{key}' (mapped to '{fname}') is missing\")",
    "    val = data[key]",
    "    if val is None:",
    "        raise SscJsonFieldMissingError(f\"{prefix}Field '{key}' is null, but '{fname}' is not nullable\")",
    "    return val",
    "",
    "def ssc_json_req_path(data: Any, path: str, target: str = '', field: str = '') -> Any:",
    "    val = ssc_resolve_dotpath(data, path, is_optional=False, target=target)",
    "    if val is None:",
    "        prefix = f'{target}: ' if target else ''",
    "        fname = field or (target.rsplit('.', 1)[-1] if '.' in target else path)",
    "        raise SscJsonFieldMissingError(f\"{prefix}Field '{path}' is null, but '{fname}' is not nullable\")",
    "    return val",
]


class SscJsonError(Exception):
    """Base exception for runtime JSON projection and dotpath resolution failures."""


class SscJsonPathError(SscJsonError):
    """Raised when traversal of a GJSON path fails on invalid types or out-of-bounds indices."""


class SscJsonFieldMissingError(SscJsonError):
    """Raised when a non-optional required JSON field is absent or null in input data."""


class SscJsonSchemaError(SscJsonError):
    """Raised when input JSON does not match schema structure (e.g. expected dict or list)."""


def ssc_expect_dict(data: Any, target: str = "") -> dict[str, Any]:
    """Validate that input JSON value is a dictionary.

    Args:
        data (Any): Value to validate.
        target (str): Schema or field context for error reporting.

    Returns:
        dict[str, Any]: The validated dictionary.

    Raises:
        SscJsonSchemaError: If `data` is not a `dict`.
    """
    if not isinstance(data, dict):
        prefix = f"{target}: " if target else ""
        raise SscJsonSchemaError(
            f"{prefix}Expected dict, got {type(data).__name__}"
        )
    return data


def ssc_expect_list(data: Any, target: str = "") -> list[Any]:
    """Validate that input JSON value is a list.

    Args:
        data (Any): Value to validate.
        target (str): Schema or field context for error reporting.

    Returns:
        list[Any]: The validated list.

    Raises:
        SscJsonSchemaError: If `data` is not a `list`.
    """
    if not isinstance(data, list):
        prefix = f"{target}: " if target else ""
        raise SscJsonSchemaError(
            f"{prefix}Expected list, got {type(data).__name__}"
        )
    return data


def ssc_resolve_dotpath(
    data: Any, path: str, is_optional: bool = False, target: str = ""
) -> Any:
    """Evaluate a filter-free GJSON path expression over nested dicts and lists.

    Args:
        data (Any): Root JSON-compatible data structure.
        path (str): GJSON path expression supporting escaped keys, indices, `#`, and `#.subpath`.
        is_optional (bool): When `True`, returns `None` on missing keys, null values, or invalid types.
        target (str): Optional `<SchemaName>.<field_name>` prefix for error messages.

    Returns:
        Any: The extracted value, array length, projected list, or `None` when optional and missing.

    Raises:
        SscJsonPathError: If path traversal fails and `is_optional` is `False`.
    """
    prefix = f"{target}: " if target else ""
    raw_segs: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(path)
    while i < n:
        ch = path[i]
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(path[i + 1])
            i += 2
        elif ch == ".":
            raw_segs.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    raw_segs.append("".join(buf))
    current = data
    for idx_seg, raw_seg in enumerate(raw_segs):
        if raw_seg == "#":
            if current is None:
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"{prefix}Cannot traverse segment '#' on null object in path '{path}'"
                )
            if not isinstance(current, list):
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"{prefix}Expected list for '#' in path '{path}', got {type(current).__name__}"
                )
            if idx_seg == len(raw_segs) - 1:
                return len(current)
            subpath = ".".join(raw_segs[idx_seg + 1 :])
            out: list[Any] = []
            for item in current:
                v = ssc_resolve_dotpath(
                    item, subpath, is_optional=True, target=target
                )
                if v is not None:
                    out.append(v)
            return out
        has_escape = "\\" in raw_seg
        if has_escape:
            seg_chars: list[str] = []
            j = 0
            m = len(raw_seg)
            while j < m:
                if raw_seg[j] == "\\" and j + 1 < m:
                    seg_chars.append(raw_seg[j + 1])
                    j += 2
                else:
                    seg_chars.append(raw_seg[j])
                    j += 1
            seg = "".join(seg_chars)
        else:
            seg = raw_seg
        if current is None:
            if is_optional:
                return None
            raise SscJsonPathError(
                f"{prefix}Cannot traverse segment '{seg}' on null object in path '{path}'"
            )
        if not has_escape and seg.isdigit():
            idx = int(seg)
            if not isinstance(current, list):
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"{prefix}Expected list for index '{idx}' in path '{path}', got {type(current).__name__}"
                )
            if not (0 <= idx < len(current)):
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"{prefix}Index {idx} out of bounds (len={len(current)}) in path '{path}'"
                )
            current = current[idx]
        elif isinstance(current, dict):
            if seg not in current:
                if is_optional:
                    return None
                raise SscJsonPathError(
                    f"{prefix}Missing key '{seg}' in path '{path}'"
                )
            current = current[seg]
        else:
            if is_optional:
                return None
            raise SscJsonPathError(
                f"{prefix}Cannot access key '{seg}' on non-dict {type(current).__name__} in path '{path}'"
            )
    return current


def ssc_json_req(
    data: dict[str, Any], key: str, target: str = "", field: str = ""
) -> Any:
    """Extract a required non-nullable field by direct dictionary key.

    Args:
        data (dict[str, Any]): Source JSON object dictionary.
        key (str): Unescaped wire key to look up.
        target (str): Qualified `<SchemaName>.<field_name>` context.
        field (str): Optional canonical field name override.

    Returns:
        Any: The non-null value associated with `key`.

    Raises:
        SscJsonFieldMissingError: If `key` is missing or its value is `None`.
    """
    fname = field or (target.rsplit(".", 1)[-1] if "." in target else key)
    qual = target if (not target or "." in target) else f"{target}.{fname}"
    prefix = f"{qual}: " if qual else ""
    if key not in data:
        raise SscJsonFieldMissingError(
            f"{prefix}Required JSON field '{key}' (mapped to '{fname}') is missing"
        )
    val = data[key]
    if val is None:
        raise SscJsonFieldMissingError(
            f"{prefix}Field '{key}' is null, but '{fname}' is not nullable"
        )
    return val


def ssc_json_req_path(
    data: Any, path: str, target: str = "", field: str = ""
) -> Any:
    """Extract a required non-nullable field via a GJSON path expression.

    Args:
        data (Any): Source JSON object dictionary.
        path (str): GJSON path expression to evaluate.
        target (str): Qualified `<SchemaName>.<field_name>` context.
        field (str): Optional canonical field name override.

    Returns:
        Any: The non-null value resolved at `path`.

    Raises:
        SscJsonPathError: If path traversal fails.
        SscJsonFieldMissingError: If the resolved value at `path` is `None`.
    """
    val = ssc_resolve_dotpath(data, path, is_optional=False, target=target)
    if val is None:
        prefix = f"{target}: " if target else ""
        fname = field or (target.rsplit(".", 1)[-1] if "." in target else path)
        raise SscJsonFieldMissingError(
            f"{prefix}Field '{path}' is null, but '{fname}' is not nullable"
        )
    return val


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
