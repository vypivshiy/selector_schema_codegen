import { DEFAULT_PRESET } from "./presets";
import {
  DEFAULT_TARGET_CONFIG,
  type Bs4ParserEngine,
  type HttpIoMode,
  type JsHttpClient,
  type PythonHtmlLib,
  type PythonHttpClient,
  type TargetConfig,
  type TargetLang,
} from "./types";

export const WORKSPACE_STORAGE_KEY = "ssc_codegen_playground_draft_v1";
export const HASH_STATE_PARAM = "state";

export interface WorkspaceState {
  kdl: string;
  html: string;
  target: TargetConfig;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem?(key: string): void;
}

const VALID_LANGS: ReadonlySet<TargetLang> = new Set([
  "python",
  "js",
  "go",
  "rust",
]);
const VALID_PY_LIBS: ReadonlySet<PythonHtmlLib> = new Set([
  "bs4",
  "lxml",
  "parsel",
  "slax",
]);
const VALID_BS4_PARSERS: ReadonlySet<Bs4ParserEngine> = new Set([
  "lxml",
  "html.parser",
  "html5lib",
]);
const VALID_PY_HTTP_CLIENTS: ReadonlySet<PythonHttpClient> = new Set([
  "httpx",
  "httpx2",
  "aiohttp",
  "requests",
]);
const VALID_JS_HTTP_CLIENTS: ReadonlySet<JsHttpClient> = new Set([
  "fetch",
  "axios",
]);
const VALID_HTTP_IO_MODES: ReadonlySet<HttpIoMode> = new Set([
  "both",
  "sync",
  "async",
]);

export function getDefaultWorkspaceState(): WorkspaceState {
  return {
    kdl: DEFAULT_PRESET.kdl,
    html: DEFAULT_PRESET.html,
    target: { ...DEFAULT_TARGET_CONFIG },
  };
}

/**
 * Sanitize an untrusted target configuration object, filling missing or invalid
 * properties from `DEFAULT_TARGET_CONFIG`.
 */
export function normalizeTargetConfig(raw: unknown): TargetConfig {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_TARGET_CONFIG };
  }
  const obj = raw as Record<string, unknown>;
  const lang = VALID_LANGS.has(obj.lang as TargetLang)
    ? (obj.lang as TargetLang)
    : DEFAULT_TARGET_CONFIG.lang;
  const lib = VALID_PY_LIBS.has(obj.lib as PythonHtmlLib)
    ? (obj.lib as PythonHtmlLib)
    : DEFAULT_TARGET_CONFIG.lib;
  const bs4_parser = VALID_BS4_PARSERS.has(obj.bs4_parser as Bs4ParserEngine)
    ? (obj.bs4_parser as Bs4ParserEngine)
    : DEFAULT_TARGET_CONFIG.bs4_parser;
  const py_http_client = VALID_PY_HTTP_CLIENTS.has(
    obj.py_http_client as PythonHttpClient,
  )
    ? (obj.py_http_client as PythonHttpClient)
    : DEFAULT_TARGET_CONFIG.py_http_client;
  const js_http_client = VALID_JS_HTTP_CLIENTS.has(
    obj.js_http_client as JsHttpClient,
  )
    ? (obj.js_http_client as JsHttpClient)
    : DEFAULT_TARGET_CONFIG.js_http_client;
  let http_io = VALID_HTTP_IO_MODES.has(obj.http_io as HttpIoMode)
    ? (obj.http_io as HttpIoMode)
    : DEFAULT_TARGET_CONFIG.http_io;
  if (py_http_client === "aiohttp" && http_io === "sync") {
    http_io = "async";
  }
  const separate_runtime =
    typeof obj.separate_runtime === "boolean"
      ? obj.separate_runtime
      : DEFAULT_TARGET_CONFIG.separate_runtime;

  return {
    lang,
    lib,
    bs4_parser,
    py_http_client,
    js_http_client,
    http_io,
    separate_runtime,
  };
}

