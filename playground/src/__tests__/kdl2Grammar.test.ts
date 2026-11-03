import { describe, expect, it, vi } from "vitest";
import type * as Monaco from "monaco-editor";
import {
  ALL_KDL2_COMPLETION_TEMPLATES,
  createKdl2CompletionProvider,
  getKdl2CompletionItems,
  INSERT_AS_SNIPPET,
  registerKdl2Completions,
} from "../editor/kdl2Completion";
import {
  classifyKdl2Token,
  KDL2_DARK_THEME,
  KDL2_DARK_THEME_DATA,
  KDL2_DECLARATIONS,
  KDL2_DIRECTIVES,
  KDL2_LANGUAGE_ID,
  KDL2_LIGHT_THEME,
  KDL2_LIGHT_THEME_DATA,
  KDL2_PIPELINE_OPS,
  KDL2_PREDICATE_OPS,
  registerKdl2Language,
  tokenizeKdl2,
} from "../editor/kdl2Monarch";

describe("KDL 2.0 literals vs invalid KDL 1.0 bare literals", () => {
  it("tokenizes KDL 2.0 #-prefixed literals (#true, #false, #null, #inf, #-inf, #nan) as valid language constants", () => {
    expect(classifyKdl2Token("#true")).toBe("constant.language.boolean");
    expect(classifyKdl2Token("#false")).toBe("constant.language.boolean");
    expect(classifyKdl2Token("#null")).toBe("constant.language.null");
    expect(classifyKdl2Token("#inf")).toBe("constant.language.numeric");
    expect(classifyKdl2Token("#-inf")).toBe("constant.language.numeric");
    expect(classifyKdl2Token("#nan")).toBe("constant.language.numeric");

    const tokens = tokenizeKdl2(
      "fallback #true #false #null #inf #-inf #nan",
    );
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      ["fallback", "support.function.pipeline"],
      ["#true", "constant.language.boolean"],
      ["#false", "constant.language.boolean"],
      ["#null", "constant.language.null"],
      ["#inf", "constant.language.numeric"],
      ["#-inf", "constant.language.numeric"],
      ["#nan", "constant.language.numeric"],
    ]);
  });

  it("tokenizes bare KDL 1.0 literals (true, false, null, inf, -inf, nan) as invalid", () => {
    for (const bare of ["true", "false", "null", "inf", "-inf", "nan"]) {
      expect(classifyKdl2Token(bare)).toBe("invalid");
    }

    const tokens = tokenizeKdl2("fallback true false null inf -inf nan");
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      ["fallback", "support.function.pipeline"],
      ["true", "invalid"],
      ["false", "invalid"],
      ["null", "invalid"],
      ["inf", "invalid"],
      ["-inf", "invalid"],
      ["nan", "invalid"],
    ]);
  });

  it("does not misclassify hyphenated identifiers starting with literal prefixes as invalid", () => {
    expect(classifyKdl2Token("true-value")).toBe("identifier");
    expect(classifyKdl2Token("null-coalesce")).toBe("identifier");
    expect(classifyKdl2Token("nan-safe")).toBe("identifier");
    expect(classifyKdl2Token("inf-bound")).toBe("identifier");
  });
});

