import type * as Monaco from "monaco-editor";

export const KDL2_LANGUAGE_ID = "kdl2";
export const KDL2_DARK_THEME = "kdl2-dark";
export const KDL2_LIGHT_THEME = "kdl2-light";

/**
 * Top-level declarations in `ssc-gen` KDL Schema DSL (v2.1) plus legacy aliases
 * surfaced by the linter.
 */
export const KDL2_DECLARATIONS = [
  "struct",
  "json",
  "fn",
  "define",
  "extension",
  "import",
  "imports",
  "module",
  "doc",
  "fieldset",
] as const;

/**
 * Canonical type annotations used on `struct`, `json`, `fn`, and `import` nodes.
 */
export const KDL2_TYPE_ANNOTATIONS = [
  "item",
  "list",
  "table",
  "dict",
  "flat",
  "raw",
  "rest",
  "array",
  "struct",
  "json",
  "define",
  "extension",
  "fn",
] as const;

/**
 * Canonical `@` directives in `ssc-gen` DSL v2.1.
 */
export const KDL2_DIRECTIVES = [
  "@request",
  "@error",
  "@split-doc",
  "@table",
  "@rows",
  "@match",
  "@key",
  "@value",
  "@init",
  "@pre-validate",
  "@check",
  "@doc",
  "@skip",
  "@omitempty",
] as const;

/**
 * Built-in pipeline operations and selectors from `ssc_codegen/core/type_checking.py`
 * and `ssc_codegen/core/linter.py`.
 */
export const KDL2_PIPELINE_OPS = [
  "css",
  "css-all",
  "css-remove",
  "xpath",
  "xpath-all",
  "xpath-remove",
  "text",
  "raw",
  "attr",
  "trim",
  "ltrim",
  "rtrim",
  "normalize-space",
  "lower",
  "upper",
  "unescape",
  "fmt",
  "repl",
  "rm-prefix",
  "rm-suffix",
  "rm-prefix-suffix",
  "split",
  "join",
  "re",
  "re-all",
  "re-sub",
  "first",
  "last",
  "index",
  "slice",
  "len",
  "unique",
  "to-int",
  "to-float",
  "to-bool",
  "jsonify",
  "nested",
  "fallback",
  "self",
] as const;

/**
 * Predicate blocks and predicate comparison operators from `ssc_codegen/core/linter.py`.
 */
export const KDL2_PREDICATE_OPS = [
  "filter",
  "assert",
  "match",
  "not",
  "and",
  "or",
  "eq",
  "ne",
  "starts",
  "ends",
  "contains",
  "len-eq",
  "len-ne",
  "len-gt",
  "len-lt",
  "len-ge",
  "len-le",
  "len-range",
  "has-attr",
  "attr-eq",
  "attr-ne",
  "attr-starts",
  "attr-ends",
  "attr-contains",
  "attr-re",
  "text-re",
  "text-starts",
  "text-ends",
  "text-contains",
  "re-any",
] as const;

/**
 * Primitive types used in `json` schemas and `extension` signatures.
 */
export const KDL2_PRIMITIVE_TYPES = [
  "str",
  "int",
  "float",
  "bool",
  "nil",
  "doc",
  "T",
  "str?",
  "int?",
  "float?",
  "bool?",
  "doc?",
  "T?",
] as const;

export const kdl2LanguageConfiguration: Monaco.languages.LanguageConfiguration =
  {
    comments: {
      lineComment: "//",
      blockComment: ["/*", "*/"],
    },
    brackets: [
      ["{", "}"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: "{", close: "}" },
      { open: "(", close: ")" },
      { open: '"', close: '"', notIn: ["string"] },
    ],
    surroundingPairs: [
      { open: "{", close: "}" },
      { open: "(", close: ")" },
      { open: '"', close: '"' },
    ],
  };

