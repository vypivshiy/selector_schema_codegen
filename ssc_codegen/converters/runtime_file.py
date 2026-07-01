"""Assembly of the separate runtime module file (``--separate-runtime`` / ``-R``).

Produces a single ``sscgen_runtime.py`` (name configurable via
``--runtime-name``) containing the base text helpers plus the REST runtime
classes/functions, when any REST struct is present in the reference module.
"""

from __future__ import annotations

from collections.abc import Callable

import ssc_codegen.ast as a

from ssc_codegen.converters.visitor import Visitor, module_has_rest


# ---------------------------------------------------------------------------
# Base runtime source lines (shared by HTML-parser and REST dialects).
# ---------------------------------------------------------------------------

_BASE_UTILITY_LINES: list[str] = [
    "_RE_HEX_ENTITY = re.compile(r'&#x([0-9a-fA-F]+);')",
    "_RE_UNICODE_ENTITY = re.compile(r'\\\\u([0-9a-fA-F]{4})')",
    "_RE_BYTES_ENTITY = re.compile(r'\\\\x([0-9a-fA-F]{2})')",
    "_RE_CHARS_MAP = {'\\b': '\\b', '\\f': '\\f', '\\n': '\\n', '\\r': '\\r', '\\t': '\\t'}",
    "",
    "def repl_map(s: str, rmap: Dict[str, str]) -> str:",
    "    for k, v in rmap.items():",
    "        s = s.replace(k, v)",
    "    return s",
    "",
    "def normalize_text(text: str) -> str:",
    "    return ' '.join(text.split()) if text else \"\"",
    "",
    "class _UnmatchedTableRow:",
    "    pass",
    "",
    "def unescape_text(text: str) -> str:",
    "    s = ssc_html_unescape(text)",
    "    s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
    "    s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
    "    s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)",
    "    for ch, r in _RE_CHARS_MAP.items():",
    "        s = s.replace(ch, r)",
    "    return s",
    "",
    "if sys.version_info >= (3, 9):",
    "    def rm_prefix(s: str, p: str) -> str:",
    "        return s.removeprefix(p)",
    "",
    "    def rm_suffix(s: str, p: str) -> str:",
    "        return s.removesuffix(p)",
    "",
    "else:",
    "    def rm_prefix(s: str, p: str) -> str:",
    "        return s[len(p):] if s.startswith(p) else s",
    "",
    "    def rm_suffix(s: str, p: str) -> str:",
    "        return s[:-(len(p))] if s.endswith(p) else s",
    "",
    "",
    "UNMATCHED_TABLE_ROW = _UnmatchedTableRow()",
]


# ---------------------------------------------------------------------------
# REST runtime source lines.
# ---------------------------------------------------------------------------


