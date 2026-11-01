# Linter `ErrorCode` Reference, CLI Cheat Sheet & Repair Mode (DSL v2.1)

## 1. CLI Reference

```bash
# Check CLI version (ALWAYS use subcommand `version`, NEVER `--version`)
ssc-gen version

# HTML reconnaissance (ALWAYS first step on HTML sources; never Read raw .html)
ssc-gen scout -i page.html --discover -f json
ssc-gen scout -i page.html --text '\$\d+\.\d{2}' --fields path -f json
ssc-gen scout -i page.html --attr 'href=~^/product/\d+' --fields path -f json
ssc-gen scout -i page.html --css ".price" --up 2 --fields path,text -f json

# Bootstrap hierarchical inline json schema from a sample JSON file
ssc-gen json-to-kdl sample.json -o schema.kdl --name ResponseName --force

# Lint schema (validates KDL 2.0 syntax, types, imports & reserved words across all 4 targets)
ssc-gen check schema.kdl -f json
ssc-gen check schema.kdl -t python

# Test HTML/raw struct execution and selector health
ssc-gen run schema.kdl:StructName -L bs4 -i page.html
ssc-gen health schema.kdl:StructName -i page.html -f json

# Generate standalone parser / HTTP client code
ssc-gen generate python schema.kdl -L bs4 [--http-client httpx|httpx2|requests|aiohttp] [--http-io both|sync|async] [-R] -o out/
ssc-gen generate js     schema.kdl [--http-client fetch|axios] -o out/
ssc-gen generate go     schema.kdl -o out/                             # emits schema.go + sscgen_runtime.go
ssc-gen generate rust   schema.kdl [--http-client reqwest] -o out/     # emits schema.rs + sscgen_runtime.rs
```

---

## 2. Canonical Linter `ErrorCode` Fixes (`ssc-gen check -f json`)

Filter `"severity": "error"`, sort by line ascending, and fix top-to-bottom. Never return a `.kdl` file until `ssc-gen check` exits `0`.

