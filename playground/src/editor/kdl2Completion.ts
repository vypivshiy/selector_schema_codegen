import type * as Monaco from "monaco-editor";
import {
  KDL2_LANGUAGE_ID,
  KDL2_PIPELINE_OPS,
  KDL2_PREDICATE_OPS,
} from "./kdl2Monarch";

// Numeric values matching Monaco's standaloneenums.js so completions work in
// both browser runtime and headless Vitest unit tests.
export const COMPLETION_KIND = {
  Function: 1 as Monaco.languages.CompletionItemKind,
  Struct: 6 as Monaco.languages.CompletionItemKind,
  Property: 9 as Monaco.languages.CompletionItemKind,
  Operator: 11 as Monaco.languages.CompletionItemKind,
  Constant: 14 as Monaco.languages.CompletionItemKind,
  Keyword: 17 as Monaco.languages.CompletionItemKind,
  TypeParameter: 24 as Monaco.languages.CompletionItemKind,
  Snippet: 27 as Monaco.languages.CompletionItemKind,
} as const;

export const INSERT_AS_SNIPPET =
  4 as Monaco.languages.CompletionItemInsertTextRule;

export type Kdl2CompletionCategory =
  | "directive"
  | "annotation"
  | "declaration"
  | "pipeline"
  | "predicate"
  | "constant";

export interface Kdl2CompletionTemplate {
  label: string;
  category: Kdl2CompletionCategory;
  kind: Monaco.languages.CompletionItemKind;
  insertText: string;
  isSnippet?: boolean;
  detail: string;
  documentation: string;
}

const DIRECTIVE_TEMPLATES: Kdl2CompletionTemplate[] = [
  {
    label: "@request",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText:
      '@request name="${1:fetch_item}" response=${2:ResponseSchema} """\n${3:GET https://api.example.com/v1/items}\n"""',
    isSnippet: true,
    detail: "Directive · HTTP request specification",
    documentation:
      "Declares an HTTP endpoint (raw HTTP or curl) on a struct or `(rest)struct`.",
  },
  {
    label: "@error",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: "@error ${1:404} ${2:ErrorSchema}",
    isSnippet: true,
    detail: "Directive · REST error mapping",
    documentation:
      "Maps an HTTP error status code (and optional required keys/conditions) to a typed JSON error schema.",
  },
  {
    label: "@error:suffix",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: "@error:${1:rate_limit} ${2:429} ${3:ErrorSchema}",
    isSnippet: true,
    detail: "Directive · Named REST error variant",
    documentation:
      "Maps an HTTP error status code with an explicit variant suffix (`@error:<suffix>`).",
  },
  {
    label: "@split-doc",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@split-doc { css-all "${1:.item}" }',
    isSnippet: true,
    detail: "Directive · Split document into items",
    documentation:
      "Splits the input document into repeating elements or text chunks for `(list)struct`, `(dict)struct`, or `(raw)struct`.",
  },
  {
    label: "@table",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@table { css "${1:table}" }',
    isSnippet: true,
    detail: "Directive · Locate table element",
    documentation: "Selects the root `<table>` element in a `(table)struct`.",
  },
  {
    label: "@rows",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@rows { css-all "${1:tr}" }',
    isSnippet: true,
    detail: "Directive · Select table rows",
    documentation: "Selects row elements from `@table` in a `(table)struct`.",
  },
  {
    label: "@match",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@match { css "${1:th}"; text; trim }',
    isSnippet: true,
    detail: "Directive · Table row header key",
    documentation:
      "Extracts the header key from each row in a `(table)struct` for field `match` blocks.",
  },
  {
    label: "@key",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@key { ${1:attr "name"} }',
    isSnippet: true,
    detail: "Directive · Dictionary key pipeline",
    documentation:
      "Extracts the dictionary key string for each split item in a `(dict)struct`.",
  },
  {
    label: "@value",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@value { ${1:css "td"; text; trim} }',
    isSnippet: true,
    detail: "Directive · Dict or table value pipeline",
    documentation:
      "Extracts the dictionary value in a `(dict)struct` or cell value in a `(table)struct`.",
  },
  {
    label: "@init",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@init {\n\t${1:shared} { ${2:css ".card"} }\n}',
    isSnippet: true,
    detail: "Directive · Precomputed instance values",
    documentation:
      "Precomputes and caches values on the struct instance; referenced in fields via `@<name>`.",
  },
  {
    label: "@pre-validate",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@pre-validate {\n\tassert { ${1:css ".container"} }\n}',
    isSnippet: true,
    detail: "Directive · Pre-parse input assertion",
    documentation:
      "Validates input before `parse()` runs; raises an assertion error when predicates fail.",
  },
  {
    label: "@check",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText:
      '@check ${1:is-valid} { ${2:css ".main"}; to-bool; fallback #false }',
    isSnippet: true,
    detail: "Directive · Public boolean check method",
    documentation:
      "Emits a public boolean helper method on the generated struct.",
  },
  {
    label: "@doc",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: '@doc "${1:Documentation summary}"',
    isSnippet: true,
    detail: "Directive · Docstring annotation",
    documentation:
      "Emits a docstring on the module, `struct`, or `fn` declaration.",
  },
  {
    label: "@skip",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: "@skip",
    isSnippet: false,
    detail: "Directive · Omit JSON field",
    documentation: "Excludes a JSON field from the generated projector output.",
  },
  {
    label: "@omitempty",
    category: "directive",
    kind: COMPLETION_KIND.Property,
    insertText: "@omitempty",
    isSnippet: false,
    detail: "Directive · Omit empty/null JSON field",
    documentation:
      "Marks a JSON schema field to be omitted when empty or null.",
  },
];

