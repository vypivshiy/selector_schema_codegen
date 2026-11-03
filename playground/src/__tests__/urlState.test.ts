import { describe, expect, it } from "vitest";
import { formatHtml, minifyHtmlForShare } from "../htmlFormat";
import {
  DEFAULT_PRESET,
  findMatchingPresetId,
  getPresetById,
  PRESETS,
} from "../presets";
import { DEFAULT_TARGET_CONFIG, type TargetConfig } from "../types";
import {
  decodeFromBase64Url,
  decodeWorkspaceFromHash,
  encodeToBase64Url,
  encodeWorkspaceToHash,
  loadDraftFromStorage,
  normalizeTargetConfig,
  resolveInitialWorkspaceState,
  saveDraftToStorage,
  type StorageLike,
  type WorkspaceState,
} from "../urlState";

function createMemoryStorage(): StorageLike & { store: Map<string, string> } {
  const store = new Map<string, string>();
  return {
    store,
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
  };
}

describe("Curated presets integrity", () => {
  it("contains 5-6 curated presets covering html, table, raw, and rest", () => {
    expect(PRESETS.length).toBeGreaterThanOrEqual(5);
    expect(PRESETS.length).toBeLessThanOrEqual(6);

    const categories = new Set(PRESETS.map((p) => p.category));
    expect(categories.has("html")).toBe(true);
    expect(categories.has("table")).toBe(true);
    expect(categories.has("raw")).toBe(true);
    expect(categories.has("rest")).toBe(true);

    const ids = new Set<string>();
    for (const preset of PRESETS) {
      expect(preset.id.length).toBeGreaterThan(0);
      expect(ids.has(preset.id)).toBe(false);
      ids.add(preset.id);

      expect(preset.title.length).toBeGreaterThan(0);
      expect(preset.description.length).toBeGreaterThan(0);
      expect(preset.kdl).toContain("struct ");
      expect(preset.html.length).toBeGreaterThan(0);
      expect(getPresetById(preset.id)).toEqual(preset);
      expect(findMatchingPresetId(preset.kdl, preset.html)).toBe(preset.id);
    }

    expect(DEFAULT_PRESET).toEqual(PRESETS[0]);
    expect(getPresetById("non-existent-preset")).toBeUndefined();
    expect(findMatchingPresetId("// edited", "<div></div>")).toBeUndefined();
  });
});

describe("Base64url helpers", () => {
  it("round-trips arbitrary binary buffers without padding or unsafe URL chars", () => {
    const sample = new Uint8Array([0, 1, 2, 62, 63, 128, 254, 255]);
    const encoded = encodeToBase64Url(sample);
    expect(encoded).not.toMatch(/[+/=]/);
    const decoded = decodeFromBase64Url(encoded);
    expect(decoded).toEqual(sample);
  });

  it("returns null for invalid base64url strings", () => {
    expect(decodeFromBase64Url("")).toBeNull();
    expect(decodeFromBase64Url("not valid base64!!!")).toBeNull();
  });
});

