"""
RequestSpec — normalised intermediate form produced at codegen-time from a raw
@request payload.  Converters consume RequestSpec to emit explicit fetch() code
for a target HTTP library; no ssc_codegen import appears in generated code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from .curl import parse_curl_to_httpx_kwargs
from .http import parse_http_to_httpx_kwargs

_PH = re.compile(r"\{\{([\w-]+)\}\}")

# ── RequestSpec ───────────────────────────────────────────────────────────────


@dataclass
class RequestSpec:
    method: str  # "GET", "POST", …
    url: str  # base URL, no query string
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body_kind: str = "empty"  # "empty" | "json" | "form" | "raw"
    body: str | dict | None = None  # raw template string or form dict

    @property
    def placeholders(self) -> list[str]:
        """All unique placeholder names in declaration order across every field."""
        seen: set[str] = set()
        result: list[str] = []
        for text in _iter_strings(self):
            for m in _PH.finditer(text):
                name = m.group(1)
                if name not in seen:
                    seen.add(name)
                    result.append(name)
        return result


def _iter_strings(spec: RequestSpec):
    """Yield every string value that may contain placeholders."""
    yield spec.url
    yield from spec.headers.values()
    yield from spec.cookies.values()
    yield from spec.params.values()
    if isinstance(spec.body, str) and spec.body:
        yield spec.body
    elif isinstance(spec.body, dict):
        yield from _iter_dict_strings(spec.body)


def _iter_dict_strings(d: dict):
    for v in d.values():
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            yield from _iter_dict_strings(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    yield item


# ── Parser → RequestSpec ─────────────────────────────────────────────────────


def _strip_query(url: str) -> str:
    p = urlparse(url)
    return urlunparse(p._replace(query="", fragment=""))


def _detect_format(payload: str) -> str:
    stripped = payload.lstrip()
    if re.match(r"curl\s", stripped, re.IGNORECASE):
        return "curl"
    if re.match(r"^[A-Z]+\s+\S+\s+HTTP/\d", stripped):
        return "http"
    raise ValueError(
        "Unsupported @request format: expected 'curl ...' "
        "or a raw HTTP request line (METHOD URI HTTP/x.y)"
    )


def parse_to_spec(payload: str) -> RequestSpec:
    """
    Parse a raw @request payload (curl or raw HTTP, with {{placeholders}})
    into a RequestSpec.  Placeholders are preserved as-is so the converter
    can render them as named parameters.
    """
    fmt = _detect_format(payload)
    if fmt == "curl":
        kwargs = parse_curl_to_httpx_kwargs(payload)
    else:
        kwargs = parse_http_to_httpx_kwargs(payload)

    method: str = kwargs.get("method", "GET").upper()
    full_url: str = kwargs.get("url", "")
    url = _strip_query(full_url)
    headers: dict = kwargs.get("headers", {})
    cookies: dict = kwargs.get("cookies", {})
    params: dict = kwargs.get("params", {})

    # ── body ─────────────────────────────────────────────────────────────────
    body_kind = "empty"
    body = None
    content_type = headers.get("Content-Type", "").lower()

    if "json" in kwargs or (
        "data" in kwargs and "application/json" in content_type
    ):
        # "data" branch: json.loads failed in the underlying parser because
        # {{placeholders}} made the body invalid JSON, but Content-Type tells
        # us it is intended as JSON.
        body_kind = "json"
        raw_body = _extract_raw_body(payload, fmt)
        _validate_json_body(raw_body)  # raises ValueError on genuinely bad JSON
        body = raw_body  # kept as raw str; rendered as f-string

    elif "data" in kwargs:
        raw_body = _extract_raw_body(payload, fmt)
        if isinstance(kwargs["data"], dict):
            body_kind = "form"
            body = kwargs[
                "data"
            ]  # dict with original values (may have placeholders)
        else:
            body_kind = "raw"
            body = raw_body

    return RequestSpec(
        method=method,
        url=url,
        headers=headers,
        cookies=cookies,
        params=params,
        body_kind=body_kind,
        body=body,
    )


def _extract_raw_body(payload: str, fmt: str) -> str:
    """Return the raw body string from the original payload."""
    if fmt == "curl":
        return _curl_raw_body(payload)
    return _http_raw_body(payload)


def _curl_raw_body(payload: str) -> str:
    import shlex

    parts = shlex.split(payload.strip())[1:]  # drop "curl"
    i = 0
    while i < len(parts):
        if parts[i] in ("-d", "--data", "--json") and i + 1 < len(parts):
            return parts[i + 1]
        i += 1
    return ""


def _http_raw_body(payload: str) -> str:
    lines = payload.strip().splitlines()
    i = 1
    while i < len(lines) and lines[i].strip():
        i += 1
    if i < len(lines):
        i += 1  # skip blank separator
    return "\n".join(lines[i:]).strip()


# ── JSON body validation ──────────────────────────────────────────────────────

# Sentinel: a valid JSON string used to substitute {{placeholders}} before
# validating structure.  Must not appear naturally in user payloads.
_PH_SENTINEL = "0"


def _validate_json_body(raw: str) -> None:
    """
    Validate JSON body that may contain {{placeholders}}.

    Strategy: replace every {{name}} with a valid JSON string sentinel, then
    attempt json.loads().  If it still fails the JSON is genuinely malformed.

    Raises:
        ValueError: with a clear message pointing at the parse error.
    """
    if not raw:
        return
    substituted = _PH.sub(_PH_SENTINEL, raw)
    try:
        json.loads(substituted)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON body in @request (line {exc.lineno}, col {exc.colno}): "
            f"{exc.msg}\n"
            f"  body: {raw!r}"
        ) from exc


# ── Placeholder name normalization ───────────────────────────────────────────


def normalize_placeholder_names(
    spec: RequestSpec, transform: "Callable[[str], str]"
) -> RequestSpec:
    """Return a copy of *spec* with every placeholder name passed through *transform*.

    Call this before rendering so that ``{{page-num}}`` becomes e.g.
    ``{{page_num}}`` (Python) or ``{{pageNum}}`` (JS) in all spec fields.
    """
    from typing import Callable  # local import to avoid top-level cost

    mapping = {ph: transform(ph) for ph in spec.placeholders}
    if all(old == new for old, new in mapping.items()):
        return spec

    def _sub(text: str) -> str:
        return _PH.sub(
            lambda m: "{{" + mapping.get(m.group(1), m.group(1)) + "}}", text
        )

    def _sub_dict(d: dict) -> dict:
        return {k: _sub(str(v)) for k, v in d.items()}

    new_body = spec.body
    if isinstance(spec.body, str):
        new_body = _sub(spec.body)
    elif isinstance(spec.body, dict):
        new_body = _sub_dict(spec.body)

    return RequestSpec(
        method=spec.method,
        url=_sub(spec.url),
        headers=_sub_dict(spec.headers),
        cookies=_sub_dict(spec.cookies),
        params=_sub_dict(spec.params),
        body_kind=spec.body_kind,
        body=new_body,
    )


# ── Code-generation helpers ───────────────────────────────────────────────────


def render_value(v: str) -> str:
    """
    Convert a RequestSpec string value to a Python code fragment.

    "{{query}}"          → query            (bare variable)
    "Bearer {{token}}"   → f"Bearer {token}"  (f-string)
    "Mozilla/5.0"        → "Mozilla/5.0"    (string literal)
    """
    if m := _PH.fullmatch(v):
        return m.group(1)
    if _PH.search(v):
        inner = _PH.sub(r"{\1}", v)
        # escape any { } that are NOT our substituted {name} fragments
        # (they were already plain chars, not placeholder braces)
        # We do this by processing the original string token-by-token.
        return f'f"{_escape_fstring(v)}"'
    return repr(v)


def _escape_fstring(template: str) -> str:
    """
    Convert a placeholder template string to an f-string body.

    Non-placeholder { and } are doubled (escaped); {{name}} → {name}.
    """
    result = []
    i = 0
    while i < len(template):
        if template[i : i + 2] == "{{" and _PH.match(template, i):
            m = _PH.match(template, i)
            result.append("{" + m.group(1) + "}")
            i = m.end()
        elif template[i] in "{}":
            result.append(template[i] * 2)  # escape lone brace
            i += 1
        else:
            result.append(template[i])
            i += 1
    return "".join(result)


def render_dict(d: dict[str, str], *, indent: str = "") -> str:
    """Render a flat string dict as a Python dict literal."""
    if not d:
        return "{}"
    inner = ", ".join(f"{k!r}: {render_value(str(v))}" for k, v in d.items())
    return "{" + inner + "}"


def render_json_body(raw: str) -> str:
    """
    Render a JSON body template (with {{placeholders}}) as a Python f-string.

    Validates the JSON structure first; raises ValueError on genuinely bad JSON.
    Uses single-quote f-string because JSON values contain double quotes.
    Single quotes inside the body are escaped as \\'.
    """
    _validate_json_body(raw)
    inner = _escape_fstring(raw).replace("'", "\\'")
    return "f'" + inner + "'"


def render_body(spec: RequestSpec) -> str | None:
    """
    Return the Python code fragment for the body argument, or None if empty.

    Returns a (kwarg_name, code) tuple, e.g. ("json", 'f"{{...}}"').
    """
    if spec.body_kind == "empty" or spec.body is None:
        return None
    if spec.body_kind == "json":
        return ("json", render_json_body(str(spec.body)))
    if spec.body_kind == "form":
        assert isinstance(spec.body, dict)
        return ("data", render_dict(spec.body))
    # raw
    return ("data", render_value(str(spec.body)))