const ANNOTATION_TEMPLATES: Kdl2CompletionTemplate[] = [
  {
    label: "(item)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(item)struct ${1:ItemName} {\n\t${2:title} { css "${3:h1}"; text; trim }\n}',
    isSnippet: true,
    detail: "Struct · Single item HTML schema",
    documentation:
      "Declares an item struct that extracts a single structured object from an HTML document.",
  },
  {
    label: "(list)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(list)struct ${1:Catalogue} {\n\t@split-doc { css-all "${2:.item}" }\n\t${3:title} { css "${4:h2}"; text; trim }\n}',
    isSnippet: true,
    detail: "Struct · Repeating list HTML schema",
    documentation:
      "Splits a document via `@split-doc` and runs field pipelines on each item.",
  },
  {
    label: "(table)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(table)struct ${1:SpecsTable} {\n\t@table { css "${2:table}" }\n\t@rows { css-all "${3:tr}" }\n\t@match { css "${4:th}"; text; trim }\n\t@value { css "${5:td}"; text; trim }\n\t${6:field} { match { eq "${7:Header}" } }\n}',
    isSnippet: true,
    detail: "Struct · Key-value HTML table schema",
    documentation:
      "Extracts fields from an HTML `<table>` by matching row headers via `@table`, `@rows`, `@match`, and `@value`.",
  },
  {
    label: "(dict)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(dict)struct ${1:MetaMap} {\n\t@split-doc { css-all "${2:meta[name]}" }\n\t@key { attr "${3:name}" }\n\t@value { attr "${4:content}"; fallback #null }\n}',
    isSnippet: true,
    detail: "Struct · Dynamic key-value dictionary schema",
    documentation:
      "Splits a document via `@split-doc` and maps each element to `@key` and `@value`.",
  },
  {
    label: "(flat)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(flat)struct ${1:FlatLinks} {\n\t${2:links} { css-all "${3:a}"; attr "href" }\n}',
    isSnippet: true,
    detail: "Struct · Flattened string list schema",
    documentation:
      "Collects `STR` and `STR[]` field outputs into a single flat string list.",
  },
  {
    label: "(raw)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(raw)struct ${1:RawParser} {\n\t${2:value} { re #"${3:^(\\S+)}"# }\n}',
    isSnippet: true,
    detail: "Struct · Plain-text raw schema",
    documentation:
      "Operates directly on plain text (`STR`) without an HTML DOM parser.",
  },
  {
    label: "(rest)struct",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText:
      '(rest)struct ${1:ApiClient} {\n\t@request name="${2:get_item}" response=${3:ItemJson} """\n\tGET ${4:https://api.example.com/items/{{id}}}\n\t"""\n}',
    isSnippet: true,
    detail: "Struct · Typed REST HTTP client schema",
    documentation:
      "Declares a REST API client struct containing `@request` and `@error` directives.",
  },
  {
    label: "(dict)json",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText: "(dict)json ${1:MapSchema} value=${2:str}",
    isSnippet: true,
    detail: "JSON · Dictionary map schema",
    documentation:
      "Declares a JSON projector schema for dynamic `dict[str, V]` objects.",
  },
  {
    label: "(array)json",
    category: "annotation",
    kind: COMPLETION_KIND.Struct,
    insertText: "(array)json ${1:ListSchema} ${2:str}",
    isSnippet: true,
    detail: "JSON · Top-level array schema",
    documentation: "Declares a top-level JSON array schema.",
  },
  {
    label: "(raw)fn",
    category: "annotation",
    kind: COMPLETION_KIND.Function,
    insertText: "(raw)fn ${1:clean-text} {\n\t${2:trim}\n}",
    isSnippet: true,
    detail: "Function · Plain-text helper function",
    documentation:
      "Declares a standalone plain-text pipeline function starting with `STR`.",
  },
  {
    label: "(item)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(item)",
    isSnippet: false,
    detail: "Type annotation · Item struct",
    documentation: "Item struct type annotation.",
  },
  {
    label: "(list)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(list)",
    isSnippet: false,
    detail: "Type annotation · List struct",
    documentation: "List struct type annotation.",
  },
  {
    label: "(table)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(table)",
    isSnippet: false,
    detail: "Type annotation · Table struct",
    documentation: "Table struct type annotation.",
  },
  {
    label: "(dict)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(dict)",
    isSnippet: false,
    detail: "Type annotation · Dict struct or JSON map",
    documentation: "Dictionary struct or JSON map type annotation.",
  },
  {
    label: "(flat)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(flat)",
    isSnippet: false,
    detail: "Type annotation · Flat struct",
    documentation: "Flat string-list struct type annotation.",
  },
  {
    label: "(raw)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(raw)",
    isSnippet: false,
    detail: "Type annotation · Raw plain-text struct or fn",
    documentation: "Plain-text `raw` type annotation.",
  },
  {
    label: "(rest)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(rest)",
    isSnippet: false,
    detail: "Type annotation · REST client struct",
    documentation: "REST API client struct type annotation.",
  },
  {
    label: "(array)",
    category: "annotation",
    kind: COMPLETION_KIND.TypeParameter,
    insertText: "(array)",
    isSnippet: false,
    detail: "Type annotation · Array modifier",
    documentation: "Array type annotation for `json` schemas or fields.",
  },
];