describe("KDL 2.0 raw strings and multi-line strings", () => {
  it("tracks opening # counts on single-line raw strings (#\"...\"# and ##\"...\"##)", () => {
    const singleHash = tokenizeKdl2('re #"^price:\\s+"(\\d+)"$"#');
    expect(singleHash.map((t) => [t.value, t.type])).toEqual([
      ["re", "support.function.pipeline"],
      ['#"', "string.raw.delim"],
      ['^price:\\s+"(\\d+)"$', "string.raw"],
      ['"#', "string.raw.delim"],
    ]);

    // Inside ##"..."##, an inner "# with only 1 hash must NOT close the raw string
    const doubleHash = tokenizeKdl2(
      're ##"pattern with "quote" and "# inner hash-quote"## trim',
    );
    expect(doubleHash.map((t) => [t.value, t.type])).toEqual([
      ["re", "support.function.pipeline"],
      ['##"', "string.raw.delim"],
      ['pattern with "quote" and "# inner hash-quote', "string.raw"],
      ['"##', "string.raw.delim"],
      ["trim", "support.function.pipeline"],
    ]);
  });

  it("tracks opening # counts on multi-line raw strings (#\"\"\"...\"\"\"# and ##\"\"\"...\"\"\"##)", () => {
    const src = [
      '##"""',
      'line with "quotes" and """ and """# inside',
      '"""##',
      "text",
    ].join("\n");

    const tokens = tokenizeKdl2(src);
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      ['##"""', "string.raw.delim"],
      ['line with "quotes" and """ and """# inside', "string.raw"],
      ['"""##', "string.raw.delim"],
      ["text", "support.function.pipeline"],
    ]);
  });

  it("tokenizes KDL 2.0 multi-line strings (\"\"\"...\"\"\") across lines with escapes and placeholders", () => {
    const src = [
      '@request name="create_user" response=UserJson """',
      "POST https://api.example.com/users/{{org_id}}",
      'Content-Type: "application/json"\\n',
      '"""',
    ].join("\n");

    const tokens = tokenizeKdl2(src);
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      ["@request", "annotation.directive"],
      ["name", "attribute.name"],
      ["=", "delimiter"],
      ['"', "string.quote"],
      ["create_user", "string"],
      ['"', "string.quote"],
      ["response", "attribute.name"],
      ["=", "delimiter"],
      ["UserJson", "identifier"],
      ['"""', "string.quote"],
      ["POST https://api.example.com/users/", "string"],
      ["{{org_id}}", "variable.placeholder"],
      ['Content-Type: "application/json"', "string"],
      ["\\n", "string.escape"],
      ['"""', "string.quote"],
    ]);
  });

  it("highlights {{placeholder}} templates inside strings while keeping regex {min,max} quantifiers as raw string content", () => {
    const regexTokens = tokenizeKdl2('re #"^\\d{2,4}-{{YEAR}}$"#');
    expect(regexTokens.map((t) => [t.value, t.type])).toEqual([
      ["re", "support.function.pipeline"],
      ['#"', "string.raw.delim"],
      ["^\\d{2,4}-", "string.raw"],
      ["{{YEAR}}", "variable.placeholder"],
      ["$", "string.raw"],
      ['"#', "string.raw.delim"],
    ]);
  });
});

describe("KDL 2.0 comments (//, nested /* ... */, and /- slashdash)", () => {
  it("tokenizes line comments and /- slashdash comments", () => {
    const tokens = tokenizeKdl2(
      '// top comment\n/- css ".deprecated"\ncss ".active"',
    );
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      ["// top comment", "comment"],
      ["/-", "comment.slashdash"],
      ["css", "support.function.pipeline"],
      ['"', "string.quote"],
      [".deprecated", "string"],
      ['"', "string.quote"],
      ["css", "support.function.pipeline"],
      ['"', "string.quote"],
      [".active", "string"],
      ['"', "string.quote"],
    ]);
  });

  it("supports arbitrarily nested /* ... /* ... */ ... */ block comments", () => {
    const src =
      "/* outer start /* nested level 2 /* level 3 */ back to 2 */ still in outer */ struct Book";
    const tokens = tokenizeKdl2(src);
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      [
        "/* outer start /* nested level 2 /* level 3 */ back to 2 */ still in outer */",
        "comment",
      ],
      ["struct", "keyword.declaration"],
      ["Book", "identifier"],
    ]);
  });
});

