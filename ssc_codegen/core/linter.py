"""Unified linter — structural validation, inline pipeline/predicate linting, cross-refs."""

from __future__ import annotations

import difflib as _difflib
import re as _re
from collections.abc import Iterable, Mapping
from typing import Iterator

from ssc_codegen.symbols import (
    HTTP_REQUEST_SIGNATURES,
    REQUEST_LINE_CONTINUATION_HINT,
    SymbolKind,
    SymbolRecord,
    SymbolScope,
    local_symbol,
    is_valid_symbol,
    normalize_targets,
    top_symbol_names,
    target_symbol_plan,
)
from ssc_codegen.naming import to_pascal_case
from ssc_codegen.ast.struct import PLACEHOLDER_WIDE_RE, PlaceholderSpec
from kdlquery import KdlDocument, KdlNode, ReadDiagnostic, Severity


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _diag(
    node: KdlNode,
    message: str,
    source_path: str,
    severity: Severity,
    *,
    code: str = "",
    hint: str = "",
) -> ReadDiagnostic:
    return ReadDiagnostic(
        message=message,
        severity=severity,
        span=node.span,
        path=source_path,
        code=code,
        hint=hint,
    )


def _error(
    node: KdlNode,
    message: str,
    source_path: str,
    *,
    code: str = "",
    hint: str = "",
) -> ReadDiagnostic:
    return _diag(
        node, message, source_path, Severity.ERROR, code=code, hint=hint
    )


def _warning(
    node: KdlNode,
    message: str,
    source_path: str,
    *,
    code: str = "",
    hint: str = "",
) -> ReadDiagnostic:
    return _diag(
        node, message, source_path, Severity.WARNING, code=code, hint=hint
    )


def _node_arg(node: KdlNode, index: int) -> str | None:
    if index < len(node.args):
        return str(node.args[index].value)
    return None


def _node_args(node: KdlNode) -> list[str]:
    return [str(a.value) for a in node.args]


def is_http_status(value: int) -> bool:
    """Validate whether an integer represents a valid HTTP status code (100..599).

    Args:
        value: Numeric status code candidate.

    Returns:
        `True` if `100 <= value <= 599`, otherwise `False`.
    """
    return 100 <= value <= 599


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════


_VALID_STRUCT_TYPES = frozenset(
    {"item", "list", "dict", "table", "flat", "rest", "raw"}
)

_REQUIRED_RESERVED: dict[str, frozenset[str]] = {
    "item": frozenset(),
    "list": frozenset({"@split-doc"}),
    "dict": frozenset({"@split-doc", "@key", "@value"}),
    "table": frozenset({"@table", "@rows", "@match", "@value"}),
    "flat": frozenset(),
    "rest": frozenset({"@request"}),
    "raw": frozenset(),
}

_RESERVED_ALLOWED: dict[str, frozenset[str] | None] = {
    "@request": None,
    "@doc": None,
    "@pre-validate": frozenset(
        {"item", "list", "dict", "table", "flat", "raw"}
    ),
    "@check": frozenset({"item", "list", "dict", "table", "flat", "raw"}),
    "@init": frozenset({"item", "list", "dict", "table", "flat", "raw"}),
    "@split-doc": frozenset({"list", "dict", "raw"}),
    "@key": frozenset({"dict"}),
    "@value": frozenset({"dict", "table"}),
    "@table": frozenset({"table"}),
    "@rows": frozenset({"table"}),
    "@match": frozenset({"table"}),
    "@error": frozenset({"rest"}),
}

_VALID_JSON_MODIFIERS = frozenset({"@skip", "@omitempty"})
_VALID_JSON_TYPES = frozenset({"str", "int", "float", "bool", "null", "nil"})
_VALID_IMPORT_KINDS = frozenset({"define", "extension", "fn", "json", "struct"})