function parseWorkspacePayload(rawJson: string): WorkspaceState | null {
  try {
    const parsed: unknown = JSON.parse(rawJson);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const record = parsed as Record<string, unknown>;
    if (typeof record.kdl !== "string" || typeof record.html !== "string") {
      return null;
    }
    return {
      kdl: record.kdl,
      html: record.html,
      target: normalizeTargetConfig(record.target),
    };
  } catch {
    return null;
  }
}

/**
 * Encode a `Uint8Array` into a URL-safe base64url string without `=` padding.
 */
export function encodeToBase64Url(bytes: Uint8Array): string {
  const chunkSize = 0x8000;
  const chunks: string[] = [];
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const slice = bytes.subarray(i, i + chunkSize);
    chunks.push(String.fromCharCode(...slice));
  }
  const binary = chunks.join("");
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Decode a URL-safe base64url string back into a `Uint8Array`, returning `null`
 * if the string is malformed.
 */
export function decodeFromBase64Url(encoded: string): Uint8Array | null {
  const trimmed = encoded.trim();
  if (!trimmed || !/^[A-Za-z0-9\-_=]+$/.test(trimmed)) {
    return null;
  }
  try {
    const base64 = trimmed.replace(/-/g, "+").replace(/_/g, "/");
    const padLen = (4 - (base64.length % 4)) % 4;
    const padded = base64 + "=".repeat(padLen);
    const binary = atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
  } catch {
    return null;
  }
}

async function runTransformStream(
  input: Uint8Array,
  stream: ReadableWritablePair<Uint8Array, Uint8Array>,
): Promise<Uint8Array> {
  const writer = stream.writable.getWriter();
  const reader = stream.readable.getReader();

  const writeTask = (async () => {
    const copy = new Uint8Array(input.byteLength);
    copy.set(input);
    await writer.write(copy);
    await writer.close();
  })();

  const chunks: Uint8Array[] = [];
  let totalLength = 0;
  const readTask = (async () => {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) {
        chunks.push(value);
        totalLength += value.byteLength;
      }
    }
  })();

  await Promise.all([writeTask, readTask]);

  const output = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

export interface EncodeHashOptions {
  /** Force uncompressed base64url encoding (for fallback testing). */
  forceUncompressed?: boolean;
}

/**
 * Compress and encode a `WorkspaceState` into `#state=<base64url>` using
 * `CompressionStream("deflate-raw")` with an uncompressed base64url fallback.
 */
export async function encodeWorkspaceToHash(
  state: WorkspaceState,
  options?: EncodeHashOptions,
): Promise<string> {
  const payload = JSON.stringify({
    kdl: state.kdl,
    html: state.html,
    target: normalizeTargetConfig(state.target),
  });
  const utf8Bytes = new TextEncoder().encode(payload);

  if (
    !options?.forceUncompressed &&
    typeof CompressionStream === "function"
  ) {
    try {
      const compressed = await runTransformStream(
        utf8Bytes,
        new CompressionStream("deflate-raw"),
      );
      return `#${HASH_STATE_PARAM}=${encodeToBase64Url(compressed)}`;
    } catch {
      // Fall back to uncompressed base64url if deflate-raw is unsupported
    }
  }

  return `#${HASH_STATE_PARAM}=${encodeToBase64Url(utf8Bytes)}`;
}

function extractStateTokenFromHash(hash: string): string | null {
  if (!hash) {
    return null;
  }
  const stripped = hash.startsWith("#") ? hash.slice(1) : hash;
  if (!stripped) {
    return null;
  }
  const prefix = `${HASH_STATE_PARAM}=`;
  if (stripped.startsWith(prefix)) {
    const raw = stripped.slice(prefix.length);
    const ampIdx = raw.indexOf("&");
    return ampIdx === -1 ? raw : raw.slice(0, ampIdx);
  }
  try {
    const params = new URLSearchParams(stripped);
    return params.get(HASH_STATE_PARAM);
  } catch {
    return null;
  }
}