describe("ssc-gen DSL v2.1 semantic token classification", () => {
  it("classifies struct, json, fn, and nullable type annotations as type.annotation", () => {
    const annotations = [
      "(item)",
      "(list)",
      "(table)",
      "(dict)",
      "(flat)",
      "(raw)",
      "(rest)",
      "(array)",
      "(str?)",
      "(BookItem?)",
    ];
    for (const ann of annotations) {
      expect(classifyKdl2Token(ann)).toBe("type.annotation");
    }

    const combined = tokenizeKdl2("(item)struct Quote { (array)tags str? }");
    expect(combined.map((t) => [t.value, t.type])).toEqual([
      ["(item)", "type.annotation"],
      ["struct", "keyword.declaration"],
      ["Quote", "identifier"],
      ["{", "delimiter"],
      ["(array)", "type.annotation"],
      ["tags", "identifier"],
      ["str?", "type.primitive"],
      ["}", "delimiter"],
    ]);
  });

  it("classifies top-level declarations as keyword.declaration", () => {
    for (const decl of KDL2_DECLARATIONS) {
      expect(classifyKdl2Token(decl)).toBe("keyword.declaration");
    }
  });

  it("classifies @ directives and @error:<suffix> variants as annotation.directive", () => {
    for (const dir of KDL2_DIRECTIVES) {
      expect(classifyKdl2Token(dir)).toBe("annotation.directive");
    }
    expect(classifyKdl2Token("@error:rate_limit")).toBe("annotation.directive");
    expect(classifyKdl2Token("@error:not-found")).toBe("annotation.directive");

    const errorLine = tokenizeKdl2(
      '@error:rate_limit 429 RateLimitJson "retry_after" code="RATE_LIMIT"',
    );
    expect(errorLine.map((t) => [t.value, t.type])).toEqual([
      ["@error:rate_limit", "annotation.directive"],
      ["429", "number"],
      ["RateLimitJson", "identifier"],
      ['"', "string.quote"],
      ["retry_after", "string"],
      ['"', "string.quote"],
      ["code", "attribute.name"],
      ["=", "delimiter"],
      ['"', "string.quote"],
      ["RATE_LIMIT", "string"],
      ['"', "string.quote"],
    ]);
  });

  it("classifies all built-in pipeline operations as support.function.pipeline", () => {
    for (const op of KDL2_PIPELINE_OPS) {
      expect(classifyKdl2Token(op)).toBe("support.function.pipeline");
    }
  });

  it("classifies all predicate blocks and operators as keyword.operator.predicate", () => {
    for (const pred of KDL2_PREDICATE_OPS) {
      expect(classifyKdl2Token(pred)).toBe("keyword.operator.predicate");
    }
  });

  it("classifies UPPER_CASE defines in both scalar assignments and pipeline references as constant.define", () => {
    const scalarDef = tokenizeKdl2('define BASE_URL="https://example.com"');
    expect(scalarDef.map((t) => [t.value, t.type])).toEqual([
      ["define", "keyword.declaration"],
      ["BASE_URL", "constant.define"],
      ["=", "delimiter"],
      ['"', "string.quote"],
      ["https://example.com", "string"],
      ['"', "string.quote"],
    ]);

    const blockDefAndRef = tokenizeKdl2(
      'define EXTRACT_HREF { css "a"; attr "href" }\nstruct Link { url { EXTRACT_HREF } }',
    );
    const defineTokens = blockDefAndRef.filter(
      (t) => t.type === "constant.define",
    );
    expect(defineTokens.map((t) => t.value)).toEqual([
      "EXTRACT_HREF",
      "EXTRACT_HREF",
    ]);
  });

  it("classifies custom !Namespace.op extension calls and KDL 2.0 numbers", () => {
    const tokens = tokenizeKdl2(
      "slice 0x10 0o77 0b1010 -3.14e+2 1_000; !Utils.slugify",
    );
    expect(tokens.map((t) => [t.value, t.type])).toEqual([
      ["slice", "support.function.pipeline"],
      ["0x10", "number.hex"],
      ["0o77", "number.octal"],
      ["0b1010", "number.binary"],
      ["-3.14e+2", "number.float"],
      ["1_000", "number"],
      [";", "delimiter"],
      ["!Utils.slugify", "function.extension"],
    ]);
  });
});

describe("Monaco theme rules and language registration", () => {
  it("defines distinct theme rules for all semantic token classes in kdl2-dark and kdl2-light", () => {
    const requiredTokens = [
      "comment",
      "comment.slashdash",
      "keyword.declaration",
      "type.annotation",
      "type.primitive",
      "annotation.directive",
      "support.function.pipeline",
      "keyword.operator.predicate",
      "function.extension",
      "constant.define",
      "constant.language.boolean",
      "constant.language.null",
      "constant.language.numeric",
      "string",
      "string.raw",
      "string.raw.delim",
      "variable.placeholder",
      "invalid",
    ];

    const darkRuleTokens = new Set(KDL2_DARK_THEME_DATA.rules.map((r) => r.token));
    const lightRuleTokens = new Set(
      KDL2_LIGHT_THEME_DATA.rules.map((r) => r.token),
    );

    for (const token of requiredTokens) {
      expect(darkRuleTokens.has(token)).toBe(true);
      expect(lightRuleTokens.has(token)).toBe(true);
    }
  });

  it("registers kdl2 language, Monarch tokens provider, themes, and completions on Monaco instance", () => {
    const register = vi.fn();
    const setLanguageConfiguration = vi.fn();
    const setMonarchTokensProvider = vi.fn();
    const registerCompletionItemProvider = vi.fn(() => ({
      dispose: vi.fn(),
    }));
    const defineTheme = vi.fn();

    const mockMonaco = {
      languages: {
        getLanguages: () => [],
        register,
        setLanguageConfiguration,
        setMonarchTokensProvider,
        registerCompletionItemProvider,
      },
      editor: {
        defineTheme,
      },
    } as unknown as typeof Monaco;

    registerKdl2Language(mockMonaco);
    registerKdl2Completions(mockMonaco);
    // Second call on same instance should be idempotent
    registerKdl2Completions(mockMonaco);

    expect(register).toHaveBeenCalledWith(
      expect.objectContaining({ id: KDL2_LANGUAGE_ID, extensions: [".kdl"] }),
    );
    expect(setLanguageConfiguration).toHaveBeenCalledWith(
      KDL2_LANGUAGE_ID,
      expect.any(Object),
    );
    expect(setMonarchTokensProvider).toHaveBeenCalledWith(
      KDL2_LANGUAGE_ID,
      expect.any(Object),
    );
    expect(defineTheme).toHaveBeenCalledWith(
      KDL2_DARK_THEME,
      KDL2_DARK_THEME_DATA,
    );
    expect(defineTheme).toHaveBeenCalledWith(
      KDL2_LIGHT_THEME,
      KDL2_LIGHT_THEME_DATA,
    );
    expect(registerCompletionItemProvider).toHaveBeenCalledTimes(1);
    expect(registerCompletionItemProvider).toHaveBeenCalledWith(
      KDL2_LANGUAGE_ID,
      expect.objectContaining({
        triggerCharacters: ["@", "("],
      }),
    );
  });
});

