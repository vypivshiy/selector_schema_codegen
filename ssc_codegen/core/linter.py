"""Structural pre-pass linter — validates KDL tree before AST construction."""

from __future__ import annotations

import re as _re

from ssc_codegen.ast import VariableType
from ssc_codegen.ast.struct import PLACEHOLDER_RE, PLACEHOLDER_WIDE_RE
from kdlquery import KdlNode, ReadDiagnostic, Severity


# ── Helpers ──────────────────────────────────────────────────────────────────────


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


# ── Constants ────────────────────────────────────────────────────────────────────


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

_VALID_TRANSFORM_TYPES = frozenset(
    {t.name for t in VariableType if t.name not in ("AUTO", "LIST_AUTO")}
)

_DEFINE_NAME_RE = _re.compile(r"^[A-Z_][A-Z0-9_-]*\Z")


# ── Public API ───────────────────────────────────────────────────────────────────


def lint_nodes(
    nodes: list[KdlNode], source_path: str = ""
) -> list[ReadDiagnostic]:
    """Structural pre-pass linting on flat KDL node list."""
    diags: list[ReadDiagnostic] = []
    children_defines: dict[str, list[KdlNode]] = {}
    _lint_top_level(nodes, source_path, diags)
    _lint_defines(nodes, source_path, diags, children_defines)
    _lint_transforms(nodes, source_path, diags)
    _lint_json_defs(nodes, source_path, diags, children_defines)
    _lint_structs(nodes, source_path, diags, children_defines)
    _lint_cross_refs(nodes, source_path, diags)
    return diags


# ── Top-level ────────────────────────────────────────────────────────────────────


def _lint_top_level(
    nodes: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    for node in nodes:
        if node.name not in (
            "@doc",
            "json",
            "struct",
            "define",
            "transform",
            "import",
        ):
            diags.append(
                _error(
                    node,
                    f"Unknown node: {node.name}",
                    source_path,
                    code="E200",
                )
            )


# ── Define lint ──────────────────────────────────────────────────────────────────


def _lint_defines(
    nodes: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    for node in nodes:
        if node.name != "define":
            continue
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


# ── Transform lint ───────────────────────────────────────────────────────────────


def _lint_transforms(
    nodes: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    for node in nodes:
        if node.name != "transform":
            continue
        accept_str = node.get_prop("accept")
        ret_str = node.get_prop("return")
        lang_nodes = list(node.children)
        is_definition = bool(accept_str or ret_str or lang_nodes)
        if not is_definition:
            continue

        args = _node_args(node)
        if not args:
            diags.append(
                _error(
                    node,
                    "'transform' requires a name",
                    source_path,
                    code="E001",
                )
            )
            continue
        name = args[0]

        if not accept_str:
            diags.append(
                _error(
                    node,
                    f"'transform {name}' missing required property 'accept'",
                    source_path,
                    code="E001",
                )
            )
        elif accept_str not in _VALID_TRANSFORM_TYPES:
            diags.append(
                _error(
                    node,
                    f"'transform {name}': invalid accept type '{accept_str}' (AUTO not allowed)",
                    source_path,
                    code="E001",
                )
            )

        if not ret_str:
            diags.append(
                _error(
                    node,
                    f"'transform {name}' missing required property 'return'",
                    source_path,
                    code="E001",
                )
            )
        elif ret_str not in _VALID_TRANSFORM_TYPES:
            diags.append(
                _error(
                    node,
                    f"'transform {name}': invalid return type '{ret_str}' (AUTO not allowed)",
                    source_path,
                    code="E001",
                )
            )

        if not lang_nodes:
            diags.append(
                _error(
                    node,
                    f"'transform {name}' has no language implementations",
                    source_path,
                    code="E001",
                )
            )
            continue

        for lang_node in lang_nodes:
            lang = lang_node.name
            if not lang:
                continue
            impl_nodes = list(lang_node.children)
            has_code = any(n.name == "code" for n in impl_nodes)
            for impl_node in impl_nodes:
                impl_name = impl_node.name
                if impl_name == "code" and not _node_args(impl_node):
                    diags.append(
                        _error(
                            impl_node,
                            f"'transform {name}' > '{lang}' > 'code' requires a string argument",
                            source_path,
                            code="E001",
                        )
                    )
                elif impl_name == "import" and not _node_args(impl_node):
                    diags.append(
                        _error(
                            impl_node,
                            f"'transform {name}' > '{lang}' > 'import' requires a string argument",
                            source_path,
                            code="E001",
                        )
                    )
                elif impl_name and impl_name not in ("code", "import"):
                    diags.append(
                        _error(
                            impl_node,
                            f"'transform {name}' > '{lang}': unknown keyword '{impl_name}'",
                            source_path,
                            code="E200",
                        )
                    )
            if not has_code:
                diags.append(
                    _error(
                        lang_node,
                        f"'transform {name}' > '{lang}' has no 'code' statement",
                        source_path,
                        code="E001",
                    )
                )


# ── JSON lint ────────────────────────────────────────────────────────────────────


def _lint_json_defs(
    nodes: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    seen_json_names: set[str] = set()
    for node in nodes:
        if node.name != "json":
            continue
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


# ── Struct lint ──────────────────────────────────────────────────────────────────


def _lint_structs(
    nodes: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    for node in nodes:
        if node.name != "struct":
            continue
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

    fields = list(node.children)
    reserved_present = {f.name for f in fields if f.name.startswith("@")}

    missing = sorted(_REQUIRED_RESERVED[struct_type] - reserved_present)
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

    for field_node in fields:
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
            # Validate placeholders in @request payload
            _lint_request_placeholders(node, source_path, diags)
    elif field_name == "@init":
        sub_pipelines = list(node.children)
        if not sub_pipelines:
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
        elif not any(o.name == "to-bool" for o in ops):
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
    # Expand block defines for nested check
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


# ── Cross-reference lint ─────────────────────────────────────────────────────────


def _lint_cross_refs(
    nodes: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    json_names: set[str] = set()
    # json_field_refs: (field_node, field_name, ref_name, parent_json_name)
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
            for child in node.children:
                if child.name == "@request":
                    response = child.get_prop("response")
                    if response:
                        rest_response_refs.append((child, response))
                elif child.name == "@error":
                    schema = _node_arg(child, 1)
                    if schema:
                        rest_error_refs.append((child, schema))

    # Validate @request response refs
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

    # Validate @error schema refs
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

    # Validate json field type refs
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


def _collect_json_field_refs(
    field_node: KdlNode,
    parent_json_name: str,
    refs: list[tuple[KdlNode, str, str, str]],
) -> None:
    field_name = field_node.name
    # Only the first non-modifier arg is the type; others are alias/extra
    type_found = False
    for arg in field_node.args:
        val = str(arg.value)
        if val.startswith("@"):
            continue
        if type_found:
            break  # remaining args are alias, not types
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
