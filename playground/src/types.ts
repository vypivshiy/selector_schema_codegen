export interface DiagnosticPosition {
  offset: number;
  line: number;
  column: number;
}

export interface DiagnosticSpan {
  start: DiagnosticPosition;
  end: DiagnosticPosition;
}

export interface SscDiagnostic {
  code: string;
  severity: "error" | "warning";
  message: string;
  hint: string;
  path?: string;
  label?: string | null;
  notes?: string[];
  span: DiagnosticSpan;
}

export type StructKind =
  | "item"
  | "list"
  | "table"
  | "dict"
  | "flat"
  | "raw"
  | "rest";

export interface StructInfo {
  name: string;
  class_name?: string;
  type: StructKind | string;
  is_rest: boolean;
  referenced_by?: string[];
}

export type TargetLang = "python" | "js" | "go" | "rust";
export type PythonHtmlLib = "bs4" | "lxml" | "parsel" | "slax";
export type Bs4ParserEngine = "lxml" | "html.parser" | "html5lib";
export type PythonHttpClient = "httpx" | "httpx2" | "aiohttp" | "requests";
export type JsHttpClient = "fetch" | "axios";
export type HttpIoMode = "both" | "sync" | "async";

export interface TargetConfig {
  lang: TargetLang;
  lib: PythonHtmlLib;
  bs4_parser: Bs4ParserEngine;
  py_http_client: PythonHttpClient;
  js_http_client: JsHttpClient;
  http_io: HttpIoMode;
  separate_runtime: boolean;
}

export interface TargetSpecPayload {
  lang: TargetLang;
  lib?: PythonHtmlLib | null;
  bs4_parser?: Bs4ParserEngine | null;
  http_client?: string | null;
  http_io?: HttpIoMode | null;
  separate_runtime?: boolean;
  emit_runtime?: boolean;
  package?: string;
}

export interface CompileAndLintResult {
  ok: boolean;
  diagnostics: SscDiagnostic[];
  structs: StructInfo[];
  files: Record<string, string>;
  target_error: string | null;
}

export type HealthCheckStatus = "ok" | "warn" | "fail";

export interface SelectorHealthCheck {
  path: string;
  selector_type: string;
  query: string;
  matches: number;
  status: HealthCheckStatus;
  message: string;
}

export interface StructHealthReport {
  struct_name: string;
  passed: boolean;
  checks: SelectorHealthCheck[];
}

export interface TestHtmlResult {
  ok: boolean;
  struct_name: string | null;
  run_result: unknown;
  run_error: string | null;
  elapsed_ms: number;
  health: StructHealthReport | null;
}

export type WorkerStatus = "loading" | "ready" | "error";

export type WorkerRequest =
  | {
      id: number;
      action: "compile_and_lint";
      payload: {
        kdlSrc: string;
        target: TargetSpecPayload;
      };
    }
  | {
      id: number;
      action: "test_html";
      payload: {
        kdlSrc: string;
        htmlSrc: string;
        structName: string | null;
      };
    };

export type WorkerResponse =
  | {
      type: "ready";
      version: string;
    }
  | {
      type: "init_error";
      error: string;
    }
  | {
      type: "result";
      id: number;
      action: "compile_and_lint";
      result: CompileAndLintResult;
    }
  | {
      type: "result";
      id: number;
      action: "test_html";
      result: TestHtmlResult;
    }
  | {
      type: "error";
      id: number;
      error: string;
    };

export const DEFAULT_TARGET_CONFIG: TargetConfig = {
  lang: "python",
  lib: "bs4",
  bs4_parser: "lxml",
  py_http_client: "httpx",
  js_http_client: "fetch",
  http_io: "both",
  separate_runtime: false,
};

/**
 * Normalize a `TargetConfig`, coercing unsupported option combinations
 * (such as `aiohttp` with `sync` I/O mode -> `async`) in one place.
 */
export function normalizeTargetConfig(config: TargetConfig): TargetConfig {
  const http_io: HttpIoMode =
    config.py_http_client === "aiohttp" && config.http_io === "sync"
      ? "async"
      : config.http_io;
  return {
    ...config,
    http_io,
  };
}

/**
 * Convert UI `TargetConfig` state into the contextual `TargetSpecPayload`
 * sent to `compile_and_lint`, omitting language-specific options that do not
 * apply to the active target language.
 */
export function buildTargetSpecPayload(
  config: TargetConfig,
): TargetSpecPayload {
  const normalized = normalizeTargetConfig(config);
  switch (normalized.lang) {
    case "python":
      return {
        lang: "python",
        lib: normalized.lib,
        bs4_parser: normalized.lib === "bs4" ? normalized.bs4_parser : null,
        http_client: normalized.py_http_client,
        http_io: normalized.http_io,
        separate_runtime: normalized.separate_runtime,
        emit_runtime: true,
      };
    case "js":
      return {
        lang: "js",
        http_client: normalized.js_http_client,
        emit_runtime: true,
      };
    case "go":
      return {
        lang: "go",
        emit_runtime: true,
        package: "main",
      };
    case "rust":
      return {
        lang: "rust",
        http_client: "reqwest",
        emit_runtime: true,
      };
  }
}

