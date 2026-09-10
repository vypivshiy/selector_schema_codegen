"""Rust REST and HTTP transport codegen for ``MethodFetch`` and ``MethodRest``.

Implements asynchronous transport using ``reqwest``:
- Placeholders in URL, query parameters, headers, cookies, and body.
- Async ``fetch`` associated methods returning ``Result<Self, rt::SscError>``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from ssc_codegen.ast import (
    MethodFetch,
    PlaceholderSpec,
    PlaceholderTemplate,
    StructBase,
)
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.request_spec import parse_json_template
from ssc_codegen.symbols import RUST_RESERVED
from ssc_codegen.traversal.context import WalkContext

if TYPE_CHECKING:
    from ssc_codegen.ast.struct import RequestHttp

_RUST_KEYWORDS = RUST_RESERVED


def _str(value: object) -> str:
    """Render a Rust string literal."""
    return json.dumps(str(value), ensure_ascii=False)


def _ident(value: str) -> str:
    """Render a DSL identifier as a valid Rust identifier."""
    name = to_snake_case(value).replace("-", "_") or "value"
    return f"r#{name}" if name in _RUST_KEYWORDS else name


def _pascal(value: str) -> str:
    """Render a generated Rust type name."""
    name = to_pascal_case(value).replace("-", "") or "Value"
    return f"R#{name}" if name in _RUST_KEYWORDS else name


def rust_ph_type(ph: PlaceholderSpec) -> str:
    """Map a `PlaceholderSpec` to its idiomatic Rust parameter type."""
    if ph.is_array:
        if ph.type_name == "int":
            elem = "i64"
        elif ph.type_name == "float":
            elem = "f64"
        elif ph.type_name == "bool":
            elem = "bool"
        else:
            elem = "&str"
        base = f"&[{elem}]"
        return f"Option<{base}>" if ph.is_optional else base

    if ph.is_optional:
        if ph.type_name == "int":
            return "Option<i64>"
        if ph.type_name == "float":
            return "Option<f64>"
        if ph.type_name == "bool":
            return "Option<bool>"
        return "Option<&str>"

    if ph.type_name == "int":
        return "i64"
    if ph.type_name == "float":
        return "f64"
    if ph.type_name == "bool":
        return "bool"
    return "&str"


def render_template(tmpl: PlaceholderTemplate) -> str:
    """Render a `PlaceholderTemplate` as a Rust string expression."""
    if not tmpl.has_placeholders:
        return _str(tmpl.source)

    fmt_str = ""
    args: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            fmt_str += "{}"
            args.append(_ident(part.name))
        else:
            fmt_str += part.replace("{", "{{").replace("}", "}}")
    return f"format!({_str(fmt_str)}, {', '.join(args)})"


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    """Render a structured JSON request payload using serde_json::json!."""

    def _emit(v: object) -> str:
        if isinstance(v, PlaceholderSpec):
            return f"({_ident(v.name)})"
        if isinstance(v, PlaceholderTemplate):
            if v.has_placeholders:
                return f"({render_template(v)})"
            return _str(v.source)
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            return _str(v)
        if isinstance(v, dict):
            items = ", ".join(
                f"{_str(str(k))}: {_emit(val)}" for k, val in v.items()
            )
            return "{" + items + "}"
        if isinstance(v, list):
            items = ", ".join(_emit(x) for x in v)
            return "[" + items + "]"
        raise TypeError(f"unsupported JSON body element: {type(v).__name__}")

    ast = parse_json_template(tmpl)
    return f"serde_json::json!({_emit(ast)})"


def _emit_kv_pairs(
    var_name: str,
    pairs: dict[str, PlaceholderTemplate],
    indent: str,
) -> list[str]:
    """Emit code populating a `Vec<(&str, String)>` from placeholder templates."""
    lines: list[str] = []
    for key, tmpl in pairs.items():
        ph = tmpl.single_placeholder()
        if ph is not None:
            var = _ident(ph.name)
            effective_key = (
                f"{key}[]" if ph.is_array and ph.style == "bracket" else key
            )
            key_literal = _str(effective_key)
            if ph.is_array:
                if ph.style in ("csv", "pipe", "space"):
                    sep = _str(
                        {"csv": ",", "pipe": "|", "space": " "}[ph.style]
                    )
                    if ph.is_optional:
                        lines.append(f"{indent}if let Some(items) = {var} {{")
                        lines.append(
                            f"{indent}    let val = items.iter().map(|x| x.to_string()).collect::<Vec<_>>().join({sep});"
                        )
                        lines.append(
                            f"{indent}    {var_name}.push(({key_literal}, val));"
                        )
                        lines.append(f"{indent}}}")
                    else:
                        lines.append(
                            f"{indent}let val = {var}.iter().map(|x| x.to_string()).collect::<Vec<_>>().join({sep});"
                        )
                        lines.append(
                            f"{indent}{var_name}.push(({key_literal}, val));"
                        )
                else:
                    if ph.is_optional:
                        lines.append(f"{indent}if let Some(items) = {var} {{")
                        lines.append(f"{indent}    for item in items {{")
                        lines.append(
                            f"{indent}        {var_name}.push(({key_literal}, item.to_string()));"
                        )
                        lines.append(f"{indent}    }}")
                        lines.append(f"{indent}}}")
                    else:
                        lines.append(f"{indent}for item in {var} {{")
                        lines.append(
                            f"{indent}    {var_name}.push(({key_literal}, item.to_string()));"
                        )
                        lines.append(f"{indent}}}")
            else:
                if ph.is_optional:
                    lines.append(f"{indent}if let Some(val) = {var} {{")
                    lines.append(
                        f"{indent}    {var_name}.push(({key_literal}, val.to_string()));"
                    )
                    lines.append(f"{indent}}}")
                else:
                    lines.append(
                        f"{indent}{var_name}.push(({key_literal}, {var}.to_string()));"
                    )
        elif tmpl.has_placeholders:
            val_expr = render_template(tmpl)
            lines.append(f"{indent}{var_name}.push(({_str(key)}, {val_expr}));")
        else:
            lines.append(
                f"{indent}{var_name}.push(({_str(key)}, {_str(tmpl.source)}.to_string()));"
            )
    return lines


def emit_method_fetch(
    node: MethodFetch,
    ctx: WalkContext,
) -> list[str]:
    """Emit an asynchronous `fetch` associated method for an HTML/raw parser struct."""
    spec: RequestHttp = node.http_request.with_renamed_placeholders(
        to_snake_case
    )
    parent = node.parent
    assert isinstance(parent, StructBase)
    struct_name = _pascal(parent.name)
    method_name = f"fetch_{to_snake_case(node.name)}" if node.name else "fetch"
    context = f"{struct_name}.{method_name}"

    ordered_phs = sorted(spec.placeholders, key=lambda p: p.is_optional)
    params = ["client: &reqwest::Client"]
    for ph in ordered_phs:
        params.append(f"{_ident(ph.name)}: {rust_ph_type(ph)}")

    i1 = "    "
    i2 = "        "
    lines: list[str] = [
        f"{i1}pub async fn {method_name}({', '.join(params)}) -> Result<Self, rt::SscError> {{"
    ]

    # Render URL.
    url_expr = render_template(spec.url)
    method_upper = spec.method.upper()
    if method_upper in (
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "HEAD",
        "OPTIONS",
    ):
        method_expr = f"reqwest::Method::{method_upper}"
    else:
        method_expr = (
            f"reqwest::Method::from_bytes({_str(method_upper)}.as_bytes())"
            f".map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?"
        )

    lines.append(
        f"{i2}let mut req = client.request({method_expr}, &{url_expr});"
    )

    # Query params.
    if spec.params:
        lines.append(
            f"{i2}let mut query_pairs: Vec<(&str, String)> = Vec::new();"
        )
        lines.extend(_emit_kv_pairs("query_pairs", spec.params, i2))
        lines.append(f"{i2}req = req.query(&query_pairs);")

    # Headers.
    if spec.headers:
        for k, tmpl in spec.headers.items():
            header_ph = tmpl.single_placeholder()
            if header_ph is not None:
                var = _ident(header_ph.name)
                if header_ph.is_optional:
                    lines.append(f"{i2}if let Some(val) = {var} {{")
                    lines.append(
                        f"{i2}    req = req.header({_str(k)}, val.to_string());"
                    )
                    lines.append(f"{i2}}}")
                else:
                    lines.append(
                        f"{i2}req = req.header({_str(k)}, {var}.to_string());"
                    )
            elif tmpl.has_placeholders:
                lines.append(
                    f"{i2}req = req.header({_str(k)}, {render_template(tmpl)});"
                )
            else:
                lines.append(
                    f"{i2}req = req.header({_str(k)}, {_str(tmpl.source)});"
                )

    # Cookies.
    if spec.cookies:
        lines.append(f"{i2}let mut cookies: Vec<String> = Vec::new();")
        for k, tmpl in spec.cookies.items():
            cookie_ph = tmpl.single_placeholder()
            if cookie_ph is not None:
                var = _ident(cookie_ph.name)
                if cookie_ph.is_optional:
                    lines.append(f"{i2}if let Some(val) = {var} {{")
                    lines.append(
                        f'{i2}    cookies.push(format!("{k}={{val}}"));'
                    )
                    lines.append(f"{i2}}}")
                else:
                    lines.append(f'{i2}cookies.push(format!("{k}={{{var}}}"));')
            elif tmpl.has_placeholders:
                lines.append(
                    f'{i2}cookies.push(format!("{k}={{}}", {render_template(tmpl)}));'
                )
            else:
                lines.append(
                    f"{i2}cookies.push({_str(f'{k}={tmpl.source}')}.to_string());"
                )
        lines.append(f"{i2}if !cookies.is_empty() {{")
        lines.append(f'{i2}    req = req.header("Cookie", cookies.join("; "));')
        lines.append(f"{i2}}}")

    # Body.
    if spec.body_kind == "json" and spec.payload is not None:
        if isinstance(spec.payload, PlaceholderTemplate):
            lines.append(
                f"{i2}req = req.json(&{render_json_body(spec.payload)});"
            )
    elif spec.body_kind == "form" and isinstance(spec.payload, dict):
        lines.append(
            f"{i2}let mut form_pairs: Vec<(&str, String)> = Vec::new();"
        )
        lines.extend(
            _emit_kv_pairs(
                "form_pairs",
                cast(dict[str, PlaceholderTemplate], spec.payload),
                i2,
            )
        )
        lines.append(f"{i2}req = req.form(&form_pairs);")
    elif spec.body_kind == "raw" and spec.payload is not None:
        if isinstance(spec.payload, PlaceholderTemplate):
            lines.append(
                f"{i2}req = req.body({render_template(spec.payload)});"
            )

    # Execute request.
    lines.extend(
        [
            f"{i2}let resp = req.send().await.map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?;",
            f"{i2}let status = resp.status();",
            f"{i2}let body = resp.text().await.map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?;",
            f"{i2}if status.as_u16() >= 400 {{",
            f'{i2}    return Err(rt::SscError::new({_str(context)}, format!("HTTP {{}}: {{body}}", status.as_u16())));',
            f"{i2}}}",
        ]
    )

    # Response extraction via JSON path.
    if node.response_path:
        lines.append(
            f"{i2}let body_val = rt::parse_json(&body, {_str(node.response_path)}, {_str(context)})?;"
        )
        if node.response_join:
            lines.extend(
                [
                    f"{i2}let body = match body_val {{",
                    f"{i2}    serde_json::Value::Array(items) => items.iter()",
                    f"{i2}        .map(|item| item.as_str().map(|s| s.to_string()).unwrap_or_else(|| item.to_string()))",
                    f"{i2}        .collect::<Vec<_>>()",
                    f"{i2}        .join({_str(node.response_join)}),",
                    f"{i2}    serde_json::Value::String(s) => s,",
                    f"{i2}    other => other.to_string(),",
                    f"{i2}}};",
                ]
            )
        else:
            lines.extend(
                [
                    f"{i2}let body = match body_val {{",
                    f"{i2}    serde_json::Value::String(s) => s,",
                    f"{i2}    other => other.to_string(),",
                    f"{i2}}};",
                ]
            )

    lines.append(f"{i2}Self::new(body)")
    lines.append(f"{i1}}}")
    lines.append("")
    return lines
