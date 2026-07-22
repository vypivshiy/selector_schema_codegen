"""
@request payload parsing — curl / raw HTTP → ``RequestHttp`` AST node.

``parse_to_http`` is the entry point consumed at parse time by
``core/struct_parser.py``.  Converters read ``RequestHttp`` fields directly
(or call ``RequestHttp.with_renamed_placeholders`` to adapt placeholder
names to the target language) instead of going through an intermediate form.
"""

from __future__ import annotations

import json
import re
import shlex
from urllib.parse import urlparse, unquote_plus, urlunparse

from ssc_codegen.ast.struct import (
    PlaceholderSpec,
    RequestHttp,
    PlaceholderTemplate,
)
from ssc_codegen.parsers.curl import parse_curl_command
from ssc_codegen.parsers.http import parse_http_request


def _tmpl_dict(d: dict) -> dict[str, PlaceholderTemplate]:
    """Wrap every dict value in a Template."""
    return {k: PlaceholderTemplate.parse(str(v)) for k, v in d.items()}


# ── Parser → RequestHttp ──────────────────────────────────────────────────────


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


def parse_to_http(payload: str) -> RequestHttp:
    """
    Parse a raw @request payload (curl or raw HTTP, with ``{{placeholders}}``)
    into a ``RequestHttp`` AST node.  Placeholders are preserved as-is so the
    converter can render them as named parameters.
    """
    fmt = _detect_format(payload)
    if fmt == "curl":
        kwargs = parse_curl_command(payload)
    else:
        kwargs = parse_http_request(payload)

    method: str = kwargs.get("method", "GET").upper()
    full_url: str = kwargs.get("url", "")
    url = _strip_query(full_url)
    headers: dict = kwargs.get("headers", {})
    cookies: dict = kwargs.get("cookies", {})
    params: dict = kwargs.get("params", {})

    # ── body ─────────────────────────────────────────────────────────────────
    body_kind = "empty"
    body: PlaceholderTemplate | dict[str, PlaceholderTemplate] | None = None
    content_type = headers.get("Content-Type", "").lower()

    if "json" in kwargs or (
        "data" in kwargs and "application/json" in content_type
    ):
        body_kind = "json"
        raw_body = _extract_raw_body(payload, fmt)
        validate_json_body(raw_body)
        body = PlaceholderTemplate.parse(raw_body)  # rendered as f-string

    elif "data" in kwargs:
        raw_body = _extract_raw_body(payload, fmt)
        if isinstance(kwargs["data"], dict):
            body_kind = "form"
            body = _tmpl_dict(kwargs["data"])
        elif "application/x-www-form-urlencoded" in content_type:
            body_kind = "form"
            body = _tmpl_dict(_parse_urlencoded_body(raw_body))
        else:
            body_kind = "raw"
            body = PlaceholderTemplate.parse(raw_body)

    return RequestHttp(
        method=method,
        url=PlaceholderTemplate.parse(url),
        headers=_tmpl_dict(headers),
        cookies=_tmpl_dict(cookies),
        params=_tmpl_dict(params),
        body_kind=body_kind,
        body=body,
    )


def _extract_raw_body(payload: str, fmt: str) -> str:
    """Return the raw body string from the original payload."""
    if fmt == "curl":
        return _curl_raw_body(payload)
    return _http_raw_body(payload)


def _curl_raw_body(payload: str) -> str:
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


def validate_json_body(raw: str) -> None:
    """
    Validate JSON body that may contain ``{{placeholders}}``.

    Strategy: replace every ``{{name}}`` with a valid JSON string sentinel, then
    attempt ``json.loads()``.  If it still fails the JSON is genuinely malformed.

    Raises:
        ValueError: with a clear message pointing at the parse error.
    """
    if not raw:
        return
    substituted = PlaceholderSpec.sub(raw, _PH_SENTINEL)
    try:
        json.loads(substituted)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON body in @request (line {exc.lineno}, col {exc.colno}): "
            f"{exc.msg}\n"
            f"  body: {raw!r}"
        ) from exc
