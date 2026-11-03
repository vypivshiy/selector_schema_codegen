"""Browser playground bridge for schema validation and multi-target code generation.

Provides JSON-serializable handlers used by the Pyodide WebWorker in `/playground/`
to validate KDL v2.1 schemas, inspect declared structs, and emit target source files
across Python, JavaScript, Go, and Rust.
"""

from __future__ import annotations

import json
import re
import sys
import time
import types
from collections.abc import Mapping
from typing import Any

from kdlquery import KdlNode, KDLParseError, ReadDiagnostic, Severity
from kdlquery import parse as kdl_parse
from kdlquery.types import Position, Span

from ssc_codegen.ast import Nested, StructBase, StructRest, StructType
from ssc_codegen.core.format import diagnostic_to_dict
from ssc_codegen.core.reader import parse_module
from ssc_codegen.exceptions import BuildTimeError, ParseError
from ssc_codegen.generation.runtime import register_runtime_file
from ssc_codegen.health import check_struct_health
from ssc_codegen.naming import to_pascal_case
from ssc_codegen.targets.golang.visitor import GoVisitor
from ssc_codegen.targets.python.visitor import PythonVisitor
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.rust.visitor import RustVisitor
from ssc_codegen.targets.spec import TargetSpec

__all__ = ["compile_and_lint", "test_html"]

_TOP_IMPORT_LINE_RE = re.compile(r"^(\s*)(imports?)(?=\s|\{|$)")

_VALID_STRUCT_TYPES: frozenset[str] = frozenset(
    {"item", "list", "table", "dict", "flat", "raw", "rest"}
)

_STRING_ARG_OPS: dict[str, str] = {
    "trim": 'example: trim  or  trim "chars"',
    "ltrim": 'example: ltrim  or  ltrim "chars"',
    "rtrim": 'example: rtrim  or  rtrim "chars"',
    "rm-prefix": 'example: rm-prefix "substring"',
    "rm-suffix": 'example: rm-suffix "substring"',
    "rm-prefix-suffix": 'example: rm-prefix-suffix "substring"',
    "fmt": 'example: fmt "prefix-{{}}-suffix"',
    "repl": 'example: repl "old" "new"',
    "split": 'example: split " "',
    "join": 'example: join " "',
    "re": 'example: re #"(\\d+)"#',
    "re-all": 'example: re-all #"(\\d+)"#',
    "re-sub": 'example: re-sub #"\\D"# ""',
    "attr": 'example: attr "href"',
    "css": 'example: css ".selector"',
    "css-all": 'example: css-all ".selector"',
    "css-remove": 'example: css-remove ".selector"',
    "xpath": 'example: xpath "//div"',
    "xpath-all": 'example: xpath-all "//div"',
    "xpath-remove": 'example: xpath-remove "//div"',
    "starts": 'example: starts "value"',
    "ends": 'example: ends "value"',
    "contains": 'example: contains "value"',
    "has-attr": 'example: has-attr "href"',
    "attr-starts": 'example: attr-starts "href" "value"',
    "attr-ends": 'example: attr-ends "href" "value"',
    "attr-contains": 'example: attr-contains "href" "value"',
    "attr-re": 'example: attr-re "href" #".*\\.com$"#',
    "text-re": 'example: text-re #"\\d+"#',
    "text-starts": 'example: text-starts "value"',
    "text-ends": 'example: text-ends "value"',
    "text-contains": 'example: text-contains "value"',
    "re-any": 'example: re-any #"\\d+"#',
}


def _scan_non_string_op_arg_errors(
    nodes: list[KdlNode],
) -> list[ReadDiagnostic]:
    """Detect non-string arguments passed to string pipeline/predicate ops in the CST."""
    errors: list[ReadDiagnostic] = []
    for top in nodes:
        if top.name not in ("struct", "fn", "define"):
            continue
        for desc in top.iter_descendants():
            hint = _STRING_ARG_OPS.get(desc.name)
            if hint is None or not desc.args:
                continue
            for arg in desc.args:
                val = arg.value
                if not isinstance(val, str):
                    val_type = "null" if val is None else type(val).__name__
                    errors.append(
                        ReadDiagnostic(
                            message=(
                                f"'{desc.name}' argument must be a string, "
                                f"got {val_type}"
                            ),
                            severity=Severity.ERROR,
                            span=desc.span,
                            path="",
                            hint=hint,
                            code="E001",
                            label="invalid argument type",
                        )
                    )
                    break
    return errors