export const kdl2MonarchLanguage: Monaco.languages.IMonarchLanguage = {
  defaultToken: "source",
  tokenPostfix: ".kdl2",

  declarations: [...KDL2_DECLARATIONS],
  pipelineOps: [...KDL2_PIPELINE_OPS],
  predicateOps: [...KDL2_PREDICATE_OPS],
  primitiveTypes: [...KDL2_PRIMITIVE_TYPES],

  tokenizer: {
    root: [
      // Whitespace and statement/block delimiters
      [/[ \t\r\n]+/, "white"],
      [/[;{}]/, "delimiter"],

      // KDL 2.0 comments: // line, nested /* ... */ block, and /- slashdash
      [/\/\/.*$/, "comment"],
      [/\/\*/, "comment", "@blockComment"],
      [/\/-/, "comment.slashdash"],

      // KDL 2.0 type annotations: (item), (list), (dict), (table), (flat), (rest), (raw), (array), (Type?)
      [/\([A-Za-z_][A-Za-z0-9_-]*\??\)/, "type.annotation"],

      // KDL 2.0 #-prefixed language literals (#true, #false, #null, #inf, #-inf, #nan)
      [/#(?:true|false)(?![A-Za-z0-9_-])/, "constant.language.boolean"],
      [/#null(?![A-Za-z0-9_-])/, "constant.language.null"],
      [/#(?:-?inf|nan)(?![A-Za-z0-9_-])/, "constant.language.numeric"],

      // KDL 2.0 raw strings: #"..."#, ##"..."##, #"""..."""# (stores opening # count in $S2)
      [/(#+)(""")/, { token: "string.raw.delim", next: "@rawMultiString.$1" }],
      [/(#+)(")/, { token: "string.raw.delim", next: "@rawString.$1" }],

      // Unknown #-prefixed tokens
      [/#[A-Za-z0-9_-]+/, "invalid"],

      // KDL 2.0 multi-line and single-line quoted strings
      [/"""/, "string.quote", "@multiString"],
      [/"/, "string.quote", "@string"],

      // KDL 2.0 numeric literals (hex, octal, binary, float, exponent, integer with _ separators)
      [/[+-]?0x[0-9a-fA-F][0-9a-fA-F_]*(?![A-Za-z0-9_-])/, "number.hex"],
      [/[+-]?0o[0-7][0-7_]*(?![A-Za-z0-9_-])/, "number.octal"],
      [/[+-]?0b[01][01_]*(?![A-Za-z0-9_-])/, "number.binary"],
      [
        /[+-]?[0-9][0-9_]*\.[0-9][0-9_]*(?:[eE][+-]?[0-9_]+)?(?![A-Za-z0-9_-])/,
        "number.float",
      ],
      [/[+-]?[0-9][0-9_]*(?:[eE][+-]?[0-9_]+)(?![A-Za-z0-9_-])/, "number.float"],
      [/[+-]?[0-9][0-9_]*(?![A-Za-z0-9_-])/, "number"],

      // ssc-gen @ directives (@request, @error, @error:suffix, @split-doc, @init, @table, @skip, @omitempty)
      [/@[A-Za-z_][A-Za-z0-9_:-]*/, "annotation.directive"],

      // Custom extension operation calls (!Utils.slugify)
      [/![A-Za-z_][A-Za-z0-9_.-]*/, "function.extension"],

      // Scalar UPPER_CASE define assignments (define KEY="value") and key=value properties
      [/([A-Z_][A-Z0-9_-]*)(=)/, ["constant.define", "delimiter"]],
      [/([A-Za-z_][A-Za-z0-9_-]*)(=)/, ["attribute.name", "delimiter"]],

      // Forbidden KDL 1.0 bare literals (true, false, null, nan, inf, -inf without leading #)
      [/(?:true|false|null|nan|-?inf)(?![A-Za-z0-9_?-])/, "invalid"],

      // Identifiers classified against ssc-gen DSL vocabularies
      [
        /[A-Za-z_][A-Za-z0-9_-]*\??/,
        {
          cases: {
            "@declarations": "keyword.declaration",
            "@pipelineOps": "support.function.pipeline",
            "@predicateOps": "keyword.operator.predicate",
            "@primitiveTypes": "type.primitive",
            "^[A-Z_][A-Z0-9_-]*$": "constant.define",
            "@default": "identifier",
          },
        },
      ],
    ],

    // KDL 2.0 nested block comments /* ... /* ... */ ... */
    blockComment: [
      [/[^/*]+/, "comment"],
      [/\/\*/, "comment", "@push"],
      [/\*\//, "comment", "@pop"],
      [/[/*]/, "comment"],
    ],

    // Quoted string with KDL 2.0 escapes and {{placeholder}} interpolation
    string: [
      [/\{\{[^{}]*\}\}/, "variable.placeholder"],
      [/\\(?:[nrtbfs\\"/]|u\{[0-9a-fA-F]{1,6}\}|\s+)/, "string.escape"],
      [/[^\\"{]+/, "string"],
      [/\{/, "string"],
      [/"/, "string.quote", "@pop"],
    ],

    // KDL 2.0 multi-line string """..."""
    multiString: [
      [/\{\{[^{}]*\}\}/, "variable.placeholder"],
      [/"""/, "string.quote", "@pop"],
      [/\\(?:[nrtbfs\\"/]|u\{[0-9a-fA-F]{1,6}\}|\s+)/, "string.escape"],
      [/[^\\"{]+/, "string"],
      [/["{]/, "string"],
    ],

    // KDL 2.0 raw string #"..."# (closes only when closing # count equals $S2)
    rawString: [
      [/\{\{[^{}]*\}\}/, "variable.placeholder"],
      [
        /"(#+)/,
        {
          cases: {
            "$1==$S2": { token: "string.raw.delim", next: "@pop" },
            "@default": "string.raw",
          },
        },
      ],
      [/[^"{]+/, "string.raw"],
      [/["{]/, "string.raw"],
    ],

    // KDL 2.0 multi-line raw string #"""..."""# (closes only when closing # count equals $S2)
    rawMultiString: [
      [/\{\{[^{}]*\}\}/, "variable.placeholder"],
      [
        /"""(#+)/,
        {
          cases: {
            "$1==$S2": { token: "string.raw.delim", next: "@pop" },
            "@default": "string.raw",
          },
        },
      ],
      [/[^"{]+/, "string.raw"],
      [/["{]/, "string.raw"],
    ],
  },
};

export const KDL2_DARK_THEME_DATA: Monaco.editor.IStandaloneThemeData = {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "comment", foreground: "6A9955", fontStyle: "italic" },
    { token: "comment.slashdash", foreground: "858585", fontStyle: "italic" },
    { token: "keyword.declaration", foreground: "C586C0", fontStyle: "bold" },
    { token: "type.annotation", foreground: "4EC9B0", fontStyle: "bold" },
    { token: "type.primitive", foreground: "4EC9B0" },
    { token: "annotation.directive", foreground: "DCDCAA", fontStyle: "bold" },
    { token: "support.function.pipeline", foreground: "569CD6" },
    { token: "keyword.operator.predicate", foreground: "CE9178" },
    { token: "function.extension", foreground: "DCDCAA" },
    { token: "constant.define", foreground: "4FC1FF", fontStyle: "bold" },
    { token: "constant.language.boolean", foreground: "569CD6", fontStyle: "bold" },
    { token: "constant.language.null", foreground: "569CD6", fontStyle: "italic" },
    { token: "constant.language.numeric", foreground: "B5CEA8", fontStyle: "bold" },
    { token: "number", foreground: "B5CEA8" },
    { token: "number.float", foreground: "B5CEA8" },
    { token: "number.hex", foreground: "B5CEA8" },
    { token: "number.octal", foreground: "B5CEA8" },
    { token: "number.binary", foreground: "B5CEA8" },
    { token: "string", foreground: "CE9178" },
    { token: "string.quote", foreground: "CE9178" },
    { token: "string.raw", foreground: "D7BA7D" },
    { token: "string.raw.delim", foreground: "D7BA7D", fontStyle: "bold" },
    { token: "string.escape", foreground: "D7BA7D" },
    { token: "variable.placeholder", foreground: "4FC1FF", fontStyle: "bold" },
    { token: "attribute.name", foreground: "9CDCFE" },
    { token: "identifier", foreground: "D4D4D4" },
    { token: "delimiter", foreground: "D4D4D4" },
    { token: "invalid", foreground: "F44747", fontStyle: "underline bold" },
  ],
  colors: {},
};

export const KDL2_LIGHT_THEME_DATA: Monaco.editor.IStandaloneThemeData = {
  base: "vs",
  inherit: true,
  rules: [
    { token: "comment", foreground: "008000", fontStyle: "italic" },
    { token: "comment.slashdash", foreground: "6E7681", fontStyle: "italic" },
    { token: "keyword.declaration", foreground: "AF00DB", fontStyle: "bold" },
    { token: "type.annotation", foreground: "267F99", fontStyle: "bold" },
    { token: "type.primitive", foreground: "267F99" },
    { token: "annotation.directive", foreground: "795E26", fontStyle: "bold" },
    { token: "support.function.pipeline", foreground: "0000FF" },
    { token: "keyword.operator.predicate", foreground: "A31515" },
    { token: "function.extension", foreground: "795E26" },
    { token: "constant.define", foreground: "0070C1", fontStyle: "bold" },
    { token: "constant.language.boolean", foreground: "0000FF", fontStyle: "bold" },
    { token: "constant.language.null", foreground: "0000FF", fontStyle: "italic" },
    { token: "constant.language.numeric", foreground: "098658", fontStyle: "bold" },
    { token: "number", foreground: "098658" },
    { token: "number.float", foreground: "098658" },
    { token: "number.hex", foreground: "098658" },
    { token: "number.octal", foreground: "098658" },
    { token: "number.binary", foreground: "098658" },
    { token: "string", foreground: "A31515" },
    { token: "string.quote", foreground: "A31515" },
    { token: "string.raw", foreground: "811F3F" },
    { token: "string.raw.delim", foreground: "811F3F", fontStyle: "bold" },
    { token: "string.escape", foreground: "EE0000" },
    { token: "variable.placeholder", foreground: "0070C1", fontStyle: "bold" },
    { token: "attribute.name", foreground: "0451A5" },
    { token: "identifier", foreground: "001080" },
    { token: "delimiter", foreground: "000000" },
    { token: "invalid", foreground: "CD3131", fontStyle: "underline bold" },
  ],
  colors: {},
};

/**
 * Register the `kdl2` language, bracket/comment configuration, Monarch tokenizer,
 * and `kdl2-dark` / `kdl2-light` themes on a Monaco Editor instance.
 */
export function registerKdl2Language(monacoInstance: typeof Monaco): void {
  const alreadyRegistered = monacoInstance.languages
    .getLanguages()
    .some((lang) => lang.id === KDL2_LANGUAGE_ID);

  if (!alreadyRegistered) {
    monacoInstance.languages.register({
      id: KDL2_LANGUAGE_ID,
      extensions: [".kdl"],
      aliases: ["KDL 2.0 (ssc-gen)", "kdl2", "kdl"],
    });
  }

  monacoInstance.languages.setLanguageConfiguration(
    KDL2_LANGUAGE_ID,
    kdl2LanguageConfiguration,
  );
  monacoInstance.languages.setMonarchTokensProvider(
    KDL2_LANGUAGE_ID,
    kdl2MonarchLanguage,
  );
  monacoInstance.editor.defineTheme(KDL2_DARK_THEME, KDL2_DARK_THEME_DATA);
  monacoInstance.editor.defineTheme(KDL2_LIGHT_THEME, KDL2_LIGHT_THEME_DATA);
}

// ---------------------------------------------------------------------------
// Pure Monarch State Runner (for headless Vitest testing without DOM canvas)
// ---------------------------------------------------------------------------

export interface Kdl2Token {
  type: string;
  value: string;
  line: number;
  startColumn: number;
  endColumn: number;
  offset: number;
}

type MonarchActionSpec =
  | string
  | string[]
  | {
      token?: string;
      next?: string;
      cases?: Record<string, MonarchActionSpec>;
    };

type MonarchRuleTuple = [RegExp, MonarchActionSpec, string?];

function resolveStateRules(
  tokenizer: Record<string, MonarchRuleTuple[]>,
  state: string,
): MonarchRuleTuple[] {
  let current: string | null = state;
  while (current) {
    if (tokenizer[current]) {
      return tokenizer[current];
    }
    const dotIndex = current.lastIndexOf(".");
    current = dotIndex >= 0 ? current.slice(0, dotIndex) : null;
  }
  throw new Error(`Undefined Monarch state: ${state}`);
}

function substituteStateParams(
  template: string,
  matched: string,
  matches: RegExpMatchArray,
  state: string,
): string {
  const stateParts = [state, ...state.split(".")];
  return template.replace(
    /\$((\$)|(#)|(\d\d?)|[sS](\d\d?))/g,
    (_full, _sub, dollar, hash, groupNum, stateNum) => {
      if (dollar) return "$";
      if (hash) return matched;
      if (groupNum !== undefined) {
        const idx = Number.parseInt(groupNum, 10);
        return matches[idx] ?? "";
      }
      if (stateNum !== undefined) {
        const idx = Number.parseInt(stateNum, 10);
        return stateParts[idx] ?? "";
      }
      return "";
    },
  );
}

function evaluateCaseGuard(
  caseKey: string,
  matched: string,
  matches: RegExpMatchArray,
  state: string,
  vocabularies: Record<string, Set<string>>,
): boolean {
  if (caseKey === "@default" || caseKey === "@" || caseKey === "") {
    return true;
  }
  if (caseKey.startsWith("@")) {
    const listName = caseKey.slice(1);
    return vocabularies[listName]?.has(matched) ?? false;
  }
  const eqMatch = caseKey.match(/^\$(\d+)==\$[sS](\d+)$/);
  if (eqMatch) {
    const groupIdx = Number.parseInt(eqMatch[1], 10);
    const stateIdx = Number.parseInt(eqMatch[2], 10);
    const stateParts = [state, ...state.split(".")];
    return (matches[groupIdx] ?? "") === (stateParts[stateIdx] ?? "");
  }
  const re = new RegExp(caseKey);
  return re.test(matched);
}

function applyNextState(
  stack: string[],
  nextSpec: string,
  matched: string,
  matches: RegExpMatchArray,
): void {
  const currentState = stack[stack.length - 1];
  if (nextSpec === "@pop") {
    if (stack.length > 1) {
      stack.pop();
    }
    return;
  }
  if (nextSpec === "@push") {
    stack.push(currentState);
    return;
  }
  if (nextSpec === "@popall") {
    stack.splice(1);
    return;
  }
  const resolved = substituteStateParams(
    nextSpec.startsWith("@") ? nextSpec.slice(1) : nextSpec,
    matched,
    matches,
    currentState,
  );
  stack.push(resolved);
}

/**
 * Tokenize KDL 2.0 source text using the `kdl2MonarchLanguage` state machine.
 * Executes in pure TypeScript without requiring a browser DOM or Canvas.
 */
export function tokenizeKdl2(
  source: string,
  options: { includeWhitespace?: boolean } = {},
): Kdl2Token[] {
  const includeWhitespace = options.includeWhitespace ?? false;
  const tokenizer = kdl2MonarchLanguage.tokenizer as unknown as Record<
    string,
    MonarchRuleTuple[]
  >;
  const vocabularies: Record<string, Set<string>> = {
    declarations: new Set(KDL2_DECLARATIONS),
    pipelineOps: new Set(KDL2_PIPELINE_OPS),
    predicateOps: new Set(KDL2_PREDICATE_OPS),
    primitiveTypes: new Set(KDL2_PRIMITIVE_TYPES),
  };

  const stack: string[] = ["root"];
  const rawTokens: Kdl2Token[] = [];
  const lines = source.split(/\r?\n/);

  let lineStartOffset = 0;
  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const lineText = lines[lineIdx];
    const lineNumber = lineIdx + 1;
    let pos = 0;

    while (pos < lineText.length) {
      const currentState = stack[stack.length - 1];
      const rules = resolveStateRules(tokenizer, currentState);
      const rest = lineText.slice(pos);

      let matchedRule: MonarchRuleTuple | null = null;
      let matchResult: RegExpMatchArray | null = null;

      for (const rule of rules) {
        const anchoredRegex = new RegExp(
          `^(?:${rule[0].source})`,
          rule[0].flags,
        );
        const m = rest.match(anchoredRegex);
        if (m && m[0].length > 0) {
          matchedRule = rule;
          matchResult = m;
          break;
        }
      }

      if (!matchedRule || !matchResult) {
        const ch = lineText[pos];
        rawTokens.push({
          type: (kdl2MonarchLanguage.defaultToken as string) ?? "source",
          value: ch,
          line: lineNumber,
          startColumn: pos + 1,
          endColumn: pos + 2,
          offset: lineStartOffset + pos,
        });
        pos += 1;
        continue;
      }

      const matchedText = matchResult[0];
      let action: MonarchActionSpec = matchedRule[1];
      let explicitNext: string | undefined = matchedRule[2];

      while (
        typeof action === "object" &&
        !Array.isArray(action) &&
        action.cases
      ) {
        let resolvedCase: MonarchActionSpec = "identifier";
        for (const [caseKey, caseVal] of Object.entries(action.cases)) {
          if (
            evaluateCaseGuard(
              caseKey,
              matchedText,
              matchResult,
              currentState,
              vocabularies,
            )
          ) {
            resolvedCase = caseVal;
            break;
          }
        }
        action = resolvedCase;
      }

      if (Array.isArray(action)) {
        let groupOffset = pos;
        for (let i = 0; i < action.length; i++) {
          const groupVal = matchResult[i + 1] ?? "";
          const groupToken = action[i];
          if (groupVal.length > 0) {
            rawTokens.push({
              type: groupToken,
              value: groupVal,
              line: lineNumber,
              startColumn: groupOffset + 1,
              endColumn: groupOffset + groupVal.length + 1,
              offset: lineStartOffset + groupOffset,
            });
            groupOffset += groupVal.length;
          }
        }
      } else {
        const tokenType =
          typeof action === "string" ? action : (action.token ?? "source");
        if (typeof action === "object" && action.next) {
          explicitNext = action.next;
        }
        rawTokens.push({
          type: tokenType,
          value: matchedText,
          line: lineNumber,
          startColumn: pos + 1,
          endColumn: pos + matchedText.length + 1,
          offset: lineStartOffset + pos,
        });
      }

      if (explicitNext) {
        applyNextState(stack, explicitNext, matchedText, matchResult);
      }

      pos += matchedText.length;
    }

    lineStartOffset += lineText.length + 1;
  }

  // Merge adjacent segments on the same line that share the same token type
  // (matching Monaco's MonarchClassicTokensCollector behavior).
  const merged: Kdl2Token[] = [];
  for (const tok of rawTokens) {
    if (!includeWhitespace && tok.type === "white") {
      continue;
    }
    const prev = merged[merged.length - 1];
    if (
      prev &&
      prev.line === tok.line &&
      prev.endColumn === tok.startColumn &&
      prev.type === tok.type
    ) {
      prev.value += tok.value;
      prev.endColumn = tok.endColumn;
    } else {
      merged.push({ ...tok });
    }
  }

  return merged;
}

/**
 * Convenience helper returning the token type of a single KDL 2.0 lexeme.
 */
export function classifyKdl2Token(lexeme: string): string {
  const tokens = tokenizeKdl2(lexeme);
  return tokens[0]?.type ?? "white";
}
