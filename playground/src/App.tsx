import { useEffect, useState } from "react";
import { CodeOutputPane } from "./components/CodeOutputPane";
import { KdlEditorPane } from "./components/KdlEditorPane";
import {
  buildTargetSpecPayload,
  DEFAULT_TARGET_CONFIG,
  type CompileAndLintResult,
  type TargetConfig,
} from "./types";
import { usePyodideWorker } from "./worker/usePyodideWorker";
import "./App.css";

export const DEFAULT_KDL_SCHEMA = `// KDL 2.0 Schema DSL (v2.1) — HTML Catalogue Example
(item)struct QuoteAuthor {
    name { css ".author"; text; trim }
    tags { css-all ".tag"; text }
}

(list)struct QuoteCatalogue {
    @split-doc ".quote"
    quote_text { css ".text"; text; trim }
    author_info { nested QuoteAuthor }
}
`;

export type RightColumnTab = "code" | "test";

export function App() {
  const [kdlSrc, setKdlSrc] = useState<string>(DEFAULT_KDL_SCHEMA);
  const [target, setTarget] = useState<TargetConfig>(DEFAULT_TARGET_CONFIG);
  const [activeTab, setActiveTab] = useState<RightColumnTab>("code");
  const [theme, setTheme] = useState<"vs-dark" | "light">("vs-dark");
  const [compileResult, setCompileResult] =
    useState<CompileAndLintResult | null>(null);

  const { status, version, workerError, isCompiling, compileAndLint } =
    usePyodideWorker();

  useEffect(() => {
    if (status !== "ready") {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      const payload = buildTargetSpecPayload(target);
      compileAndLint(kdlSrc, payload)
        .then((res) => {
          if (!cancelled) {
            setCompileResult(res);
          }
        })
        .catch(() => {
          // Worker errors are surfaced via workerError state
        });
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [status, kdlSrc, target, compileAndLint]);

  const diagnostics = compileResult?.diagnostics ?? [];
  const structs = compileResult?.structs ?? [];

  return (
    <div className={`app-shell ${theme === "light" ? "theme-light" : "theme-dark"}`}>
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand-title">ssc-gen Playground</span>
          <span className="brand-tag">KDL 2.0 Schema DSL v2.1</span>
        </div>

        <div className="topbar-structs">
          {structs.map((s) => (
            <span
              key={s.name}
              className={`struct-pill ${s.is_rest ? "struct-rest" : "struct-html"}`}
              title={`Struct ${s.name} (${s.type})`}
            >
              ({s.type}) {s.name}
            </span>
          ))}
        </div>

        <div className="topbar-actions">
          <div
            className={`worker-status-badge status-${status}`}
            data-testid="worker-status-badge"
          >
            <span className="status-dot" />
            {status === "loading" && (
              <span>Loading Pyodide &amp; ssc-codegen…</span>
            )}
            {status === "ready" && (
              <span>Ready · ssc-codegen v{version ?? "0.45.0"}</span>
            )}
            {status === "error" && (
              <span title={workerError ?? undefined}>
                Runtime Error{workerError ? `: ${workerError}` : ""}
              </span>
            )}
          </div>

          <button
            type="button"
            className="theme-toggle-btn"
            onClick={() =>
              setTheme((prev) => (prev === "vs-dark" ? "light" : "vs-dark"))
            }
          >
            {theme === "vs-dark" ? "☀ Light" : "🌙 Dark"}
          </button>
        </div>
      </header>

      <main className="workspace-grid">
        <section className="workspace-col workspace-left">
          <KdlEditorPane
            value={kdlSrc}
            onChange={setKdlSrc}
            diagnostics={diagnostics}
            theme={theme}
            isCompiling={isCompiling}
          />
        </section>

        <section className="workspace-col workspace-right">
          <div className="right-tabs-header" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "code"}
              className={`right-tab-btn ${activeTab === "code" ? "active" : ""}`}
              onClick={() => setActiveTab("code")}
            >
              Generated Code
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "test"}
              className={`right-tab-btn ${activeTab === "test" ? "active" : ""}`}
              onClick={() => setActiveTab("test")}
            >
              Test &amp; Health (HTML)
            </button>
          </div>

          <div className="right-tab-body">
            {activeTab === "code" ? (
              <CodeOutputPane
                target={target}
                onChangeTarget={setTarget}
                result={compileResult}
                theme={theme}
              />
            ) : (
              <div
                className="html-test-placeholder"
                data-testid="html-test-tab-slot"
              >
                <h3>Test &amp; Health (HTML)</h3>
                <p>
                  Interactive HTML / Raw schema parser execution and selector
                  health check workspace.
                </p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