_DEFINE_NAME_RE = _re.compile(r"^[A-Z_][A-Z0-9_-]*\Z")
_EXTENSION_NAME_RE = _re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\Z")
_PORTABLE_IDENTIFIER_RE = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\Z")
_EXTENSION_PLACEHOLDER_RE = _re.compile(r"\{\{([^{}]+)\}\}")
_EXTENSION_PLACEHOLDERS = frozenset({"in", "in_type", "out", "out_type"})
_JS_RESERVED = frozenset(
    {
        "await",
        "break",
        "case",
        "catch",
        "class",
        "const",
        "constructor",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "implements",
        "import",
        "in",
        "instanceof",
        "interface",
        "let",
        "new",
        "null",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)
_GO_RESERVED = frozenset(
    {
        "break",
        "default",
        "func",
        "interface",
        "select",
        "case",
        "defer",
        "go",
        "map",
        "struct",
        "chan",
        "else",
        "goto",
        "package",
        "switch",
        "const",
        "fallthrough",
        "if",
        "range",
        "type",
        "continue",
        "for",
        "import",
        "return",
        "var",
    }
)

_NO_ARGS_OPS: frozenset[str] = frozenset(
    {
        "text",
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
    }
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Structural linting — KdlDocument API
# ═══════════════════════════════════════════════════════════════════════════════


def lint_module(
    doc: KdlDocument, source_path: str = "", *, source_text: str = ""
) -> list[ReadDiagnostic]:
    """Execute single-file structural and syntactic validation passes on a parsed KDL document.

    Checks:
    - Top-level node whitelist (`struct`, `json`, `fn`, `define`, `extension`, `import`, `@doc`).
    - Explicit import block syntax and kind annotations.
    - Extension signatures and valid targets (`py`, `js`, `go`, `rust`).
    - Define names (UPPER_CASE) and scalar/block structure.
    - JSON schema definitions, field types, and dot-notation paths.
    - Struct structural invariants and required directives per struct type.
    - Function declarations (`fn`, `(raw)fn`).
    - Local top-down declaration order (`E302`) for `nested` and `json` type references.

    Args:
        doc: The parsed `KdlDocument` to validate.
        source_path: Filesystem path to the KDL source file.
        source_text: Raw source code text for quoted string checks.

    Returns:
        List of collected `ReadDiagnostic` warnings and errors.
    """
    diags: list[ReadDiagnostic] = []
    children_defines: dict[str, list[KdlNode]] = {}
    _lint_top_level(doc, source_path, diags)
    _lint_imports(doc, source_path, diags)
    _lint_extensions(doc, source_path, diags)
    _lint_defines(doc, source_path, diags, children_defines)
    _lint_json_defs(doc, source_path, diags, children_defines, source_text)
    _lint_structs(doc, source_path, diags, children_defines)
    _lint_fns(doc, source_path, diags)
    _lint_nested_topdown(doc, source_path, diags)
    _lint_json_refs_topdown(doc, source_path, diags, children_defines)
    return diags


def _lint_top_level(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    for node in doc.select(
        ":root:not(@doc, json, struct, fn, define, extension, import)"
    ):
        diags.append(
            _error(
                node,
                f"Unknown node: {node.name}",
                source_path,
                code="E200",
            )
        )


def _lint_imports(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    seen_paths: set[str] = set()
    for node in doc.select("import:root"):
        args = _node_args(node)
        if len(args) != 1:
            diags.append(
                _error(
                    node,
                    "'import' requires exactly one path argument",
                    source_path,
                    code="E001",
                    hint='example: import "./shared.kdl" { (struct)Shared }',
                )
            )
        elif args[0] in seen_paths:
            diags.append(
                _error(
                    node,
                    f"duplicate import path '{args[0]}'",
                    source_path,
                    code="E003",
                    hint="combine symbols into one import block",
                )
            )
        else:
            seen_paths.add(args[0])
        if node.properties:
            diags.append(
                _error(
                    node,
                    "'import' does not accept properties",
                    source_path,
                    code="E001",
                )
            )
        children = list(node.children)
        if not children:
            diags.append(
                _error(
                    node,
                    "'import' requires an explicit non-empty symbol block",
                    source_path,
                    code="E001",
                    hint='example: import "./shared.kdl" { (struct)Shared }',
                )
            )
            continue
        seen_items: set[tuple[str, str]] = set()
        for child in children:
            annotation = child.type_annotation
            if not annotation:
                diags.append(
                    _error(
                        child,
                        f"imported symbol '{child.name}' requires a kind annotation",
                        source_path,
                        code="E001",
                        hint=f"use `(struct){child.name}` or another explicit kind",
                    )
                )
                continue
            kind = annotation[1:-1]
            if kind not in _VALID_IMPORT_KINDS:
                diags.append(
                    _error(
                        child,
                        f"unknown import kind '{kind}'",
                        source_path,
                        code="E002",
                        hint="valid kinds: "
                        + ", ".join(sorted(_VALID_IMPORT_KINDS)),
                    )
                )
                continue
            if child.args or child.properties or child.children:
                diags.append(
                    _error(
                        child,
                        "import items cannot have arguments, properties, or children",
                        source_path,
                        code="E001",
                        hint=f"use `({kind}){child.name}`",
                    )
                )
            item = (kind, child.name)
            if item in seen_items:
                diags.append(
                    _error(
                        child,
                        f"duplicate imported symbol: {kind} '{child.name}'",
                        source_path,
                        code="E003",
                    )
                )
            seen_items.add(item)


def _lint_extension_type(
    value,
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    name = str(value.value).rstrip("?")
    annotation = value.type_annotation
    if name not in {"T", "bool", "doc", "float", "int", "str"}:
        diags.append(
            _error(
                node,
                f"unknown extension signature type '{name}'",
                source_path,
                code="E400",
                hint="valid types: T, bool, doc, float, int, str",
            )
        )
    if annotation and annotation != "(array)":
        diags.append(
            _error(
                node,
                f"unsupported extension type annotation '{annotation}'",
                source_path,
                code="E400",
                hint="only '(array)' is supported",
            )
        )
    if name == "T" and (annotation or str(value.value).endswith("?")):
        diags.append(
            _error(
                node,
                "generic type T cannot have modifiers",
                source_path,
                code="E400",
            )
        )


def _lint_extension_import(
    node: KdlNode,
    target: str,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    if len(node.args) != 1 or node.children:
        diags.append(
            _error(
                node,
                "extension import requires one string argument and no children",
                source_path,
                code="E001",
            )
        )
    unknown_props = set(node.properties) - {"alias"}
    if unknown_props:
        diags.append(
            _error(
                node,
                "unknown extension import properties: "
                + ", ".join(sorted(unknown_props)),
                source_path,
                code="E002",
            )
        )
    if node.get_prop("alias") and target not in ("go", "rust"):
        diags.append(
            _error(
                node,
                "import alias is only supported for Go package imports",
                source_path,
                code="E203",
            )
        )


def _lint_extension_target(
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    allowed = {"emit", "helper", "import"}
    for child in node.children:
        if child.name not in allowed:
            diags.append(
                _error(
                    child,
                    f"unknown '{node.name}' extension entry '{child.name}'",
                    source_path,
                    code="E200",
                    hint="valid entries: emit, helper, import",
                )
            )
    emits = [child for child in node.children if child.name == "emit"]
    if len(emits) != 1 or len(emits[0].args) != 1:
        diags.append(
            _error(
                node,
                f"extension target '{node.name}' requires exactly one `emit <template>`",
                source_path,
                code="E001",
            )
        )
    else:
        template = str(emits[0].args[0].value)
        placeholders = set(_EXTENSION_PLACEHOLDER_RE.findall(template))
        unknown = placeholders - _EXTENSION_PLACEHOLDERS
        if unknown:
            diags.append(
                _error(
                    emits[0],
                    "unknown extension template placeholders: "
                    + ", ".join(sorted(unknown)),
                    source_path,
                    code="E002",
                )
            )
        if "out" not in placeholders:
            diags.append(
                _error(
                    emits[0],
                    "extension emit template must assign '{{out}}'",
                    source_path,
                    code="E002",
                )
            )
    for child in node.children:
        if child.name == "import":
            _lint_extension_import(child, node.name, source_path, diags)
        elif child.name == "helper":
            helper_name = str(child.args[0].value) if child.args else ""
            target_name = {"py": "python", "js": "javascript"}.get(
                node.name, node.name
            )
            if (
                len(child.args) != 1
                or not _PORTABLE_IDENTIFIER_RE.fullmatch(helper_name)
                or not _is_valid_generated_identifier(target_name, helper_name)
            ):
                diags.append(
                    _error(
                        child,
                        "helper requires one portable identifier",
                        source_path,
                        code="E403",
                    )
                )
            helper_allowed = {"import", "source"}
            for entry in child.children:
                if entry.name not in helper_allowed:
                    diags.append(
                        _error(
                            entry,
                            f"unknown helper entry '{entry.name}'",
                            source_path,
                            code="E200",
                            hint="valid entries: import, source",
                        )
                    )
                elif entry.name == "import":
                    _lint_extension_import(entry, node.name, source_path, diags)
            sources = [
                entry for entry in child.children if entry.name == "source"
            ]
            if len(sources) != 1 or len(sources[0].args) != 1:
                diags.append(
                    _error(
                        child,
                        "helper requires exactly one `source <code>` entry",
                        source_path,
                        code="E001",
                    )
                )


def _lint_extensions(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    seen_namespaces: set[str] = set()
    for node in doc.select("extension:root"):
        namespace = _node_arg(node, 0) or ""
        if len(node.args) != 1 or not _EXTENSION_NAME_RE.fullmatch(namespace):
            diags.append(
                _error(
                    node,
                    "'extension' requires one portable namespace",
                    source_path,
                    code="E001",
                    hint="example: extension Utils { ... }",
                )
            )
        elif namespace in seen_namespaces:
            diags.append(
                _error(
                    node,
                    f"duplicate extension namespace '{namespace}'",
                    source_path,
                    code="E402",
                )
            )
        seen_namespaces.add(namespace)
        if not node.children:
            diags.append(
                _error(
                    node,
                    f"extension '{namespace}' must declare at least one operation",
                    source_path,
                    code="E001",
                )
            )
        seen_operations: set[str] = set()
        for operation in node.children:
            if (
                not _EXTENSION_NAME_RE.fullmatch(operation.name)
                or operation.args
                or operation.properties
            ):
                diags.append(
                    _error(
                        operation,
                        "extension operation must be a portable child node without entries",
                        source_path,
                        code="E001",
                    )
                )
            if operation.name in seen_operations:
                diags.append(
                    _error(
                        operation,
                        f"duplicate extension operation '{namespace}.{operation.name}'",
                        source_path,
                        code="E402",
                    )
                )
            seen_operations.add(operation.name)
            sigs = [
                child for child in operation.children if child.name == "sig"
            ]
            targets = [
                child
                for child in operation.children
                if child.name in ("go", "js", "py", "rust")
            ]
            unknown = [
                child
                for child in operation.children
                if child.name not in ("go", "js", "py", "rust", "sig")
            ]
            for child in unknown:
                diags.append(
                    _error(
                        child,
                        f"unknown extension operation entry '{child.name}'",
                        source_path,
                        code="E200",
                        hint="valid entries: sig, py, js, go, rust",
                    )
                )
            if len(sigs) != 1 or len(sigs[0].args) != 2:
                diags.append(
                    _error(
                        operation,
                        "extension operation requires exactly one `sig <input> <output>`",
                        source_path,
                        code="E001",
                    )
                )
            else:
                _lint_extension_type(
                    sigs[0].args[0], sigs[0], source_path, diags
                )
                _lint_extension_type(
                    sigs[0].args[1], sigs[0], source_path, diags
                )
                output_name = str(sigs[0].args[1].value).rstrip("?")
                input_name = str(sigs[0].args[0].value).rstrip("?")
                if output_name == "T" and input_name != "T":
                    diags.append(
                        _error(
                            sigs[0],
                            "generic output T must be bound by generic input T",
                            source_path,
                            code="E100",
                        )
                    )
            if not targets:
                diags.append(
                    _error(
                        operation,
                        "extension operation requires at least one target",
                        source_path,
                        code="E001",
                    )
                )
            seen_targets: set[str] = set()
            for target in targets:
                if target.name in seen_targets:
                    diags.append(
                        _error(
                            target,
                            f"duplicate extension target '{target.name}'",
                            source_path,
                            code="E402",
                        )
                    )
                seen_targets.add(target.name)
                _lint_extension_target(target, source_path, diags)


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


def _is_malformed_dotpath(path: str) -> bool:
    if not path:
        return True
    if path.startswith(".") or path.endswith("."):
        return True
    if ".." in path:
        return True
    return any(seg == "" for seg in path.split("."))


def _lint_json_defs(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
    source_text: str = "",
) -> None:
    seen_json_names: set[str] = set()
    declared_json_names: set[str] = set()
    for node in doc.select("json:root"):
        name = _node_arg(node, 0)
        if name:
            seen_json_names.add(name)

    for node in doc.select("json:root"):
        _lint_single_json(
            node,
            source_path,
            diags,
            declared_json_names,
            children_defines,
            source_text,
            seen_json_names_all=seen_json_names,
        )


def _extract_value_model_and_array(
    child: KdlNode,
) -> tuple[str, bool]:
    raw_ann = (child.type_annotation or "").strip("()")
    if raw_ann.endswith("?"):
        raw_ann = raw_ann.rstrip("?")
    is_arr = raw_ann.lower() == "array"
    explicit_model_name = ""
    if raw_ann and raw_ann.lower() != "array":
        explicit_model_name = raw_ann

    for arg in child.args:
        arg_ann = (arg.type_annotation or "").strip("()")
        if arg_ann.lower() == "array":
            is_arr = True
        val_str = str(arg.value)
        if val_str.endswith("?"):
            val_str = val_str.rstrip("?")
        if val_str.startswith("@"):
            continue
        if val_str.lower() in ("array", "(array)"):
            is_arr = True
        elif not explicit_model_name and val_str:
            explicit_model_name = val_str

    return explicit_model_name, is_arr


def _synthesize_value_schema_name(
    explicit_model_name: str,
    explicit_dict_name: str,
    parent_json_name: str,
    field_name: str,
) -> str:
    if explicit_model_name:
        return explicit_model_name
    if explicit_dict_name:
        return f"{explicit_dict_name}Value"
    clean_field = field_name.rstrip("?")
    if parent_json_name and clean_field:
        return f"{parent_json_name}{to_pascal_case(clean_field)}Value"
    if parent_json_name:
        return f"{parent_json_name}Value"
    if clean_field:
        return f"{to_pascal_case(clean_field)}Value"
    return "Value"


def _lint_dict_json_block(
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]] | None = None,
    source_text: str = "",
    seen_json_names: set[str] | None = None,
) -> None:
    seen_directives: set[str] = set()
    has_value = False
    valid_key_types = {"str", "int", "float", "bool"}

    for child in node.children:
        child_name = child.name
        if child_name not in ("@key", "@value"):
            diags.append(
                _error(
                    child,
                    f"unexpected child '{child_name}' in dict schema block; only '@key' and '@value' directives are permitted",
                    source_path,
                    code="E001",
                    hint="use '@value <Type>' and optional '@key <ScalarType>'",
                )
            )
            continue

        if child_name in seen_directives:
            diags.append(
                _error(
                    child,
                    f"duplicate '{child_name}' directive in dict schema block",
                    source_path,
                    code="E001",
                    hint=f"remove duplicate '{child_name}'",
                )
            )
        seen_directives.add(child_name)

        if child_name == "@key":
            if not child.args:
                diags.append(
                    _error(
                        child,
                        "'@key' requires a scalar type ('str', 'int', 'float', 'bool')",
                        source_path,
                        code="E001",
                        hint="example: @key int",
                    )
                )
            else:
                raw_key_type = str(child.args[0].value).rstrip("?")
                is_arr = any(
                    (arg.type_annotation or "").strip("()") == "array"
                    for arg in child.args
                )
                if is_arr or raw_key_type not in valid_key_types:
                    diags.append(
                        _error(
                            child,
                            f"unsupported key type '{raw_key_type}' in '@key'; only scalar types ({', '.join(sorted(valid_key_types))}) are supported",
                            source_path,
                            code="E001",
                            hint=f"valid key types: {', '.join(sorted(valid_key_types))}",
                        )
                    )

        elif child_name == "@value":
            has_value = True
            raw_child = (
                source_text[child.span.start.offset : child.span.end.offset]
                if source_text
                else ""
            )
            has_children = bool(child.children)
            is_empty_block = not has_children and "{" in raw_child

            has_skip = (
                any(str(arg.value) == "@skip" for arg in child.args)
                or (child.type_annotation or "").strip("()") == "@skip"
            )

            explicit_model_name, is_arr = _extract_value_model_and_array(child)

            if is_empty_block:
                diags.append(
                    _error(
                        child,
                        "empty inline json block in '@value'",
                        source_path,
                        code="E001",
                        hint="add fields to inline block or remove empty braces",
                    )
                )

            if has_skip and (has_children or is_empty_block):
                diags.append(
                    _error(
                        child,
                        "cannot use '@skip' on inline json block in '@value'",
                        source_path,
                        code="E002",
                        hint="remove '@skip' from '@value' declaration",
                    )
                )

            if (
                (has_children or is_empty_block)
                and is_arr
                and not explicit_model_name
            ):
                diags.append(
                    _error(
                        child,
                        "inline array block in '@value' requires an item model name",
                        source_path,
                        code="E001",
                        hint="example: (array)@value ItemModel { ... } or @value (array)ItemModel { ... }",
                    )
                )

            if (has_children or is_empty_block) and explicit_model_name:
                if seen_json_names is not None:
                    if explicit_model_name in seen_json_names:
                        diags.append(
                            _error(
                                child,
                                f"duplicate json definition '{explicit_model_name}'",
                                source_path,
                                code="E001",
                                hint=f"rename inline schema '{explicit_model_name}' to avoid collision",
                            )
                        )
                    else:
                        seen_json_names.add(explicit_model_name)

            if not has_children and not is_empty_block:
                if not explicit_model_name:
                    diags.append(
                        _error(
                            child,
                            "'@value' requires a type specification",
                            source_path,
                            code="E001",
                            hint="example: @value (array)str  or  @value Item",
                        )
                    )

            if has_children:
                sub_seen_fields: set[str] = set()
                sub_seen_source_keys: set[str] = set()
                sub_seen_output_keys: set[str] = set()
                sub_field_names: set[str] = {c.name for c in child.children}
                _lint_json_children(
                    list(child.children),
                    source_path,
                    diags,
                    children_defines if children_defines is not None else {},
                    sub_seen_fields,
                    sub_seen_source_keys,
                    sub_seen_output_keys,
                    sub_field_names,
                    source_text,
                    seen_json_names=seen_json_names,
                )

    if not has_value:
        diags.append(
            _error(
                node,
                "dict schema block is missing mandatory '@value' directive",
                source_path,
                code="E001",
                hint="add '@value <Type>' specifying the dictionary value type",
            )
        )


def _lint_single_json(
    node: KdlNode,
    source_path: str,
    diags: list[ReadDiagnostic],
    seen_json_names: set[str],
    children_defines: dict[str, list[KdlNode]],
    source_text: str = "",
    *,
    seen_json_names_all: set[str] | None = None,
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
        elif _is_malformed_dotpath(path_val):
            diags.append(
                _error(
                    node,
                    f"malformed dot-path '{path_val}'",
                    source_path,
                    code="E040",
                    hint='example: json MySchema path="response.data" { ... }',
                )
            )

    raw_ann = node.type_annotation or ""
    type_prop = node.properties.get("type")
    type_prop_val = str(type_prop.value) if type_prop is not None else ""
    is_dict = raw_ann.strip("()") == "dict" or type_prop_val == "dict"
    if is_dict:
        _lint_dict_json_block(
            node,
            source_path,
            diags,
            children_defines=children_defines,
            source_text=source_text,
            seen_json_names=seen_json_names_all
            if seen_json_names_all is not None
            else seen_json_names,
        )
        return

    seen_fields: set[str] = set()
    seen_source_keys: set[str] = set()
    seen_output_keys: set[str] = set()
    field_names: set[str] = {child.name for child in node.children}
    _lint_json_children(
        list(node.children),
        source_path,
        diags,
        children_defines,
        seen_fields,
        seen_source_keys,
        seen_output_keys,
        field_names,
        source_text,
        seen_json_names=seen_json_names_all
        if seen_json_names_all is not None
        else seen_json_names,
    )


def _lint_json_children(
    children: list[KdlNode],
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
    seen_fields: set[str],
    seen_source_keys: set[str],
    seen_output_keys: set[str],
    field_names: set[str],
    source_text: str = "",
    seen_json_names: set[str] | None = None,
) -> None:
    def is_quoted(arg_index: int) -> bool:
        if not source_text or arg_index >= len(field_node.args):
            return False
        value = field_node.args[arg_index]
        raw = source_text[value.span.start.offset : value.span.end.offset]
        return raw.startswith(('"', "'"))

    for field_node in children:
        field_name = field_node.name
        clean_field_name = field_name.rstrip("?")
        args = _node_args(field_node)

        # Block define expansion
        if not args and field_name in children_defines:
            _lint_json_children(
                children_defines[field_name],
                source_path,
                diags,
                children_defines,
                seen_fields,
                seen_source_keys,
                seen_output_keys,
                field_names,
                source_text,
                seen_json_names,
            )
            continue

        path_prop = field_node.properties.get("path")
        if path_prop is not None:
            diags.append(
                _warning(
                    field_node,
                    "use 'from' instead of 'path' to specify JSON key alias on fields",
                    source_path,
                    code="W041",
                    hint=f"example: {field_name} ... from={path_prop.value!r}",
                )
            )

        raw_ann = field_node.type_annotation or ""
        type_prop = field_node.properties.get("type")
        type_prop_val = str(type_prop.value) if type_prop is not None else ""
        is_dict_field = (
            raw_ann.strip("()") == "dict"
            or type_prop_val == "dict"
            or any(
                (arg.type_annotation or "").strip("()") == "dict"
                or str(arg.value) == "(dict)"
                for arg in field_node.args
            )
        )

        has_type = False
        has_skip = False
        for index, arg in enumerate(args):
            if arg.startswith("@") and not is_quoted(index):
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

        has_children = bool(field_node.children)
        raw_field = (
            source_text[
                field_node.span.start.offset : field_node.span.end.offset
            ]
            if source_text
            else ""
        )
        is_empty_block = (
            not has_children
            and "{" in raw_field
            and not (not args and field_name in children_defines)
        )

        if is_empty_block:
            diags.append(
                _error(
                    field_node,
                    f"empty inline json block '{field_name}'",
                    source_path,
                    code="E001",
                    hint="add field definitions to the inline block or remove it",
                )
            )

        if has_skip and (has_children or is_empty_block):
            diags.append(
                _error(
                    field_node,
                    f"cannot use '@skip' on inline json block '{field_name}'",
                    source_path,
                    code="E002",
                    hint="remove '@skip' from inline block declaration",
                )
            )

        if is_dict_field:
            has_type = True
            _lint_dict_json_block(
                field_node,
                source_path,
                diags,
                children_defines=children_defines,
                source_text=source_text,
                seen_json_names=seen_json_names,
            )
        elif has_children and len(field_node.children) > 0:
            has_type = True
            is_array = any(
                (arg.type_annotation or "").strip("()") == "array"
                for arg in field_node.args
            )
            value_args = [
                arg
                for arg in args
                if not arg.startswith("@") or is_quoted(args.index(arg))
            ]
            if is_array and not value_args:
                diags.append(
                    _error(
                        field_node,
                        f"inline array block '{field_name}' requires an item model name",
                        source_path,
                        code="E001",
                        hint=f"example: {field_name} (array)ItemModelName {{ ... }}",
                    )
                )
            elif value_args:
                explicit_name = value_args[0].rstrip("?")
                if seen_json_names is not None:
                    if explicit_name in seen_json_names:
                        diags.append(
                            _error(
                                field_node,
                                f"duplicate json definition '{explicit_name}'",
                                source_path,
                                code="E001",
                                hint=f"rename inline schema '{explicit_name}' to avoid collision",
                            )
                        )
                    else:
                        seen_json_names.add(explicit_name)

            sub_seen_fields: set[str] = set()
            sub_seen_source_keys: set[str] = set()
            sub_seen_output_keys: set[str] = set()
            sub_field_names: set[str] = {c.name for c in field_node.children}
            _lint_json_children(
                list(field_node.children),
                source_path,
                diags,
                children_defines,
                sub_seen_fields,
                sub_seen_source_keys,
                sub_seen_output_keys,
                sub_field_names,
                source_text,
                seen_json_names,
            )

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

        if clean_field_name in seen_fields:
            diags.append(
                _error(
                    field_node,
                    f"duplicate json field '{field_name}'",
                    source_path,
                    code="E001",
                    hint=f"remove or rename the duplicate '{field_name}' field",
                )
            )
        seen_fields.add(clean_field_name)
        field_names.add(clean_field_name)
        value_args = [
            arg
            for arg in args
            if not arg.startswith("@") or is_quoted(args.index(arg))
        ]
        positional_alias = (
            value_args[1]
            if len(value_args) > 1
            and not (has_children and len(field_node.children) > 0)
            else ""
        )
        if positional_alias:
            type_repr = value_args[0] if value_args else "str"
            diags.append(
                _warning(
                    field_node,
                    'positional JSON key alias is deprecated, use from="..." instead',
                    source_path,
                    code="W011",
                    hint=f'example: {field_name} {type_repr} from="{positional_alias}"',
                )
            )

        from_prop = field_node.properties.get("from")
        from_val: str | None = None
        if from_prop is not None:
            if not isinstance(from_prop.value, str) or not from_prop.value:
                diags.append(
                    _error(
                        field_node,
                        "'from' property must be a non-empty string",
                        source_path,
                        code="E001",
                        hint=f'example: {field_name} str from="source_key"',
                    )
                )
            else:
                from_val = from_prop.value
                if from_val != from_val.strip():
                    diags.append(
                        _warning(
                            field_node,
                            f"leading or trailing whitespace in 'from' path '{from_val}'",
                            source_path,
                            code="W040",
                            hint=f'remove whitespace: from="{from_val.strip()}"',
                        )
                    )
                if _is_malformed_dotpath(from_val.strip()):
                    diags.append(
                        _error(
                            field_node,
                            f"malformed dot-path '{from_val}'",
                            source_path,
                            code="E040",
                            hint=f'example: {field_name} str from="profile.avatar.url"',
                        )
                    )

            if positional_alias:
                diags.append(
                    _error(
                        field_node,
                        f"cannot specify both positional alias and 'from' property on json field '{field_name}'",
                        source_path,
                        code="E001",
                        hint="remove positional alias and keep 'from=\"...\"' property",
                    )
                )
        elif (
            path_prop is not None
            and isinstance(path_prop.value, str)
            and path_prop.value
        ):
            from_val = path_prop.value

        if from_val is not None:
            source_key = from_val
        elif positional_alias:
            source_key = positional_alias
        else:
            source_key = clean_field_name

        if source_key in seen_source_keys:
            diags.append(
                _error(
                    field_node,
                    f"duplicate json source key '{source_key}'",
                    source_path,
                    code="E041",
                    hint=f"rename or remove one of the fields mapping to '{source_key}'",
                )
            )
        seen_source_keys.add(source_key)
        output_key = clean_field_name
        if source_key != clean_field_name and source_key in field_names - {
            clean_field_name
        }:
            diags.append(
                _error(
                    field_node,
                    f"json alias '{source_key}' conflicts with field name",
                    source_path,
                    code="E041",
                )
            )
        if output_key in seen_output_keys:
            diags.append(
                _error(
                    field_node,
                    f"duplicate json output key '{output_key}'",
                    source_path,
                    code="E001",
                )
            )
        seen_output_keys.add(output_key)


def _lint_structs(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    seen_names: set[str] = set()
    for node in doc.select("struct:root"):
        name = _node_arg(node, 0)
        if name and name in seen_names:
            diags.append(
                _error(
                    node,
                    f"duplicate struct definition '{name}'",
                    source_path,
                    code="E402",
                    hint=f"remove or rename duplicate struct '{name}'",
                )
            )
        if name:
            seen_names.add(name)
        _lint_single_struct(node, source_path, diags, children_defines)


# Directives allowed inside ``fn`` / ``(raw)fn`` body.
_FN_ALLOWED_RESERVED: frozenset[str] = frozenset({"@doc"})


def _lint_fns(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    """Structural lint for ``fn`` / ``(raw)fn`` directives."""
    seen_names: set[str] = set()
    for node in doc.select("fn:root"):
        name = _node_arg(node, 0)
        if not name:
            diags.append(
                _error(
                    node,
                    "'fn' requires a name",
                    source_path,
                    code="E001",
                    hint='example: fn page_title { css "h1" { text } }',
                )
            )
            continue
        if name in seen_names:
            diags.append(
                _error(
                    node,
                    f"duplicate fn definition '{name}'",
                    source_path,
                    code="E402",
                    hint=f"remove or rename duplicate fn '{name}'",
                )
            )
        seen_names.add(name)

        annotation = node.type_annotation
        if annotation and annotation != "(raw)":
            diags.append(
                _error(
                    node,
                    f"unsupported fn annotation '{annotation}' — only '(raw)' is recognized",
                    source_path,
                    code="E400",
                    hint="use 'fn { ... }' (HTML) or '(raw)fn { ... }' (plain text)",
                )
            )

        ops = list(node.children)
        if not ops:
            diags.append(
                _error(
                    node,
                    f"fn '{name}' must contain at least one pipeline operation",
                    source_path,
                    code="E001",
                    hint='example: fn title { css "h1" { text } }',
                )
            )

        for child in ops:
            if (
                child.name.startswith("@")
                and child.name not in _FN_ALLOWED_RESERVED
            ):
                diags.append(
                    _error(
                        child,
                        f"'{child.name}' is not allowed inside fn — use a struct for init/check/request/etc.",
                        source_path,
                        code="E203",
                    )
                )


def _lint_nested_topdown(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
) -> None:
    """Enforce top-down declaration order for `nested` refs (current file only).

    Emits:
      E300 — ``nested X`` references a struct ``X`` that is not declared at all
      E302 — ``nested X`` references a struct ``X`` declared BELOW the caller
             (top-down ordering is required: helpers first, entrypoint last)
    """
    structs = list(doc.select("struct:root"))
    # Pre-compute declaration order — O(1) position comparison later.
    order: dict[str, int] = {}
    for idx, s in enumerate(structs):
        name = _node_arg(s, 0)
        if name:
            order[name] = idx

    # Only inspect structs that actually use `nested`.
    for caller in doc.select("struct:root:has(nested)"):
        caller_name = _node_arg(caller, 0) or "<unnamed>"
        caller_idx = order.get(caller_name, -1)
        for nested_op in caller.select("nested"):
            target = _node_arg(nested_op, 0)
            if not target:
                continue  # arg-count error already emitted inline
            if target not in order:
                # Imported and genuinely missing refs are distinguished after
                # imports are flattened by lint_cross_refs().
                continue
            if order[target] > caller_idx:
                diags.append(
                    _error(
                        nested_op,
                        f"'nested {target}': struct '{target}' must be declared BEFORE use (top-down order)",
                        source_path,
                        code="E302",
                        hint=f"move 'struct {target} {{ ... }}' above 'struct {caller_name}'",
                    )
                )


def _lint_json_refs_topdown(
    doc: KdlDocument,
    source_path: str,
    diags: list[ReadDiagnostic],
    children_defines: dict[str, list[KdlNode]],
) -> None:
    """Enforce top-down declaration order for json field type refs.

    A json field whose type is not a primitive (str/int/float/bool/null/nil)
    references another ``json`` definition. That target must be declared in
    the same file, BEFORE the referencing json def (helpers first,
    entrypoint last) — mirrors the ``nested`` top-down rule.

    Emits:
      E302 — json field references a json def declared BELOW the caller

    Refs not in the local order map are skipped: imported defs are resolved
    cross-file, and genuinely undefined refs are reported (E300) by
    :func:`lint_cross_refs`.
    """
    json_nodes = list(doc.select("json:root"))
    order: dict[str, int] = {}
    for idx, j in enumerate(json_nodes):
        name = _node_arg(j, 0)
        if name:
            order[name] = idx

    for caller in json_nodes:
        caller_name = _node_arg(caller, 0)
        if not caller_name:
            continue
        caller_idx = order.get(caller_name, -1)
        for field_node, ref_name in _iter_json_field_type_refs(
            caller, children_defines
        ):
            if ref_name not in order:
                continue  # imported or undefined — handled by lint_cross_refs
            if order[ref_name] > caller_idx:
                diags.append(
                    _error(
                        field_node,
                        f"json field '{field_node.name}': json type '{ref_name}' must be declared BEFORE use (top-down order)",
                        source_path,
                        code="E302",
                        hint=f"move 'json {ref_name} {{ ... }}' above 'json {caller_name}'",
                    )
                )


def _iter_json_field_type_refs(
    json_node: KdlNode,
    children_defines: dict[str, list[KdlNode]],
) -> Iterator[tuple[KdlNode, str]]:
    """Yield ``(field_node, ref_name)`` for each non-primitive json field type.

    Expands block defines (bare field name → recursive field list) to match
    ``parse_json_fields`` semantics.
    """
    queue: list[KdlNode] = list(json_node.children)
    while queue:
        field_node = queue.pop(0)
        args = _node_args(field_node)
        if not args and field_node.name in children_defines:
            queue = list(children_defines[field_node.name]) + queue
            continue

        if field_node.children:
            raw_ann = field_node.type_annotation or ""
            type_prop = field_node.properties.get("type")
            type_prop_val = (
                str(type_prop.value) if type_prop is not None else ""
            )
            is_dict = (
                raw_ann.strip("()") == "dict"
                or type_prop_val == "dict"
                or any(
                    (arg.type_annotation or "").strip("()") == "dict"
                    or str(arg.value) == "(dict)"
                    for arg in field_node.args
                )
            )
            if is_dict:
                for c in field_node.children:
                    if c.name == "@value":
                        if c.children:
                            queue = list(c.children) + queue
                        else:
                            explicit_model, _ = _extract_value_model_and_array(
                                c
                            )
                            if (
                                explicit_model
                                and explicit_model not in _VALID_JSON_TYPES
                            ):
                                yield c, explicit_model
            else:
                queue = list(field_node.children) + queue
            continue

        if field_node.name == "@value":
            if field_node.children:
                queue = list(field_node.children) + queue
            else:
                explicit_model, _ = _extract_value_model_and_array(field_node)
                if explicit_model and explicit_model not in _VALID_JSON_TYPES:
                    yield field_node, explicit_model
            continue

        type_ = ""
        for a in args:
            if a.startswith("@"):
                continue
            type_ = a
            break
        if not type_:
            continue
        if type_.startswith("(array)"):
            type_ = type_[len("(array)") :]
        if type_.endswith("?"):
            type_ = type_[:-1]
        if type_ and type_ not in _VALID_JSON_TYPES:
            yield field_node, type_


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
                hint = (
                    REQUEST_LINE_CONTINUATION_HINT
                    if field_name.startswith(HTTP_REQUEST_SIGNATURES)
                    else ""
                )
                diags.append(
                    _error(
                        field_node,
                        f"regular field '{field_name}' not allowed in struct type='rest'",
                        source_path,
                        code="E203",
                        hint=hint,
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
        try:
            status = int(err_args[0])
        except ValueError:
            status = None
        if status is not None and not is_http_status(status):
            diags.append(
                _error(
                    node,
                    f"@error status must be in HTTP range 100..599, got {status}",
                    source_path,
                    code="E002",
                    hint="use an HTTP status code from 100 through 599",
                )
            )
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
        spec = PlaceholderSpec.parse(token)
        if spec is None:
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
        name = spec.name
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
        hint = (
            REQUEST_LINE_CONTINUATION_HINT
            if field_name.startswith(HTTP_REQUEST_SIGNATURES)
            else f'add at least one operation: {field_name} {{ css ".item"; text }}'
        )
        diags.append(
            _error(
                field_node,
                f"field '{field_name}' has no operations",
                source_path,
                code="E001",
                hint=hint,
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
    nodes: list[KdlNode],
    source_path: str = "",
    *,
    node_source_paths: Mapping[int, object] | None = None,
    targets: Iterable[str] | None = None,
) -> list[ReadDiagnostic]:
    """Execute cross-reference validation and multi-target symbol collision checks.

    Operates on the flattened list of top-level nodes after import graph resolution.
    Validates:
    - `@request response="..."` references exist in declared JSON schemas (`E300`).
    - `@error ... <Schema>` references exist in declared JSON schemas (`E300`).
    - `nested <Struct>` references exist in declared struct definitions (`E300`).
    - JSON field type references exist and do not form circular reference cycles (`E300`).
    - Target symbol collisions (`E402`) and invalid target identifiers (`E403`) across Python, JS, Go.

    Args:
        nodes: Merged flat list of KDL nodes (root file plus imported definitions).
        source_path: Fallback path to the root document.
        node_source_paths: Mapping of node object IDs to originating file paths.
        targets: Target languages to validate generated symbols against.

    Returns:
        List of collected `ReadDiagnostic` records.
    """
    diags: list[ReadDiagnostic] = []
    json_names: set[str] = set()
    json_field_refs: list[tuple[KdlNode, str, str, str]] = []
    rest_response_refs: list[tuple[KdlNode, str]] = []
    rest_error_refs: list[tuple[KdlNode, str]] = []
    json_nodes: dict[str, KdlNode] = {}
    struct_names: set[str] = set()
    nested_refs: list[tuple[KdlNode, str]] = []

    def source_for(node: KdlNode) -> str:
        if node_source_paths is None:
            return source_path
        return str(node_source_paths.get(id(node), source_path))

    for node in nodes:
        if node.name == "json":
            name = _node_arg(node, 0)
            if name:
                json_names.add(name)
                json_nodes[name] = node
            for field_node in node.children:
                _collect_json_field_refs(
                    field_node,
                    name or "",
                    json_field_refs,
                    json_names,
                    json_nodes,
                )
        elif node.name == "struct":
            struct_name = _node_arg(node, 0)
            if struct_name:
                struct_names.add(struct_name)
            for nested in node.select("nested"):
                target = _node_arg(nested, 0)
                if target:
                    nested_refs.append((nested, target))
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
                    source_for(req_node),
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
                    source_for(err_node),
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
                    source_for(field_node),
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
                        source_for(kdl_node),
                        code="E300",
                        hint="break the cycle by removing or changing one of the referenced types",
                    )
                )
            break

    for nested_node, target in nested_refs:
        if target not in struct_names:
            diags.append(
                _error(
                    nested_node,
                    f"'nested {target}' references undefined struct '{target}'",
                    source_for(nested_node),
                    code="E300",
                    hint=f"declare 'struct {target} {{ ... }}' before use",
                )
            )

    _lint_generated_symbols(nodes, diags, source_for, targets=targets)

    return diags


def _is_valid_generated_identifier(target: str, name: str) -> bool:
    return is_valid_symbol(target, name)


def _lint_generated_symbols(
    nodes: list[KdlNode],
    diags: list[ReadDiagnostic],
    source_for,
    *,
    targets: Iterable[str] | None = None,
) -> None:
    requested = normalize_targets(targets)
    _lint_placeholder_specifications(nodes, diags, source_for)
    records = _collect_symbol_records(nodes, requested, source_for)
    for finding in target_symbol_plan(records, requested):
        declaration = finding.record.declaration
        if declaration is not None:
            diags.append(
                _error(
                    declaration,
                    finding.message,
                    source_for(declaration),
                    code=finding.code,
                    hint=finding.hint,
                )
            )


def _lint_placeholder_specifications(
    nodes: list[KdlNode], diags: list[ReadDiagnostic], source_for
) -> None:
    """Reject one request parameter being declared with different specs."""
    for struct in nodes:
        if struct.name != "struct":
            continue
        for request in struct.select("@request"):
            seen: dict[str, PlaceholderSpec] = {}
            payload = str(request.args[0].value) if request.args else ""
            for match in PLACEHOLDER_WIDE_RE.finditer(payload):
                spec = PlaceholderSpec.parse(match.group(0))
                if spec is None:
                    continue
                previous = seen.get(spec.name)
                if previous is not None and previous != spec:
                    diags.append(
                        _error(
                            request,
                            f"placeholder '{spec.name}' uses conflicting type/style declarations",
                            source_for(request),
                            code="E402",
                            hint="use one placeholder specification consistently",
                        )
                    )
                else:
                    seen[spec.name] = spec


def _collect_symbol_records(
    nodes: list[KdlNode], targets: tuple[str, ...], source_for
) -> tuple[SymbolRecord, ...]:
    """Normalize CST declarations before handing them to symbol policy."""
    records: list[SymbolRecord] = []

    def add(
        node: KdlNode, kind: SymbolKind, raw: str, scope: SymbolScope
    ) -> None:
        for target in targets:
            for symbol in top_symbol_names(kind, raw, target):
                records.append(
                    SymbolRecord(
                        kind,
                        raw,
                        target,
                        symbol,
                        scope,
                        source_for(node),
                        node.span,
                        node,
                    )
                )

    for index, node in enumerate(nodes):
        raw = _node_arg(node, 0)
        if not raw:
            continue
        if node.name == "struct":
            add(node, SymbolKind.STRUCT, raw, SymbolScope.MODULE)
            local_source = f"{source_for(node)}#{index}"
            if (node.type_annotation or "").strip(
                "()"
            ) != "rest" and node.get_prop("type") != "rest":
                for target in targets:
                    records.append(
                        SymbolRecord(
                            SymbolKind.TYPE,
                            raw,
                            target,
                            top_symbol_names(SymbolKind.STRUCT, raw, target)[1],
                            SymbolScope.MODULE,
                            source_for(node),
                            node.span,
                            node,
                        )
                    )
            for child_index, child in enumerate(node.children):
                if not child.name.startswith("@"):
                    for target in targets:
                        records.append(
                            SymbolRecord(
                                SymbolKind.FIELD,
                                child.name,
                                target,
                                local_symbol(
                                    SymbolKind.FIELD, child.name, target
                                ),
                                SymbolScope.STRUCT,
                                local_source,
                                child.span,
                                child,
                            )
                        )
                elif child.name == "@request":
                    name = str(child.get_prop("name") or "fetch")
                    for target in targets:
                        records.append(
                            SymbolRecord(
                                SymbolKind.METHOD,
                                name,
                                target,
                                local_symbol(SymbolKind.METHOD, name, target),
                                SymbolScope.METHOD,
                                local_source,
                                child.span,
                                child,
                            )
                        )
                    payload = str(child.args[0].value) if child.args else ""
                    request_source = f"{local_source}#req#{child_index}"
                    seen_placeholders: set[str] = set()
                    for match in PLACEHOLDER_WIDE_RE.finditer(payload):
                        spec = PlaceholderSpec.parse(match.group(0))
                        if spec and spec.name not in seen_placeholders:
                            seen_placeholders.add(spec.name)
                            for target in targets:
                                records.append(
                                    SymbolRecord(
                                        SymbolKind.PLACEHOLDER,
                                        spec.name,
                                        target,
                                        local_symbol(
                                            SymbolKind.PLACEHOLDER,
                                            spec.name,
                                            target,
                                        ),
                                        SymbolScope.PLACEHOLDER,
                                        request_source,
                                        child.span,
                                        child,
                                    )
                                )
                elif child.name == "@check" and child.args:
                    name = str(child.args[0].value)
                    for target in targets:
                        records.append(
                            SymbolRecord(
                                SymbolKind.METHOD,
                                name,
                                target,
                                local_symbol(SymbolKind.METHOD, name, target),
                                SymbolScope.METHOD,
                                local_source,
                                child.span,
                                child,
                            )
                        )
                elif child.name == "@init":
                    for field in child.children:
                        for target in targets:
                            records.append(
                                SymbolRecord(
                                    SymbolKind.INIT,
                                    field.name,
                                    target,
                                    local_symbol(
                                        SymbolKind.INIT, field.name, target
                                    ),
                                    SymbolScope.STRUCT,
                                    local_source,
                                    field.span,
                                    field,
                                )
                            )
        elif node.name == "json":
            add(node, SymbolKind.JSON, raw, SymbolScope.MODULE)
        elif node.name == "fn":
            add(node, SymbolKind.FUNCTION, raw, SymbolScope.MODULE)
    return tuple(records)


def _collect_json_field_refs(
    field_node: KdlNode,
    parent_json_name: str,
    refs: list[tuple[KdlNode, str, str, str]],
    json_names: set[str],
    json_nodes: dict[str, KdlNode],
) -> None:
    field_name = field_node.name
    raw_ann = field_node.type_annotation or ""
    type_prop = field_node.properties.get("type")
    type_prop_val = str(type_prop.value) if type_prop is not None else ""
    is_dict = (
        raw_ann.strip("()").rstrip("?") == "dict"
        or type_prop_val == "dict"
        or any(
            (arg.type_annotation or "").strip("()").rstrip("?") == "dict"
            or str(arg.value).rstrip("?") == "(dict)"
            for arg in field_node.args
        )
    )

    if field_node.name == "@value":
        explicit_model_name, is_arr = _extract_value_model_and_array(field_node)
        if field_node.children:
            child_schema_name = _synthesize_value_schema_name(
                explicit_model_name,
                explicit_dict_name="",
                parent_json_name=parent_json_name,
                field_name="",
            )
            json_names.add(child_schema_name)
            json_nodes[child_schema_name] = field_node
            refs.append(
                (field_node, field_name, child_schema_name, parent_json_name)
            )
            for sub_child in field_node.children:
                _collect_json_field_refs(
                    sub_child,
                    child_schema_name,
                    refs,
                    json_names,
                    json_nodes,
                )
        else:
            val_arg = explicit_model_name
            if val_arg and val_arg not in _VALID_JSON_TYPES:
                refs.append((field_node, field_name, val_arg, parent_json_name))
        return

    if field_node.children:
        if is_dict:
            explicit_dict_name = ""
            for arg in field_node.args:
                a = str(arg.value)
                if a in {"@skip", "@omitempty"} or a.startswith("@"):
                    continue
                if a not in {"(dict)", "dict"}:
                    if a.endswith("?"):
                        a = a.rstrip("?")
                    if a:
                        explicit_dict_name = a
                        break

            for child in field_node.children:
                if child.name == "@value":
                    explicit_model_name, is_arr = (
                        _extract_value_model_and_array(child)
                    )
                    if child.children:
                        child_schema_name = _synthesize_value_schema_name(
                            explicit_model_name,
                            explicit_dict_name,
                            parent_json_name,
                            field_name,
                        )
                        json_names.add(child_schema_name)
                        json_nodes[child_schema_name] = child
                        refs.append(
                            (
                                child,
                                field_name,
                                child_schema_name,
                                parent_json_name,
                            )
                        )
                        for sub_child in child.children:
                            _collect_json_field_refs(
                                sub_child,
                                child_schema_name,
                                refs,
                                json_names,
                                json_nodes,
                            )
                    else:
                        val_arg = explicit_model_name
                        if val_arg and val_arg not in _VALID_JSON_TYPES:
                            refs.append(
                                (child, field_name, val_arg, parent_json_name)
                            )
            return

        # Inline block
        args = _node_args(field_node)
        type_args = [arg for arg in args if not arg.startswith("@")]
        if type_args:
            raw_type = type_args[0]
            if raw_type.startswith("(array)"):
                raw_type = raw_type[len("(array)") :]
            if raw_type.endswith("?"):
                raw_type = raw_type[:-1]
            child_schema_name = raw_type
        else:
            clean_field = field_name.rstrip("?")
            child_schema_name = (
                f"{parent_json_name}{to_pascal_case(clean_field)}"
            )

        json_names.add(child_schema_name)
        json_nodes[child_schema_name] = field_node
        refs.append(
            (field_node, field_name, child_schema_name, parent_json_name)
        )

        for child in field_node.children:
            _collect_json_field_refs(
                child, child_schema_name, refs, json_names, json_nodes
            )
        return

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
    """Validate positional argument counts on a KDL node.

    Args:
        node: The node being validated.
        lint: Lint context for recording error diagnostics.
        exact: Optional exact required argument count.
        min_count: Optional minimum required argument count.
        max_count: Optional maximum allowed argument count.
        example: Optional usage example shown in diagnostic hints.

    Returns:
        List of stringified arguments if validation passes, or `None` on error.
    """
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
    """Validate that all provided argument strings are valid integers.

    Args:
        node: The node being checked.
        lint: Lint context for reporting errors (`E001`).
        args: List of argument strings to parse.

    Returns:
        `True` if all arguments parse as integers, otherwise `False`.
    """
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
    """Validate Python/PCRE regex syntax at compile time.

    Args:
        node: The originating KDL node.
        lint: Lint context for reporting regex syntax errors (`E002`).
        pattern: The raw regex pattern string to validate.

    Returns:
        `True` if valid regex syntax, otherwise `False`.
    """
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
    """Validate CSS selector syntax using soupsieve parser.

    Args:
        node: The originating KDL node.
        lint: Lint context for reporting CSS syntax errors (`E002`).
        selector: The CSS selector query string to validate.

    Returns:
        `True` if valid CSS selector, otherwise `False`.
    """
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
    """Validate XPath expression syntax using lxml parser.

    Args:
        node: The originating KDL node.
        lint: Lint context for reporting XPath syntax errors (`E002`).
        expr: The XPath query string to validate.

    Returns:
        `True` if valid XPath expression, otherwise `False`.
    """
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
    """Enforce that the current node is placed inside a predicate container.

    Args:
        node: The predicate node being checked.
        lint: Lint context tracking predicate nesting depth.

    Returns:
        `True` if inside a predicate context, otherwise reports `E203` and returns `False`.
    """
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
    """Enforce that the current node is placed inside an `assert` block.

    Args:
        node: The node being checked.
        lint: Lint context tracking assert block context.

    Returns:
        `True` if inside an assert block, otherwise reports `E203` and returns `False`.
    """
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
    """Perform syntactic and argument-level linting on an individual pipeline operation node.

    Args:
        node: The pipeline operation KDL node being validated.
        lint: Lint context for recording validation diagnostics (`E001`, `E002`, `E203`, `E301`).
    """
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

    elif name == "raw":
        args = _node_args(node)
        if len(args) > 1:
            lint.error(
                node,
                message="'raw' accepts at most 1 argument",
                code="E001",
                hint="example: raw  or  raw outer  or  raw inner",
            )
        elif args and args[0] not in ("outer", "inner"):
            lint.error(
                node,
                message=(
                    f"invalid 'raw' mode {args[0]!r}"
                    " — expected 'outer' or 'inner'"
                ),
                code="E001",
                hint="example: raw  or  raw outer  or  raw inner",
            )

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
        raw_args = node.args
        args = lint_require_args(  # type: ignore[assignment]
            node, lint, exact=1, example='re-all #"(\\d+)"#'
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
        path_prop = node.properties.get("path")
        if path_prop is not None:
            path_val = str(path_prop.value)
            if not path_val:
                lint.error(
                    node,
                    message="'path' property must be a non-empty string",
                    code="E002",
                    hint='example: jsonify MySchema path="response.data"',
                )
            elif _is_malformed_dotpath(path_val.strip()):
                lint.error(
                    node,
                    message=f"malformed dot-path '{path_val}'",
                    code="E040",
                    hint='example: jsonify MySchema path="response.data"',
                )

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
        if name == "assert":
            # assert accepts an optional string message arg:
            # assert { ... }                  # default
            # assert "expected non-empty" { ... }
            if len(node.args) > 1:
                lint.error(
                    node,
                    message="'assert' accepts at most one argument",
                    code="E001",
                    hint='example: assert "msg" { ... }  or  assert { ... }',
                )
            elif node.args:
                arg_val = node.args[0].value
                if not isinstance(arg_val, str):
                    lint.error(
                        node,
                        message="'assert' message argument must be a string",
                        code="E001",
                        hint='example: assert "expected non-empty" { ... }',
                    )
        elif node.args:
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
    """Validate argument count, regex patterns, and context constraints for a predicate operation.

    Args:
        node: The predicate operation KDL node (e.g. `eq`, `contains`, `attr-re`, `len-gt`).
        lint: Lint context for recording predicate diagnostics.
    """
    name = node.name

    if name in ("eq", "ne"):
        if not lint_require_predicate_ctx(node, lint):
            return
        lint_require_args(node, lint, min_count=1, example=f'{name} "value"')

    elif name in ("starts", "ends", "contains"):
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


def lint_wildcard_op(
    node: KdlNode, ctx: ParseContext, lint: LintContext
) -> None:
    """Validate unrecognized or dynamic operations appearing within a pipeline context.

    Distinguishes `@init` references, un-prefixed extensions, scalar defines,
    and provides fuzzy-matching spelling suggestions for typos (`E200`).

    Args:
        node: The unrecognized KDL node.
        ctx: Global parse context containing registered extensions and defines.
        lint: Lint context for recording error diagnostics.
    """
    from ssc_codegen.core.type_checking import BUILTIN_PIPELINE_OPS

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

    if op_name in ctx.extensions:
        lint.error(
            node,
            message=f"custom operation '{op_name}' requires the '!' prefix",
            code="E001",
            hint=f"use '!{op_name}'",
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
        BUILTIN_PIPELINE_OPS | _EXTRA_PIPELINE_OPS | _PREDICATE_OPS
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