def _mask_span(text: str, start_offset: int, end_offset: int) -> str:
    """Replace characters in `[start_offset, end_offset)` with spaces while keeping newlines."""
    start = max(0, min(start_offset, len(text)))
    end = max(start, min(end_offset, len(text)))
    segment = text[start:end]
    masked = "".join(ch if ch in ("\r", "\n") else " " for ch in segment)
    return text[:start] + masked + text[end:]


def _extract_cst_structs(nodes: list[KdlNode]) -> list[dict[str, Any]]:
    """Extract declared struct descriptors from top-level CST nodes as a fallback."""
    structs: list[dict[str, Any]] = []
    seen: set[str] = set()
    ref_map: dict[str, list[str]] = {}
    for node in nodes:
        if node.name != "struct" or not node.args:
            continue
        parent_name = str(node.args[0].value)
        if not parent_name:
            continue
        for desc in node.iter_descendants():
            if desc.name == "nested" and desc.args:
                target_name = str(desc.args[0].value)
                parents = ref_map.setdefault(target_name, [])
                if parent_name not in parents:
                    parents.append(parent_name)

    for node in nodes:
        if node.name != "struct" or not node.args:
            continue
        name = str(node.args[0].value)
        if not name or name in seen:
            continue
        raw_ann = node.type_annotation
        struct_type = (
            raw_ann[1:-1] if raw_ann else str(node.get_prop("type") or "item")
        )
        if struct_type not in _VALID_STRUCT_TYPES:
            struct_type = "item"
        seen.add(name)
        structs.append(
            {
                "name": name,
                "class_name": to_pascal_case(name),
                "type": struct_type,
                "is_rest": struct_type == "rest",
                "referenced_by": ref_map.get(name, []),
            }
        )
    return structs


def _collect_ast_nested_refs(
    struct_nodes: list[StructBase],
) -> dict[str, list[str]]:
    """Map each struct name to the list of parent struct names that reference it via `nested`."""
    ref_map: dict[str, list[str]] = {}

    def _walk_body(parent_name: str, body: list[Any]) -> None:
        for item in body:
            if isinstance(item, Nested) and item.struct_name:
                parents = ref_map.setdefault(item.struct_name, [])
                if parent_name not in parents:
                    parents.append(parent_name)
            child_body = getattr(item, "body", None)
            if isinstance(child_body, list):
                _walk_body(parent_name, child_body)

    for s in struct_nodes:
        _walk_body(s.name, list(getattr(s, "body", [])))
    return ref_map


def _serialize_diagnostic(diag: ReadDiagnostic) -> dict[str, Any]:
    """Convert a `ReadDiagnostic` into a dictionary with guaranteed 1-based spans."""
    start = diag.span.start
    end = diag.span.end
    norm_start = Position(
        offset=max(start.offset, 0),
        line=max(start.line, 1),
        column=max(start.column, 1),
    )
    norm_end = Position(
        offset=max(end.offset, norm_start.offset),
        line=max(end.line, norm_start.line),
        column=max(end.column, 1),
    )
    normalized = ReadDiagnostic(
        message=diag.message,
        severity=diag.severity,
        span=Span(start=norm_start, end=norm_end),
        path=diag.path,
        hint=diag.hint,
        code=diag.code,
        label=diag.label,
        notes=tuple(diag.notes),
    )
    return diagnostic_to_dict(normalized)


def _resolve_lint_targets(
    raw_lang: str, resolved_language: str | None
) -> tuple[str, ...] | None:
    """Determine target language names to pass to `parse_module` symbol checks."""
    if resolved_language is not None:
        return (resolved_language,)
    alias_map = {
        "python": "python",
        "py": "python",
        "javascript": "javascript",
        "js": "javascript",
        "go": "go",
        "rust": "rust",
    }
    mapped = alias_map.get(raw_lang)
    return (mapped,) if mapped is not None else None


def _is_rest_struct(struct: StructBase) -> bool:
    """Return True if the struct is a `(rest)struct`."""
    return isinstance(struct, StructRest) or struct.type == StructType.REST


