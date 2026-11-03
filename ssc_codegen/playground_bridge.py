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

from ssc_codegen.ast import StructBase, StructRest, StructType
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

_DICT_ANNOTATION_RE = re.compile(
    r"(?<!\(dict\))(\b[a-zA-Z_][\w-]*)\s+\(dict\)(\??)(?=\s*(?:\{|from|path|@))"
)

_VALID_STRUCT_TYPES: frozenset[str] = frozenset(
    {"item", "list", "table", "dict", "flat", "raw", "rest"}
)


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
                "type": struct_type,
                "is_rest": struct_type == "rest",
            }
        )
    return structs


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


def _prepare_source_for_parse(
    kdl_src: str,
) -> tuple[str, list[ReadDiagnostic], list[dict[str, Any]]]:
    """Normalize `(dict)` annotations and mask external `import`/`imports` nodes."""
    normalized_src = _DICT_ANNOTATION_RE.sub(r"(dict)\1\2", kdl_src)
    source_for_parse = normalized_src
    import_warnings: list[ReadDiagnostic] = []
    fallback_structs: list[dict[str, Any]] = []

    try:
        doc = kdl_parse(normalized_src)
        top_nodes = list(doc.nodes)
        fallback_structs = _extract_cst_structs(top_nodes)
        for node in top_nodes:
            if node.name in ("import", "imports"):
                import_warnings.append(
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
    except KDLParseError:
        source_for_parse = kdl_src

    return source_for_parse, import_warnings, fallback_structs


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

    all_diagnostics = [*import_warnings, *module_diagnostics]
    diag_dicts = [_serialize_diagnostic(d) for d in all_diagnostics]

    structs = [
        {
            "name": s.name,
            "type": s.type.name.lower(),
            "is_rest": _is_rest_struct(s),
        }
        for s in ast_mod.body
        if isinstance(s, StructBase)
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

    except (BuildTimeError, ParseError, ValueError) as exc:
        return {
            "ok": False,
            "diagnostics": diag_dicts,
            "structs": structs,
            "files": {},
            "target_error": str(exc),
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