/**
 * Map a target language or emitted file name to its Monaco Editor language ID.
 */
export function getMonacoLanguageForFile(
  filename: string,
  fallbackLang: TargetLang,
): string {
  if (filename.endsWith(".py")) return "python";
  if (filename.endsWith(".js") || filename.endsWith(".mjs")) return "javascript";
  if (filename.endsWith(".go")) return "go";
  if (filename.endsWith(".rs")) return "rust";
  return fallbackLang === "js" ? "javascript" : fallbackLang;
}

/**
 * Return the generated PascalCase class name for a struct descriptor.
 */
export function getStructClassName(struct: StructInfo): string {
  if (struct.class_name && struct.class_name.trim()) {
    return struct.class_name.trim();
  }
  return struct.name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

/**
 * Format a clear entrypoint label for the Struct dropdown showing the class name,
 * struct type, and whether it is a root entrypoint or nested inside another struct.
 */
export function formatStructOptionLabel(struct: StructInfo): string {
  const clsName = getStructClassName(struct);
  if (struct.is_rest) {
    return `${clsName} — (${struct.type} · REST client)`;
  }
  const refs = struct.referenced_by ?? [];
  if (refs.length > 0) {
    return `${clsName}.parse() — (${struct.type} · nested in ${refs.join(", ")})`;
  }
  return `${clsName}.parse() — (${struct.type} · root entrypoint)`;
}

/**
 * Select the active struct name for the HTML Test & Health pane.
 * Preserves `currentStructName` when it exists in `structs`; otherwise
 * auto-selects the primary (last) root non-REST struct, falling back to the
 * last non-REST struct or last declared struct.
 */
export function selectDefaultStructName(
  structs: StructInfo[],
  currentStructName?: string | null,
): string {
  if (structs.length === 0) {
    return "";
  }
  if (
    currentStructName &&
    structs.some((s) => s.name === currentStructName)
  ) {
    return currentStructName;
  }
  const nonRest = structs.filter((s) => !s.is_rest);
  if (nonRest.length > 0) {
    const rootNonRest = nonRest.filter(
      (s) => !s.referenced_by || s.referenced_by.length === 0,
    );
    if (rootNonRest.length > 0) {
      return rootNonRest[rootNonRest.length - 1].name;
    }
    return nonRest[nonRest.length - 1].name;
  }
  return structs[structs.length - 1].name;
}

export interface HtmlTestActionState {
  activeStruct: StructInfo | null;
  isRestSelected: boolean;
  canRun: boolean;
  restNotice: string | null;
}

/**
 * Compute action availability and REST notice state for the HTML Test & Health pane.
 */
export function getHtmlTestActionState(
  structs: StructInfo[],
  selectedStructName: string | null,
  workerReady: boolean,
  hasSchemaErrors: boolean,
  isTesting: boolean,
): HtmlTestActionState {
  const resolvedName = selectDefaultStructName(structs, selectedStructName);
  const activeStruct =
    structs.find((s) => s.name === resolvedName) ?? null;
  const isRestSelected = Boolean(activeStruct?.is_rest);
  const restNotice =
    isRestSelected && activeStruct
      ? `REST schema: lint & codegen only — (${activeStruct.type}) ${activeStruct.name} does not execute against HTML or raw text input.`
      : null;
  const canRun =
    workerReady &&
    !isTesting &&
    !hasSchemaErrors &&
    activeStruct !== null &&
    !isRestSelected;

  return {
    activeStruct,
    isRestSelected,
    canRun,
    restNotice,
  };
}

export interface HealthSummaryCounts {
  total: number;
  okCount: number;
  warnCount: number;
  failCount: number;
  passed: boolean;
}

/**
 * Compute aggregate check counts from a `StructHealthReport`.
 */
export function summarizeHealthReport(
  health: StructHealthReport | null,
): HealthSummaryCounts {
  if (!health) {
    return {
      total: 0,
      okCount: 0,
      warnCount: 0,
      failCount: 0,
      passed: false,
    };
  }
  let okCount = 0;
  let warnCount = 0;
  let failCount = 0;
  for (const check of health.checks) {
    if (check.status === "ok") okCount += 1;
    else if (check.status === "warn") warnCount += 1;
    else if (check.status === "fail") failCount += 1;
  }
  return {
    total: health.checks.length,
    okCount,
    warnCount,
    failCount,
    passed: health.passed,
  };
}