const DECLARATION_AND_CONSTANT_TEMPLATES: Kdl2CompletionTemplate[] = [
  {
    label: "struct",
    category: "declaration",
    kind: COMPLETION_KIND.Keyword,
    insertText:
      'struct ${1:StructName} {\n\t${2:field} { css "${3:.selector}"; text; trim }\n}',
    isSnippet: true,
    detail: "Declaration · Struct definition",
    documentation: "Declares a parser struct.",
  },
  {
    label: "json",
    category: "declaration",
    kind: COMPLETION_KIND.Keyword,
    insertText: "json ${1:SchemaName} {\n\t${2:id} ${3:int}\n}",
    isSnippet: true,
    detail: "Declaration · JSON projector schema",
    documentation:
      "Declares an allowlist JSON schema for `jsonify` or REST `@request`/`@error` responses.",
  },
  {
    label: "fn",
    category: "declaration",
    kind: COMPLETION_KIND.Keyword,
    insertText: 'fn ${1:extract-text} {\n\tcss "${2:p}"; text; trim\n}',
    isSnippet: true,
    detail: "Declaration · Reusable pipeline function",
    documentation: "Declares a module-level reusable pipeline function.",
  },
  {
    label: "define",
    category: "declaration",
    kind: COMPLETION_KIND.Keyword,
    insertText: 'define ${1:CONST_NAME}="${2:value}"',
    isSnippet: true,
    detail: "Declaration · Compile-time constant or block macro",
    documentation: "Declares an `UPPER_CASE` scalar or block `define`.",
  },
  {
    label: "extension",
    category: "declaration",
    kind: COMPLETION_KIND.Keyword,
    insertText:
      'extension ${1:Utils} {\n\t${2:op_name} {\n\t\tsig ${3:str} ${4:str}\n\t\tpy { emit #"{{out}} = {{in}}"# }\n\t}\n}',
    isSnippet: true,
    detail: "Declaration · Custom target extension",
    documentation:
      "Declares typed, target-specific custom pipeline operations.",
  },
  {
    label: "#true",
    category: "constant",
    kind: COMPLETION_KIND.Constant,
    insertText: "#true",
    isSnippet: false,
    detail: "KDL 2.0 · Boolean true literal",
    documentation: "KDL 2.0 boolean `#true` literal.",
  },
  {
    label: "#false",
    category: "constant",
    kind: COMPLETION_KIND.Constant,
    insertText: "#false",
    isSnippet: false,
    detail: "KDL 2.0 · Boolean false literal",
    documentation: "KDL 2.0 boolean `#false` literal.",
  },
  {
    label: "#null",
    category: "constant",
    kind: COMPLETION_KIND.Constant,
    insertText: "#null",
    isSnippet: false,
    detail: "KDL 2.0 · Null literal",
    documentation: "KDL 2.0 `#null` literal.",
  },
];

