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
  type: StructKind | string;
  is_rest: boolean;
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

export type WorkerStatus = "loading" | "ready" | "error";

export type WorkerRequest = {
  id: number;
  action: "compile_and_lint";
  payload: {
    kdlSrc: string;
    target: TargetSpecPayload;
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
 * Convert UI `TargetConfig` state into the contextual `TargetSpecPayload`
 * sent to `compile_and_lint`, omitting language-specific options that do not
 * apply to the active target language.
 */
export function buildTargetSpecPayload(
  config: TargetConfig,
): TargetSpecPayload {
  switch (config.lang) {
    case "python": {
      const effectiveHttpIo: HttpIoMode =
        config.py_http_client === "aiohttp" && config.http_io === "sync"
          ? "async"
          : config.http_io;
      return {
        lang: "python",
        lib: config.lib,
        bs4_parser: config.lib === "bs4" ? config.bs4_parser : null,
        http_client: config.py_http_client,
        http_io: effectiveHttpIo,
        separate_runtime: config.separate_runtime,
        emit_runtime: true,
      };
    }
    case "js":
      return {
        lang: "js",
        http_client: config.js_http_client,
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
