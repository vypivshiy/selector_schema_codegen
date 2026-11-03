import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { CodeOutputPane } from "./components/CodeOutputPane";
import { HtmlTestPane } from "./components/HtmlTestPane";
import { KdlEditorPane } from "./components/KdlEditorPane";
import {
  DEFAULT_HTML_MINIFY_OPTIONS,
  type HtmlMinifyOptions,
} from "./htmlFormat";
import { useCopyFeedback } from "./hooks/useCopyFeedback";
import {
  DEFAULT_PRESET,
  findMatchingPresetId,
  getPresetById,
  PRESETS,
} from "./presets";
import {
  buildTargetSpecPayload,
  DEFAULT_TARGET_CONFIG,
  type CompileAndLintResult,
  type TargetConfig,
} from "./types";
import {
  decodeWorkspaceFromHash,
  encodeWorkspaceToHash,
  loadDraftFromStorage,
  resolveInitialWorkspaceState,
  saveDraftToStorage,
} from "./urlState";
import { usePyodideWorker } from "./worker/usePyodideWorker";
import "./App.css";

export const DEFAULT_KDL_SCHEMA = DEFAULT_PRESET.kdl;
export const DEFAULT_SAMPLE_HTML = DEFAULT_PRESET.html;

export type RightColumnTab = "code" | "test";

