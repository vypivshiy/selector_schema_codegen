"""
RequestSpec — normalised intermediate form produced at codegen-time from a raw
@request payload.  Converters consume RequestSpec to emit explicit fetch() code
for a target HTTP library; no ssc_codegen import appears in generated code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse, urlunparse

from .curl import parse_curl_to_httpx_kwargs
from .http import parse_http_to_httpx_kwargs
from ..ast.struct import PlaceholderSpec, _parse_placeholder

# Strict placeholder regex — kept in sync with ssc_codegen/ast/struct.py.
# Groups: 1=NAME, 2=PRIM, 3="[]", 4="?", 5=STYLE.
_PH = re.compile(
    r"\{\{"
    r"([A-Za-z][A-Za-z0-9_-]*)"
    r"(?::(str|int|float|bool))?"
    r"(\[\])?"
    r"(\?)?"
    r"(?:\|(repeat|csv|bracket|pipe|space))?"
    r"\}\}"
)

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
    def placeholders(self) -> list[PlaceholderSpec]:
        """All unique placeholders in declaration order across every field."""
        seen: set[str] = set()
        result: list[PlaceholderSpec] = []
        for text in _iter_strings(self):
            for m in _PH.finditer(text):
                spec = _parse_placeholder(m)
                if spec.name not in seen:
                    seen.add(spec.name)
                    result.append(spec)
        return result

    @property
    def placeholder_names(self) -> list[str]:
        """Unique placeholder names in declaration order."""
        return [p.name for p in self.placeholders]


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
        elif "application/x-www-form-urlencoded" in content_type:
            body_kind = "form"
            body = _parse_urlencoded_body(raw_body)
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
        if parts[i] in ("-d", "--data", "--data-raw", "--json") and i + 1 < len(
            parts
        ):
            return parts[i + 1]
        i += 1
    return ""


def _parse_urlencoded_body(raw: str) -> dict[str, str]:
    """Split an application/x-www-form-urlencoded body into a dict.

    Preserves ``{{placeholders}}`` intact; URL-decodes everything else so the
    target HTTP client can re-encode without double-encoding.
    """
    from urllib.parse import unquote_plus

    out: dict[str, str] = {}
    if not raw:
        return out
    for pair in raw.split("&"):
        if not pair:
            continue
        key, sep, value = pair.partition("=")
        out[unquote_plus(key)] = unquote_plus(value) if sep else ""
    return out


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
    spec: RequestSpec, transform: Callable[[str], str]
) -> RequestSpec:
    """Return a copy of *spec* with every placeholder name passed through *transform*.

    Call this before rendering so that ``{{page-num:int[]?|csv}}`` becomes e.g.
    ``{{page_num:int[]?|csv}}`` (Python) or ``{{pageNum:int[]?|csv}}`` (JS).
    Type/array/optional/style suffixes are preserved; only NAME changes.
    """
    mapping = {ph.name: transform(ph.name) for ph in spec.placeholders}
    if all(old == new for old, new in mapping.items()):
        return spec

    def _sub(text: str) -> str:
        def _replace(m: "re.Match[str]") -> str:
            new_name = mapping.get(m.group(1), m.group(1))
            type_part = f":{m.group(2)}" if m.group(2) else ""
            array_part = m.group(3) or ""
            optional_part = m.group(4) or ""
            style_part = f"|{m.group(5)}" if m.group(5) else ""
            return (
                "{{"
                + new_name
                + type_part
                + array_part
                + optional_part
                + style_part
                + "}}"
            )

        return _PH.sub(_replace, text)

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


_STYLE_SEPARATOR = {"csv": ",", "pipe": "|", "space": " "}


def _render_array_join(ph: PlaceholderSpec) -> str:
    """Array placeholder → Python expression producing a joined string."""
    sep = _STYLE_SEPARATOR[ph.style or "csv"]
    return f"{sep!r}.join(str(_x) for _x in {ph.name})"


def render_value(v: str) -> str:
    """
    Convert a RequestSpec string value to a Python code fragment.

    "{{query}}"          → query             (bare variable; scalar or repeat-array)
    "{{tags:int[]|csv}}" → ",".join(...)     (array with explicit separator)
    "Bearer {{token}}"   → f"Bearer {token}" (f-string, scalars only)
    "Mozilla/5.0"        → "Mozilla/5.0"     (string literal)
    """
    if m := _PH.fullmatch(v):
        ph = _parse_placeholder(m)
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            return _render_array_join(ph)
        # Scalar or repeat/bracket-array → bare variable name.
        # repeat:  requests/httpx expands list in params natively (?a=1&a=2).
        # bracket: key rewrite happens at dict-level; value stays bare.
        return ph.name
    if _PH.search(v):
        # Mixed literal + placeholder(s) → f-string. Only scalar placeholders
        # are valid here (arrays/optional forbidden inside f-string by linter).
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


def _dict_entry_placeholder(v: str) -> PlaceholderSpec | None:
    """Return the PlaceholderSpec if value is a fullmatch placeholder, else None."""
    m = _PH.fullmatch(str(v))
    return _parse_placeholder(m) if m else None


def dict_needs_builder(d: dict[str, str]) -> bool:
    """
    True when dict rendering requires a multi-line local builder.

    Needed if any value is an optional fullmatch placeholder (conditional drop)
    or uses bracket-style serialization (key rewrite).
    """
    for v in d.values():
        ph = _dict_entry_placeholder(str(v))
        if ph is None:
            continue
        if ph.is_optional:
            return True
        if ph.is_array and ph.style == "bracket":
            return True
    return False


def emit_dict_builder(
    varname: str, d: dict[str, str], indent: str
) -> list[str]:
    """
    Emit Python lines building a local dict that supports optional drops and
    bracket key rewrites:

        _params = {}
        if q is not None:
            _params["q"] = q
        _params["tags[]"] = tags
        _params["limit"] = limit
    """
    lines = [f"{indent}{varname}: dict = {{}}"]
    for key, value in d.items():
        value = str(value)
        ph = _dict_entry_placeholder(value)
        if ph is None:
            # Literal value or f-string mix — always set.
            lines.append(f"{indent}{varname}[{key!r}] = {render_value(value)}")
            continue
        effective_key = (
            f"{key}[]" if (ph.is_array and ph.style == "bracket") else key
        )
        expr = render_value(value)
        if ph.is_optional:
            lines.append(f"{indent}if {ph.name} is not None:")
            lines.append(f"{indent}    {varname}[{effective_key!r}] = {expr}")
        else:
            lines.append(f"{indent}{varname}[{effective_key!r}] = {expr}")
    return lines


def render_json_body(raw: str) -> str:
    """
    Render a JSON body template (with {{placeholders}}) as a Python dict/list
    literal expression suitable for `requests(json=...)` / `httpx(json=...)`.

    Placeholders become bare Python variable references at the JSON position
    they occupied; literal strings containing embedded placeholders become
    f-strings; everything else emits as a Python literal.

    Validates the JSON structure first; raises ValueError on genuinely bad JSON.
    """
    _validate_json_body(raw)

    sentinels: dict[str, str] = {}  # sentinel → placeholder-name
    out: list[str] = []
    i = 0
    n = len(raw)
    in_string = False
    while i < n:
        if raw[i : i + 2] == "{{":
            m = _PH.match(raw, i)
            if m is not None:
                name = _parse_placeholder(m).name
                key = f"__SSC_PH_{len(sentinels)}__"
                sentinels[key] = name
                out.append(key if in_string else '"' + key + '"')
                i = m.end()
                continue
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            out.append(raw[i : i + 2])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
        out.append(ch)
        i += 1
    substituted = "".join(out)
    parsed = json.loads(substituted)
    sentinel_re = re.compile(r"__SSC_PH_\d+__")

    def _emit(v: object) -> str:
        if v is None:
            return "None"
        if isinstance(v, bool):
            return "True" if v else "False"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            if v in sentinels:
                return sentinels[v]
            if sentinel_re.search(v):
                # Mixed literal + placeholder(s) → f-string.
                def _fmt(m: re.Match) -> str:
                    return "{" + sentinels[m.group(0)] + "}"

                escaped = v.replace("\\", "\\\\").replace("'", "\\'")
                escaped = escaped.replace("{", "{{").replace("}", "}}")
                # _fmt injects literal `{name}` after escaping, so the braces
                # inside the injected fragment are not doubled.
                body = sentinel_re.sub(_fmt, escaped)
                return "f'" + body + "'"
            return repr(v)
        if isinstance(v, dict):
            items = ", ".join(f"{k!r}: {_emit(val)}" for k, val in v.items())
            return "{" + items + "}"
        if isinstance(v, list):
            items = ", ".join(_emit(x) for x in v)
            return "[" + items + "]"
        raise TypeError(f"unsupported JSON body element: {type(v).__name__}")

    return _emit(parsed)


def render_body(spec: RequestSpec) -> tuple[str, str] | None:
    """
    Return the Python code fragment for the body argument, or None if empty.

    Returns a (kwarg_name, code) tuple, e.g. ("json", '{"id": id}').
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
