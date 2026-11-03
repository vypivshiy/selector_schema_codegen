import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CompileAndLintResult,
  TargetSpecPayload,
  TestHtmlResult,
  WorkerRequest,
  WorkerResponse,
  WorkerStatus,
} from "../types";

type PendingRequest =
  | {
      action: "compile_and_lint";
      resolve: (value: CompileAndLintResult) => void;
      reject: (reason: Error) => void;
    }
  | {
      action: "test_html";
      resolve: (value: TestHtmlResult) => void;
      reject: (reason: Error) => void;
    };

export interface PyodideWorkerHandle {
  status: WorkerStatus;
  version: string | null;
  workerError: string | null;
  isCompiling: boolean;
  isTestingHtml: boolean;
  compileAndLint: (
    kdlSrc: string,
    target: TargetSpecPayload,
  ) => Promise<CompileAndLintResult>;
  testHtml: (
    kdlSrc: string,
    htmlSrc: string,
    structName?: string | null,
  ) => Promise<TestHtmlResult>;
}

export function usePyodideWorker(): PyodideWorkerHandle {
  const [status, setStatus] = useState<WorkerStatus>("loading");
  const [version, setVersion] = useState<string | null>(null);
  const [workerError, setWorkerError] = useState<string | null>(null);
  const [isCompiling, setIsCompiling] = useState<boolean>(false);
  const [isTestingHtml, setIsTestingHtml] = useState<boolean>(false);

  const workerRef = useRef<Worker | null>(null);
  const requestIdRef = useRef<number>(0);
  const pendingRef = useRef<Map<number, PendingRequest>>(new Map());

  const syncBusyFlags = useCallback(() => {
    let hasCompile = false;
    let hasTestHtml = false;
    for (const [, pending] of pendingRef.current) {
      if (pending.action === "compile_and_lint") {
        hasCompile = true;
      } else if (pending.action === "test_html") {
        hasTestHtml = true;
      }
    }
    setIsCompiling(hasCompile);
    setIsTestingHtml(hasTestHtml);
  }, []);

  useEffect(() => {
    const worker = new Worker(
      new URL("./pyodide.worker.ts", import.meta.url),
      { type: "module" },
    );
    workerRef.current = worker;
    const pendingMap = pendingRef.current;

    worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
      const msg = event.data;
      if (!msg) return;

      if (msg.type === "ready") {
        setVersion(msg.version);
        setStatus("ready");
        setWorkerError(null);
        return;
      }

      if (msg.type === "init_error") {
        setStatus("error");
        setWorkerError(msg.error);
        return;
      }

      if (msg.type === "result") {
        const pending = pendingMap.get(msg.id);
        if (pending) {
          pendingMap.delete(msg.id);
          syncBusyFlags();
          if (
            msg.action === "compile_and_lint" &&
            pending.action === "compile_and_lint"
          ) {
            pending.resolve(msg.result);
          } else if (
            msg.action === "test_html" &&
            pending.action === "test_html"
          ) {
            pending.resolve(msg.result);
          }
        }
        return;
      }

      if (msg.type === "error") {
        const pending = pendingMap.get(msg.id);
        if (pending) {
          pendingMap.delete(msg.id);
          syncBusyFlags();
          pending.reject(new Error(msg.error));
        }
      }
    };

    worker.onerror = (err) => {
      setStatus("error");
      setWorkerError(err.message || "Pyodide WebWorker crashed.");
    };

    return () => {
      worker.terminate();
      workerRef.current = null;
      for (const [, pending] of pendingMap) {
        pending.reject(new Error("Worker terminated"));
      }
      pendingMap.clear();
    };
  }, [syncBusyFlags]);

  const compileAndLint = useCallback(
    (
      kdlSrc: string,
      target: TargetSpecPayload,
    ): Promise<CompileAndLintResult> => {
      const worker = workerRef.current;
      if (!worker) {
        return Promise.reject(new Error("Pyodide worker is not initialized"));
      }
      const id = ++requestIdRef.current;
      setIsCompiling(true);
      return new Promise<CompileAndLintResult>((resolve, reject) => {
        pendingRef.current.set(id, {
          action: "compile_and_lint",
          resolve,
          reject,
        });
        const request: WorkerRequest = {
          id,
          action: "compile_and_lint",
          payload: { kdlSrc, target },
        };
        worker.postMessage(request);
      });
    },
    [],
  );

  const testHtml = useCallback(
    (
      kdlSrc: string,
      htmlSrc: string,
      structName?: string | null,
    ): Promise<TestHtmlResult> => {
      const worker = workerRef.current;
      if (!worker) {
        return Promise.reject(new Error("Pyodide worker is not initialized"));
      }
      const id = ++requestIdRef.current;
      setIsTestingHtml(true);
      return new Promise<TestHtmlResult>((resolve, reject) => {
        pendingRef.current.set(id, {
          action: "test_html",
          resolve,
          reject,
        });
        const request: WorkerRequest = {
          id,
          action: "test_html",
          payload: { kdlSrc, htmlSrc, structName: structName ?? null },
        };
        worker.postMessage(request);
      });
    },
    [],
  );

  return {
    status,
    version,
    workerError,
    isCompiling,
    isTestingHtml,
    compileAndLint,
    testHtml,
  };
}