def _scan_fallback_import_warnings(kdl_src: str) -> list[ReadDiagnostic]:
    """Scan raw source lines for top-level `import`/`imports` when CST parsing fails."""
    warnings: list[ReadDiagnostic] = []
    offset = 0
    for line_no, raw_line in enumerate(
        kdl_src.splitlines(keepends=True), start=1
    ):
        match = _TOP_IMPORT_LINE_RE.match(raw_line)
        if match is not None:
            indent, keyword = match.group(1), match.group(2)
            col_start = len(indent) + 1
            line_body = raw_line.rstrip("\r\n")
            col_end = max(len(line_body) + 1, col_start + len(keyword))
            start_pos = Position(
                offset=offset + len(indent),
                line=line_no,
                column=col_start,
            )
            end_pos = Position(
                offset=offset + len(line_body),
                line=line_no,
                column=col_end,
            )
            warnings.append(
                ReadDiagnostic(
                    message=(
                        f"External file imports ('{keyword}') are not supported "
                        "in the single-buffer browser playground."
                    ),
                    severity=Severity.WARNING,
                    span=Span(start=start_pos, end=end_pos),
                    path="",
                    hint="Inline shared definitions directly into the active schema buffer.",
                    code="W003",
                    label="unsupported in single-buffer playground",
                )
            )
        offset += len(raw_line)
    return warnings


def _prepare_source_for_parse(
    kdl_src: str,
) -> tuple[str, list[ReadDiagnostic], list[dict[str, Any]]]:
    """Mask external `import`/`imports` nodes and collect pre-parse CST diagnostics."""
    source_for_parse = kdl_src
    extra_diagnostics: list[ReadDiagnostic] = []
    fallback_structs: list[dict[str, Any]] = []

    try:
        doc = kdl_parse(kdl_src)
        top_nodes = list(doc.nodes)
        fallback_structs = _extract_cst_structs(top_nodes)
        for node in top_nodes:
            if node.name in ("import", "imports"):
                extra_diagnostics.append(
                    ReadDiagnostic(
                        message=(
                            f"External file imports ('{node.name}') are not supported "
                            "in the single-buffer browser playground."
                        ),
                        severity=Severity.WARNING,
                        span=node.span,
                        path="",
                        hint="Inline shared definitions directly into the active schema buffer.",
                        code="W003",
                        label="unsupported in single-buffer playground",
                    )
                )
                source_for_parse = _mask_span(
                    source_for_parse,
                    node.span.start.offset,
                    node.span.end.offset,
                )
        extra_diagnostics.extend(_scan_non_string_op_arg_errors(top_nodes))
    except KDLParseError:
        source_for_parse = kdl_src
        extra_diagnostics = _scan_fallback_import_warnings(kdl_src)

    return source_for_parse, extra_diagnostics, fallback_structs


def _ensure_httpx_stub() -> None:
    """Install a lightweight `httpx` stub in `sys.modules` if `httpx` is absent."""
    if "httpx" in sys.modules:
        return
    try:
        import httpx  # noqa: F401
    except ImportError:
        stub = types.ModuleType("httpx")
        stub.Client = object  # type: ignore[attr-defined]
        stub.AsyncClient = object  # type: ignore[attr-defined]
        stub.HTTPError = Exception  # type: ignore[attr-defined]
        sys.modules["httpx"] = stub