const PIPELINE_SNIPPETS: Record<
  string,
  { insertText: string; isSnippet: boolean; detail: string; doc: string }
> = {
  css: {
    insertText: 'css "${1:.selector}"',
    isSnippet: true,
    detail: "Pipeline · Select first matching CSS element (DOC -> DOC)",
    doc: "Selects the first descendant matching a CSS selector.",
  },
  "css-all": {
    insertText: 'css-all "${1:.selector}"',
    isSnippet: true,
    detail: "Pipeline · Select all matching CSS elements (DOC -> DOC[])",
    doc: "Selects all descendants matching a CSS selector as a list.",
  },
  "css-remove": {
    insertText: 'css-remove "${1:. unwanted}"',
    isSnippet: true,
    detail: "Pipeline · Remove matching CSS elements (DOC -> DOC)",
    doc: "Removes all elements matching the CSS selector from the current document node.",
  },
  xpath: {
    insertText: 'xpath "${1:.//div}"',
    isSnippet: true,
    detail: "Pipeline · Select first matching XPath node (DOC -> DOC)",
    doc: "Selects the first node matching an XPath expression.",
  },
  "xpath-all": {
    insertText: 'xpath-all "${1:.//div}"',
    isSnippet: true,
    detail: "Pipeline · Select all matching XPath nodes (DOC -> DOC[])",
    doc: "Selects all nodes matching an XPath expression.",
  },
  "xpath-remove": {
    insertText: 'xpath-remove "${1:.//script}"',
    isSnippet: true,
    detail: "Pipeline · Remove matching XPath nodes (DOC -> DOC)",
    doc: "Removes all nodes matching the XPath expression.",
  },
  attr: {
    insertText: 'attr "${1:href}"',
    isSnippet: true,
    detail: "Pipeline · Extract HTML attribute value (DOC -> STR)",
    doc: "Extracts the specified attribute(s) from the element.",
  },
  re: {
    insertText: 're #"${1:(\\d+)}"#',
    isSnippet: true,
    detail: "Pipeline · Extract first regex capture group (STR -> STR)",
    doc: "Extracts the first regex match/capture group using a KDL 2.0 raw string.",
  },
  "re-all": {
    insertText: 're-all #"${1:(\\d+)}"#',
    isSnippet: true,
    detail: "Pipeline · Extract all regex matches (STR -> STR[])",
    doc: "Extracts all matches of the regular expression as a string list.",
  },
  "re-sub": {
    insertText: 're-sub #"${1:\\s+}"# "${2: }"',
    isSnippet: true,
    detail: "Pipeline · Regex search and replace (STR -> STR)",
    doc: "Replaces matches of a regular expression with a replacement string.",
  },
  fmt: {
    insertText: 'fmt "${1:{{}}}"',
    isSnippet: true,
    detail: "Pipeline · Format string template (STR -> STR)",
    doc: "Interpolates the current string into `{{}}` placeholder(s).",
  },
  repl: {
    insertText: 'repl "${1:old}" "${2:new}"',
    isSnippet: true,
    detail: "Pipeline · Substring replacement (STR -> STR)",
    doc: "Replaces literal substring occurrences.",
  },
  "rm-prefix": {
    insertText: 'rm-prefix "${1:prefix}"',
    isSnippet: true,
    detail: "Pipeline · Strip leading prefix (STR -> STR)",
    doc: "Removes the specified prefix if present.",
  },
  "rm-suffix": {
    insertText: 'rm-suffix "${1:suffix}"',
    isSnippet: true,
    detail: "Pipeline · Strip trailing suffix (STR -> STR)",
    doc: "Removes the specified suffix if present.",
  },
  "rm-prefix-suffix": {
    insertText: 'rm-prefix-suffix "${1:prefix}" "${2:suffix}"',
    isSnippet: true,
    detail: "Pipeline · Strip prefix and suffix (STR -> STR)",
    doc: "Removes both leading prefix and trailing suffix.",
  },
  split: {
    insertText: 'split "${1:,}"',
    isSnippet: true,
    detail: "Pipeline · Split string by delimiter (STR -> STR[])",
    doc: "Splits a string by the given delimiter into a list of strings.",
  },
  join: {
    insertText: 'join "${1:, }"',
    isSnippet: true,
    detail: "Pipeline · Join string list (STR[] -> STR)",
    doc: "Joins a list of strings using the given separator.",
  },
  index: {
    insertText: "index ${1:0}",
    isSnippet: true,
    detail: "Pipeline · Select element at index (T[] -> T)",
    doc: "Selects a single element from a list by 0-based (or negative) index.",
  },
  slice: {
    insertText: "slice ${1:0} ${2:5}",
    isSnippet: true,
    detail: "Pipeline · Slice list range (T[] -> T[])",
    doc: "Extracts a sub-slice `[start:end]` from a list.",
  },
  jsonify: {
    insertText: "jsonify ${1:SchemaName}",
    isSnippet: true,
    detail: "Pipeline · Parse JSON into typed schema (STR -> JSON)",
    doc: "Parses a JSON string and projects it through a declared `json` schema.",
  },
  nested: {
    insertText: "nested ${1:StructName}",
    isSnippet: true,
    detail: "Pipeline · Delegate to nested struct (DOC -> NESTED)",
    doc: "Delegates extraction of the current node to another declared `struct`.",
  },
  fallback: {
    insertText: "fallback ${1:#null}",
    isSnippet: true,
    detail: "Pipeline · Default value on failure",
    doc: "Provides a fallback value (`#null`, `#false`, number, or string) when prior steps fail.",
  },
};

