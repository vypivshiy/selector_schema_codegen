import { useCallback, useMemo, useRef, useState, type ChangeEvent } from "react";
import Editor from "@monaco-editor/react";
import {
  getHtmlTestActionState,
  selectDefaultStructName,
  summarizeHealthReport,
  type StructInfo,
  type TestHtmlResult,
} from "../types";

export interface HtmlTestPaneProps {
  kdlSrc: string;
  htmlSrc: string;
  onChangeHtml: (nextHtml: string) => void;
  structs: StructInfo[];
  hasSchemaErrors: boolean;
  workerReady: boolean;
  isTesting: boolean;
  onRunTestHtml: (
    kdlSrc: string,
    htmlSrc: string,
    structName: string | null,
  ) => Promise<TestHtmlResult>;
  theme: "vs-dark" | "light";
}

export type HtmlTestResultTab = "json" | "health";

export function HtmlTestPane({
  kdlSrc,
  htmlSrc,
  onChangeHtml,
  structs,
  hasSchemaErrors,
  workerReady,
  isTesting,
  onRunTestHtml,
  theme,
}: HtmlTestPaneProps) {
  const [userSelectedStruct, setUserSelectedStruct] = useState<string | null>(
    null,
  );
  const [resultTab, setResultTab] = useState<HtmlTestResultTab>("json");
  const [testResult, setTestResult] = useState<TestHtmlResult | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [copiedJson, setCopiedJson] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeStructName = useMemo(
    () => selectDefaultStructName(structs, userSelectedStruct),
    [structs, userSelectedStruct],
  );

  const actionState = useMemo(
    () =>
      getHtmlTestActionState(
        structs,
        activeStructName,
        workerReady,
        hasSchemaErrors,
        isTesting,
      ),
    [structs, activeStructName, workerReady, hasSchemaErrors, isTesting],
  );

  const healthSummary = useMemo(
    () => summarizeHealthReport(testResult?.health ?? null),
    [testResult],
  );

  const formattedJson = useMemo(() => {
    if (!testResult || testResult.run_result === undefined) {
      return "";
    }
    if (testResult.run_result === null && testResult.run_error) {
      return "";
    }
    return JSON.stringify(testResult.run_result, null, 2);
  }, [testResult]);

  const handleExecute = useCallback(
    async (preferredTab: HtmlTestResultTab) => {
      if (!actionState.canRun || !actionState.activeStruct) {
        return;
      }
      setResultTab(preferredTab);
      try {
        const res = await onRunTestHtml(
          kdlSrc,
          htmlSrc,
          actionState.activeStruct.name,
        );
        setTestResult(res);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        setTestResult({
          ok: false,
          struct_name: actionState.activeStruct.name,
          run_result: null,
          run_error: message,
          elapsed_ms: 0,
          health: null,
        });
      }
    },
    [actionState, kdlSrc, htmlSrc, onRunTestHtml],
  );

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const content = typeof reader.result === "string" ? reader.result : "";
        onChangeHtml(content);
        setUploadedFileName(file.name);
      };
      reader.readAsText(file);
      event.target.value = "";
    },
    [onChangeHtml],
  );

  const handleCopyJson = useCallback(async () => {
    if (!formattedJson) return;
    try {
      await navigator.clipboard.writeText(formattedJson);
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 1500);
    } catch {
      // Clipboard API may be unavailable in restricted contexts
    }
  }, [formattedJson]);

  return (
    <div className="html-test-pane" data-testid="html-test-tab-slot">
      <div className="html-test-controls-bar">
        <div className="html-test-controls-left">
          <label className="target-option-label" htmlFor="test-struct-select">
            <span>Struct</span>
            <select
              id="test-struct-select"
              data-testid="struct-select"
              value={activeStructName}
              disabled={structs.length === 0}
              onChange={(e) => setUserSelectedStruct(e.target.value)}
            >
              {structs.length === 0 ? (
                <option value="">No structs declared</option>
              ) : (
                structs.map((s) => (
                  <option key={s.name} value={s.name}>
                    ({s.type}) {s.name}
                  </option>
                ))
              )}
            </select>
          </label>

          <button
            type="button"
            className="html-action-btn html-action-primary"
            data-testid="run-parser-btn"
            disabled={!actionState.canRun}
            onClick={() => void handleExecute("json")}
          >
            {isTesting && resultTab === "json" ? "Running…" : "▶ Run Parser"}
          </button>

          <button
            type="button"
            className="html-action-btn html-action-secondary"
            data-testid="check-health-btn"
            disabled={!actionState.canRun}
            onClick={() => void handleExecute("health")}
          >
            {isTesting && resultTab === "health"
              ? "Checking…"
              : "✓ Check Health"}
          </button>
        </div>

        <div className="html-test-controls-right">
          {uploadedFileName && (
            <span
              className="uploaded-file-badge"
              title={`Loaded from local file: ${uploadedFileName}`}
            >
              📄 {uploadedFileName}
            </span>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".html,.htm,.txt,text/html,text/plain"
            className="hidden-file-input"
            data-testid="html-file-input"
            onChange={handleFileChange}
          />
          <button
            type="button"
            className="upload-html-btn"
            data-testid="upload-html-btn"
            onClick={() => fileInputRef.current?.click()}
          >
            Upload .html
          </button>
        </div>
      </div>

      {actionState.isRestSelected && actionState.restNotice && (
        <div
          className="rest-struct-notice-banner"
          role="status"
          data-testid="rest-struct-notice"
        >
          <span className="badge badge-rest">
            REST schema: lint &amp; codegen only
          </span>
          <span>{actionState.restNotice}</span>
        </div>
      )}

      {!actionState.isRestSelected && hasSchemaErrors && (
        <div className="codegen-blocked-banner" role="status">
          Fix schema validation errors in the KDL editor before running HTML
          tests or selector health checks.
        </div>
      )}

      <div className="html-test-split">
        <div className="html-input-section">
          <div className="html-section-header">
            <span className="html-section-title">
              Sample HTML / Raw Text Input
            </span>
            <span className="html-section-meta">
              {actionState.activeStruct?.type === "raw"
                ? "(raw)struct plain-text input"
                : "HTML document"}
            </span>
          </div>
          <div className="editor-container">
            <Editor
              height="100%"
              language={
                actionState.activeStruct?.type === "raw" ? "plaintext" : "html"
              }
              theme={theme}
              value={htmlSrc}
              onChange={(val) => onChangeHtml(val ?? "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                automaticLayout: true,
                wordWrap: "on",
              }}
            />
          </div>
        </div>

        <div className="html-results-section">
          <div className="file-tabs-bar">
            <div
              className="file-tabs"
              role="tablist"
              aria-label="HTML test results"
            >
              <button
                type="button"
                role="tab"
                aria-selected={resultTab === "json"}
                data-testid="result-tab-json"
                className={`file-tab-btn ${resultTab === "json" ? "active" : ""}`}
                onClick={() => setResultTab("json")}
              >
                Extracted JSON
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={resultTab === "health"}
                data-testid="result-tab-health"
                className={`file-tab-btn ${resultTab === "health" ? "active" : ""}`}
                onClick={() => setResultTab("health")}
              >
                Selector Health
                {testResult?.health && (
                  <span
                    className={`health-tab-count ${
                      testResult.health.passed ? "count-ok" : "count-fail"
                    }`}
                  >
                    {healthSummary.okCount}/{healthSummary.total}
                  </span>
                )}
              </button>
            </div>

            <div className="html-results-toolbar-right">
              {testResult && (
                <span
                  className="execution-duration-badge"
                  data-testid="execution-duration"
                >
                  {testResult.elapsed_ms.toFixed(2)} ms
                </span>
              )}
              {resultTab === "json" && (
                <button
                  type="button"
                  className="copy-code-btn"
                  onClick={() => void handleCopyJson()}
                  disabled={!formattedJson}
                >
                  {copiedJson ? "Copied!" : "Copy JSON"}
                </button>
              )}
            </div>
          </div>

          {resultTab === "json" ? (
            <div className="html-json-output-body" data-testid="json-output-view">
              {testResult?.run_error && (
                <div
                  className="target-error-banner"
                  role="alert"
                  data-testid="run-error-banner"
                >
                  <strong>Execution Error:</strong> {testResult.run_error}
                </div>
              )}

              {!testResult ? (
                <div className="html-results-empty">
                  Click <strong>Run Parser</strong> to execute{" "}
                  <code>{activeStructName || "struct"}</code> against the HTML
                  input above.
                </div>
              ) : (
                <div className="editor-container">
                  <Editor
                    height="100%"
                    language="json"
                    theme={theme}
                    value={formattedJson}
                    options={{
                      readOnly: true,
                      minimap: { enabled: false },
                      fontSize: 13,
                      lineNumbers: "on",
                      scrollBeyondLastLine: false,
                      automaticLayout: true,
                      wordWrap: "on",
                    }}
                  />
                </div>
              )}
            </div>
          ) : (
            <div
              className="html-health-output-body"
              data-testid="health-output-view"
            >
              {!testResult?.health ? (
                <div className="html-results-empty">
                  Click <strong>Check Health</strong> to inspect selector match
                  counts for <code>{activeStructName || "struct"}</code>.
                </div>
              ) : (
                <div className="health-report-container">
                  <div className="health-summary-bar">
                    <span className="health-struct-label">
                      Struct: <code>{testResult.health.struct_name}</code>
                    </span>
                    <div className="pane-badges">
                      <span
                        className={`badge ${
                          testResult.health.passed ? "badge-ok" : "badge-error"
                        }`}
                        data-testid="health-overall-badge"
                      >
                        {testResult.health.passed ? "Passed" : "Failed"}
                      </span>
                      <span className="badge badge-ok">
                        {healthSummary.okCount} ok
                      </span>
                      {healthSummary.warnCount > 0 && (
                        <span className="badge badge-warning">
                          {healthSummary.warnCount} warn
                        </span>
                      )}
                      {healthSummary.failCount > 0 && (
                        <span className="badge badge-error">
                          {healthSummary.failCount} fail
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="health-table-scroll">
                    <table
                      className="health-checks-table"
                      data-testid="health-checks-table"
                    >
                      <thead>
                        <tr>
                          <th>Path</th>
                          <th>Type</th>
                          <th>Query</th>
                          <th>Matches</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {testResult.health.checks.map((check, idx) => (
                          <tr
                            key={`${check.path}-${check.query}-${idx}`}
                            className={`health-row health-row-${check.status}`}
                          >
                            <td className="health-cell-mono">{check.path}</td>
                            <td className="health-cell-mono">
                              <span className="selector-type-tag">
                                {check.selector_type}
                              </span>
                            </td>
                            <td className="health-cell-mono">
                              <code>{check.query || "—"}</code>
                            </td>
                            <td className="health-cell-matches">
                              {check.matches}
                            </td>
                            <td className="health-cell-status">
                              <span
                                className={`health-status-pill status-pill-${check.status}`}
                              >
                                {check.status}
                              </span>
                              {check.message && (
                                <span className="health-status-msg">
                                  {check.message}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