describe("URL #state=... workspace codec", () => {
  it("compresses and losslessly round-trips workspace state via deflate-raw", async () => {
    const customTarget: TargetConfig = {
      lang: "rust",
      lib: "lxml",
      bs4_parser: "html.parser",
      py_http_client: "httpx2",
      js_http_client: "axios",
      http_io: "sync",
      separate_runtime: true,
    };
    const original: WorkspaceState = {
      kdl: PRESETS[0].kdl,
      html: PRESETS[0].html,
      target: customTarget,
    };

    const hash = await encodeWorkspaceToHash(original);
    expect(hash.startsWith("#state=")).toBe(true);
    expect(hash.slice("#state=".length)).not.toMatch(/[+/=]/);

    const restored = await decodeWorkspaceFromHash(hash);
    expect(restored).toEqual(original);

    // Also accepts hash without leading '#'
    const restoredWithoutHashPrefix = await decodeWorkspaceFromHash(
      hash.slice(1),
    );
    expect(restoredWithoutHashPrefix).toEqual(original);
  });

  it("round-trips every curated preset losslessly", async () => {
    for (const preset of PRESETS) {
      const state: WorkspaceState = {
        kdl: preset.kdl,
        html: preset.html,
        target: DEFAULT_TARGET_CONFIG,
      };
      const hash = await encodeWorkspaceToHash(state);
      const decoded = await decodeWorkspaceFromHash(hash);
      expect(decoded).toEqual(state);
    }
  });

  it("supports uncompressed base64url fallback payloads", async () => {
    const state: WorkspaceState = {
      kdl: '(item)struct Demo { title { css "h1"; text } }',
      html: "<h1>Fallback Demo</h1>",
      target: { ...DEFAULT_TARGET_CONFIG, lang: "go" },
    };

    const uncompressedHash = await encodeWorkspaceToHash(state, {
      forceUncompressed: true,
    });
    expect(uncompressedHash.startsWith("#state=")).toBe(true);

    const decoded = await decodeWorkspaceFromHash(uncompressedHash);
    expect(decoded).toEqual(state);
  });

  it("returns null for empty, unrelated, or corrupted hashes", async () => {
    expect(await decodeWorkspaceFromHash("")).toBeNull();
    expect(await decodeWorkspaceFromHash("#")).toBeNull();
    expect(await decodeWorkspaceFromHash("#tab=test")).toBeNull();
    expect(await decodeWorkspaceFromHash("#state=")).toBeNull();
    expect(await decodeWorkspaceFromHash("#state=***invalid***")).toBeNull();
    // Valid base64url for `{}` (missing kdl and html fields)
    expect(await decodeWorkspaceFromHash("#state=e30")).toBeNull();
  });
});