def compile_and_lint(
    kdl_src: str,
    target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a KDL v2.1 schema and compile it for the requested target backend.

    Runs the 5-pass `parse_module` pipeline, surfaces a non-fatal `W003` warning
    when top-level external file imports (`import` or `imports`) are present in the
    single-buffer playground, enumerates declared structs, and invokes the resolved
    target converter to emit `parser.*` and optional `sscgen_runtime.*` files.

    Args:
        kdl_src (str): KDL 2.0 schema source text to validate and compile.
        target (Mapping[str, Any] | None): Optional target configuration dictionary
            supporting `lang`, `lib`, `bs4_parser`, `http_client`, `http_io`,
            `separate_runtime`, `emit_runtime`, and `package`.

    Returns:
        dict[str, Any]: JSON-serializable result dictionary containing `ok`,
            `diagnostics`, `structs`, `files`, and `target_error`.
    """
    target_cfg = dict(target) if target is not None else {}
    raw_lang = str(target_cfg.get("lang") or "python").strip().lower()
    lib = target_cfg.get("lib") or None
    bs4_parser = target_cfg.get("bs4_parser") or None
    http_client = target_cfg.get("http_client") or None
    http_io = target_cfg.get("http_io") or None
    separate_runtime = bool(target_cfg.get("separate_runtime", False))
    emit_runtime = bool(target_cfg.get("emit_runtime", True))
    package = str(target_cfg.get("package") or "main")

    spec = TargetSpec(
        lang=raw_lang,
        lib=lib,
        http_client=http_client,
        separate_runtime=separate_runtime,
        bs4_parser=bs4_parser,
        http_io=http_io,
    )

    profile = None
    target_error: str | None = None
    try:
        profile = resolve(spec)
    except ResolutionError as exc:
        target_error = str(exc)

    source_for_parse, import_warnings, fallback_structs = (
        _prepare_source_for_parse(kdl_src)
    )

    lint_targets = _resolve_lint_targets(
        raw_lang, profile.language if profile is not None else None
    )
    ast_mod, module_diagnostics = parse_module(
        source_for_parse,
        targets=lint_targets,
    )

    existing_keys = {
        (d.code, d.span.start.line, d.span.start.column, d.message)
        for d in module_diagnostics
    }
    deduped_extra = [
        d
        for d in import_warnings
        if (d.code, d.span.start.line, d.span.start.column, d.message)
        not in existing_keys
    ]
    all_diagnostics = [*deduped_extra, *module_diagnostics]
    diag_dicts = [_serialize_diagnostic(d) for d in all_diagnostics]

    ast_structs = [s for s in ast_mod.body if isinstance(s, StructBase)]
    nested_ref_map = _collect_ast_nested_refs(ast_structs)
    structs = [
        {
            "name": s.name,
            "class_name": to_pascal_case(s.name),
            "type": s.type.name.lower(),
            "is_rest": _is_rest_struct(s),
            "referenced_by": nested_ref_map.get(s.name, []),
        }
        for s in ast_structs
    ]
    if not structs and fallback_structs:
        structs = fallback_structs

    has_errors = any(d["severity"] == "error" for d in diag_dicts)
    if has_errors or profile is None:
        return {
            "ok": False,
            "diagnostics": diag_dicts,
            "structs": structs,
            "files": {},
            "target_error": target_error,
        }

    try:
        converter = profile.create_converter()
        meta: dict[str, Any] = {"package": package}
        if spec.http_client:
            meta["http_client"] = spec.http_client
        if spec.bs4_parser and profile.language == "python":
            meta["bs4_parser"] = spec.bs4_parser
        if spec.http_io and profile.language == "python":
            meta["http_io"] = spec.http_io

        if spec.separate_runtime and profile.language == "python":
            runtime_name = "sscgen_runtime"
            meta["runtime_module"] = runtime_name
            http_strategy = None
            if isinstance(converter, PythonVisitor):
                http_strategy = PythonVisitor.http_strategy_for(
                    spec.http_client
                )
            register_runtime_file(
                converter,
                runtime_name,
                include_fallback=profile.runtime_include_fallback,
                http_strategy=http_strategy,
            )

        raw_files = converter.convert_all(ast_mod, **meta)
        main_filename = f"parser{profile.file_extension}"
        files: dict[str, str] = {main_filename: raw_files.get("", "")}
        for fname, content in raw_files.items():
            if fname:
                files[fname] = content

        if emit_runtime:
            if profile.language == "go" and isinstance(converter, GoVisitor):
                files["sscgen_runtime.go"] = converter.emit_runtime(package)
            elif profile.language == "rust" and isinstance(
                converter, RustVisitor
            ):
                files["sscgen_runtime.rs"] = converter.emit_runtime()

    except (
        BuildTimeError,
        ParseError,
        ValueError,
        NotImplementedError,
        TypeError,
        AttributeError,
        KeyError,
        RuntimeError,
    ) as exc:
        err_msg = str(exc) or (
            f"XPath selectors are not supported by target "
            f"'{profile.language}' ({spec.lib or 'default'})."
            if isinstance(exc, NotImplementedError)
            else type(exc).__name__
        )
        return {
            "ok": False,
            "diagnostics": diag_dicts,
            "structs": structs,
            "files": {},
            "target_error": err_msg,
        }

    return {
        "ok": True,
        "diagnostics": diag_dicts,
        "structs": structs,
        "files": files,
        "target_error": None,
    }


def test_html(
    kdl_src: str,
    html_src: str,
    struct_name: str | None = None,
) -> dict[str, Any]:
    """Execute a generated Python parser and selector health check against HTML or text.

    Selects the requested struct (or auto-selects the primary non-REST struct when
    `struct_name` is `None`), rejects `(rest)struct` definitions, evaluates selector
    health via `check_struct_health`, and runs the compiled Python parser against
    `html_src` while measuring execution latency.

    Args:
        kdl_src (str): KDL 2.0 schema source text defining the target struct.
        html_src (str): Sample HTML document or plain text input to parse and check.
        struct_name (str | None): Optional target struct name; defaults to the
            primary (last) non-REST struct in the module when `None`.

    Returns:
        dict[str, Any]: JSON-serializable dictionary containing `ok`, `struct_name`,
            `run_result`, `run_error`, `elapsed_ms`, and `health`.
    """
    requested_name = (
        struct_name.strip() if struct_name and struct_name.strip() else None
    )
    source_for_parse, _, _ = _prepare_source_for_parse(kdl_src)
    ast_mod, module_diagnostics = parse_module(
        source_for_parse,
        targets=("python",),
    )

    errors = [d for d in module_diagnostics if d.severity == Severity.ERROR]
    if errors:
        error_msg = "; ".join(
            f"{d.code}: {d.message}" if d.code else d.message for d in errors
        )
        return {
            "ok": False,
            "struct_name": requested_name,
            "run_result": None,
            "run_error": error_msg,
            "elapsed_ms": 0.0,
            "health": None,
        }

    structs = [s for s in ast_mod.body if isinstance(s, StructBase)]
    if not structs:
        return {
            "ok": False,
            "struct_name": requested_name,
            "run_result": None,
            "run_error": "No structs declared in schema.",
            "elapsed_ms": 0.0,
            "health": None,
        }

    target_struct: StructBase | None = None
    if requested_name is not None:
        for s in structs:
            if s.name == requested_name:
                target_struct = s
                break
        if target_struct is None:
            available = ", ".join(s.name for s in structs)
            return {
                "ok": False,
                "struct_name": requested_name,
                "run_result": None,
                "run_error": (
                    f"Struct '{requested_name}' not found in schema. "
                    f"Available: {available}"
                ),
                "elapsed_ms": 0.0,
                "health": None,
            }
    else:
        non_rest = [s for s in structs if not _is_rest_struct(s)]
        target_struct = non_rest[-1] if non_rest else structs[-1]

    if _is_rest_struct(target_struct):
        return {
            "ok": False,
            "struct_name": target_struct.name,
            "run_result": None,
            "run_error": (
                f"Struct '{target_struct.name}' is a (rest)struct. "
                "REST schemas support linting and code generation only; "
                "HTML parser execution and selector health checks are not supported."
            ),
            "elapsed_ms": 0.0,
            "health": None,
        }

    health_report = check_struct_health(target_struct, html_src, module=ast_mod)
    health_dict: dict[str, Any] = {
        "struct_name": health_report.struct_name,
        "passed": not health_report.has_failures(),
        "checks": [
            {
                "path": c.path,
                "selector_type": c.selector_type,
                "query": c.query,
                "matches": c.matches,
                "status": c.status,
                "message": c.message,
            }
            for c in health_report.checks
        ],
    }

    t0 = time.perf_counter()
    try:
        profile = resolve(
            TargetSpec(lang="python", lib="bs4", bs4_parser="lxml")
        )
        converter = profile.create_converter()
        try:
            code = converter.convert(ast_mod, bs4_parser="lxml")
        except NotImplementedError:
            lxml_profile = resolve(TargetSpec(lang="python", lib="lxml"))
            code = lxml_profile.create_converter().convert(ast_mod)

        _ensure_httpx_stub()
        namespace: dict[str, Any] = {}
        exec(code, namespace)  # noqa: S102
        class_name = to_pascal_case(target_struct.name)
        parser_cls = namespace.get(class_name)
        if parser_cls is None:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            return {
                "ok": False,
                "struct_name": target_struct.name,
                "run_result": None,
                "run_error": (
                    f"Generated parser class '{class_name}' not found."
                ),
                "elapsed_ms": elapsed_ms,
                "health": health_dict,
            }

        raw_result = parser_cls(html_src).parse()
        run_result = json.loads(json.dumps(raw_result, default=str))
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        return {
            "ok": False,
            "struct_name": target_struct.name,
            "run_result": None,
            "run_error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": elapsed_ms,
            "health": health_dict,
        }

    return {
        "ok": True,
        "struct_name": target_struct.name,
        "run_result": run_result,
        "run_error": None,
        "elapsed_ms": elapsed_ms,
        "health": health_dict,
    }


test_html.__test__ = False  # type: ignore[attr-defined]