const PIPELINE_TEMPLATES: Kdl2CompletionTemplate[] = KDL2_PIPELINE_OPS.map(
  (op) => {
    const custom = PIPELINE_SNIPPETS[op];
    return {
      label: op,
      category: "pipeline",
      kind: COMPLETION_KIND.Function,
      insertText: custom ? custom.insertText : op,
      isSnippet: custom ? custom.isSnippet : false,
      detail: custom ? custom.detail : `Pipeline · Built-in '${op}' operation`,
      documentation: custom
        ? custom.doc
        : `Built-in ssc-gen pipeline operation \`${op}\`.`,
    };
  },
);

const PREDICATE_SNIPPETS: Record<
  string,
  { insertText: string; isSnippet: boolean; detail: string; doc: string }
> = {
  filter: {
    insertText: 'filter { ${1:has-attr "href"} }',
    isSnippet: true,
    detail: "Predicate container · Filter list elements",
    doc: "Keeps only list items that satisfy the inner predicates (implicit AND).",
  },
  assert: {
    insertText: 'assert { ${1:ne ""} }',
    isSnippet: true,
    detail: "Predicate container · Assert condition",
    doc: "Validates that the current value satisfies all inner predicates.",
  },
  match: {
    insertText: 'match { ${1:eq "Header"} }',
    isSnippet: true,
    detail: "Predicate container · Match table row header",
    doc: "Matches a table row header against inner predicates in a `(table)struct` field.",
  },
  not: {
    insertText: 'not { ${1:eq ""} }',
    isSnippet: true,
    detail: "Logical combinator · Negate predicates",
    doc: "Negates the inner predicate block.",
  },
  and: {
    insertText: 'and { ${1:starts "http"}; ${2:ends ".html"} }',
    isSnippet: true,
    detail: "Logical combinator · All predicates must hold",
    doc: "Succeeds when all child predicates hold.",
  },
  or: {
    insertText: 'or { ${1:eq "a"}; ${2:eq "b"} }',
    isSnippet: true,
    detail: "Logical combinator · Any predicate must hold",
    doc: "Succeeds when at least one child predicate holds.",
  },
  eq: {
    insertText: 'eq "${1:value}"',
    isSnippet: true,
    detail: "Predicate · Equal to value(s)",
    doc: "Checks equality against one or more string or integer literals.",
  },
  ne: {
    insertText: 'ne "${1:value}"',
    isSnippet: true,
    detail: "Predicate · Not equal to value(s)",
    doc: "Checks inequality against one or more literals.",
  },
  starts: {
    insertText: 'starts "${1:prefix}"',
    isSnippet: true,
    detail: "Predicate · String starts with prefix",
    doc: "Checks whether the string starts with any of the given prefixes.",
  },
  ends: {
    insertText: 'ends "${1:suffix}"',
    isSnippet: true,
    detail: "Predicate · String ends with suffix",
    doc: "Checks whether the string ends with any of the given suffixes.",
  },
  contains: {
    insertText: 'contains "${1:substring}"',
    isSnippet: true,
    detail: "Predicate · String contains substring",
    doc: "Checks whether the string contains any of the given substrings.",
  },
  "has-attr": {
    insertText: 'has-attr "${1:href}"',
    isSnippet: true,
    detail: "Predicate · Element has HTML attribute",
    doc: "Checks whether the HTML element has the specified attribute(s).",
  },
  "attr-eq": {
    insertText: 'attr-eq "${1:class}" "${2:active}"',
    isSnippet: true,
    detail: "Predicate · Attribute equals value",
    doc: "Checks whether an element's attribute equals the expected value.",
  },
  "attr-ne": {
    insertText: 'attr-ne "${1:class}" "${2:hidden}"',
    isSnippet: true,
    detail: "Predicate · Attribute not equal to value",
    doc: "Checks whether an element's attribute does not equal the given value.",
  },
  "attr-starts": {
    insertText: 'attr-starts "${1:href}" "${2:https}"',
    isSnippet: true,
    detail: "Predicate · Attribute starts with prefix",
    doc: "Checks whether an element's attribute starts with the given prefix.",
  },
  "attr-ends": {
    insertText: 'attr-ends "${1:href}" "${2:.pdf}"',
    isSnippet: true,
    detail: "Predicate · Attribute ends with suffix",
    doc: "Checks whether an element's attribute ends with the given suffix.",
  },
  "attr-contains": {
    insertText: 'attr-contains "${1:class}" "${2:btn}"',
    isSnippet: true,
    detail: "Predicate · Attribute contains substring",
    doc: "Checks whether an element's attribute contains the given substring.",
  },
  "attr-re": {
    insertText: 'attr-re "${1:href}" #"${2:^https://}"#',
    isSnippet: true,
    detail: "Predicate · Attribute matches regex",
    doc: "Checks whether an element's attribute matches a regular expression.",
  },
  "text-re": {
    insertText: 'text-re #"${1:\\d+}"#',
    isSnippet: true,
    detail: "Predicate · Element text matches regex",
    doc: "Checks whether the element's text content matches a regular expression.",
  },
  "text-starts": {
    insertText: 'text-starts "${1:prefix}"',
    isSnippet: true,
    detail: "Predicate · Element text starts with prefix",
    doc: "Checks whether the element's text content starts with the given prefix.",
  },
  "text-ends": {
    insertText: 'text-ends "${1:suffix}"',
    isSnippet: true,
    detail: "Predicate · Element text ends with suffix",
    doc: "Checks whether the element's text content ends with the given suffix.",
  },
  "text-contains": {
    insertText: 'text-contains "${1:substring}"',
    isSnippet: true,
    detail: "Predicate · Element text contains substring",
    doc: "Checks whether the element's text content contains the given substring.",
  },
  "re-any": {
    insertText: 're-any #"${1:pattern}"#',
    isSnippet: true,
    detail: "Predicate · String matches regex",
    doc: "Checks whether the string matches the given regular expression.",
  },
  "len-eq": {
    insertText: "len-eq ${1:1}",
    isSnippet: true,
    detail: "Predicate · Length equals N",
    doc: "Checks whether the collection/string length equals N.",
  },
  "len-ne": {
    insertText: "len-ne ${1:0}",
    isSnippet: true,
    detail: "Predicate · Length not equal to N",
    doc: "Checks whether the collection/string length is not equal to N.",
  },
  "len-gt": {
    insertText: "len-gt ${1:0}",
    isSnippet: true,
    detail: "Predicate · Length greater than N",
    doc: "Checks whether the collection/string length is greater than N.",
  },
  "len-lt": {
    insertText: "len-lt ${1:10}",
    isSnippet: true,
    detail: "Predicate · Length less than N",
    doc: "Checks whether the collection/string length is less than N.",
  },
  "len-ge": {
    insertText: "len-ge ${1:1}",
    isSnippet: true,
    detail: "Predicate · Length greater than or equal to N",
    doc: "Checks whether the collection/string length is at least N.",
  },
  "len-le": {
    insertText: "len-le ${1:10}",
    isSnippet: true,
    detail: "Predicate · Length less than or equal to N",
    doc: "Checks whether the collection/string length is at most N.",
  },
  "len-range": {
    insertText: "len-range ${1:1} ${2:10}",
    isSnippet: true,
    detail: "Predicate · Length within [min, max]",
    doc: "Checks whether the collection/string length lies within `[min, max]`.",
  },
};

