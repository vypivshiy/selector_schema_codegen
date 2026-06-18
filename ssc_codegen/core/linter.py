"""Unified linter — structural validation, inline pipeline/predicate linting, cross-refs."""

from __future__ import annotations

import difflib as _difflib
import re as _re

from ssc_codegen.ast.struct import PLACEHOLDER_RE, PLACEHOLDER_WIDE_RE
from kdlquery import KdlDocument, KdlNode, ReadDiagnostic, Severity


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _error(
    node: KdlNode,
    message: str,
    source_path: str,
    *,
    code: str = "",
    hint: str = "",
) -> ReadDiagnostic:
    return ReadDiagnostic(
        message=message,
        severity=Severity.ERROR,
        span=node.span,
        path=source_path,
        code=code,
        hint=hint,
    )


def _warning(
    node: KdlNode,
    message: str,
    source_path: str,
    *,
    code: str = "",
    hint: str = "",
) -> ReadDiagnostic:
    return ReadDiagnostic(
        message=message,
        severity=Severity.WARNING,
        span=node.span,
        path=source_path,
        code=code,
        hint=hint,
    )


def _node_arg(node: KdlNode, index: int) -> str | None:
    if index < len(node.args):
        return str(node.args[index].value)
    return None


def _node_args(node: KdlNode) -> list[str]:
    return [str(a.value) for a in node.args]


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════


_VALID_STRUCT_TYPES = frozenset(
    {"item", "list", "dict", "table", "flat", "rest"}
)

_REQUIRED_RESERVED: dict[str, frozenset[str]] = {
    "item": frozenset(),
    "list": frozenset({"@split-doc"}),
    "dict": frozenset({"@split-doc", "@key", "@value"}),
    "table": frozenset({"@table", "@rows", "@match", "@value"}),
    "flat": frozenset(),
    "rest": frozenset({"@request"}),
}

_RESERVED_ALLOWED: dict[str, frozenset[str] | None] = {
    "@request": None,
    "@doc": None,
    "@pre-validate": frozenset({"item", "list", "dict", "table", "flat"}),
    "@check": frozenset({"item", "list", "dict", "table", "flat"}),
    "@init": frozenset({"item", "list", "dict", "table", "flat"}),
    "@split-doc": frozenset({"list", "dict"}),
    "@key": frozenset({"dict"}),
    "@value": frozenset({"dict", "table"}),
    "@table": frozenset({"table"}),
    "@rows": frozenset({"table"}),
    "@match": frozenset({"table"}),
    "@error": frozenset({"rest"}),
}

_VALID_JSON_MODIFIERS = frozenset({"@skip", "@omitempty"})
_VALID_JSON_TYPES = frozenset({"str", "int", "float", "bool", "null", "nil"})

_DEFINE_NAME_RE = _re.compile(r"^[A-Z_][A-Z0-9_-]*\Z")

_NO_ARGS_OPS: frozenset[str] = frozenset(
    {
        "text",
        "raw",
        "normalize-space",
        "lower",
        "upper",
        "unescape",
        "first",
        "last",
        "len",
        "unique",
        "to-int",
        "to-float",
        "to-bool",
    }
)

_TRIM_OPS: frozenset[str] = frozenset({"trim", "ltrim", "rtrim"})
_RM_OPS: frozenset[str] = frozenset(
    {"rm-prefix", "rm-suffix", "rm-prefix-suffix"}
)
_PREDICATE_BLOCKS: frozenset[str] = frozenset(
    {"filter", "assert", "match", "not", "and", "or"}
)

_EXTRA_PIPELINE_OPS: frozenset[str] = frozenset(
    {
        "filter",
        "assert",
        "match",
        "fallback",
        "self",
        "not",
        "and",
        "or",
    }
)

