import { describe, expect, it } from "vitest";
import playgroundBridgeSource from "../../../ssc_codegen/playground_bridge.py?raw";
import workerSource from "../worker/pyodide.worker.ts?raw";
import {
  getHtmlTestActionState,
  selectDefaultStructName,
  summarizeHealthReport,
  type StructHealthReport,
  type StructInfo,
} from "../types";

const CATALOGUE_STRUCTS: StructInfo[] = [
  { name: "QuoteAuthor", type: "item", is_rest: false },
  { name: "QuoteCatalogue", type: "list", is_rest: false },
];

const MIXED_STRUCTS: StructInfo[] = [
  { name: "QuoteAuthor", type: "item", is_rest: false },
  { name: "QuoteCatalogue", type: "list", is_rest: false },
  { name: "QuotesApi", type: "rest", is_rest: true },
];

const REST_ONLY_STRUCTS: StructInfo[] = [
  { name: "UserApi", type: "rest", is_rest: true },
];

describe("selectDefaultStructName", () => {
  it("auto-selects the primary (last) non-REST struct when no struct is chosen", () => {
    expect(selectDefaultStructName(CATALOGUE_STRUCTS)).toBe("QuoteCatalogue");
    expect(selectDefaultStructName(CATALOGUE_STRUCTS, null)).toBe(
      "QuoteCatalogue",
    );
    expect(selectDefaultStructName(MIXED_STRUCTS, null)).toBe("QuoteCatalogue");
  });

  it("preserves an explicitly selected nested or REST struct when present", () => {
    expect(selectDefaultStructName(CATALOGUE_STRUCTS, "QuoteAuthor")).toBe(
      "QuoteAuthor",
    );
    expect(selectDefaultStructName(MIXED_STRUCTS, "QuotesApi")).toBe(
      "QuotesApi",
    );
  });

  it("falls back to the primary non-REST struct if the previous selection was removed", () => {
    expect(selectDefaultStructName(CATALOGUE_STRUCTS, "DeletedStruct")).toBe(
      "QuoteCatalogue",
    );
  });

  it("falls back to the REST struct when the schema only declares REST structs", () => {
    expect(selectDefaultStructName(REST_ONLY_STRUCTS, null)).toBe("UserApi");
  });

  it("returns empty string when no structs are declared", () => {
    expect(selectDefaultStructName([], "QuoteCatalogue")).toBe("");
  });
});

describe("getHtmlTestActionState", () => {
  it("enables Run Parser and Check Health for HTML and Raw structs when worker is ready", () => {
    const state = getHtmlTestActionState(
      CATALOGUE_STRUCTS,
      null,
      true,
      false,
      false,
    );
    expect(state.activeStruct?.name).toBe("QuoteCatalogue");
    expect(state.isRestSelected).toBe(false);
    expect(state.canRun).toBe(true);
    expect(state.restNotice).toBeNull();
  });

  it("disables Run Parser and Check Health with an explanatory notice when a (rest)struct is selected", () => {
    const state = getHtmlTestActionState(
      MIXED_STRUCTS,
      "QuotesApi",
      true,
      false,
      false,
    );
    expect(state.activeStruct?.name).toBe("QuotesApi");
    expect(state.isRestSelected).toBe(true);
    expect(state.canRun).toBe(false);
    expect(state.restNotice).toContain("REST schema: lint & codegen only");
    expect(state.restNotice).toContain("QuotesApi");
  });

  it("disables actions when worker is loading, schema has errors, or a test is running", () => {
    expect(
      getHtmlTestActionState(CATALOGUE_STRUCTS, null, false, false, false)
        .canRun,
    ).toBe(false);
    expect(
      getHtmlTestActionState(CATALOGUE_STRUCTS, null, true, true, false).canRun,
    ).toBe(false);
    expect(
      getHtmlTestActionState(CATALOGUE_STRUCTS, null, true, false, true).canRun,
    ).toBe(false);
    expect(getHtmlTestActionState([], null, true, false, false).canRun).toBe(
      false,
    );
  });
});

describe("summarizeHealthReport", () => {
  it("counts ok, warn, and fail selector checks accurately", () => {
    const report: StructHealthReport = {
      struct_name: "ProductCard",
      passed: false,
      checks: [
        {
          path: "ProductCard.title",
          selector_type: "css",
          query: "h1.title",
          matches: 1,
          status: "ok",
          message: "(1 matches)",
        },
        {
          path: "ProductCard.discount",
          selector_type: "css",
          query: ".discount",
          matches: 0,
          status: "warn",
          message: "(0 matches, fallback='0%')",
        },
        {
          path: "ProductCard.badges",
          selector_type: "css-all",
          query: ".missing-badge",
          matches: 0,
          status: "fail",
          message: "(0 matches)",
        },
      ],
    };

    expect(summarizeHealthReport(report)).toEqual({
      total: 3,
      okCount: 1,
      warnCount: 1,
      failCount: 1,
      passed: false,
    });
  });

  it("returns zero counts when health report is null", () => {
    expect(summarizeHealthReport(null)).toEqual({
      total: 0,
      okCount: 0,
      warnCount: 0,
      failCount: 0,
      passed: false,
    });
  });
});

describe("test_html worker and Python bridge contract", () => {
  it("exposes test_html in playground_bridge.py and pyodide.worker.ts", () => {
    expect(playgroundBridgeSource).toContain("def test_html(");
    expect(playgroundBridgeSource).toContain("check_struct_health(");
    expect(workerSource).toContain("def _worker_test_html(");
    expect(workerSource).toContain('msg.action === "test_html"');
  });
});
