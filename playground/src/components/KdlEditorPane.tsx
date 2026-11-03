import { useCallback, useEffect, useRef, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type * as Monaco from "monaco-editor";
import { registerKdl2Completions } from "../editor/kdl2Completion";
import {
  KDL2_DARK_THEME,
  KDL2_LANGUAGE_ID,
  KDL2_LIGHT_THEME,
  registerKdl2Language,
} from "../editor/kdl2Monarch";
import { applyDiagnosticsToModel } from "../editor/linterMarkers";
import type { SscDiagnostic } from "../types";

export interface KdlEditorPaneProps {
  value: string;
  onChange: (nextValue: string) => void;
  diagnostics: SscDiagnostic[];
  theme: "vs-dark" | "light";
  isCompiling: boolean;
}

export function KdlEditorPane({
  value,
  onChange,
  diagnostics,
  theme,
  isCompiling,
}: KdlEditorPaneProps) {
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<typeof Monaco | null>(null);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(true);

  const errorCount = diagnostics.filter((d) => d.severity === "error").length;
  const warningCount = diagnostics.filter(
    (d) => d.severity === "warning",
  ).length;

  const handleBeforeMount = useCallback((monacoInstance: typeof Monaco) => {
    registerKdl2Language(monacoInstance);
    registerKdl2Completions(monacoInstance);
  }, []);

  const handleMount: OnMount = useCallback(
    (editor, monacoInstance) => {
      editorRef.current = editor;
      monacoRef.current = monacoInstance;
      const model = editor.getModel();
      if (model) {
        applyDiagnosticsToModel(monacoInstance, model, diagnostics);
      }
    },
    [diagnostics],
  );

  useEffect(() => {
    const editor = editorRef.current;
    const monacoInstance = monacoRef.current;
    if (!editor || !monacoInstance) return;
    const model = editor.getModel();
    if (model) {
      applyDiagnosticsToModel(monacoInstance, model, diagnostics);
    }
  }, [diagnostics]);

  const handleJumpToDiagnostic = useCallback((diag: SscDiagnostic) => {
    const editor = editorRef.current;
    if (!editor) return;
    const lineNumber = Math.max(diag.span?.start?.line ?? 1, 1);
    const column = Math.max(diag.span?.start?.column ?? 1, 1);
    editor.setPosition({ lineNumber, column });
    editor.revealLineInCenter(lineNumber);
    editor.focus();
  }, []);

  return (
    <div className="pane kdl-editor-pane">
      <div className="pane-header">
        <div className="pane-title-group">
          <span className="pane-title">KDL 2.0 Schema</span>
          <span className="pane-subtitle">schema.kdl</span>
        </div>
        <div className="pane-badges">
          {isCompiling && (
            <span className="badge badge-neutral">Validating…</span>
          )}
          {!isCompiling && errorCount === 0 && warningCount === 0 && (
            <span className="badge badge-ok">0 issues</span>
          )}
          {errorCount > 0 && (
            <span className="badge badge-error">
              {errorCount} {errorCount === 1 ? "error" : "errors"}
            </span>
          )}
          {warningCount > 0 && (
            <span className="badge badge-warning">
              {warningCount} {warningCount === 1 ? "warning" : "warnings"}
            </span>
          )}
        </div>
      </div>

      <div className="editor-container">
        <Editor
          height="100%"
          language={KDL2_LANGUAGE_ID}
          theme={theme === "vs-dark" ? KDL2_DARK_THEME : KDL2_LIGHT_THEME}
          value={value}
          beforeMount={handleBeforeMount}
          onMount={handleMount}
          onChange={(v) => onChange(v ?? "")}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            wordWrap: "on",
          }}
        />
      </div>

      <div
        className={`diagnostics-drawer ${drawerOpen ? "open" : "collapsed"}`}
      >
        <button
          type="button"
          className="diagnostics-drawer-header"
          onClick={() => setDrawerOpen((prev) => !prev)}
        >
          <span>
            Diagnostics ({diagnostics.length})
          </span>
          <span className="drawer-toggle-label">
            {drawerOpen ? "Hide ▼" : "Show ▲"}
          </span>
        </button>

        {drawerOpen && (
          <div className="diagnostics-list" role="list">
            {diagnostics.length === 0 ? (
              <div className="diagnostics-empty">
                No schema validation errors or warnings.
              </div>
            ) : (
              diagnostics.map((diag, idx) => (
                <button
                  key={`${diag.code}-${diag.span.start.line}-${diag.span.start.column}-${idx}`}
                  type="button"
                  role="listitem"
                  className={`diagnostic-item diagnostic-${diag.severity}`}
                  onClick={() => handleJumpToDiagnostic(diag)}
                >
                  <div className="diagnostic-item-top">
                    <span
                      className={`diagnostic-severity severity-${diag.severity}`}
                    >
                      {diag.severity.toUpperCase()}
                    </span>
                    <span className="diagnostic-code">{diag.code}</span>
                    <span className="diagnostic-location">
                      Ln {diag.span.start.line}, Col {diag.span.start.column}
                    </span>
                  </div>
                  <div className="diagnostic-message">{diag.message}</div>
                  {diag.hint && (
                    <div className="diagnostic-hint">Hint: {diag.hint}</div>
                  )}
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