_PREDICATE_OPS: frozenset[str] = frozenset(
    {
        "eq",
        "ne",
        "starts",
        "ends",
        "contains",
        "in",
        "len-eq",
        "len-ne",
        "len-gt",
        "len-lt",
        "len-ge",
        "len-le",
        "len-range",
        "has-attr",
        "attr-eq",
        "attr-ne",
        "attr-starts",
        "attr-ends",
        "attr-contains",
        "attr-re",
        "text-re",
        "text-starts",
        "text-ends",
        "text-contains",
        "re-any",
        "gt",
        "lt",
        "ge",
        "le",
    }
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Structural linting — KdlDocument API
# ═══════════════════════════════════════════════════════════════════════════════


def lint_module(
    doc: KdlDocument, source_path: str = ""
) -> list[ReadDiagnostic]:
    """Structural pre-pass linting on the parsed KDL document."""
    diags: list[ReadDiagnostic] = []
    children_defines: dict[str, list[KdlNode]] = {}
    _lint_top_level(doc, source_path, diags)
    _lint_defines(doc, source_path, diags, children_defines)
    _lint_json_defs(doc, source_path, diags, children_defines)
    _lint_structs(doc, source_path, diags, children_defines)
    return diags


def _lint_top_level(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    for node in doc.select(":root:not(@doc, json, struct, define, import)"):
        diags.append(
            _error(
                node,
                f"Unknown node: {node.name}",
                source_path,
                code="E200",
            )
        )


def _lint_defines(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    for node in doc.select("define:root"):
        args = _node_args(node)
        children = list(node.children)
        if args:
            name = args[0]
            if not _DEFINE_NAME_RE.match(name):
                diags.append(
                    _error(
                        node,
                        f"define name '{name}' must be UPPER_CASE ([A-Z_][A-Z0-9_-]*)",
                        source_path,
                        code="E002",
                        hint="use UPPER_CASE: define MY-VAR=... or define MY_BLOCK { ... }",
                    )
                )
            if children:
                children_defines[name] = children
        if children:
            if not args:
                diags.append(
                    _error(
                        node,
                        "block 'define' requires a name",
                        source_path,
                        code="E001",
                        hint='example: define EXTRACT-HREF { css "a"; attr "href" }',
                    )
                )
        elif not node.properties:
            diags.append(
                _error(
                    node,
                    "'define' must be scalar (NAME=value) or block (NAME { ... })",
                    source_path,
                    code="E001",
                )
            )


def _lint_json_defs(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    seen_json_names: set[str] = set()
    for node in doc.select("json:root"):
        _lint_single_json(
            node, source_path, diags, seen_json_names, children_defines
        )


def _lint_single_json(
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
    seen_json_names: set[str],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    name = _node_arg(node, 0)
    if not name:
        diags.append(
            _error(
                node,
                "'json' requires a name",
                source_path,
                code="E001",
                hint="example: json MySchema { ... }",
            )
        )
        return

    if name in seen_json_names:
        diags.append(
            _error(
                node,
                f"duplicate json definition '{name}'",
                source_path,
                code="E001",
                hint=f"rename or remove one of the 'json {name}' definitions",
            )
        )
    seen_json_names.add(name)

    path_prop = node.properties.get("path")
    if path_prop is not None:
        path_val = str(path_prop.value)
        if not path_val:
            diags.append(
                _error(
                    node,
                    "'path' property must be a non-empty string",
                    source_path,
                    code="E002",
                    hint='example: json MySchema path="response.data" { ... }',
                )
            )

    seen_fields: set[str] = set()
    _lint_json_children(
        list(node.children),
        source_path,
        diags,
        children_defines,
        seen_fields,
    )


def _lint_json_children(
    children: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
    seen_fields: set[str],
) -> None:
    for field_node in children:
        field_name = field_node.name
        args = _node_args(field_node)

        # Block define expansion
        if not args and field_name in children_defines:
            _lint_json_children(
                children_defines[field_name],
                source_path,
                diags,
                children_defines,
                seen_fields,
            )
            continue

        has_type = False
        has_skip = False
        for arg in args:
            if arg.startswith("@"):
                if arg not in _VALID_JSON_MODIFIERS:
                    diags.append(
                        _error(
                            field_node,
                            f"unknown json field modifier '{arg}'",
                            source_path,
                            code="E002",
                            hint=f"valid modifiers: {', '.join(sorted(_VALID_JSON_MODIFIERS))}",
                        )
                    )
                if arg == "@skip":
                    has_skip = True
            else:
                has_type = True

        if not has_type and not has_skip:
            diags.append(
                _error(
                    field_node,
                    f"json field '{field_name}' requires a type",
                    source_path,
                    code="E001",
                    hint="example: field-name str  or  field-name @skip",
                )
            )

        if field_name in seen_fields:
            diags.append(
                _error(
                    field_node,
                    f"duplicate json field '{field_name}'",
                    source_path,
                    code="E001",
                    hint=f"remove or rename the duplicate '{field_name}' field",
                )
            )
        seen_fields.add(field_name)


def _lint_structs(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    for node in doc.select("struct:root"):
        _lint_single_struct(node, source_path, diags, children_defines)


def _lint_single_struct(
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    struct_name = _node_arg(node, 0)
    if not struct_name:
        diags.append(
            _error(
                node,
                "'struct' requires a name",
                source_path,
                code="E001",
                hint="example: struct MyStruct { ... }",
            )
        )
        return

    raw = node.type_annotation
    struct_type = raw[1:-1] if raw else (node.get_prop("type") or "item")
    if struct_type not in _VALID_STRUCT_TYPES:
        diags.append(
            _error(
                node,
                f"unknown struct type '{struct_type}'",
                source_path,
                code="E400",
                hint=f"valid types: {', '.join(sorted(_VALID_STRUCT_TYPES))}",
            )
        )
        return

    # Check required reserved fields using selectors
    missing = [
        r for r in _REQUIRED_RESERVED[struct_type] if node.select_one(r) is None
    ]
    if missing:
        diags.append(
            _error(
                node,
                f"struct type='{struct_type}' missing required field(s) "
                + ", ".join(missing),
                source_path,
                code="E401",
                hint=f"add: {', '.join(missing)}",
            )
        )

    for field_node in node.children:
        field_name = field_node.name
        if not field_name:
            continue
        if field_name.startswith("@"):
            _lint_reserved_field(
                field_node, field_name, struct_type, source_path, diags
            )
        else:
            if struct_type == "rest":
                diags.append(
                    _error(
                        field_node,
                        f"regular field '{field_name}' not allowed in struct type='rest'",
                        source_path,
                        code="E203",
                    )
                )
            else:
                _lint_regular_field_structural(
                    field_node,
                    field_name,
                    struct_type,
                    source_path,
                    diags,
                    children_defines,
                )


def _lint_reserved_field(
    node: KdlNode,
    field_name: str,
    struct_type: str,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    allowed = _RESERVED_ALLOWED.get(field_name)
    if allowed is not None and struct_type not in allowed:
        diags.append(
            _error(
                node,
                f"'{field_name}' not allowed in struct type='{struct_type}'",
                source_path,
                code="E203",
                hint=f"'{field_name}' only valid in: {', '.join(sorted(allowed))}",
            )
        )
        return

    if field_name == "@doc":
        if not _node_arg(node, 0):
            diags.append(
                _error(
                    node,
                    "'@doc' requires a description string",
                    source_path,
                    code="E001",
                )
            )
    elif field_name == "@request":
        if not _node_arg(node, 0):
            diags.append(
                _error(
                    node,
                    "'@request' requires a raw HTTP string",
                    source_path,
                    code="E001",
                )
            )
        else:
            _lint_request_placeholders(node, source_path, diags)
    elif field_name == "@init":
        if not list(node.children):
            diags.append(
                _error(
                    node,
                    "'@init' block must contain at least one named pipeline",
                    source_path,
                    code="E001",
                    hint='@init {\n    my-field { css ".x"; text }\n}',
                )
            )
    elif field_name == "@check":
        check_args = _node_args(node)
        check_name = check_args[0] if check_args else None
        ops = list(node.children)
        if not ops:
            diags.append(
                _error(
                    node,
                    f"@check {check_name or ''}block must contain at least one operation",
                    source_path,
                    code="E001",
                )
            )
        elif node.select_one("to-bool") is None:
            diags.append(
                _error(
                    node,
                    f"@check {check_name or ''}must contain 'to-bool' to guarantee BOOL return type",
                    source_path,
                    code="E100",
                )
            )
    elif field_name == "@error":
        err_args = _node_args(node)
        if len(err_args) < 2:
            diags.append(
                _error(
                    node,
                    "@error requires both status and schema name",
                    source_path,
                    code="E001",
                    hint="example: @error 404 ApiError",
                )
            )
            return
        positional_keys = set(err_args[2:])
        property_keys = set(node.properties.keys())
        duplicates = positional_keys & property_keys
        if duplicates:
            diags.append(
                _error(
                    node,
                    f"@error has duplicate keys: {', '.join(sorted(duplicates))}",
                    source_path,
                    code="E400",
                    hint="each key must be either a positional arg (presence check) or a property (value check)",
                )
            )


def _lint_request_placeholders(
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    raw_payload = str(node.args[0].value) if node.args else ""
    for m in PLACEHOLDER_WIDE_RE.finditer(raw_payload):
        token = m.group(0)
        strict = PLACEHOLDER_RE.match(token)
        if strict is None:
            diags.append(
                _error(
                    node,
                    f"malformed placeholder {token!r} in @request",
                    source_path,
                    code="E002",
                    hint="expected syntax: {{name}} or {{name:type}} (lowercase)",
                )
            )
            continue
        name = strict.group(1)
        if name != name.lower():
            diags.append(
                _error(
                    node,
                    f"placeholder '{{{{{name}}}}}' in @request must be lowercase; "
                    f"uppercase names are define substitutions which don't resolve in @request",
                    source_path,
                    code="E002",
                    hint=f"use lowercase for runtime params (e.g. {{{{{name.lower()}}}}}), "
                    f"or compose the URL in a define first",
                )
            )


def _lint_regular_field_structural(
    field_node: KdlNode,
    field_name: str,
    struct_type: str,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    ops = list(field_node.children)
    expanded = _expand_defines(ops, children_defines)
    if len(expanded) == 1 and expanded[0].name == "nested":
        return
    if not expanded:
        diags.append(
            _error(
                field_node,
                f"field '{field_name}' has no operations",
                source_path,
                code="E001",
                hint=f'add at least one operation: {field_name} {{ css ".item"; text }}',
            )
        )
        return
    if struct_type == "table":
        if expanded[0].name != "match":
            diags.append(
                _error(
                    field_node,
                    f"table field '{field_name}' must start with 'match {{ ... }}'",
                    source_path,
                    code="E001",
                )
            )


def _expand_defines(
    ops: list[KdlNode],
    children_defines: dict[str, list[KdlNode]],
    _visiting: set[str] | None = None,
) -> list[KdlNode]:
    """Expand block define references in a list of ops."""
    if _visiting is None:
        _visiting = set()
    result: list[KdlNode] = []
    for op in ops:
        if op.name in children_defines and op.name not in _visiting:
            _visiting.add(op.name)
            result.extend(
                _expand_defines(
                    children_defines[op.name], children_defines, _visiting
                )
            )
            _visiting.discard(op.name)
        else:
            result.append(op)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Cross-reference linting — flat list API (needs merged nodes with imports)
# ═══════════════════════════════════════════════════════════════════════════════


def lint_cross_refs(
    nodes: list[KdlNode], source_path: str = ""
) -> list[ReadDiagnostic]:
    """Cross-reference validation — needs merged node list including imports."""
    diags: list[ReadDiagnostic] = []
    json_names: set[str] = set()
    json_field_refs: list[tuple[KdlNode, str, str, str]] = []
    rest_response_refs: list[tuple[KdlNode, str]] = []
    rest_error_refs: list[tuple[KdlNode, str]] = []
    json_nodes: dict[str, KdlNode] = {}

    for node in nodes:
        if node.name == "json":
            name = _node_arg(node, 0)
            if name:
                json_names.add(name)
                json_nodes[name] = node
            for field_node in node.children:
                _collect_json_field_refs(
                    field_node, name or "", json_field_refs
                )
        elif node.name == "struct":
            for req in node.select("@request"):
                response = req.get_prop("response")
                if response:
                    rest_response_refs.append((req, response))
            for err in node.select("@error"):
                schema = _node_arg(err, 1)
                if schema:
                    rest_error_refs.append((err, schema))

    for req_node, schema_name in rest_response_refs:
        if schema_name not in json_names:
            diags.append(
                _error(
                    req_node,
                    f"@request response='{schema_name}' references undefined json definition '{schema_name}'",
                    source_path,
                    code="E300",
                    hint=f"define 'json {schema_name} {{ ... }}' or fix the response name",
                )
            )

    for err_node, schema_name in rest_error_refs:
        if schema_name not in json_names:
            diags.append(
                _error(
                    err_node,
                    f"@error schema '{schema_name}' references undefined json definition '{schema_name}'",
                    source_path,
                    code="E300",
                    hint=f"define 'json {schema_name} {{ ... }}' or fix the schema name",
                )
            )

    for field_node, field_name, ref_name, _parent in json_field_refs:
        if ref_name not in json_names:
            diags.append(
                _error(
                    field_node,
                    f"json field '{field_name}' references undefined json definition '{ref_name}'",
                    source_path,
                    code="E300",
                    hint=f"define 'json {ref_name} {{ ... }}' or fix the type name",
                )
            )

    # Circular reference detection for json
    graph: dict[str, set[str]] = {name: set() for name in json_names}
    for _, _, ref_name, parent_name in json_field_refs:
        if parent_name in graph and ref_name in json_names:
            graph[parent_name].add(ref_name)

    visited: set[str] = set()
    for name in list(json_names):
        visited.clear()
        stack: set[str] = set()
        cycle = _has_cycle(name, graph, stack, visited)
        if cycle:
            kdl_node = json_nodes.get(name)
            if kdl_node:
                diags.append(
                    _error(
                        kdl_node,
                        f"circular reference detected involving json definition '{name}'",
                        source_path,
                        code="E300",
                        hint="break the cycle by removing or changing one of the referenced types",
                    )
                )
            break

    return diags


def _collect_json_field_refs(
    field_node: KdlNode,
    parent_json_name: str,
    refs: list[tuple[KdlNode, str, str, str]],
) -> None:
    field_name = field_node.name
    type_found = False
    for arg in field_node.args:
        val = str(arg.value)
        if val.startswith("@"):
            continue
        if type_found:
            break
        type_found = True
        raw_type = val
        if raw_type.startswith("(array)"):
            raw_type = raw_type[len("(array)") :]
        if raw_type.endswith("?"):
            raw_type = raw_type[:-1]
        if raw_type and raw_type not in _VALID_JSON_TYPES:
            refs.append((field_node, field_name, raw_type, parent_json_name))


def _has_cycle(
    name: str,
    graph: dict[str, set[str]],
    stack: set[str],
    visited: set[str],
) -> str | None:
    if name in stack:
        return name
    if name in visited:
        return None
    visited.add(name)
    stack.add(name)
    for dep in graph.get(name, set()):
        cycle = _has_cycle(dep, graph, stack, visited)
        if cycle:
            stack.discard(name)
            return cycle
    stack.discard(name)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Inline linting — argument validation, pattern validation
# ═══════════════════════════════════════════════════════════════════════════════


def lint_require_args(
    node: KdlNode,
    lint: LintContext,
    *,
    exact: int | None = None,
    min_count: int | None = None,
    max_count: int | None = None,
    example: str = "",
) -> list[str] | None:
    args = _node_args(node)
    name = node.name
    count = len(args)

    if exact is not None and count != exact:
        noun = "argument" if exact == 1 else "arguments"
        lint.error(
            node,
            message=f"'{name}' requires exactly {exact} {noun}, got {count}",
            code="E001",
            hint=example,
        )
        return None

    if min_count is not None and count < min_count:
        noun = "argument" if min_count == 1 else "arguments"
        lint.error(
            node,
            message=f"'{name}' requires at least {min_count} {noun}, got {count}",
            code="E001",
            hint=example,
        )
        return None

    if max_count is not None and count > max_count:
        lint.error(
            node,
            message=f"'{name}' allows at most {max_count} argument(s), got {count}",
            code="E001",
            hint=example,
        )
        return None

    return args


def lint_require_int_args(
    node: KdlNode, lint: LintContext, args: list[str]
) -> bool:
    name = node.name
    for arg in args:
        try:
            int(arg)
        except ValueError:
            lint.error(
                node,
                message=f"'{name}' arguments must be integers, got '{arg}'",
                code="E001",
                hint=f"example: {name} 0",
            )
            return False
    return True


def lint_validate_regex(node: KdlNode, lint: LintContext, pattern: str) -> bool:
    try:
        _re.compile(pattern.lstrip())
        return True
    except _re.error as e:
        lint.error(
            node,
            message=f"invalid regex pattern: {e.msg}",
            code="E002",
            hint="check regex syntax",
        )
        return False


def lint_validate_css(node: KdlNode, lint: LintContext, selector: str) -> bool:
    try:
        import soupsieve

        soupsieve.compile(selector)
        return True
    except Exception as e:
        msg = str(e).split("\n")[0] if str(e) else "invalid selector"
        lint.error(
            node,
            message=f"invalid CSS selector: {msg}",
            code="E002",
            hint="check selector syntax",
        )
        return False


def lint_validate_xpath(node: KdlNode, lint: LintContext, expr: str) -> bool:
    try:
        from lxml import etree

        etree.XPath(expr)
        return True
    except Exception as e:
        msg = str(e).split("\n")[0] if str(e) else "invalid expression"
        lint.error(
            node,
            message=f"invalid XPath expression: {msg}",
            code="E002",
            hint="check XPath syntax",
        )
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  Inline linting — pipeline and predicate op validation
# ═══════════════════════════════════════════════════════════════════════════════


def lint_require_predicate_ctx(node: KdlNode, lint: LintContext) -> bool:
    if lint.in_predicate:
        return True
    name = node.name
    blocks = ", ".join(sorted(_PREDICATE_BLOCKS))
    lint.error(
        node,
        message=f"'{name}' is only valid inside a predicate block",
        code="E203",
        hint=f"wrap it in one of: {blocks}. Example: filter {{ {name} ... }}",
    )
    return False


def lint_require_assert_ctx(node: KdlNode, lint: LintContext) -> bool:
    if lint.in_assert:
        return True
    name = node.name
    lint.error(
        node,
        message=f"'{name}' is only valid inside an assert block",
        code="E203",
        hint=f"example: assert {{ {name} ... }}",
    )
    return False


def lint_pipeline_op(node: KdlNode, lint: LintContext) -> None:
    """Validate a single pipeline operation node."""
    name = node.name

    if name in _NO_ARGS_OPS:
        if node.args:
            lint.error(
                node,
                message=f"'{name}' does not accept arguments",
                code="E001",
                hint=f"remove arguments: use just '{name}'",
            )
        return

    if name == "attr":
        lint_require_args(node, lint, min_count=1, example='attr "href"')

    elif name in _TRIM_OPS:
        args = _node_args(node)
        if len(args) > 1:
            lint.error(
                node,
                message=f"'{name}' accepts at most 1 argument",
                code="E001",
                hint=f'example: {name}  or  {name} "chars"',
            )

    elif name in _RM_OPS:
        lint_require_args(node, lint, exact=1, example=f'{name} "substring"')

    elif name == "fmt":
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=1, example='fmt "prefix-{{}}-suffix"'
        )
        if args and not (args[0].isupper() or "{{}}" in args[0]):
            lint.error(
                node,
                message="'fmt' template is missing the '{{}}' placeholder",
                code="E001",
                hint=f'add placeholder to template, example: fmt "{args[0]}{{}}"',
            )

    elif name == "repl":
        children = list(node.children)
        args = _node_args(node)
        if not args and not children:
            lint.error(
                node,
                message="'repl' requires 2 arguments or a children block",
                code="E001",
                hint='example: repl "old" "new"  or  repl { "old" "new"; "foo" "bar" }',
            )
        elif args:
            lint_require_args(node, lint, exact=2, example='repl "old" "new"')

    elif name in ("split", "join"):
        lint_require_args(node, lint, exact=1, example=f'{name} " "')

    elif name == "re":
        raw_args = node.args
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=1, example=f'{name} #"(\\d+)"#'
        )
        if args:
            pattern = args[0]
            if raw_args and _DEFINE_NAME_RE.match(str(raw_args[0].value)):
                resolved = lint.resolve_scalar_arg(pattern)
                if resolved is not None:
                    pattern = resolved
            normalized = pattern.lstrip()
            if (
                lint_validate_regex(node, lint, normalized)
                and not lint.in_predicate
            ):
                groups = _re.compile(normalized).groups
                if groups == 0:
                    lint.error(
                        node,
                        message=f"'{name}' pattern must have exactly one capture group",
                        code="E001",
                        hint=f'wrap the match in a group: {name} #"({pattern})"#',
                    )
                elif groups > 1:
                    lint.error(
                        node,
                        message=f"'{name}' pattern must have exactly one capture group, got {groups}",
                        code="E001",
                        hint="use a non-capturing group (?:...) for grouping without capturing",
                    )

    elif name == "re-all":
        if lint.in_predicate and not lint_require_assert_ctx(node, lint):
            return
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=1, example='re-all #"(\\d+)"#'
        )
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name == "re-sub":
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=2, example='re-sub #"\\D"# ""'
        )
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name == "index":
        args = lint_require_args(node, lint, exact=1, example="index 0")  # type: ignore[assignment]
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "slice":
        args = lint_require_args(node, lint, exact=2, example="slice 0 10")  # type: ignore[assignment]
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "jsonify":
        lint_require_args(node, lint, exact=1, example="jsonify MySchema")

    elif name == "nested":
        lint_require_args(node, lint, exact=1, example="nested MyStruct")

    elif name == "self":
        args = lint_require_args(node, lint, exact=1, example="self field-name")  # type: ignore[assignment]
        if args and args[0] not in lint.init_fields:
            lint.error(
                node,
                message=f"'self {args[0]}': field '{args[0]}' not found in @init block (deprecated syntax)",
                code="E301",
                hint=f"declare it in @init: @init {{ {args[0]} {{ ... }} }} or use new syntax: @{args[0]}",
            )

    elif name == "fallback":
        children = list(node.children)
        args = _node_args(node)
        if not args and not children and len(node.children) == 0:
            pass  # empty block fallback is ok (for lists)
        elif not args and not children:
            lint.error(
                node,
                message="'fallback' requires exactly 1 argument or a block",
                code="E001",
                hint='example: fallback ""  or  fallback 0  or  fallback #null  or  fallback {}',
            )

    elif name in ("filter", "assert", "match"):
        if node.args:
            lint.error(
                node,
                message=f"'{name}' does not accept arguments",
                code="E001",
                hint=f"move expressions into the children block: {name} {{ ... }}",
            )
        if not list(node.children) and len(node.children) == 0:
            lint.error(
                node,
                message=f"'{name}' block must contain at least one predicate expression",
                code="E001",
                hint=f'example: {name} {{ css ".item"; has-attr href }}',
            )

    elif name in ("not", "and", "or"):
        if node.args:
            lint.error(
                node,
                message=f"'{name}' does not accept arguments",
                code="E001",
                hint=f"move expressions into the children block: {name} {{ ... }}",
            )
        if not list(node.children) and len(node.children) == 0:
            lint.error(
                node,
                message=f"'{name}' block must contain at least one predicate expression",
                code="E001",
                hint=f'example: {name} {{ starts "foo" }}',
            )

    # @init reference validation
    elif name.startswith("@") and name not in {
        "@doc",
        "@init",
        "@pre-validate",
        "@split-doc",
        "@key",
        "@value",
        "@table",
        "@rows",
        "@match",
    }:
        field_name = name[1:]
        if field_name not in lint.init_fields:
            lint.error(
                node,
                message=f"'@{field_name}': field '{field_name}' not found in @init block",
                code="E301",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}",
            )


def lint_predicate_op(node: KdlNode, lint: LintContext) -> None:
    """Validate a predicate operation node inside filter/assert/match."""
    name = node.name

    if name in ("eq", "ne"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("starts", "ends", "contains", "in"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("len-eq", "len-ne"):
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, min_count=1, example=f"{name} 5")
        if args:
            for arg in args:
                try:
                    val = int(arg)
                    if val < 0:
                        lint.error(
                            node,
                            message=f"'{name}' argument must be non-negative, got {val}",
                            code="E001",
                            hint=f"example: {name} 5",
                        )
                        return
                except ValueError:
                    lint.error(
                        node,
                        message=f"'{name}' argument must be integer, got '{arg}'",
                        code="E001",
                        hint=f"example: {name} 5",
                    )
                    return

    elif name in ("len-gt", "len-lt", "len-ge", "len-le"):
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=1, example=f"{name} 10")
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "len-range":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=2, example="len-range 1 100")
        if args:
            lint_require_int_args(node, lint, args)

    elif name == "has-attr":
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example='has-attr "href"')

    elif name in (
        "attr-eq",
        "attr-ne",
        "attr-starts",
        "attr-ends",
        "attr-contains",
    ):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(
            node, lint, min_count=2, example=f'{name} "href" "value"'
        )

    elif name == "attr-re":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(
            node, lint, exact=2, example='attr-re "href" #".*\\.com$"#'
        )
        if args:
            lint_validate_regex(node, lint, args[1])

    elif name == "text-re":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(
            node, lint, exact=1, example='text-re #"\\d+"#'
        )
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name in ("text-starts", "text-ends", "text-contains"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name == "re-any":
        if not lint_require_assert_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=1, example='re-any #"\\d+"#')
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name in ("gt", "lt", "ge", "le"):
        if not lint_require_assert_ctx(node, lint):
            return
        lint_require_args(node, lint, exact=1, example=f"{name} 42")

    elif name == "re":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=1, example='re #"(\\d+)"#')
        if args:
            lint_validate_regex(node, lint, args[0])

    elif name == "css":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = _node_args(node)
        if args:
            lint_validate_css(node, lint, args[0])

    elif name == "xpath":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = _node_args(node)
        if args:
            lint_validate_xpath(node, lint, args[0])

    elif name == "range":
        if not lint_require_predicate_ctx(node, lint):
            return
        args = lint_require_args(node, lint, exact=2, example="range 1 100")
        if args:
            lint_require_int_args(node, lint, args)


def lint_wildcard_op(
    node: KdlNode, ctx: ParseContext, lint: LintContext
) -> None:
    """Validate unknown ops in pipeline context."""
    from ssc_codegen.core.type_checking import _OP_TYPES

    op_name = node.name
    if not op_name:
        return

    if op_name.startswith("@"):
        field_name = op_name[1:]
        if field_name not in lint.init_fields:
            lint.error(
                node,
                message=f"'@{field_name}': field '{field_name}' not found in @init block",
                code="E301",
                hint=f"declare it in @init: @init {{ {field_name} {{ ... }} }}",
            )
        return

    info = lint.defines.get(op_name)
    if info is not None:
        if info.kind == DefineKind.SCALAR:
            lint.error(
                node,
                message=f"'{op_name}' is a scalar define — cannot be used as a pipeline operation",
                code="E001",
                hint=f"use a block define: define {op_name} {{ ... }}",
            )
        return

    _KNOWN_OPS: frozenset[str] = (
        frozenset(_OP_TYPES.keys()) | _EXTRA_PIPELINE_OPS | _PREDICATE_OPS
    )
    candidates = sorted(
        _KNOWN_OPS
        | {k for k, v in lint.defines.items() if v.kind == DefineKind.BLOCK}
    )
    suggestions = _difflib.get_close_matches(
        op_name, candidates, n=3, cutoff=0.6
    )
    if suggestions:
        hint = (
            "did you mean " + " or ".join(f"'{s}'" for s in suggestions) + "?"
        )
    else:
        hint = f"check spelling or declare it: define {op_name} {{ ... }}"
    lint.error(
        node,
        message=f"unknown operation '{op_name}'",
        code="E200",
        hint=hint,
    )


# lazy imports for forward refs
from ssc_codegen.core.contexts import (  # noqa: E402
    DefineKind,
    LintContext,
    ParseContext,
)
