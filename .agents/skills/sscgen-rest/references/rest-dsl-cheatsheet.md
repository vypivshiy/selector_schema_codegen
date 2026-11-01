# REST Linter Diagnostics & CLI Cheat Sheet (DSL v2.1)

## 1. CLI Commands

```bash
# Check CLI version (ALWAYS use subcommand `version`, NEVER `--version`)
ssc-gen version

# Bootstrap hierarchical inline json schema from a sample JSON file
ssc-gen json-to-kdl sample.json -o schema.kdl --name ResponseName --force

# Lint schema (validates KDL 2.0 syntax, types, imports & reserved words across all 4 targets)
ssc-gen check schema.kdl -f json
ssc-gen check schema.kdl -t python

# Generate typed HTTP client code
ssc-gen generate python schema.kdl -L bs4 --http-client httpx -o out/
ssc-gen generate python schema.kdl -L bs4 --http-client httpx2 --http-io async -R -o out/
ssc-gen generate js     schema.kdl --http-client fetch -o out/
ssc-gen generate js     schema.kdl --http-client axios -o out/
ssc-gen generate go     schema.kdl -o out/
ssc-gen generate rust   schema.kdl --http-client reqwest -o out/
```

---

## 2. Canonical Linter `ErrorCode` Fixes (`ssc-gen check -f json`)

| Code | Name | Common Cause in REST Schemas | Canonical Fix |
|---|---|---|---|
| `E000` | `SYNTAX_ERROR` | Unquoted string, `true`/`null` without `#`, unclosed `{`, or `//` comment immediately after `\` continuation | Quote strings, use `#true`/`#false`/`#null`, remove `//` comments after `\` |
| `E001` | `INVALID_ARGUMENT_COUNT` | Missing `response` / status / schema arg, empty `{}` in inline block or `@value`, anonymous `field (array) { ... }`, colliding inline model name, or `response-join` on `(rest)struct` | Name array item model `field (array)ItemModel { ... }`; remove `response-join` from `(rest)struct`; populate or remove empty `{}` |
| `E002` | `INVALID_ARGUMENT_VALUE` | HTTP status outside `100..599`, `[]`/`?` in URL path placeholder, `\|style` without `[]`, uppercase `{{NAME}}` in `@request` literal, `@skip` on inline/`@value` block, or invalid `@error:<suffix>` | Use lowercase runtime placeholders (`{{id:int}}`); compose `{{UPPER_NAME}}` in a `define` first; move `[]`/`?` to query string; use valid ASCII `:suffix` |
| `E003` | `INVALID_IMPORT` | Empty `import` block, missing `(kind)` tag (`(json)`, `(struct)`, `(define)`), missing file, or circular import | Use `import "./shared.kdl" { (json)ModelName; (define)CONST-NAME }` |
| `E040` | `MALFORMED_DOTPATH` | Leading/trailing `.`, `..`, negative index, `*`, or `#[...]` filter in `from="..."` | Use valid GJSON path (`a.b.0.c`, `#"a\.b"#`, `items.#`, `tags.#.name`) |
| `E041` | `DUPLICATE_JSON_KEY` | Duplicate field name or duplicate wire key (`from=`) in the same `json` schema | Rename duplicate field or disambiguate `from="..."` wire paths |
| `E200` | `UNKNOWN_NODE` | Unrecognized top-level declaration or directive | Use valid top-level `json`, `(array)json`, `(dict)json`, `define`, `import`, `(rest)struct` |
| `E203` | `DISALLOWED_DIRECTIVE` | Regular field, `@init`, or HTML op inside `(rest)struct` (often caused by broken `\` continuation in `@request`) | Keep only `@doc`, `@request`, `@error[:<suffix>]` in `(rest)struct`; check `\` continuations |
| `E300` | `UNDEFINED_SYMBOL` | `response=<Schema>`, `@error <status> <Schema>`, or `json` field references an undeclared schema or forms a cycle | Declare the referenced `json` schema or import it |
| `E302` | `INVALID_DECLARATION_ORDER` | Top-level `json` schema references another top-level `json` schema declared below it | Move shared/referenced `json` schemas **above** their callers (or inline single-use schemas) |
| `E400` | `INVALID_TYPE_DECLARATION` | Duplicate resolved `@error` variant names in the same `(rest)struct`, or same key in `@error` positional args and properties | Disambiguate with explicit `@error:<suffix> <status> <Schema>`; use each condition key once |
| `E401` | `MISSING_REQUIRED_FIELD` | `(rest)struct` has no `@request` block | Add at least one `@request` directive |
| `E402` | `DUPLICATE_DECLARATION` | Duplicate symbol/field/`@request name=`, or conflicting specs for the same placeholder in one `@request` | Rename colliding symbols/methods; use identical spec for repeated `{{param:type}}` |
| `E403` | `INVALID_IDENTIFIER` | `json` field name has `-` (`kebab-case`), trailing colon (`url: str`), `@`/`$`, or collides with a target reserved word (`from`, `type`, `class`, `in`) | Use a portable `snake_case` identifier + `from="wire-key"` (e.g. `sender str from="from"`) |
| `W011` | `DEPRECATED_JSON_ALIAS` | Positional string alias `field str "wire_key"` | Replace with `field str from="wire_key"` |
| `W040` | `WHITESPACE_IN_PATH` | Leading/trailing spaces in `from=" ... "` | Strip accidental whitespace in `from="..."` |
| `W041` | `PATH_SYNONYM_IN_JSON` | `path="..."` used on a `json` field | Replace `path="..."` with `from="..."` |
