"""Rust REST and HTTP transport codegen for ``MethodFetch`` and ``MethodRest``.

Implements asynchronous transport using ``reqwest``:
- Placeholders in URL, query parameters, headers, cookies, and body.
- Async ``fetch`` associated methods returning ``Result<Self, rt::SscError>``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from ssc_codegen.ast import (
    MatcherListDef,
    MethodFetch,
    MethodRest,
    PlaceholderSpec,
    PlaceholderTemplate,
    ResultAliasDef,
    ResultVariantDef,
    StructBase,
    StructRest,
)
from ssc_codegen.naming import to_pascal_case, to_snake_case
from ssc_codegen.request_spec import parse_json_template
from ssc_codegen.symbols import RUST_RESERVED
from ssc_codegen.traversal.context import WalkContext

if TYPE_CHECKING:
    from ssc_codegen.ast.struct import RequestHttp

_RUST_KEYWORDS = RUST_RESERVED


def _str(value: object) -> str:
    """Render a Python value as an escaped Rust string literal.

    Args:
        value (object): Value to convert and quote as a Rust string literal.

    Returns:
        str: Double-quoted Rust string literal.
    """
    return json.dumps(str(value), ensure_ascii=False)


def _ident(value: str) -> str:
    """Render a DSL identifier as a valid snake_case Rust identifier.

    Args:
        value (str): Raw DSL identifier string.

    Returns:
        str: Valid Rust snake_case identifier, escaped with `r#` if reserved.
    """
    name = to_snake_case(value).replace("-", "_") or "value"
    return f"r#{name}" if name in _RUST_KEYWORDS else name


def _pascal(value: str) -> str:
    """Render a DSL identifier as a PascalCase Rust type name.

    Args:
        value (str): Raw DSL identifier string.

    Returns:
        str: Valid PascalCase Rust type name.
    """
    name = to_pascal_case(value).replace("-", "") or "Value"
    return f"R#{name}" if name in _RUST_KEYWORDS else name


def rust_ph_type(ph: PlaceholderSpec) -> str:
    """Map a `PlaceholderSpec` to its idiomatic Rust parameter type annotation.

    Args:
        ph (PlaceholderSpec): Placeholder metadata specification.

    Returns:
        str: Rust parameter type string (e.g. `"&str"`, `"i64"`, `"Option<&str>"`).
    """
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
    """Render a `PlaceholderTemplate` as a Rust string or `format!(...)` expression.

    Args:
        tmpl (PlaceholderTemplate): Template containing literal parts and/or placeholders.

    Returns:
        str: Rust string literal or `format!(...)` expression.
    """
    if not tmpl.has_placeholders:
        return _str(tmpl.source)

    fmt_str = ""
    args: list[str] = []
    for part in tmpl.parts:
        if isinstance(part, PlaceholderSpec):
            fmt_str += "{}"
            ident = _ident(part.name)
            if part.is_optional:
                if part.type_name == "str" and not part.is_array:
                    args.append(f"{ident}.unwrap_or_default()")
                else:
                    args.append(
                        f"{ident}.map(|v| v.to_string()).unwrap_or_default()"
                    )
            else:
                args.append(ident)
        else:
            fmt_str += part.replace("{", "{{").replace("}", "}}")
    return f"format!({_str(fmt_str)}, {', '.join(args)})"


def render_json_body(tmpl: PlaceholderTemplate) -> str:
    """Render a structured JSON request payload using `serde_json::json!`.

    Optional placeholders (`Option<T>`) are emitted as parenthesized variable
    expressions `(ident)` inside `serde_json::json!(...)`, so `None` serializes
    as JSON `null` and `Some(v)` serializes as the typed value.

    Args:
        tmpl (PlaceholderTemplate): JSON body template with optional placeholders.

    Returns:
        str: Rust `serde_json::json!(...)` macro invocation expression.
    """

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
    """Emit Rust statements populating a `Vec<(&str, String)>` from placeholder templates.

    Args:
        var_name (str): Name of the mutable `Vec<(&str, String)>` variable to push into.
        pairs (dict[str, PlaceholderTemplate]): Key-to-template mapping for query or form parameters.
        indent (str): Indentation prefix for emitted lines.

    Returns:
        list[str]: Generated Rust statements populating `var_name`.
    """
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


def rust_variant_name(struct_name: str, factory_name: str) -> str:
    """Derive an idiomatic Rust enum variant name from an error factory name.

    Args:
        struct_name (str): Enclosing REST struct name.
        factory_name (str): Synthesized error factory/class name.

    Returns:
        str: Stripped PascalCase enum variant identifier.
    """
    pascal = _pascal(struct_name)
    if factory_name.startswith(pascal):
        tail = factory_name[len(pascal) :]
        if tail:
            return tail
    return factory_name


def placeholder_params(spec: RequestHttp) -> list[str]:
    """Emit the `client` and placeholder parameter declarations for `reqwest` methods.

    Args:
        spec (RequestHttp): HTTP request specification containing placeholders.

    Returns:
        list[str]: Ordered list of Rust `<name>: <type>` parameter declarations.
    """
    ordered_phs = sorted(spec.placeholders, key=lambda p: p.is_optional)
    params = ["client: &reqwest::Client"]
    for ph in ordered_phs:
        params.append(f"{_ident(ph.name)}: {rust_ph_type(ph)}")
    return params


def render_rust_condition(path: str, val: Any) -> str:
    """Render a boolean condition check against a `serde_json::Value` body.

    Args:
        path (str): GJSON dot-path to inspect in `_body_val`.
        val (Any): Expected literal value (`None`, `bool`, `int`, `float`, or `str`).

    Returns:
        str: Rust boolean expression evaluating the condition.
    """
    path_lit = _str(path)
    if val is None:
        return (
            f"rt::json_opt(_body_val, {path_lit}).map_or(true, |v| v.is_null())"
        )
    if isinstance(val, bool):
        b = "true" if val else "false"
        return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_bool()) == Some({b})"
    if isinstance(val, int):
        return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_i64()) == Some({val})"
    if isinstance(val, float):
        return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_f64()) == Some({val})"
    s = _str(str(val))
    return f"rt::json_opt(_body_val, {path_lit}).and_then(|v| v.as_str()) == Some({s})"


def _emit_request_builder(
    spec: RequestHttp,
    indent: str,
    context: str = "",
) -> list[str]:
    """Emit Rust statements building a `reqwest::RequestBuilder` bound to `req`.

    Args:
        spec (RequestHttp): HTTP request specification AST node.
        indent (str): Indentation prefix for emitted statements.
        context (str): Error context label used when propagating custom method parse errors.

    Returns:
        list[str]: Generated Rust statements constructing and configuring `req`.
    """
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
        if context:
            method_expr = (
                f"reqwest::Method::from_bytes({_str(method_upper)}.as_bytes())"
                f".map_err(|e| rt::SscError::new({_str(context)}, e.to_string()))?"
            )
        else:
            method_expr = (
                f"reqwest::Method::from_bytes({_str(method_upper)}.as_bytes())"
                f'.expect("valid HTTP method")'
            )

    lines: list[str] = [
        f"{indent}let mut req = client.request({method_expr}, {url_expr});",
        f"{indent}let _ = &mut req;",
    ]

    # Query params.
    if spec.params:
        lines.append(
            f"{indent}let mut query_pairs: Vec<(&str, String)> = Vec::new();"
        )
        lines.extend(_emit_kv_pairs("query_pairs", spec.params, indent))
        lines.append(f"{indent}req = req.query(&query_pairs);")

    # Headers.
    if spec.headers:
        for k, tmpl in spec.headers.items():
            header_ph = tmpl.single_placeholder()
            if header_ph is not None:
                var = _ident(header_ph.name)
                if header_ph.is_optional:
                    lines.append(f"{indent}if let Some(val) = {var} {{")
                    lines.append(
                        f"{indent}    req = req.header({_str(k)}, val.to_string());"
                    )
                    lines.append(f"{indent}}}")
                else:
                    lines.append(
                        f"{indent}req = req.header({_str(k)}, {var}.to_string());"
                    )
            elif tmpl.has_placeholders:
                lines.append(
                    f"{indent}req = req.header({_str(k)}, {render_template(tmpl)});"
                )
            else:
                lines.append(
                    f"{indent}req = req.header({_str(k)}, {_str(tmpl.source)});"
                )

    # Cookies.
    if spec.cookies:
        lines.append(f"{indent}let mut cookies: Vec<String> = Vec::new();")
        for k, tmpl in spec.cookies.items():
            cookie_ph = tmpl.single_placeholder()
            if cookie_ph is not None:
                var = _ident(cookie_ph.name)
                if cookie_ph.is_optional:
                    lines.append(f"{indent}if let Some(val) = {var} {{")
                    lines.append(
                        f'{indent}    cookies.push(format!("{k}={{val}}"));'
                    )
                    lines.append(f"{indent}}}")
                else:
                    lines.append(
                        f'{indent}cookies.push(format!("{k}={{{var}}}"));'
                    )
            elif tmpl.has_placeholders:
                lines.append(
                    f'{indent}cookies.push(format!("{k}={{}}", {render_template(tmpl)}));'
                )
            else:
                lines.append(
                    f"{indent}cookies.push({_str(f'{k}={tmpl.source}')}.to_string());"
                )
        lines.append(f"{indent}if !cookies.is_empty() {{")
        lines.append(
            f'{indent}    req = req.header("Cookie", cookies.join("; "));'
        )
        lines.append(f"{indent}}}")

    # Body.
    if spec.body_kind == "json" and spec.payload is not None:
        if isinstance(spec.payload, PlaceholderTemplate):
            lines.append(
                f"{indent}req = req.json(&{render_json_body(spec.payload)});"
            )
    elif spec.body_kind == "form" and isinstance(spec.payload, dict):
        lines.append(
            f"{indent}let mut form_pairs: Vec<(&str, String)> = Vec::new();"
        )
        lines.extend(
            _emit_kv_pairs(
                "form_pairs",
                cast(dict[str, PlaceholderTemplate], spec.payload),
                indent,
            )
        )
        lines.append(f"{indent}req = req.form(&form_pairs);")
    elif spec.body_kind == "raw" and spec.payload is not None:
        if isinstance(spec.payload, PlaceholderTemplate):
            lines.append(
                f"{indent}req = req.body({render_template(spec.payload)});"
            )

    return lines


def emit_method_fetch(
    node: MethodFetch,
    ctx: WalkContext,
) -> list[str]:
    """Emit an asynchronous `fetch` associated method for an HTML/raw parser struct.

    Args:
        node (MethodFetch): AST node describing the document fetch request.
        ctx (WalkContext): Traversal context.

    Returns:
        list[str]: Generated Rust method lines.
    """
    spec: RequestHttp = node.http_request.with_renamed_placeholders(
        to_snake_case
    )
    parent = node.parent
    assert isinstance(parent, StructBase)
    struct_name = _pascal(parent.name)
    method_name = f"fetch_{to_snake_case(node.name)}" if node.name else "fetch"
    context = f"{struct_name}.{method_name}"
    params = placeholder_params(spec)

    i1 = "    "
    i2 = "        "
    lines: list[str] = []
    if getattr(node, "doc", ""):
        for doc_line in node.doc.splitlines():
            lines.append(f"{i1}// {doc_line}" if doc_line else f"{i1}//")
    lines.append(
        f"{i1}pub async fn {method_name}({', '.join(params)}) -> Result<Self, rt::SscError> {{"
    )

    lines.extend(_emit_request_builder(spec, i2, context=context))

    path_opt = (
        f"Some({_str(node.response_path)})" if node.response_path else "None"
    )
    join_opt = (
        f"Some({_str(node.response_join)})" if node.response_join else "None"
    )
    lines.extend(
        [
            f"{i2}let body = rt::fetch_html(req, {_str(context)}, {path_opt}, {join_opt}).await?;",
            f"{i2}Self::new(body)",
            f"{i1}}}",
            "",
        ]
    )
    return lines


def emit_result_variant_def(node: ResultVariantDef) -> list[str]:
    """Emit `ResultVariantDef` (no-op as variants are synthesized into the error enum).

    Args:
        node (ResultVariantDef): Error variant AST node.

    Returns:
        list[str]: Empty list.
    """
    return []


def resolve_struct_name_for_alias(
    node: ResultAliasDef,
    result_variants: dict[str, ResultVariantDef] | None = None,
) -> str:
    """Determine the enclosing REST struct name for a synthesized `ResultAliasDef`.

    Args:
        node (ResultAliasDef): Result alias AST node.
        result_variants (dict[str, ResultVariantDef] | None): Optional map of known
            result variant nodes by name.

    Returns:
        str: Name of the owning REST struct.
    """
    parent = node.parent
    if isinstance(parent, StructBase):
        return parent.name
    from ssc_codegen.ast.module import Module

    if isinstance(parent, Module):
        for n in parent.body:
            if isinstance(n, StructRest):
                for child in n.body:
                    if (
                        isinstance(child, MethodRest)
                        and child.result_alias_name == node.name
                        and (
                            not node.response_schema
                            or child.response_schema == node.response_schema
                        )
                    ):
                        return n.name
    if result_variants and node.err_variants:
        first_err = result_variants.get(node.err_variants[0])
        if first_err and isinstance(first_err.parent, StructBase):
            return first_err.parent.name
    return node.name.removesuffix("Result")


def emit_result_alias_def(
    node: ResultAliasDef,
    struct_name: str = "",
    emitted_aliases: set[str] | None = None,
    result_variants: dict[str, ResultVariantDef] | None = None,
) -> list[str]:
    """Emit the `pub type ... = Result<..., ...>;` alias for a REST endpoint result.

    Args:
        node (ResultAliasDef): Result alias AST node.
        struct_name (str): Optional explicit owning REST struct name.
        emitted_aliases (set[str] | None): Set tracking already-emitted type alias names.
        result_variants (dict[str, ResultVariantDef] | None): Optional map of error variant nodes.

    Returns:
        list[str]: Generated Rust type alias lines.
    """
    effective_struct = struct_name or resolve_struct_name_for_alias(
        node, result_variants
    )
    struct_pascal = _pascal(effective_struct)
    enum_name = f"{struct_pascal}Error"
    if node.response_schema:
        s_pascal = f"{_pascal(node.response_schema)}Json"
        ok_type = f"Vec<{s_pascal}>" if node.response_is_array else s_pascal
    else:
        ok_type = "()"
    alias_str = f"Result<{ok_type}, {enum_name}>"

    lines: list[str] = []
    qualified = f"{struct_pascal}{node.name}"
    if emitted_aliases is not None:
        if node.name not in emitted_aliases:
            emitted_aliases.add(node.name)
            lines.append(f"pub type {node.name} = {alias_str};")
        if qualified != node.name and qualified not in emitted_aliases:
            emitted_aliases.add(qualified)
            lines.append(f"pub type {qualified} = {alias_str};")
    else:
        lines.append(f"pub type {node.name} = {alias_str};")
    if lines:
        lines.append("")
    return lines


def emit_matcher_list_def(
    node: MatcherListDef,
    variants_by_name: dict[str, ResultVariantDef],
    is_single_rest: bool = True,
) -> list[str]:
    """Emit the `<Struct>Error` enum, trait implementations, and error matcher function.

    Args:
        node (MatcherListDef): Matcher list AST node for the REST struct.
        variants_by_name (dict[str, ResultVariantDef]): Mapping of variant names to AST nodes.
        is_single_rest (bool): Whether this is the only REST struct in the module.

    Returns:
        list[str]: Generated Rust error enum and matcher function lines.
    """
    struct_name = node.struct_name
    struct_pascal = _pascal(struct_name)
    struct_snake = to_snake_case(struct_name)
    enum_name = f"{struct_pascal}Error"

    variant_info: dict[str, tuple[str, int, bool]] = {}
    for entry in node.entries:
        v_name = rust_variant_name(struct_name, entry.factory_name)
        if v_name in variant_info:
            continue
        var_def = variants_by_name.get(entry.factory_name)
        if entry.error_schema:
            s_pascal = f"{_pascal(entry.error_schema)}Json"
            is_array = var_def.schema_is_array if var_def else False
            typ = f"Vec<{s_pascal}>" if is_array else s_pascal
            variant_info[v_name] = (typ, entry.status, False)
        else:
            variant_info[v_name] = ("serde_json::Value", entry.status, False)

    lines = [
        "#[derive(Debug)]",
        f"pub enum {enum_name} {{",
    ]
    for v_name, (typ, _, _) in variant_info.items():
        lines.append(f"    {v_name}({typ}),")
    lines.extend(
        [
            "    Transport(reqwest::Error),",
            "    Unknown(u16, serde_json::Value),",
            "}",
            "",
            f"impl {enum_name} {{",
            "    pub fn status(&self) -> Option<u16> {",
            "        match self {",
        ]
    )
    for v_name, (_, status, _) in variant_info.items():
        lines.append(f"            Self::{v_name}(_) => Some({status}),")
    lines.extend(
        [
            "            Self::Unknown(status, _) => Some(*status),",
            "            Self::Transport(_) => None,",
            "        }",
            "    }",
            "}",
            "",
            f"impl std::fmt::Display for {enum_name} {{",
            "    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {",
            "        match self {",
        ]
    )
    for v_name, (_, status, is_str) in variant_info.items():
        fmt_spec = "{}" if is_str else "{:?}"
        lines.append(
            f'            Self::{v_name}(body) => write!(f, "HTTP {status}: {fmt_spec}", body),'
        )
    lines.extend(
        [
            '            Self::Transport(err) => write!(f, "transport error: {}", err),',
            '            Self::Unknown(status, body) => write!(f, "HTTP {}: {}", status, body),',
            "        }",
            "    }",
            "}",
            "",
            f"impl std::error::Error for {enum_name} {{",
            "    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {",
            "        match self {",
            "            Self::Transport(err) => Some(err),",
            "            _ => None,",
            "        }",
            "    }",
            "}",
            "",
            f"impl From<reqwest::Error> for {enum_name} {{",
            "    fn from(err: reqwest::Error) -> Self {",
            "        Self::Transport(err)",
            "    }",
            "}",
            "",
            f"pub type {struct_pascal}EndpointError = {enum_name};",
        ]
    )
    if is_single_rest:
        lines.append(f"pub type EndpointError = {enum_name};")
    for entry in node.entries:
        v_name = rust_variant_name(struct_name, entry.factory_name)
        if entry.factory_name != v_name:
            typ, _, _ = variant_info[v_name]
            lines.append(f"pub type {entry.factory_name} = {typ};")
    lines.append("")

    # Emit matcher dispatch function.
    lines.extend(
        [
            f"fn match_{struct_snake}_error(",
            "    _status: u16,",
            "    _body_val: &serde_json::Value,",
            "    _body_text: &str,",
            f") -> Option<{enum_name}> {{",
        ]
    )
    for entry in node.entries:
        v_name = rust_variant_name(struct_name, entry.factory_name)
        var_def = variants_by_name.get(entry.factory_name)
        is_array = var_def.schema_is_array if var_def else False
        lines.append(f"    if _status == {entry.status} {{")
        checks: list[str] = []
        for k in entry.required_keys:
            checks.append(f"rt::json_opt(_body_val, {_str(k)}).is_some()")
        for path, val in entry.conditions.items():
            checks.append(render_rust_condition(path, val))

        ind = "        "
        if checks:
            cond_str = " && ".join(checks)
            lines.append(f"        if {cond_str} {{")
            ind = "            "

        if entry.error_schema:
            s_pascal = f"{_pascal(entry.error_schema)}Json"
            fallback_expr = f"let fallback = if _body_val.is_null() {{ serde_json::Value::String(_body_text.to_string()) }} else {{ _body_val.clone() }}; return Some({enum_name}::Unknown(_status, fallback));"
            if is_array:
                lines.extend(
                    [
                        f"{ind}if let Some(items) = _body_val.as_array() {{",
                        f"{ind}    if let Ok(decoded) = items.iter().cloned().map({s_pascal}::from_value).collect::<Result<Vec<_>, _>>() {{",
                        f"{ind}        return Some({enum_name}::{v_name}(decoded));",
                        f"{ind}    }}",
                        f"{ind}}}",
                        f"{ind}{fallback_expr}",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"{ind}if let Ok(decoded) = {s_pascal}::from_value(_body_val.clone()) {{",
                        f"{ind}    return Some({enum_name}::{v_name}(decoded));",
                        f"{ind}}}",
                        f"{ind}{fallback_expr}",
                    ]
                )
        else:
            lines.append(
                f"{ind}return Some({enum_name}::{v_name}(if _body_val.is_null() {{ serde_json::Value::String(_body_text.to_string()) }} else {{ _body_val.clone() }}));"
            )

        if checks:
            lines.append("        }")
        lines.append("    }")

    lines.extend(
        [
            "    None",
            "}",
            "",
        ]
    )
    return lines


def emit_method_rest(
    node: MethodRest,
    ctx: WalkContext,
) -> list[str]:
    """Emit an asynchronous REST endpoint associated method returning `Result<T, <Struct>Error>`.

    Args:
        node (MethodRest): AST node describing the REST endpoint request.
        ctx (WalkContext): Traversal context.

    Returns:
        list[str]: Generated Rust associated method lines.
    """
    spec: RequestHttp = node.http_request.with_renamed_placeholders(
        to_snake_case
    )
    parent = node.parent
    assert isinstance(parent, StructBase)
    struct_name = parent.name
    struct_pascal = _pascal(struct_name)
    struct_snake = to_snake_case(struct_name)
    enum_name = f"{struct_pascal}Error"
    method_name = to_snake_case(node.name) if node.name else "fetch"
    context = f"{struct_pascal}.{method_name}"
    params = placeholder_params(spec)

    if node.response_schema:
        s_pascal = f"{_pascal(node.response_schema)}Json"
        ok_type = (
            f"Vec<{s_pascal}>"
            if getattr(node, "response_is_array", False)
            else s_pascal
        )
    else:
        ok_type = "()"

    i1 = "    "
    i2 = "        "
    lines: list[str] = []
    if node.doc:
        for doc_line in node.doc.splitlines():
            lines.append(f"{i1}// {doc_line}" if doc_line else f"{i1}//")
    lines.append(
        f"{i1}pub async fn {method_name}({', '.join(params)}) -> Result<{ok_type}, {enum_name}> {{"
    )

    lines.extend(_emit_request_builder(spec, i2))

    if not node.response_schema:
        lines.append(
            f"{i2}rt::rest_call_void(req, match_{struct_snake}_error, {enum_name}::Unknown).await"
        )
    else:
        s_pascal = f"{_pascal(node.response_schema)}Json"
        is_array = getattr(node, "response_is_array", False)
        path_opt = (
            f"Some({_str(node.response_path)})"
            if node.response_path
            else "None"
        )
        if is_array:
            decode_expr = (
                f"|val| val.as_array()"
                f'.ok_or_else(|| rt::SscError::new({_str(context)}, "expected JSON array"))?'
                f".iter().cloned().map({s_pascal}::from_value).collect::<Result<Vec<_>, _>>()"
            )
        else:
            decode_expr = f"{s_pascal}::from_value"
        lines.append(
            f"{i2}rt::rest_call(req, {_str(context)}, {path_opt}, match_{struct_snake}_error, {decode_expr}, {enum_name}::Unknown).await"
        )

    lines.append(f"{i1}}}")
    lines.append("")
    return lines


def emit_struct_rest(
    node: StructRest,
    ctx: WalkContext,
    walk_fn: Any,
) -> list[str]:
    """Emit the REST API struct container and its `impl` block with endpoint methods.

    Args:
        node (StructRest): REST struct AST node.
        ctx (WalkContext): Traversal context.
        walk_fn (Any): Callback used to walk child AST nodes of `node`.

    Returns:
        list[str]: Generated Rust struct and `impl` block lines.
    """
    name = _pascal(node.name)
    lines: list[str] = []
    if node.doc:
        for doc_line in node.doc.splitlines():
            lines.append(f"// {doc_line}" if doc_line else "//")
    lines.extend(
        [
            f"pub struct {name};",
            "",
            f"pub type {name}Parser = {name};",
            "",
            f"impl {name} {{",
            "    pub fn new() -> Self {",
            "        Self",
            "    }",
            "",
        ]
    )
    for child in node.body:
        lines.extend(walk_fn(child, ctx))
    lines.extend(["}", ""])
    return lines