const PREDICATE_TEMPLATES: Kdl2CompletionTemplate[] = KDL2_PREDICATE_OPS.map(
  (op) => {
    const custom = PREDICATE_SNIPPETS[op];
    return {
      label: op,
      category: "predicate",
      kind: COMPLETION_KIND.Operator,
      insertText: custom ? custom.insertText : op,
      isSnippet: custom ? custom.isSnippet : false,
      detail: custom ? custom.detail : `Predicate · '${op}' operator`,
      documentation: custom
        ? custom.doc
        : `Built-in ssc-gen predicate operator \`${op}\`.`,
    };
  },
);

export const ALL_KDL2_COMPLETION_TEMPLATES: readonly Kdl2CompletionTemplate[] =
  [
    ...DIRECTIVE_TEMPLATES,
    ...ANNOTATION_TEMPLATES,
    ...DECLARATION_AND_CONSTANT_TEMPLATES,
    ...PIPELINE_TEMPLATES,
    ...PREDICATE_TEMPLATES,
  ];

function toMonacoCompletionItem(
  tpl: Kdl2CompletionTemplate,
  range: Monaco.IRange,
): Monaco.languages.CompletionItem {
  return {
    label: tpl.label,
    kind: tpl.kind,
    detail: tpl.detail,
    documentation: tpl.documentation,
    insertText: tpl.insertText,
    insertTextRules: tpl.isSnippet ? INSERT_AS_SNIPPET : undefined,
    range,
  };
}