export function App() {
  const initialDraft = useMemo(() => loadDraftFromStorage(), []);

  const [kdlSrc, setKdlSrc] = useState<string>(
    () => initialDraft?.kdl ?? DEFAULT_KDL_SCHEMA,
  );
  const [htmlSrc, setHtmlSrc] = useState<string>(
    () => initialDraft?.html ?? DEFAULT_SAMPLE_HTML,
  );
  const [target, setTarget] = useState<TargetConfig>(
    () => initialDraft?.target ?? DEFAULT_TARGET_CONFIG,
  );
  const [isHydrated, setIsHydrated] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<RightColumnTab>("code");
  const [theme, setTheme] = useState<"vs-dark" | "light">("vs-dark");
  const [compileResult, setCompileResult] =
    useState<CompileAndLintResult | null>(null);
  const [shareIncludeHtml, setShareIncludeHtml] = useState<boolean>(false);
  const [shareMinifyOptions, setShareMinifyOptions] =
    useState<HtmlMinifyOptions>(() => ({ ...DEFAULT_HTML_MINIFY_OPTIONS }));
  const [showShareOptions, setShowShareOptions] = useState<boolean>(false);
  const [lastShareLength, setLastShareLength] = useState<number | null>(null);
  const {
    copied: shareCopied,
    copyText: copyShareText,
    triggerCopied: triggerShareCopied,
  } = useCopyFeedback(2000);

  const {
    status,
    version,
    workerError,
    isCompiling,
    isTestingHtml,
    compileAndLint,
    testHtml,
  } = usePyodideWorker();

  // Restore workspace from URL #state=... hash (or localStorage fallback) on startup
  useEffect(() => {
    let cancelled = false;
    resolveInitialWorkspaceState()
      .then((resolved) => {
        if (cancelled) return;
        setKdlSrc(resolved.state.kdl);
        setHtmlSrc(resolved.state.html);
        setTarget(resolved.state.target);
        setIsHydrated(true);
      })
      .catch(() => {
        if (!cancelled) {
          setIsHydrated(true);
        }
      });

    const handleHashChange = () => {
      if (!window.location.hash) return;
      void decodeWorkspaceFromHash(window.location.hash).then((decoded) => {
        if (decoded && !cancelled) {
          setKdlSrc(decoded.kdl);
          setHtmlSrc(decoded.html);
          setTarget(decoded.target);
        }
      });
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => {
      cancelled = true;
      window.removeEventListener("hashchange", handleHashChange);
    };
  }, []);

  // Automatically persist workspace edits to localStorage once initial state is hydrated
  useEffect(() => {
    if (!isHydrated) {
      return;
    }
    saveDraftToStorage({
      kdl: kdlSrc,
      html: htmlSrc,
      target,
    });
  }, [isHydrated, kdlSrc, htmlSrc, target]);

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
        .catch((err: unknown) => {
          if (!cancelled) {
            const message = err instanceof Error ? err.message : String(err);
            setCompileResult({
              ok: false,
              diagnostics: [],
              structs: [],
              files: {},
              target_error: message,
            });
          }
        });
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [status, kdlSrc, target, compileAndLint]);

  const activePresetId = useMemo(
    () => findMatchingPresetId(kdlSrc, htmlSrc) ?? "",
    [kdlSrc, htmlSrc],
  );

  const activePreset = useMemo(
    () => (activePresetId ? getPresetById(activePresetId) : undefined),
    [activePresetId],
  );

  const handlePresetChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const preset = getPresetById(event.target.value);
      if (!preset) {
        return;
      }
      setKdlSrc(preset.kdl);
      setHtmlSrc(preset.html);
      if (typeof window !== "undefined" && window.location.hash) {
        window.history.replaceState(
          null,
          "",
          `${window.location.pathname}${window.location.search}`,
        );
      }
    },
    [],
  );

  const handleShareUrl = useCallback(async () => {
    const hash = await encodeWorkspaceToHash(
      {
        kdl: kdlSrc,
        html: htmlSrc,
        target,
      },
      {
        includeHtml: shareIncludeHtml,
        minifyHtml: true,
        minifyOptions: shareMinifyOptions,
      },
    );
    if (typeof window !== "undefined") {
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}${hash}`,
      );
      setLastShareLength(window.location.href.length);
      const copiedOk = await copyShareText(window.location.href);
      if (!copiedOk) {
        triggerShareCopied();
      }
    } else {
      setLastShareLength(hash.length);
      triggerShareCopied();
    }
  }, [
    kdlSrc,
    htmlSrc,
    target,
    shareIncludeHtml,
    shareMinifyOptions,
    copyShareText,
    triggerShareCopied,
  ]);

  const toggleMinifyFlag = useCallback((key: keyof HtmlMinifyOptions) => {
    setShareMinifyOptions((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  }, []);

  const diagnostics = compileResult?.diagnostics ?? [];
  const structs = compileResult?.structs ?? [];
  const hasSchemaErrors = diagnostics.some((d) => d.severity === "error");

  return (
    <div
      className={`app-shell ${theme === "light" ? "theme-light" : "theme-dark"}`}
    >
      <header className="topbar">
        <div className="topbar-left">
          <div className="topbar-brand">
            <span className="brand-title">ssc-gen Playground</span>
            <span className="brand-tag">KDL 2.0 Schema DSL v2.1</span>
          </div>

          <label className="topbar-preset-label" htmlFor="preset-select">
            <span className="topbar-preset-caption">Examples</span>
            <select
              id="preset-select"
              className="topbar-preset-select"
              data-testid="preset-select"
              value={activePresetId}
              title={activePreset?.description ?? "Select a curated KDL + HTML example"}
              onChange={handlePresetChange}
            >
              {activePresetId === "" && (
                <option value="" disabled>
                  Custom / Edited Workspace
                </option>
              )}
              {PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.title}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="topbar-structs">
          {structs.map((s) => {
            const isNested = (s.referenced_by?.length ?? 0) > 0;
            const roleLabel = s.is_rest
              ? "REST client"
              : isNested
                ? `nested in ${s.referenced_by?.join(", ")}`
                : "root entrypoint";
            return (
              <span
                key={s.name}
                className={`struct-pill ${
                  s.is_rest
                    ? "struct-rest"
                    : isNested
                      ? "struct-nested"
                      : "struct-html"
                }`}
                title={`(${s.type}) ${s.name} — ${roleLabel}`}
              >
                {s.is_rest ? "⇄ " : isNested ? "↳ " : "★ "}({s.type}) {s.name}
              </span>
            );
          })}
        </div>

        <div className="topbar-actions">
          <div
            className={`worker-status-badge status-${workerError ? "error" : status}`}
            data-testid="worker-status-badge"
          >
            <span className="status-dot" />
            {status === "loading" && !workerError && (
              <span>Loading Pyodide &amp; ssc-codegen…</span>
            )}
            {status === "ready" && !workerError && (
              <span>Ready · ssc-codegen v{version ?? "0.45.0"}</span>
            )}
            {(status === "error" || Boolean(workerError)) && (
              <span title={workerError ?? undefined}>
                Runtime Error{workerError ? `: ${workerError}` : ""}
              </span>
            )}
          </div>

          <div className="share-control-group">
            <select
              className="share-mode-select"
              data-testid="share-mode-select"
              value={shareIncludeHtml ? "schema+html" : "schema"}
              title="Choose whether Share URL encodes only the KDL schema or also the minified HTML"
              onChange={(e) => {
                const nextInclude = e.target.value === "schema+html";
                setShareIncludeHtml(nextInclude);
                if (!nextInclude) {
                  setShowShareOptions(false);
                }
              }}
            >
              <option value="schema">Share: Schema only</option>
              <option value="schema+html">Share: Schema + Minified HTML</option>
            </select>

            {shareIncludeHtml && (
              <button
                type="button"
                className={`share-settings-btn ${showShareOptions ? "active" : ""}`}
                data-testid="share-options-toggle-btn"
                title="Choose which HTML elements to strip when minifying HTML for URL sharing"
                onClick={() => setShowShareOptions((prev) => !prev)}
              >
                ⚙ Strip
              </button>
            )}

            <button
              type="button"
              className={`share-url-btn ${shareCopied ? "share-copied" : ""}`}
              data-testid="share-url-btn"
              title="Compress workspace into URL #state=... and copy shareable link"
              onClick={() => void handleShareUrl()}
            >
              {shareCopied
                ? `✓ Copied (${lastShareLength ?? 0} chars)`
                : "🔗 Share URL"}
            </button>

            {showShareOptions && shareIncludeHtml && (
              <div
                className="share-options-popover"
                data-testid="share-options-popover"
              >
                <div className="share-options-title">
                  HTML Minification for URL
                </div>
                <label className="share-option-check">
                  <input
                    type="checkbox"
                    checked={shareMinifyOptions.stripScriptsAndStyles}
                    onChange={() => toggleMinifyFlag("stripScriptsAndStyles")}
                  />
                  <span>
                    Strip <code>&lt;script&gt;</code>, <code>&lt;style&gt;</code>,{" "}
                    <code>&lt;noscript&gt;</code>
                  </span>
                </label>
                <label className="share-option-check">
                  <input
                    type="checkbox"
                    checked={shareMinifyOptions.stripSvg}
                    onChange={() => toggleMinifyFlag("stripSvg")}
                  />
                  <span>
                    Strip <code>&lt;svg&gt;</code> icons &amp; vectors
                  </span>
                </label>
                <label className="share-option-check">
                  <input
                    type="checkbox"
                    checked={shareMinifyOptions.stripHead}
                    onChange={() => toggleMinifyFlag("stripHead")}
                  />
                  <span>
                    Strip <code>&lt;head&gt;</code> block
                  </span>
                </label>
                <label className="share-option-check">
                  <input
                    type="checkbox"
                    checked={shareMinifyOptions.stripComments}
                    onChange={() => toggleMinifyFlag("stripComments")}
                  />
                  <span>
                    Strip HTML comments <code>&lt;!-- ... --&gt;</code>
                  </span>
                </label>
                <label className="share-option-check">
                  <input
                    type="checkbox"
                    checked={shareMinifyOptions.collapseWhitespace}
                    onChange={() => toggleMinifyFlag("collapseWhitespace")}
                  />
                  <span>
                    Collapse whitespace (auto-formats on open)
                  </span>
                </label>
              </div>
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
              <HtmlTestPane
                kdlSrc={kdlSrc}
                htmlSrc={htmlSrc}
                onChangeHtml={setHtmlSrc}
                structs={structs}
                hasSchemaErrors={hasSchemaErrors}
                workerReady={status === "ready"}
                isTesting={isTestingHtml}
                onRunTestHtml={testHtml}
                theme={theme}
              />
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
