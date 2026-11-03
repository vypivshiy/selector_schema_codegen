import type * as Monaco from "monaco-editor";
import type { SscDiagnostic } from "../types";

export const MONACO_MARKER_OWNER = "ssc-gen-linter";

// Numeric values matching monaco.MarkerSeverity (Error = 8, Warning = 4)
const SEVERITY_ERROR = 8 as Monaco.MarkerSeverity;
const SEVERITY_WARNING = 4 as Monaco.MarkerSeverity;

/**
 * Convert `SscDiagnostic` records from `compile_and_lint` into 1-based
 * Monaco Editor `IMarkerData` objects with error codes and remediation hints.
 */
export function diagnosticsToMarkers(
  diagnostics: SscDiagnostic[],
): Monaco.editor.IMarkerData[] {
  return diagnostics.map((d) => {
    const startLine = Math.max(d.span?.start?.line ?? 1, 1);
    const startCol = Math.max(d.span?.start?.column ?? 1, 1);
    const rawEndLine = d.span?.end?.line ?? startLine;
    const endLine = Math.max(rawEndLine, startLine);
    const rawEndCol = d.span?.end?.column ?? startCol + 1;
    const endCol =
      endLine === startLine && rawEndCol <= startCol
        ? startCol + 1
        : Math.max(rawEndCol, 1);

    const formattedMessage = d.hint
      ? `${d.message}\nHint: ${d.hint}`
      : d.message;

    return {
      severity: d.severity === "error" ? SEVERITY_ERROR : SEVERITY_WARNING,
      startLineNumber: startLine,
      startColumn: startCol,
      endLineNumber: endLine,
      endColumn: endCol,
      code: d.code,
      message: formattedMessage,
      source: "ssc-gen",
    };
  });
}

/**
 * Apply diagnostics markers to a Monaco `ITextModel`.
 */
export function applyDiagnosticsToModel(
  monacoInstance: typeof Monaco,
  model: Monaco.editor.ITextModel,
  diagnostics: SscDiagnostic[],
): void {
  const markers = diagnosticsToMarkers(diagnostics);
  monacoInstance.editor.setModelMarkers(model, MONACO_MARKER_OWNER, markers);
}