describe("localStorage draft persistence & URL hash precedence", () => {
  it("saves and loads workspace drafts from storage", () => {
    const storage = createMemoryStorage();
    const draft: WorkspaceState = {
      kdl: PRESETS[2].kdl,
      html: PRESETS[2].html,
      target: {
        ...DEFAULT_TARGET_CONFIG,
        lang: "js",
        js_http_client: "axios",
      },
    };

    expect(loadDraftFromStorage(storage)).toBeNull();
    expect(saveDraftToStorage(draft, storage)).toBe(true);
    expect(loadDraftFromStorage(storage)).toEqual(draft);
  });

  it("normalizes partial or invalid target fields on load", () => {
    const normalized = normalizeTargetConfig({
      lang: "python",
      py_http_client: "aiohttp",
      http_io: "sync",
      lib: "invalid-lib",
    });
    expect(normalized.lang).toBe("python");
    expect(normalized.lib).toBe("bs4");
    expect(normalized.py_http_client).toBe("aiohttp");
    expect(normalized.http_io).toBe("async");
  });

  it("gives URL #state=... precedence over localStorage when present", async () => {
    const storage = createMemoryStorage();
    const storageDraft: WorkspaceState = {
      kdl: '// from localStorage\n(item)struct LocalDraft { a { css "p"; text } }',
      html: "<p>From Storage</p>",
      target: { ...DEFAULT_TARGET_CONFIG, lang: "python" },
    };
    const sharedHashState: WorkspaceState = {
      kdl: '// from shared URL\n(item)struct SharedLink { b { css "h2"; text } }',
      html: "<h2>From Shared URL</h2>",
      target: { ...DEFAULT_TARGET_CONFIG, lang: "rust" },
    };

    saveDraftToStorage(storageDraft, storage);
    const sharedHash = await encodeWorkspaceToHash(sharedHashState);

    const resolvedFromHash = await resolveInitialWorkspaceState({
      hash: sharedHash,
      storage,
    });
    expect(resolvedFromHash.source).toBe("hash");
    expect(resolvedFromHash.state).toEqual(sharedHashState);

    // When hash is empty, falls back to localStorage draft
    const resolvedFromStorage = await resolveInitialWorkspaceState({
      hash: "",
      storage,
    });
    expect(resolvedFromStorage.source).toBe("storage");
    expect(resolvedFromStorage.state).toEqual(storageDraft);

    // When hash is malformed, falls back to localStorage draft
    const resolvedFromInvalidHash = await resolveInitialWorkspaceState({
      hash: "#state=e30",
      storage,
    });
    expect(resolvedFromInvalidHash.source).toBe("storage");
    expect(resolvedFromInvalidHash.state).toEqual(storageDraft);

    // When both hash and storage are empty, falls back to default preset
    const emptyStorage = createMemoryStorage();
    const resolvedDefault = await resolveInitialWorkspaceState({
      hash: "",
      storage: emptyStorage,
    });
    expect(resolvedDefault.source).toBe("default");
    expect(resolvedDefault.state.kdl).toBe(DEFAULT_PRESET.kdl);
    expect(resolvedDefault.state.html).toBe(DEFAULT_PRESET.html);
  });

  it("produces compact schema-only URLs and auto-formats minified HTML on decode", async () => {
    const noisyHtml = `<!DOCTYPE html>
<html>
  <head>
    <title>Books to Scrape</title>
    <style>.card { color: red; }</style>
    <script>console.log("analytics");</script>
  </head>
  <body>
    <!-- catalog comment -->
    <svg viewBox="0 0 10 10"><path d="M0 0"/></svg>
    <div class="col-lg-3">
      <h3><a href="book1.html">Book One</a></h3>
      <p class="price_color">£51.77</p>
    </div>
  </body>
</html>`;

    const state: WorkspaceState = {
      kdl: '(list)struct Book { @split-doc { css-all ".col-lg-3" }; title { css "h3 a"; text } }',
      html: noisyHtml,
      target: DEFAULT_TARGET_CONFIG,
    };

    const fullHash = await encodeWorkspaceToHash(state, {
      includeHtml: true,
      minifyHtml: false,
    });
    const minifiedHash = await encodeWorkspaceToHash(state, {
      includeHtml: true,
      minifyHtml: true,
      minifyOptions: {
        stripScriptsAndStyles: true,
        stripSvg: true,
        stripHead: true,
        stripComments: true,
        collapseWhitespace: true,
      },
    });
    const schemaOnlyHash = await encodeWorkspaceToHash(state, {
      includeHtml: false,
    });

    expect(minifiedHash.length).toBeLessThan(fullHash.length);
    expect(schemaOnlyHash.length).toBeLessThan(minifiedHash.length);

    // Decoding minifiedHash automatically pretty-prints the HTML across multiple lines
    const decodedMinified = await decodeWorkspaceFromHash(minifiedHash);
    expect(decodedMinified).not.toBeNull();
    expect(decodedMinified!.kdl).toBe(state.kdl);
    expect(decodedMinified!.html).not.toContain("<script>");
    expect(decodedMinified!.html).not.toContain("<style>");
    expect(decodedMinified!.html).not.toContain("<svg");
    expect(decodedMinified!.html).not.toContain("<!--");
    expect(decodedMinified!.html).toContain("\n  <div class=\"col-lg-3\">");
    expect(decodedMinified!.html).toContain("Book One");
  });

  it("minifies and pretty-prints HTML via minifyHtmlForShare and formatHtml", () => {
    const raw =
      '<div><!-- comment --><script>alert(1)</script><svg><circle/></svg>  <section>  <h1>  Hello World  </h1>  <p>Text</p>  </section></div>';
    const minified = minifyHtmlForShare(raw);
    expect(minified).toBe(
      "<div><section><h1> Hello World </h1><p>Text</p></section></div>",
    );

    const formatted = formatHtml(minified);
    expect(formatted).toBe(
      ["<div>", "  <section>", "    <h1>Hello World</h1>", "    <p>Text</p>", "  </section>", "</div>"].join(
        "\n",
      ),
    );
  });
});
