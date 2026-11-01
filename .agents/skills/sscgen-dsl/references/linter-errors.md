# Linter `ErrorCode` Reference & Fix Table (`ssc-gen check -f json`)

Filter `"severity": "error"`, sort by line ascending, and fix top-to-bottom. Never return a `.kdl` file until `ssc-gen check` exits `0`.

| Code | Name | Cause | Canonical Fix |
|---|---|---|---|
| `E000` | `SYNTAX_ERROR` | Invalid KDL 2.0 syntax (unquoted strings, `true`/`null` without `#`, unclosed `{`, or `//` comment breaking `\` line continuation) | Quote strings, use `#true`/`#false`/`#null`, and remove `//` comments after `\` |
| `E001` | `INVALID_ARGUMENT_COUNT` | Wrong positional arg count on op/directive, empty `{}` in selector/predicates/`@value`, anonymous `field (array) { ... }`, or missing `match` at start of `(table)struct` field | Supply required args; separate same-line ops with `;`; name item model in `(array)ItemModel { ... }`; start `(table)struct` fields with `match { ... }` |
| `E002` | `INVALID_ARGUMENT_VALUE` | `re`/`re-all` lacks 1 capture group, invalid CSS/XPath, `fmt` missing `{{}}`, invalid `raw` mode, `[]`/`?` in URL path placeholder, uppercase `{{NAME}}` in `@request` literal, or invalid `define` name | Add exactly one `(...)` group to `re`/`re-all` (use `(?:...)` for non-capturing); include `{{}}` in `fmt`; use `UPPER_CASE` for `define` |
| `E003` | `INVALID_IMPORT` | Empty `import` block, missing `(kind)` tag, missing file, duplicate import path, or circular import | Prefix every imported symbol with `(struct)`, `(json)`, `(define)`, `(extension)`, or `(fn)` |
| `E040` | `MALFORMED_DOTPATH` | Leading/trailing `.`, `..`, negative index, `*`, or `#[...]` filter in `from="..."` or `jsonify path="..."` | Use valid GJSON path (`a.b.0.c`, `#"a\.b"#`, `items.#`, `tags.#.name`) |
| `E041` | `DUPLICATE_JSON_KEY` | Duplicate field name or duplicate wire key (`from=`) in the same `json` schema | Rename duplicate field or disambiguate `from="..."` wire paths |
| `E100` | `TYPE_MISMATCH` | Op input incompatible with previous step (`css-all` into scalar op without extract, `trim` on `DOC`, `re` after `to-int`), `@check` not ending in `BOOL`, or `fallback` literal mismatch | Add `text`/`attr` after `css`/`css-all`; use `css` or `first`/`last` when scalar needed; match `fallback` literal to pipeline type (or `#null` / `{}`) |
| `E200` | `UNKNOWN_NODE` | Unrecognized top-level declaration, pipeline op (e.g. non-existent `transform`), or predicate | Use valid DSL keywords or prefix custom extension calls with `!Namespace.op` |
| `E203` | `DISALLOWED_DIRECTIVE` | HTML op inside `(raw)struct`/`(raw)fn`, struct directive inside `fn`, regular field in `(dict)struct`, `has-attr`/`css` inside `match {}`, or `len-*`/`gt`/`re-any` outside `assert {}` | Use only string/regex ops in `(raw)`; keep `match {}` to string predicates (`eq`, `starts`, `contains`, `re`); keep `len-*`/`gt`/`re-any` inside `assert {}` |
| `E300` | `UNDEFINED_SYMBOL` | Reference to undeclared `struct`, `json`, `define`, `!Namespace.op`, or circular reference | Declare the referenced symbol or import it |
| `E301` | `UNDEFINED_INIT_FIELD` | `@<name>` references a field not declared in the struct's `@init` block | Declare `<name> { ... }` inside `@init { ... }` |
| `E302` | `INVALID_DECLARATION_ORDER` | Local `struct` or `json` referenced via `nested`, `jsonify`, or schema field before its declaration | Move helper `json` and `struct` definitions **above** the caller |
| `E400` | `INVALID_TYPE_DECLARATION` | Invalid struct/json/fn type annotation, invalid `extension` `sig`, or colliding `@error` variants | Use valid `(item\|list\|dict\|table\|flat\|rest\|raw)struct` or `(raw)fn` |
| `E401` | `MISSING_REQUIRED_FIELD` | Missing `@split-doc` (`list`), `@split-doc`+`@key`+`@value` (`dict`), or `@table`+`@rows`+`@match`+`@value` (`table`) | Add all required structural directives for the struct kind |
| `E402` | `DUPLICATE_DECLARATION` | Duplicate top-level symbol, field, `@init`, `@check`, or case-folded target collision | Rename colliding symbols or fields |
| `E403` | `INVALID_IDENTIFIER` | Symbol or `json` field name is not a valid portable identifier (`kebab-case` in `json`, `url: str`) or collides with a target reserved word (`from`, `type`, `class`) | Rename identifier (for `json` fields, use `snake_case` + `from="wire-key"`) |
| `W011` | `DEPRECATED_JSON_ALIAS` | Positional string alias on `json` field (`field str "wire_key"`) | Replace with `from="wire_key"` |
| `W040` | `WHITESPACE_IN_PATH` | Leading/trailing whitespace in `from="..."` | Strip accidental spaces |
| `W041` | `PATH_SYNONYM_IN_JSON` | `path="..."` used on a `json` field | Replace `path="..."` with `from="..."` (`path=` is for `jsonify`) |