def _rest_utility_lines() -> list[str]:
    return [
        "_T = TypeVar('_T')",
        "_E = TypeVar('_E')",
        "\n",
        "@dataclass(frozen=True)",
        "class Ok(Generic[_T]):",
        "    status: int = 0",
        "    headers: Mapping[str, str] = field(default_factory=dict)",
        "    value: _T = None  # type: ignore[assignment]",
        "    is_ok: Literal[True] = True",
        "\n",
        "@dataclass(frozen=True)",
        "class Err(Generic[_E]):",
        "    status: int = 0",
        "    headers: Mapping[str, str] = field(default_factory=dict)",
        "    value: _E = None  # type: ignore[assignment]",
        "    is_ok: Literal[False] = False",
        "\n",
        "@dataclass(frozen=True)",
        "class UnknownErr(Err[Any]):",
        "    pass",
        "\n",
        "@dataclass(frozen=True)",
        "class TransportErr(Err[None]):",
        "    status: Literal[0] = 0",
        "    cause: str = ''",
        "    value: None = None",
        "    headers: Mapping[str, str] = field(default_factory=dict)",
        "\n",
        "@dataclass(frozen=True)",
        "class ErrMatcher:",
        "    status: int",
        "    check: Callable[[dict], bool] | None = None",
        "    factory: Callable[..., Err] = None  # type: ignore[assignment]",
        "",
        "    def match(self, _s: int, _h, _b) -> Err | None:",
        "        if _s != self.status:",
        "            return None",
        "        if self.check is not None:",
        "            if not isinstance(_b, dict) or not self.check(_b):",
        "                return None",
        "        return self.factory(headers=_h, value=_b)",
        "\n\n",
        "def ssc_dispatch_err(_matchers, _status: int, _headers, _body):",
        "    for _m in _matchers:",
        "        _err = _m.match(_status, _headers, _body)",
        "        if _err is not None:",
        "            return _err",
        "    if 200 <= _status < 300:",
        "        return None",
        "    return UnknownErr(status=_status, headers=_headers, value=_body)",
        "\n\n",
        "def ssc_rest_call(client, _matchers, method, url, _value_fn=None, **kw):",
        "    try:",
        "        _resp = client.request(method, url, **kw)",
        "        _status = _resp.status_code",
        "        _headers = {k.lower(): v for k, v in _resp.headers.items()}",
        "        try:",
        "            _body = _resp.json()",
        "        except Exception:",
        "            _body = None",
        "    except httpx.HTTPError as _exc:",
        "        return TransportErr(cause=repr(_exc))",
        "    _err = ssc_dispatch_err(_matchers, _status, _headers, _body)",
        "    if _err is not None:",
        "        return _err",
        "    _value = _body if _value_fn is None else _value_fn(_body)",
        "    return Ok(status=_status, headers=_headers, value=_value)",
        "\n\n",
        "async def ssc_rest_call_async(client, _matchers, method, url, _value_fn=None, **kw):",
        "    try:",
        "        _resp = await client.request(method, url, **kw)",
        "        _status = _resp.status_code",
        "        _headers = {k.lower(): v for k, v in _resp.headers.items()}",
        "        try:",
        "            _body = _resp.json()",
        "        except Exception:",
        "            _body = None",
        "    except httpx.HTTPError as _exc:",
        "        return TransportErr(cause=repr(_exc))",
        "    _err = ssc_dispatch_err(_matchers, _status, _headers, _body)",
        "    if _err is not None:",
        "        return _err",
        "    _value = _body if _value_fn is None else _value_fn(_body)",
        "    return Ok(status=_status, headers=_headers, value=_value)",
        "\n\n",
    ]


def runtime_module_content(module: a.Module) -> str:
    """Return the full source text of the separate runtime module file."""
    lines: list[str] = [
        "# autogenerated runtime helpers — do not edit",
        "import re",
        "import sys",
        "from typing import Dict",
        "from html import unescape as ssc_html_unescape",
    ]
    has_rest = module_has_rest(module)
    if has_rest:
        lines.extend(
            [
                "from dataclasses import dataclass, field",
                "from typing import Any, Callable, Generic, Literal, Mapping, TypeVar",
            ]
        )
    lines.append("")
    lines.append("")
    lines.extend(_BASE_UTILITY_LINES)
    lines.append("")
    if has_rest:
        lines.extend(_rest_utility_lines())
    return "\n".join(lines)


def register_runtime_file(
    converter: Visitor,
    runtime_name: str = "sscgen_runtime",
    *,
    include_fallback: bool = False,
) -> Callable[[list[a.Module]], str]:
    """Register a runtime module file provider on the converter.

    Returns a callable ``generate_runtime(modules) -> str`` that produces
    the runtime file content for a list of parsed modules, picking the one
    with REST structs as the reference AST automatically.
    """

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
        return _apply_fallback(runtime_module_content(module_ast))

    def _generate_runtime(modules: list[a.Module]) -> str:
        ref = next(
            (m for m in modules if module_has_rest(m)),
            modules[0],
        )
        return _apply_fallback(runtime_module_content(ref))

    return _generate_runtime