| Code | Name | Cause | Canonical Fix |
|---|---|---|---|
| `E000` | `SYNTAX_ERROR` | Invalid KDL 2.0 syntax (unquoted strings, `true`/`null` without `#`, unclosed `{`, or `//` comment immediately after `\` continuation) | Quote strings, use `#true`/`#false`/`#null`, remove `//` comments after `\` |
| `E001` | `INVALID_ARGUMENT_COUNT` | Wrong positional arg count on op/directive, empty `{}` in selector/predicates/`@value`, anonymous `field (array) { ... }`, colliding inline model name, `response-join` on `(rest)struct`, or missing `match` at start of `(table)struct` field | Supply required args; separate same-line ops with `;`; name item model in `(array)ItemModel { ... }`; remove `response-join` from `(rest)struct`; start `(table)struct` fields with `match { ... }` |
| `E002` | `INVALID_ARGUMENT_VALUE` | `re`/`re-all` lacks 1 capture group, invalid CSS/XPath, `fmt` missing `{{}}`, HTTP status outside `100..599`, `[]`/`?` in URL path placeholder, uppercase `{{NAME}}` in `@request` literal, `@skip` on inline/`@value` block, or invalid `define` / `@error:<suffix>` | Add one `(...)` group to `re`/`re-all` (`(?:...)` for non-capturing); use lowercase `{{param}}` in `@request` (compose `{{UPPER_NAME}}` in a `define` first); move `[]`/`?` to query string; use valid ASCII `:suffix` |
| `E003` | `INVALID_IMPORT` | Empty `import` block, missing `(kind)` tag, missing file, duplicate import path, or circular import | Use `import "./shared.kdl" { (struct)Name; (json)Model; (define)CONST; (extension)Utils; (fn)func }` |
| `E040` | `MALFORMED_DOTPATH` | Leading/trailing `.`, `..`, negative index, `*`, or `#[...]` filter in `from="..."` or `jsonify path="..."` | Use valid GJSON path (`a.b.0.c`, `#"a\.b"#`, `items.#`, `tags.#.name`) |
| `E041` | `DUPLICATE_JSON_KEY` | Duplicate field name or duplicate wire key (`from=`) in the same `json` schema | Rename duplicate field or disambiguate `from="..."` wire paths |
| `E100` | `TYPE_MISMATCH` | Op input incompatible with previous step (`css-all` into scalar op without extract, `trim` on `DOC`, `re` after `to-int`), `@check` not ending in `BOOL`, or `fallback` literal mismatch | Add `text`/`attr` after `css`/`css-all`; use `css` or `first`/`last` when scalar needed; match `fallback` literal to pipeline type (or `#null` / `{}`) |
| `E200` | `UNKNOWN_NODE` | Unrecognized top-level declaration, pipeline op (e.g. non-existent `transform`), or predicate | Use valid DSL keywords or prefix custom extension calls with `!Namespace.op` |
| `E203` | `DISALLOWED_DIRECTIVE` | HTML op inside `(raw)struct`/`(raw)fn`, struct directive inside `fn`, regular field in `(rest)struct`/`(dict)struct`, `has-attr`/`css` inside `match {}`, or `len-*`/`gt`/`re-any` outside `assert {}` | Keep `(rest)struct` to `@doc`/`@request`/`@error`; use only string/regex ops in `(raw)`; keep `match {}` to string predicates; keep `len-*`/`gt`/`re-any` inside `assert {}` |
| `E300` | `UNDEFINED_SYMBOL` | Reference to undeclared `struct`, `json`, `define`, `!Namespace.op`, or circular reference | Declare the referenced symbol or import it |
| `E301` | `UNDEFINED_INIT_FIELD` | `@<name>` references a field not declared in the struct's `@init` block | Declare `<name> { ... }` inside `@init { ... }` |
| `E302` | `INVALID_DECLARATION_ORDER` | Local `struct` or `json` referenced via `nested`, `jsonify`, or schema field before its declaration | Move shared `json` and helper `struct` definitions **above** the caller (or inline single-use `json` blocks) |
| `E400` | `INVALID_TYPE_DECLARATION` | Invalid struct/json/fn type annotation, invalid `extension` `sig`, duplicate resolved `@error` variant names in `(rest)struct`, or same key in `@error` positional args and properties | Use valid `(item\|list\|dict\|table\|flat\|rest\|raw)struct`; disambiguate colliding `@error` rules with `@error:<suffix>` |
| `E401` | `MISSING_REQUIRED_FIELD` | Missing `@split-doc` (`list`), `@split-doc`+`@key`+`@value` (`dict`), `@table`+`@rows`+`@match`+`@value` (`table`), or `@request` (`rest`) | Add all required structural directives for the struct kind |
| `E402` | `DUPLICATE_DECLARATION` | Duplicate symbol/field/`@init`/`@check`/`@request name=`, or conflicting specs for the same placeholder in one `@request` | Rename colliding symbols/methods; use identical spec for repeated `{{param:type}}` |
| `E403` | `INVALID_IDENTIFIER` | Symbol or `json` field name has `-` (`kebab-case`), trailing colon (`url: str`), `@`/`$`, or collides with a target reserved word (`from`, `type`, `class`, `in`) | Use a portable `snake_case` identifier + `from="wire-key"` (e.g. `sender str from="from"`) |
| `W011` | `DEPRECATED_JSON_ALIAS` | Positional string alias on `json` field (`field str "wire_key"`) | Replace with `from="wire_key"` |
| `W040` | `WHITESPACE_IN_PATH` | Leading/trailing whitespace in `from="..."` | Strip accidental spaces |
| `W041` | `PATH_SYNONYM_IN_JSON` | `path="..."` used on a `json` field | Replace `path="..."` with `from="..."` (`path=` is for `jsonify`) |

---

## 3. Safe Syntax & Repair Loop

- Keep the last known-good schema text; fix one primary diagnostic at a time top-to-bottom.
- After two identical errors on the same line, switch syntax form (e.g. inline vs block, CSS3 `:nth-of-type(N)` vs `css-all`, explicit `@error:<suffix>`).
- Stop after 5 iterations on the same line and report the minimal conflicting fragment to the user.
