import playgroundBridgeSource from "../../../ssc_codegen/playground_bridge.py?raw";
import type {
  CompileAndLintResult,
  WorkerRequest,
  WorkerResponse,
} from "../types";

interface PyodideInstance {
  loadPackage(packages: string[]): Promise<void>;
  runPython(code: string): unknown;
  runPythonAsync(code: string): Promise<unknown>;
  globals: {
    get(name: string): (...args: unknown[]) => unknown;
  };
}

const PYODIDE_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.3/full/";
const PYODIDE_MODULE_URL = `${PYODIDE_INDEX_URL}pyodide.mjs`;

let pyodideReadyPromise: Promise<PyodideInstance> | null = null;

async function initPyodideRuntime(): Promise<PyodideInstance> {
  const { loadPyodide } = (await import(
    /* @vite-ignore */ PYODIDE_MODULE_URL
  )) as {
    loadPyodide: (options: { indexURL: string }) => Promise<PyodideInstance>;
  };

  const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });

  await pyodide.loadPackage([
    "micropip",
    "lxml",
    "beautifulsoup4",
    "soupsieve",
    "cssselect",
  ]);

  await pyodide.runPythonAsync(`
import micropip
await micropip.install(["kdlquery>=1.7.0", "ssc-codegen>=0.45.0"], deps=False)
`);

  pyodide.runPython(playgroundBridgeSource);
  pyodide.runPython(`
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
`);

  const getVersion = pyodide.globals.get("_worker_get_version");
  const version = String(getVersion());
  const readyMsg: WorkerResponse = { type: "ready", version };
  self.postMessage(readyMsg);

  return pyodide;
}

function ensurePyodide(): Promise<PyodideInstance> {
  if (!pyodideReadyPromise) {
    pyodideReadyPromise = initPyodideRuntime().catch((err: unknown) => {
      const message = err instanceof Error ? err.message : String(err);
      const errMsg: WorkerResponse = { type: "init_error", error: message };
      self.postMessage(errMsg);
      throw err;
    });
  }
  return pyodideReadyPromise;
}

// Start initializing Pyodide immediately when the worker spawns.
void ensurePyodide();

self.addEventListener("message", async (event: MessageEvent<WorkerRequest>) => {
  const msg = event.data;
  if (!msg || typeof msg.id !== "number") {
    return;
  }

  try {
    const pyodide = await ensurePyodide();
    if (msg.action === "compile_and_lint") {
      const fn = pyodide.globals.get("_worker_compile_and_lint");
      const rawJson = String(
        fn(msg.payload.kdlSrc, JSON.stringify(msg.payload.target)),
      );
      const result = JSON.parse(rawJson) as CompileAndLintResult;
      const response: WorkerResponse = {
        type: "result",
        id: msg.id,
        action: "compile_and_lint",
        result,
      };
      self.postMessage(response);
    }
  } catch (err: unknown) {
    const errorText = err instanceof Error ? err.message : String(err);
    const response: WorkerResponse = {
      type: "error",
      id: msg.id,
      error: errorText,
    };
    self.postMessage(response);
  }
});
