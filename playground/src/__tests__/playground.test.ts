import { describe, expect, it } from "vitest";
import playgroundBridgeSource from "../../../ssc_codegen/playground_bridge.py?raw";
import workerSource from "../worker/pyodide.worker.ts?raw";
import { diagnosticsToMarkers } from "../editor/linterMarkers";
import {
  buildTargetSpecPayload,
  DEFAULT_TARGET_CONFIG,
  getMonacoLanguageForFile,
  normalizeTargetConfig,
  type SscDiagnostic,
  type TargetConfig,
} from "../types";

describe("normalizeTargetConfig", () => {
  it("coerces aiohttp + sync to async while preserving other options", () => {
    expect(
      normalizeTargetConfig({
        ...DEFAULT_TARGET_CONFIG,
        py_http_client: "aiohttp",
        http_io: "sync",
      }).http_io,
    ).toBe("async");

    expect(
      normalizeTargetConfig({
        ...DEFAULT_TARGET_CONFIG,
        py_http_client: "httpx",
        http_io: "sync",
      }).http_io,
    ).toBe("sync");
  });
});

describe("buildTargetSpecPayload", () => {
  it("includes Python-specific options when lang is python", () => {
    const cfg: TargetConfig = {
      ...DEFAULT_TARGET_CONFIG,
      lang: "python",
      lib: "bs4",
      bs4_parser: "html.parser",
      py_http_client: "httpx2",
      http_io: "sync",
      separate_runtime: true,
    };
    expect(buildTargetSpecPayload(cfg)).toEqual({
      lang: "python",
      lib: "bs4",
      bs4_parser: "html.parser",
      http_client: "httpx2",
      http_io: "sync",
      separate_runtime: true,
      emit_runtime: true,
    });
  });

  it("omits bs4_parser when Python HTML lib is not bs4", () => {
    const cfg: TargetConfig = {
      ...DEFAULT_TARGET_CONFIG,
      lang: "python",
      lib: "lxml",
      bs4_parser: "html5lib",
    };
    const payload = buildTargetSpecPayload(cfg);
    expect(payload.lib).toBe("lxml");
    expect(payload.bs4_parser).toBeNull();
  });

  it("adjusts aiohttp + sync to async", () => {
    const cfg: TargetConfig = {
      ...DEFAULT_TARGET_CONFIG,
      lang: "python",
      py_http_client: "aiohttp",
      http_io: "sync",
    };
    const payload = buildTargetSpecPayload(cfg);
    expect(payload.http_client).toBe("aiohttp");
    expect(payload.http_io).toBe("async");
  });

  it("includes only JS HTTP client options when lang is js", () => {
    const cfg: TargetConfig = {
      ...DEFAULT_TARGET_CONFIG,
      lang: "js",
      js_http_client: "axios",
      separate_runtime: true,
    };
    expect(buildTargetSpecPayload(cfg)).toEqual({
      lang: "js",
      http_client: "axios",
      emit_runtime: true,
    });
  });

  it("omits Python and JS options when lang is go or rust", () => {
    expect(
      buildTargetSpecPayload({ ...DEFAULT_TARGET_CONFIG, lang: "go" }),
    ).toEqual({
      lang: "go",
      emit_runtime: true,
      package: "main",
    });

    expect(
      buildTargetSpecPayload({ ...DEFAULT_TARGET_CONFIG, lang: "rust" }),
    ).toEqual({
      lang: "rust",
      http_client: "reqwest",
      emit_runtime: true,
    });
  });
});

describe("getMonacoLanguageForFile", () => {
  it("maps emitted parser and runtime filenames to Monaco languages", () => {
    expect(getMonacoLanguageForFile("parser.py", "python")).toBe("python");
    expect(getMonacoLanguageForFile("sscgen_runtime.py", "python")).toBe(
      "python",
    );
    expect(getMonacoLanguageForFile("parser.js", "js")).toBe("javascript");
    expect(getMonacoLanguageForFile("parser.go", "go")).toBe("go");
    expect(getMonacoLanguageForFile("sscgen_runtime.go", "go")).toBe("go");
    expect(getMonacoLanguageForFile("parser.rs", "rust")).toBe("rust");
    expect(getMonacoLanguageForFile("sscgen_runtime.rs", "rust")).toBe("rust");
  });
});

describe("diagnosticsToMarkers", () => {
  it("converts 1-based SscDiagnostic spans and hints to Monaco markers", () => {
    const diagnostics: SscDiagnostic[] = [
      {
        code: "E100",
        severity: "error",
        message: "'to-int' does not accept DOCUMENT; expected STRING",
        hint: "insert 'text' or 'attr' before 'to-int'",
        span: {
          start: { offset: 42, line: 4, column: 9 },
          end: { offset: 48, line: 4, column: 15 },
        },
      },
      {
        code: "W003",
        severity: "warning",
        message:
          "External file imports ('imports') are not supported in the single-buffer browser playground.",
        hint: "Inline shared definitions directly into the active schema buffer.",
        span: {
          start: { offset: 0, line: 1, column: 1 },
          end: { offset: 0, line: 1, column: 1 },
        },
      },
    ];

    const markers = diagnosticsToMarkers(diagnostics);
    expect(markers).toHaveLength(2);

    expect(markers[0]).toEqual({
      severity: 8,
      startLineNumber: 4,
      startColumn: 9,
      endLineNumber: 4,
      endColumn: 15,
      code: "E100",
      message:
        "'to-int' does not accept DOCUMENT; expected STRING\nHint: insert 'text' or 'attr' before 'to-int'",
      source: "ssc-gen",
    });

    // Zero-width span on line 1 is expanded to endColumn = startColumn + 1
    expect(markers[1].severity).toBe(4);
    expect(markers[1].code).toBe("W003");
    expect(markers[1].startLineNumber).toBe(1);
    expect(markers[1].startColumn).toBe(1);
    expect(markers[1].endLineNumber).toBe(1);
    expect(markers[1].endColumn).toBe(2);
    expect(markers[1].message).toContain("Hint: Inline shared definitions");
  });
});

describe("Pyodide worker bridge bundle", () => {
  it("bundles ssc_codegen/playground_bridge.py with compile_and_lint", () => {
    expect(playgroundBridgeSource).toContain("def compile_and_lint(");
    expect(workerSource).toContain(
      'micropip.install(["kdlquery>=1.7.0", "ssc-codegen>=0.45.0"], deps=False)',
    );
  });
});