/**
 * Decode a `#state=<base64url>` hash string back into a `WorkspaceState`.
 * Supports both `DecompressionStream("deflate-raw")` payloads and uncompressed
 * base64url JSON fallbacks. Returns `null` when the hash is empty or invalid.
 */
export async function decodeWorkspaceFromHash(
  hash: string,
): Promise<WorkspaceState | null> {
  const token = extractStateTokenFromHash(hash);
  if (!token) {
    return null;
  }
  const bytes = decodeFromBase64Url(token);
  if (!bytes || bytes.byteLength === 0) {
    return null;
  }

  // Fast-path check if payload is uncompressed UTF-8 JSON (`{...}`)
  if (bytes[0] === 0x7b && bytes[bytes.length - 1] === 0x7d) {
    const directText = new TextDecoder().decode(bytes);
    const directState = parseWorkspacePayload(directText);
    if (directState) {
      return directState;
    }
  }

  if (typeof DecompressionStream === "function") {
    try {
      const decompressed = await runTransformStream(
        bytes,
        new DecompressionStream("deflate-raw"),
      );
      const text = new TextDecoder().decode(decompressed);
      const state = parseWorkspacePayload(text);
      if (state) {
        return state;
      }
    } catch {
      // Fall through to uncompressed UTF-8 decode attempt
    }
  }

  try {
    const fallbackText = new TextDecoder().decode(bytes);
    return parseWorkspacePayload(fallbackText);
  } catch {
    return null;
  }
}

function getDefaultStorage(): StorageLike | null {
  try {
    if (typeof globalThis !== "undefined" && "localStorage" in globalThis) {
      return globalThis.localStorage;
    }
  } catch {
    // Accessing localStorage can throw in sandboxed iframes
  }
  return null;
}

/**
 * Persist the current workspace draft (`kdl`, `html`, `target`) to `localStorage`.
 */
export function saveDraftToStorage(
  state: WorkspaceState,
  storage: StorageLike | null = getDefaultStorage(),
): boolean {
  if (!storage) {
    return false;
  }
  try {
    const serialized = JSON.stringify({
      kdl: state.kdl,
      html: state.html,
      target: normalizeTargetConfig(state.target),
    });
    storage.setItem(WORKSPACE_STORAGE_KEY, serialized);
    return true;
  } catch {
    return false;
  }
}

/**
 * Load a previously saved workspace draft from `localStorage`.
 */
export function loadDraftFromStorage(
  storage: StorageLike | null = getDefaultStorage(),
): WorkspaceState | null {
  if (!storage) {
    return null;
  }
  try {
    const raw = storage.getItem(WORKSPACE_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    return parseWorkspacePayload(raw);
  } catch {
    return null;
  }
}

export interface ResolveInitialWorkspaceOptions {
  hash?: string;
  storage?: StorageLike | null;
  defaultState?: WorkspaceState;
}

export interface ResolvedWorkspaceResult {
  state: WorkspaceState;
  source: "hash" | "storage" | "default";
}

/**
 * Resolve the startup workspace state, giving precedence to `#state=...` in
 * `window.location.hash` when present and valid, falling back to `localStorage`
 * draft persistence, and finally to `defaultState` (the first curated preset).
 */
export async function resolveInitialWorkspaceState(
  options?: ResolveInitialWorkspaceOptions,
): Promise<ResolvedWorkspaceResult> {
  const effectiveHash =
    options?.hash !== undefined
      ? options.hash
      : typeof window !== "undefined"
        ? window.location.hash
        : "";

  if (effectiveHash) {
    const fromHash = await decodeWorkspaceFromHash(effectiveHash);
    if (fromHash) {
      return { state: fromHash, source: "hash" };
    }
  }

  const fromStorage = loadDraftFromStorage(options?.storage);
  if (fromStorage) {
    return { state: fromStorage, source: "storage" };
  }

  return {
    state: options?.defaultState ?? getDefaultWorkspaceState(),
    source: "default",
  };
}
