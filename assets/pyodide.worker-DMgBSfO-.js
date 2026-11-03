var _=`"""Browser playground bridge for schema validation and multi-target code generation.\r
\r
Provides JSON-serializable handlers used by the Pyodide WebWorker in \`/playground/\`\r
to validate KDL v2.1 schemas, inspect declared structs, and emit target source files\r
across Python, JavaScript, Go, and Rust.\r
"""\r
\r
from __future__ import annotations\r
\r
import json\r
import re\r
import sys\r
import time\r
import types\r
from collections.abc import Mapping\r
from typing import Any\r
\r
from kdlquery import KdlNode, KDLParseError, ReadDiagnostic, Severity\r
from kdlquery import parse as kdl_parse\r
from kdlquery.types import Position, Span\r
\r
from ssc_codegen.ast import Nested, StructBase, StructRest, StructType\r
from ssc_codegen.core.format import diagnostic_to_dict\r
from ssc_codegen.core.reader import parse_module\r
from ssc_codegen.exceptions import BuildTimeError, ParseError\r
from ssc_codegen.generation.runtime import register_runtime_file\r
from ssc_codegen.health import check_struct_health\r
from ssc_codegen.naming import to_pascal_case\r
from ssc_codegen.targets.golang.visitor import GoVisitor\r
from ssc_codegen.targets.python.visitor import PythonVisitor\r
from ssc_codegen.targets.resolver import ResolutionError, resolve\r
from ssc_codegen.targets.rust.visitor import RustVisitor\r
from ssc_codegen.targets.spec import TargetSpec\r
\r
__all__ = ["compile_and_lint", "test_html"]\r
\r
_TOP_IMPORT_LINE_RE = re.compile(r"^(\\s*)(imports?)(?=\\s|\\{|$)")\r
\r
_VALID_STRUCT_TYPES: frozenset[str] = frozenset(\r
    {"item", "list", "table", "dict", "flat", "raw", "rest"}\r
)\r
\r
_STRING_ARG_OPS: dict[str, str] = {\r
    "trim": 'example: trim  or  trim "chars"',\r
    "ltrim": 'example: ltrim  or  ltrim "chars"',\r
    "rtrim": 'example: rtrim  or  rtrim "chars"',\r
    "rm-prefix": 'example: rm-prefix "substring"',\r
    "rm-suffix": 'example: rm-suffix "substring"',\r
    "rm-prefix-suffix": 'example: rm-prefix-suffix "substring"',\r
    "fmt": 'example: fmt "prefix-{{}}-suffix"',\r
    "repl": 'example: repl "old" "new"',\r
    "split": 'example: split " "',\r
    "join": 'example: join " "',\r
    "re": 'example: re #"(\\\\d+)"#',\r
    "re-all": 'example: re-all #"(\\\\d+)"#',\r
    "re-sub": 'example: re-sub #"\\\\D"# ""',\r
    "attr": 'example: attr "href"',\r
    "css": 'example: css ".selector"',\r
    "css-all": 'example: css-all ".selector"',\r
    "css-remove": 'example: css-remove ".selector"',\r
    "xpath": 'example: xpath "//div"',\r
    "xpath-all": 'example: xpath-all "//div"',\r
    "xpath-remove": 'example: xpath-remove "//div"',\r
    "starts": 'example: starts "value"',\r
    "ends": 'example: ends "value"',\r
    "contains": 'example: contains "value"',\r
    "has-attr": 'example: has-attr "href"',\r
    "attr-starts": 'example: attr-starts "href" "value"',\r
    "attr-ends": 'example: attr-ends "href" "value"',\r
    "attr-contains": 'example: attr-contains "href" "value"',\r
    "attr-re": 'example: attr-re "href" #".*\\\\.com$"#',\r
    "text-re": 'example: text-re #"\\\\d+"#',\r
    "text-starts": 'example: text-starts "value"',\r
    "text-ends": 'example: text-ends "value"',\r
    "text-contains": 'example: text-contains "value"',\r
    "re-any": 'example: re-any #"\\\\d+"#',\r
}\r
\r
\r
def _scan_non_string_op_arg_errors(\r
    nodes: list[KdlNode],\r
) -> list[ReadDiagnostic]:\r
    """Detect non-string arguments passed to string pipeline/predicate ops in the CST."""\r
    errors: list[ReadDiagnostic] = []\r
    for top in nodes:\r
        if top.name not in ("struct", "fn", "define"):\r
            continue\r
        for desc in top.iter_descendants():\r
            hint = _STRING_ARG_OPS.get(desc.name)\r
            if hint is None or not desc.args:\r
                continue\r
            for arg in desc.args:\r
                val = arg.value\r
                if not isinstance(val, str):\r
                    val_type = "null" if val is None else type(val).__name__\r
                    errors.append(\r
                        ReadDiagnostic(\r
                            message=(\r
                                f"'{desc.name}' argument must be a string, "\r
                                f"got {val_type}"\r
                            ),\r
                            severity=Severity.ERROR,\r
                            span=desc.span,\r
                            path="",\r
                            hint=hint,\r
                            code="E001",\r
                            label="invalid argument type",\r
                        )\r
                    )\r
                    break\r
    return errors\r
\r
\r
def _mask_span(text: str, start_offset: int, end_offset: int) -> str:\r
    """Replace characters in \`[start_offset, end_offset)\` with spaces while keeping newlines."""\r
    start = max(0, min(start_offset, len(text)))\r
    end = max(start, min(end_offset, len(text)))\r
    segment = text[start:end]\r
    masked = "".join(ch if ch in ("\\r", "\\n") else " " for ch in segment)\r
    return text[:start] + masked + text[end:]\r
\r
\r
def _extract_cst_structs(nodes: list[KdlNode]) -> list[dict[str, Any]]:\r
    """Extract declared struct descriptors from top-level CST nodes as a fallback."""\r
    structs: list[dict[str, Any]] = []\r
    seen: set[str] = set()\r
    ref_map: dict[str, list[str]] = {}\r
    for node in nodes:\r
        if node.name != "struct" or not node.args:\r
            continue\r
        parent_name = str(node.args[0].value)\r
        if not parent_name:\r
            continue\r
        for desc in node.iter_descendants():\r
            if desc.name == "nested" and desc.args:\r
                target_name = str(desc.args[0].value)\r
                parents = ref_map.setdefault(target_name, [])\r
                if parent_name not in parents:\r
                    parents.append(parent_name)\r
\r
    for node in nodes:\r
        if node.name != "struct" or not node.args:\r
            continue\r
        name = str(node.args[0].value)\r
        if not name or name in seen:\r
            continue\r
        raw_ann = node.type_annotation\r
        struct_type = (\r
            raw_ann[1:-1] if raw_ann else str(node.get_prop("type") or "item")\r
        )\r
        if struct_type not in _VALID_STRUCT_TYPES:\r
            struct_type = "item"\r
        seen.add(name)\r
        structs.append(\r
            {\r
                "name": name,\r
                "class_name": to_pascal_case(name),\r
                "type": struct_type,\r
                "is_rest": struct_type == "rest",\r
                "referenced_by": ref_map.get(name, []),\r
            }\r
        )\r
    return structs\r
\r
\r
def _collect_ast_nested_refs(\r
    struct_nodes: list[StructBase],\r
) -> dict[str, list[str]]:\r
    """Map each struct name to the list of parent struct names that reference it via \`nested\`."""\r
    ref_map: dict[str, list[str]] = {}\r
\r
    def _walk_body(parent_name: str, body: list[Any]) -> None:\r
        for item in body:\r
            if isinstance(item, Nested) and item.struct_name:\r
                parents = ref_map.setdefault(item.struct_name, [])\r
                if parent_name not in parents:\r
                    parents.append(parent_name)\r
            child_body = getattr(item, "body", None)\r
            if isinstance(child_body, list):\r
                _walk_body(parent_name, child_body)\r
\r
    for s in struct_nodes:\r
        _walk_body(s.name, list(getattr(s, "body", [])))\r
    return ref_map\r
\r
\r
def _serialize_diagnostic(diag: ReadDiagnostic) -> dict[str, Any]:\r
    """Convert a \`ReadDiagnostic\` into a dictionary with guaranteed 1-based spans."""\r
    start = diag.span.start\r
    end = diag.span.end\r
    norm_start = Position(\r
        offset=max(start.offset, 0),\r
        line=max(start.line, 1),\r
        column=max(start.column, 1),\r
    )\r
    norm_end = Position(\r
        offset=max(end.offset, norm_start.offset),\r
        line=max(end.line, norm_start.line),\r
        column=max(end.column, 1),\r
    )\r
    normalized = ReadDiagnostic(\r
        message=diag.message,\r
        severity=diag.severity,\r
        span=Span(start=norm_start, end=norm_end),\r
        path=diag.path,\r
        hint=diag.hint,\r
        code=diag.code,\r
        label=diag.label,\r
        notes=tuple(diag.notes),\r
    )\r
    return diagnostic_to_dict(normalized)\r
\r
\r
def _resolve_lint_targets(\r
    raw_lang: str, resolved_language: str | None\r
) -> tuple[str, ...] | None:\r
    """Determine target language names to pass to \`parse_module\` symbol checks."""\r
    if resolved_language is not None:\r
        return (resolved_language,)\r
    alias_map = {\r
        "python": "python",\r
        "py": "python",\r
        "javascript": "javascript",\r
        "js": "javascript",\r
        "go": "go",\r
        "rust": "rust",\r
    }\r
    mapped = alias_map.get(raw_lang)\r
    return (mapped,) if mapped is not None else None\r
\r
\r
def _is_rest_struct(struct: StructBase) -> bool:\r
    """Return True if the struct is a \`(rest)struct\`."""\r
    return isinstance(struct, StructRest) or struct.type == StructType.REST\r
\r
\r
def _scan_fallback_import_warnings(kdl_src: str) -> list[ReadDiagnostic]:\r
    """Scan raw source lines for top-level \`import\`/\`imports\` when CST parsing fails."""\r
    warnings: list[ReadDiagnostic] = []\r
    offset = 0\r
    for line_no, raw_line in enumerate(\r
        kdl_src.splitlines(keepends=True), start=1\r
    ):\r
        match = _TOP_IMPORT_LINE_RE.match(raw_line)\r
        if match is not None:\r
            indent, keyword = match.group(1), match.group(2)\r
            col_start = len(indent) + 1\r
            line_body = raw_line.rstrip("\\r\\n")\r
            col_end = max(len(line_body) + 1, col_start + len(keyword))\r
            start_pos = Position(\r
                offset=offset + len(indent),\r
                line=line_no,\r
                column=col_start,\r
            )\r
            end_pos = Position(\r
                offset=offset + len(line_body),\r
                line=line_no,\r
                column=col_end,\r
            )\r
            warnings.append(\r
                ReadDiagnostic(\r
                    message=(\r
                        f"External file imports ('{keyword}') are not supported "\r
                        "in the single-buffer browser playground."\r
                    ),\r
                    severity=Severity.WARNING,\r
                    span=Span(start=start_pos, end=end_pos),\r
                    path="",\r
                    hint="Inline shared definitions directly into the active schema buffer.",\r
                    code="W003",\r
                    label="unsupported in single-buffer playground",\r
                )\r
            )\r
        offset += len(raw_line)\r
    return warnings\r
\r
\r
def _prepare_source_for_parse(\r
    kdl_src: str,\r
) -> tuple[str, list[ReadDiagnostic], list[dict[str, Any]]]:\r
    """Mask external \`import\`/\`imports\` nodes and collect pre-parse CST diagnostics."""\r
    source_for_parse = kdl_src\r
    extra_diagnostics: list[ReadDiagnostic] = []\r
    fallback_structs: list[dict[str, Any]] = []\r
\r
    try:\r
        doc = kdl_parse(kdl_src)\r
        top_nodes = list(doc.nodes)\r
        fallback_structs = _extract_cst_structs(top_nodes)\r
        for node in top_nodes:\r
            if node.name in ("import", "imports"):\r
                extra_diagnostics.append(\r
                    ReadDiagnostic(\r
                        message=(\r
                            f"External file imports ('{node.name}') are not supported "\r
                            "in the single-buffer browser playground."\r
                        ),\r
                        severity=Severity.WARNING,\r
                        span=node.span,\r
                        path="",\r
                        hint="Inline shared definitions directly into the active schema buffer.",\r
                        code="W003",\r
                        label="unsupported in single-buffer playground",\r
                    )\r
                )\r
                source_for_parse = _mask_span(\r
                    source_for_parse,\r
                    node.span.start.offset,\r
                    node.span.end.offset,\r
                )\r
        extra_diagnostics.extend(_scan_non_string_op_arg_errors(top_nodes))\r
    except KDLParseError:\r
        source_for_parse = kdl_src\r
        extra_diagnostics = _scan_fallback_import_warnings(kdl_src)\r
\r
    return source_for_parse, extra_diagnostics, fallback_structs\r
\r
\r
def _ensure_httpx_stub() -> None:\r
    """Install a lightweight \`httpx\` stub in \`sys.modules\` if \`httpx\` is absent."""\r
    if "httpx" in sys.modules:\r
        return\r
    try:\r
        import httpx  # noqa: F401\r
    except ImportError:\r
        stub = types.ModuleType("httpx")\r
        stub.Client = object  # type: ignore[attr-defined]\r
        stub.AsyncClient = object  # type: ignore[attr-defined]\r
        stub.HTTPError = Exception  # type: ignore[attr-defined]\r
        sys.modules["httpx"] = stub\r
\r
\r
def compile_and_lint(\r
    kdl_src: str,\r
    target: Mapping[str, Any] | None = None,\r
) -> dict[str, Any]:\r
    """Validate a KDL v2.1 schema and compile it for the requested target backend.\r
\r
    Runs the 5-pass \`parse_module\` pipeline, surfaces a non-fatal \`W003\` warning\r
    when top-level external file imports (\`import\` or \`imports\`) are present in the\r
    single-buffer playground, enumerates declared structs, and invokes the resolved\r
    target converter to emit \`parser.*\` and optional \`sscgen_runtime.*\` files.\r
\r
    Args:\r
        kdl_src (str): KDL 2.0 schema source text to validate and compile.\r
        target (Mapping[str, Any] | None): Optional target configuration dictionary\r
            supporting \`lang\`, \`lib\`, \`bs4_parser\`, \`http_client\`, \`http_io\`,\r
            \`separate_runtime\`, \`emit_runtime\`, and \`package\`.\r
\r
    Returns:\r
        dict[str, Any]: JSON-serializable result dictionary containing \`ok\`,\r
            \`diagnostics\`, \`structs\`, \`files\`, and \`target_error\`.\r
    """\r
    target_cfg = dict(target) if target is not None else {}\r
    raw_lang = str(target_cfg.get("lang") or "python").strip().lower()\r
    lib = target_cfg.get("lib") or None\r
    bs4_parser = target_cfg.get("bs4_parser") or None\r
    http_client = target_cfg.get("http_client") or None\r
    http_io = target_cfg.get("http_io") or None\r
    separate_runtime = bool(target_cfg.get("separate_runtime", False))\r
    emit_runtime = bool(target_cfg.get("emit_runtime", True))\r
    package = str(target_cfg.get("package") or "main")\r
\r
    spec = TargetSpec(\r
        lang=raw_lang,\r
        lib=lib,\r
        http_client=http_client,\r
        separate_runtime=separate_runtime,\r
        bs4_parser=bs4_parser,\r
        http_io=http_io,\r
    )\r
\r
    profile = None\r
    target_error: str | None = None\r
    try:\r
        profile = resolve(spec)\r
    except ResolutionError as exc:\r
        target_error = str(exc)\r
\r
    source_for_parse, import_warnings, fallback_structs = (\r
        _prepare_source_for_parse(kdl_src)\r
    )\r
\r
    lint_targets = _resolve_lint_targets(\r
        raw_lang, profile.language if profile is not None else None\r
    )\r
    ast_mod, module_diagnostics = parse_module(\r
        source_for_parse,\r
        targets=lint_targets,\r
    )\r
\r
    existing_keys = {\r
        (d.code, d.span.start.line, d.span.start.column, d.message)\r
        for d in module_diagnostics\r
    }\r
    deduped_extra = [\r
        d\r
        for d in import_warnings\r
        if (d.code, d.span.start.line, d.span.start.column, d.message)\r
        not in existing_keys\r
    ]\r
    all_diagnostics = [*deduped_extra, *module_diagnostics]\r
    diag_dicts = [_serialize_diagnostic(d) for d in all_diagnostics]\r
\r
    ast_structs = [s for s in ast_mod.body if isinstance(s, StructBase)]\r
    nested_ref_map = _collect_ast_nested_refs(ast_structs)\r
    structs = [\r
        {\r
            "name": s.name,\r
            "class_name": to_pascal_case(s.name),\r
            "type": s.type.name.lower(),\r
            "is_rest": _is_rest_struct(s),\r
            "referenced_by": nested_ref_map.get(s.name, []),\r
        }\r
        for s in ast_structs\r
    ]\r
    if not structs and fallback_structs:\r
        structs = fallback_structs\r
\r
    has_errors = any(d["severity"] == "error" for d in diag_dicts)\r
    if has_errors or profile is None:\r
        return {\r
            "ok": False,\r
            "diagnostics": diag_dicts,\r
            "structs": structs,\r
            "files": {},\r
            "target_error": target_error,\r
        }\r
\r
    try:\r
        converter = profile.create_converter()\r
        meta: dict[str, Any] = {"package": package}\r
        if spec.http_client:\r
            meta["http_client"] = spec.http_client\r
        if spec.bs4_parser and profile.language == "python":\r
            meta["bs4_parser"] = spec.bs4_parser\r
        if spec.http_io and profile.language == "python":\r
            meta["http_io"] = spec.http_io\r
\r
        if spec.separate_runtime and profile.language == "python":\r
            runtime_name = "sscgen_runtime"\r
            meta["runtime_module"] = runtime_name\r
            http_strategy = None\r
            if isinstance(converter, PythonVisitor):\r
                http_strategy = PythonVisitor.http_strategy_for(\r
                    spec.http_client\r
                )\r
            register_runtime_file(\r
                converter,\r
                runtime_name,\r
                include_fallback=profile.runtime_include_fallback,\r
                http_strategy=http_strategy,\r
            )\r
\r
        raw_files = converter.convert_all(ast_mod, **meta)\r
        main_filename = f"parser{profile.file_extension}"\r
        files: dict[str, str] = {main_filename: raw_files.get("", "")}\r
        for fname, content in raw_files.items():\r
            if fname:\r
                files[fname] = content\r
\r
        if emit_runtime:\r
            if profile.language == "go" and isinstance(converter, GoVisitor):\r
                files["sscgen_runtime.go"] = converter.emit_runtime(package)\r
            elif profile.language == "rust" and isinstance(\r
                converter, RustVisitor\r
            ):\r
                files["sscgen_runtime.rs"] = converter.emit_runtime()\r
\r
    except (\r
        BuildTimeError,\r
        ParseError,\r
        ValueError,\r
        NotImplementedError,\r
        TypeError,\r
        AttributeError,\r
        KeyError,\r
        RuntimeError,\r
    ) as exc:\r
        err_msg = str(exc) or (\r
            f"XPath selectors are not supported by target "\r
            f"'{profile.language}' ({spec.lib or 'default'})."\r
            if isinstance(exc, NotImplementedError)\r
            else type(exc).__name__\r
        )\r
        return {\r
            "ok": False,\r
            "diagnostics": diag_dicts,\r
            "structs": structs,\r
            "files": {},\r
            "target_error": err_msg,\r
        }\r
\r
    return {\r
        "ok": True,\r
        "diagnostics": diag_dicts,\r
        "structs": structs,\r
        "files": files,\r
        "target_error": None,\r
    }\r
\r
\r
def test_html(\r
    kdl_src: str,\r
    html_src: str,\r
    struct_name: str | None = None,\r
) -> dict[str, Any]:\r
    """Execute a generated Python parser and selector health check against HTML or text.\r
\r
    Selects the requested struct (or auto-selects the primary non-REST struct when\r
    \`struct_name\` is \`None\`), rejects \`(rest)struct\` definitions, evaluates selector\r
    health via \`check_struct_health\`, and runs the compiled Python parser against\r
    \`html_src\` while measuring execution latency.\r
\r
    Args:\r
        kdl_src (str): KDL 2.0 schema source text defining the target struct.\r
        html_src (str): Sample HTML document or plain text input to parse and check.\r
        struct_name (str | None): Optional target struct name; defaults to the\r
            primary (last) non-REST struct in the module when \`None\`.\r
\r
    Returns:\r
        dict[str, Any]: JSON-serializable dictionary containing \`ok\`, \`struct_name\`,\r
            \`run_result\`, \`run_error\`, \`elapsed_ms\`, and \`health\`.\r
    """\r
    requested_name = (\r
        struct_name.strip() if struct_name and struct_name.strip() else None\r
    )\r
    source_for_parse, _, _ = _prepare_source_for_parse(kdl_src)\r
    ast_mod, module_diagnostics = parse_module(\r
        source_for_parse,\r
        targets=("python",),\r
    )\r
\r
    errors = [d for d in module_diagnostics if d.severity == Severity.ERROR]\r
    if errors:\r
        error_msg = "; ".join(\r
            f"{d.code}: {d.message}" if d.code else d.message for d in errors\r
        )\r
        return {\r
            "ok": False,\r
            "struct_name": requested_name,\r
            "run_result": None,\r
            "run_error": error_msg,\r
            "elapsed_ms": 0.0,\r
            "health": None,\r
        }\r
\r
    structs = [s for s in ast_mod.body if isinstance(s, StructBase)]\r
    if not structs:\r
        return {\r
            "ok": False,\r
            "struct_name": requested_name,\r
            "run_result": None,\r
            "run_error": "No structs declared in schema.",\r
            "elapsed_ms": 0.0,\r
            "health": None,\r
        }\r
\r
    target_struct: StructBase | None = None\r
    if requested_name is not None:\r
        for s in structs:\r
            if s.name == requested_name:\r
                target_struct = s\r
                break\r
        if target_struct is None:\r
            available = ", ".join(s.name for s in structs)\r
            return {\r
                "ok": False,\r
                "struct_name": requested_name,\r
                "run_result": None,\r
                "run_error": (\r
                    f"Struct '{requested_name}' not found in schema. "\r
                    f"Available: {available}"\r
                ),\r
                "elapsed_ms": 0.0,\r
                "health": None,\r
            }\r
    else:\r
        non_rest = [s for s in structs if not _is_rest_struct(s)]\r
        target_struct = non_rest[-1] if non_rest else structs[-1]\r
\r
    if _is_rest_struct(target_struct):\r
        return {\r
            "ok": False,\r
            "struct_name": target_struct.name,\r
            "run_result": None,\r
            "run_error": (\r
                f"Struct '{target_struct.name}' is a (rest)struct. "\r
                "REST schemas support linting and code generation only; "\r
                "HTML parser execution and selector health checks are not supported."\r
            ),\r
            "elapsed_ms": 0.0,\r
            "health": None,\r
        }\r
\r
    health_report = check_struct_health(target_struct, html_src, module=ast_mod)\r
    health_dict: dict[str, Any] = {\r
        "struct_name": health_report.struct_name,\r
        "passed": not health_report.has_failures(),\r
        "checks": [\r
            {\r
                "path": c.path,\r
                "selector_type": c.selector_type,\r
                "query": c.query,\r
                "matches": c.matches,\r
                "status": c.status,\r
                "message": c.message,\r
            }\r
            for c in health_report.checks\r
        ],\r
    }\r
\r
    t0 = time.perf_counter()\r
    try:\r
        profile = resolve(\r
            TargetSpec(lang="python", lib="bs4", bs4_parser="lxml")\r
        )\r
        converter = profile.create_converter()\r
        try:\r
            code = converter.convert(ast_mod, bs4_parser="lxml")\r
        except NotImplementedError:\r
            lxml_profile = resolve(TargetSpec(lang="python", lib="lxml"))\r
            code = lxml_profile.create_converter().convert(ast_mod)\r
\r
        _ensure_httpx_stub()\r
        namespace: dict[str, Any] = {}\r
        exec(code, namespace)  # noqa: S102\r
        class_name = to_pascal_case(target_struct.name)\r
        parser_cls = namespace.get(class_name)\r
        if parser_cls is None:\r
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)\r
            return {\r
                "ok": False,\r
                "struct_name": target_struct.name,\r
                "run_result": None,\r
                "run_error": (\r
                    f"Generated parser class '{class_name}' not found."\r
                ),\r
                "elapsed_ms": elapsed_ms,\r
                "health": health_dict,\r
            }\r
\r
        raw_result = parser_cls(html_src).parse()\r
        run_result = json.loads(json.dumps(raw_result, default=str))\r
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)\r
    except Exception as exc:  # noqa: BLE001\r
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)\r
        return {\r
            "ok": False,\r
            "struct_name": target_struct.name,\r
            "run_result": None,\r
            "run_error": f"{type(exc).__name__}: {exc}",\r
            "elapsed_ms": elapsed_ms,\r
            "health": health_dict,\r
        }\r
\r
    return {\r
        "ok": True,\r
        "struct_name": target_struct.name,\r
        "run_result": run_result,\r
        "run_error": None,\r
        "elapsed_ms": elapsed_ms,\r
        "health": health_dict,\r
    }\r
\r
\r
test_html.__test__ = False  # type: ignore[attr-defined]\r
`;const l="https://cdn.jsdelivr.net/pyodide/v0.29.5/full/",p=`${l}pyodide.mjs`;let a=null;async function d(){const{loadPyodide:n}=await import(p),r=await n({indexURL:l});await r.loadPackage(["micropip","lxml","beautifulsoup4","soupsieve","cssselect"]),await r.runPythonAsync(`
import io
import sysconfig
import zipfile
import micropip
from pyodide.http import pyfetch

async def _install_pure_wheel_from_pypi(pkg_name: str) -> None:
    resp = await pyfetch(f"https://pypi.org/pypi/{pkg_name}/json")
    data = await resp.json()
    urls = data.get("urls", [])
    wheel_url = next(
        (u["url"] for u in urls if u.get("filename", "").endswith("-py3-none-any.whl")),
        None,
    )
    if not wheel_url:
        raise RuntimeError(f"No pure-Python wheel found on PyPI for {pkg_name}")
    wheel_resp = await pyfetch(wheel_url)
    wheel_bytes = await wheel_resp.bytes()
    purelib = sysconfig.get_path("purelib")
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
        zf.extractall(purelib)

await micropip.install("kdlquery>=1.7.0")
try:
    await micropip.install("ssc-codegen>=0.45.0", deps=False)
except Exception:
    await _install_pure_wheel_from_pypi("ssc-codegen")
`),r.runPython(_),r.runPython(`
import importlib.metadata
import json

def _worker_get_version() -> str:
    try:
        return importlib.metadata.version("ssc-codegen")
    except Exception:
        return "0.45.0"

def _worker_compile_and_lint(kdl_src: str, target_json: str) -> str:
    target_dict = json.loads(target_json) if target_json else {}
    res = compile_and_lint(kdl_src, target_dict)
    return json.dumps(res, ensure_ascii=False)

def _worker_test_html(kdl_src: str, html_src: str, struct_name: str = "") -> str:
    resolved_struct = struct_name if struct_name else None
    res = test_html(kdl_src, html_src, resolved_struct)
    return json.dumps(res, ensure_ascii=False)
`);const e=r.globals.get("_worker_get_version"),t={type:"ready",version:String(e())};return self.postMessage(t),r}function c(){return a||(a=d().catch(n=>{a=null;const e={type:"init_error",error:n instanceof Error?n.message:String(n)};throw self.postMessage(e),n})),a}c();self.addEventListener("message",async n=>{const r=n.data;if(!(!r||typeof r.id!="number"))try{const e=await c();if(r.action==="compile_and_lint"){const s=e.globals.get("_worker_compile_and_lint"),t=String(s(r.payload.kdlSrc,JSON.stringify(r.payload.target))),o=JSON.parse(t),i={type:"result",id:r.id,action:"compile_and_lint",result:o};self.postMessage(i)}else if(r.action==="test_html"){const s=e.globals.get("_worker_test_html"),t=String(s(r.payload.kdlSrc,r.payload.htmlSrc,r.payload.structName??"")),o=JSON.parse(t),i={type:"result",id:r.id,action:"test_html",result:o};self.postMessage(i)}}catch(e){const s=e instanceof Error?e.message:String(e),t={type:"error",id:r.id,error:s};self.postMessage(t)}});
