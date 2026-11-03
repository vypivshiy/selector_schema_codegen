import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CompileAndLintResult,
  TargetSpecPayload,
  WorkerRequest,
  WorkerResponse,
  WorkerStatus,
} from "../types";

interface PendingRequest {
  resolve: (value: CompileAndLintResult) => void;
  reject: (reason: Error) => void;
}

export interface PyodideWorkerHandle {
  status: WorkerStatus;
  version: string | null;
  workerError: string | null;
  isCompiling: boolean;
  compileAndLint: (
    kdlSrc: string,
    target: TargetSpecPayload,
  ) => Promise<CompileAndLintResult>;
}

export function usePyodideWorker(): PyodideWorkerHandle {
  const [status, setStatus] = useState<WorkerStatus>("loading");
  const [version, setVersion] = useState<string | null>(null);
  const [workerError, setWorkerError] = useState<string | null>(null);
  const [isCompiling, setIsCompiling] = useState<boolean>(false);

  const workerRef = useRef<Worker | null>(null);
  const requestIdRef = useRef<number>(0);
  const pendingRef = useRef<Map<number, PendingRequest>>(new Map());

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
          if (pendingMap.size === 0) {
            setIsCompiling(false);
          }
          pending.resolve(msg.result);
        }
        return;
      }

      if (msg.type === "error") {
        const pending = pendingMap.get(msg.id);
        if (pending) {
          pendingMap.delete(msg.id);
          if (pendingMap.size === 0) {
            setIsCompiling(false);
          }
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
  }, []);

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
        pendingRef.current.set(id, { resolve, reject });
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

  return {
    status,
    version,
    workerError,
    isCompiling,
    compileAndLint,
  };
}