/**
 * Compute context-aware Monaco completion items for the given line content and
 * 1-based cursor position.
 *
 * - Typing `@` (e.g. `@` or `@req`) filters to `@` directives.
 * - Typing `(` (e.g. `(` or `(it`) filters to `(type)` struct/json annotations.
 * - Otherwise (`Ctrl+Space` or identifier prefix), returns all directives,
 *   type annotations, declarations, pipeline operations, and predicates.
 */
export function getKdl2CompletionItems(
  lineContent = "",
  lineNumber = 1,
  column: number = lineContent.length + 1,
): Monaco.languages.CompletionItem[] {
  const safeCol = Math.max(1, Math.min(column, lineContent.length + 1));
  const linePrefix = lineContent.slice(0, safeCol - 1);

  // Case 1: `@` directive prefix
  const directiveMatch = linePrefix.match(/(@[A-Za-z0-9_:-]*)$/);
  if (directiveMatch) {
    const startColumn = safeCol - directiveMatch[1].length;
    const range: Monaco.IRange = {
      startLineNumber: lineNumber,
      startColumn,
      endLineNumber: lineNumber,
      endColumn: safeCol,
    };
    return DIRECTIVE_TEMPLATES.map((tpl) => toMonacoCompletionItem(tpl, range));
  }

  // Case 2: `(type)` annotation prefix
  const annotationMatch = linePrefix.match(/(\([A-Za-z0-9_?-]*\)?)$/);
  if (annotationMatch) {
    const startColumn = safeCol - annotationMatch[1].length;
    const hasAutoClosedParen = lineContent[safeCol - 1] === ")";
    const endColumn = hasAutoClosedParen ? safeCol + 1 : safeCol;
    const range: Monaco.IRange = {
      startLineNumber: lineNumber,
      startColumn,
      endLineNumber: lineNumber,
      endColumn,
    };
    return ANNOTATION_TEMPLATES.map((tpl) =>
      toMonacoCompletionItem(tpl, range),
    );
  }

  // Case 3: General identifier / Ctrl+Space completion
  const wordMatch = linePrefix.match(/([#A-Za-z0-9_-]*)$/);
  const wordLen = wordMatch ? wordMatch[1].length : 0;
  const range: Monaco.IRange = {
    startLineNumber: lineNumber,
    startColumn: safeCol - wordLen,
    endLineNumber: lineNumber,
    endColumn: safeCol,
  };

  return ALL_KDL2_COMPLETION_TEMPLATES.map((tpl) =>
    toMonacoCompletionItem(tpl, range),
  );
}

/**
 * Create the Monaco `CompletionItemProvider` for `kdl2`.
 */
export function createKdl2CompletionProvider(): Monaco.languages.CompletionItemProvider {
  return {
    triggerCharacters: ["@", "("],
    provideCompletionItems(model, position) {
      const lineContent = model.getLineContent(position.lineNumber);
      const suggestions = getKdl2CompletionItems(
        lineContent,
        position.lineNumber,
        position.column,
      );
      return { suggestions };
    },
  };
}

const registeredInstances = new WeakMap<object, Monaco.IDisposable>();

/**
 * Register the `kdl2` completion provider on a Monaco instance (idempotent per instance).
 */
export function registerKdl2Completions(
  monacoInstance: typeof Monaco,
): Monaco.IDisposable {
  const existing = registeredInstances.get(monacoInstance);
  if (existing) {
    return existing;
  }
  const disposable = monacoInstance.languages.registerCompletionItemProvider(
    KDL2_LANGUAGE_ID,
    createKdl2CompletionProvider(),
  );
  registeredInstances.set(monacoInstance, disposable);
  return disposable;
}