describe("Monaco CompletionItemProvider for KDL 2.0 + ssc-gen DSL", () => {
  it("returns @ directive completions with snippets when triggered after '@'", () => {
    const items = getKdl2CompletionItems("    @", 3, 6);
    const labels = items.map((item) => item.label);

    expect(labels).toContain("@request");
    expect(labels).toContain("@error");
    expect(labels).toContain("@split-doc");
    expect(labels).toContain("@table");
    expect(labels).toContain("@init");
    expect(labels).toContain("@skip");
    expect(labels).toContain("@omitempty");
    expect(labels.every((l) => String(l).startsWith("@"))).toBe(true);

    const requestItem = items.find((item) => item.label === "@request")!;
    expect(requestItem.insertTextRules).toBe(INSERT_AS_SNIPPET);
    expect(requestItem.insertText).toContain("@request");
    // Range starts at column 5 (including '@') so it replaces '@' instead of duplicating '@@'
    expect(requestItem.range).toEqual({
      startLineNumber: 3,
      startColumn: 5,
      endLineNumber: 3,
      endColumn: 6,
    });
  });

  it("returns (type) struct and json annotation completions when triggered after '('", () => {
    // Simulate auto-closed parenthesis "()" with cursor at column 2
    const items = getKdl2CompletionItems("()", 1, 2);
    const labels = items.map((item) => item.label);

    expect(labels).toContain("(item)struct");
    expect(labels).toContain("(list)struct");
    expect(labels).toContain("(table)struct");
    expect(labels).toContain("(dict)struct");
    expect(labels).toContain("(flat)struct");
    expect(labels).toContain("(raw)struct");
    expect(labels).toContain("(rest)struct");
    expect(labels).toContain("(dict)json");
    expect(labels).toContain("(array)json");
    expect(labels.every((l) => String(l).startsWith("("))).toBe(true);

    const listStruct = items.find((item) => item.label === "(list)struct")!;
    expect(listStruct.insertTextRules).toBe(INSERT_AS_SNIPPET);
    expect(listStruct.insertText).toContain("@split-doc");
    // Range covers columns 1..3 so the auto-closed ')' is also replaced cleanly
    expect(listStruct.range).toEqual({
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: 1,
      endColumn: 3,
    });
  });

  it("returns directives, type annotations, pipeline operations, and predicates on general completion", () => {
    const provider = createKdl2CompletionProvider();
    const mockModel = {
      getLineContent: () => "        cs",
    } as unknown as Monaco.editor.ITextModel;
    const position = { lineNumber: 2, column: 11 } as Monaco.Position;

    const result = provider.provideCompletionItems(
      mockModel,
      position,
      {} as Monaco.languages.CompletionContext,
      {} as Monaco.CancellationToken,
    ) as Monaco.languages.CompletionList;

    expect(result.suggestions.length).toBe(
      ALL_KDL2_COMPLETION_TEMPLATES.length,
    );

    const labels = new Set(result.suggestions.map((s) => s.label));
    // Directives
    expect(labels.has("@request")).toBe(true);
    expect(labels.has("@error")).toBe(true);
    // Annotations
    expect(labels.has("(item)struct")).toBe(true);
    expect(labels.has("(rest)struct")).toBe(true);
    // Pipeline ops
    expect(labels.has("css")).toBe(true);
    expect(labels.has("css-all")).toBe(true);
    expect(labels.has("xpath")).toBe(true);
    expect(labels.has("re")).toBe(true);
    expect(labels.has("jsonify")).toBe(true);
    expect(labels.has("nested")).toBe(true);
    expect(labels.has("fallback")).toBe(true);
    // Predicates
    expect(labels.has("filter")).toBe(true);
    expect(labels.has("assert")).toBe(true);
    expect(labels.has("match")).toBe(true);
    expect(labels.has("eq")).toBe(true);
    expect(labels.has("has-attr")).toBe(true);
    expect(labels.has("text-re")).toBe(true);
  });
});
