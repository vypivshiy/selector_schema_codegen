"""Python code rendering helpers for RequestSpec values.

Converts RequestSpec placeholders, dicts, and JSON bodies into Python code
fragments suitable for `requests(...)` / `httpx(...)` call arguments.
"""

import json
import re

from ssc_codegen.ast.struct import PlaceholderSpec, _parse_placeholder
from ssc_codegen.converters.request_spec import _PH, RequestSpec

__all__ = [
    "render_value",
    "render_dict",
    "render_body",
    "render_json_body",
    "dict_needs_builder",
    "emit_dict_builder",
]

# ---------------------------------------------------------------------------
# Array-style separator mapping
# ---------------------------------------------------------------------------

_STYLE_SEPARATOR: dict[str, str] = {"csv": ",", "pipe": "|", "space": " "}


def _render_array_join(ph: PlaceholderSpec) -> str:
    """Array placeholder -> Python expression producing a joined string."""
    sep = _STYLE_SEPARATOR[ph.style or "csv"]
    return f"{sep!r}.join(str(_x) for _x in {ph.name})"


# ---------------------------------------------------------------------------
# Value rendering
# ---------------------------------------------------------------------------


def render_value(v: str) -> str:
    """Convert a RequestSpec string value to a Python code fragment.

    ``{{query}}``          -> ``query``             (bare variable)
    ``{{tags:int[]|csv}}`` -> ``",".join(...)``     (array with separator)
    ``Bearer {{token}}``   -> ``f"Bearer {token}"`` (f-string)
    ``Mozilla/5.0``        -> ``"Mozilla/5.0"``     (string literal)
    """
    if m := _PH.fullmatch(v):
        ph = _parse_placeholder(m)
        if ph.is_array and ph.style in ("csv", "pipe", "space"):
            return _render_array_join(ph)
        return ph.name
    if _PH.search(v):
        return f'f"{_escape_fstring(v)}"'
    return repr(v)


def _escape_fstring(template: str) -> str:
    """Convert a placeholder template to an f-string body.

    Non-placeholder ``{`` and ``}`` are doubled (escaped); ``{{name}}`` -> ``{name}``.
    """
    result: list[str] = []
    i = 0
    while i < len(template):
        if template[i : i + 2] == "{{" and _PH.match(template, i):
            m = _PH.match(template, i)
            result.append("{" + m.group(1) + "}")
            i = m.end()
        elif template[i] in "{}":
            result.append(template[i] * 2)
            i += 1
        else:
            result.append(template[i])
            i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# Dict rendering
# ---------------------------------------------------------------------------


def render_dict(d: dict[str, str], *, indent: str = "") -> str:
    """Render a flat string dict as a Python dict literal."""
    if not d:
        return "{}"
    inner = ", ".join(f"{k!r}: {render_value(str(v))}" for k, v in d.items())
    return "{" + inner + "}"


def _dict_entry_placeholder(v: str) -> PlaceholderSpec | None:
    """Return PlaceholderSpec if *v* is a fullmatch placeholder, else None."""
    m = _PH.fullmatch(str(v))
    return _parse_placeholder(m) if m else None


def dict_needs_builder(d: dict[str, str]) -> bool:
    """True when dict rendering requires a multi-line local builder.

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
    """Emit Python lines building a local dict with optional drops and bracket key rewrites."""
    lines: list[str] = [f"{indent}{varname}: dict = {{}}"]
    for key, value in d.items():
        value = str(value)
        ph = _dict_entry_placeholder(value)
        if ph is None:
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


# ---------------------------------------------------------------------------
# JSON body rendering
# ---------------------------------------------------------------------------


def render_json_body(raw: str) -> str:
    """Render a JSON body template (with ``{{placeholders}}``) as a Python expression.

    Suitable for ``requests(json=...)`` / ``httpx(json=...)``.
    """
    from ssc_codegen.converters.request_spec import _validate_json_body

    _validate_json_body(raw)

    sentinels: dict[str, str] = {}
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

                def _fmt(m: re.Match) -> str:
                    return "{" + sentinels[m.group(0)] + "}"

                escaped = v.replace("\\", "\\\\").replace("'", "\\'")
                escaped = escaped.replace("{", "{{").replace("}", "}}")
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


# ---------------------------------------------------------------------------
# Body rendering
# ---------------------------------------------------------------------------


def render_body(spec: RequestSpec) -> tuple[str, str] | None:
    """Return the Python code fragment for the body argument, or None.

    Returns a ``(kwarg_name, code)`` tuple, e.g. ``("json", '{"id": id}')``.
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
