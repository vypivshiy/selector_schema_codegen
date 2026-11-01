---
name: sscgen-dsl
version: "3.0"
dsl_version: "2.1"
description: >
  Generate KDL Schema DSL (v2.1) configs for HTML scraping, plain-text parsing, embedded JSON extraction, and REST/JSON HTTP API clients (`(item|list|table|dict|flat|raw|rest)struct`, `fn`, `(raw)fn`, `json`, `(array)json`, `(dict)json`, `@request`, `@error[:<suffix>]`, `css`/`xpath`/`re`/`jsonify`, `ssc-gen scout`, `ssc-gen json-to-kdl`).
  Use whenever the user wants to design, combine, or fix `.kdl` schemas for web pages, JS/m3u8/URL text, or HTTP/JSON APIs.
---

# sscgen-dsl — Unified KDL Schema DSL Skill (DSL v2.1)

Compile `.kdl` schemas into standalone HTML/text parsers and typed REST HTTP clients via `ssc-gen generate python|js|go|rust`. HTML structs, `(raw)struct`, `fn`, `json` schemas, and `(rest)struct` can be freely combined in a single `.kdl` file.

---

## Hard Rules (Always Apply)

1. **CLI version check**: run `ssc-gen version` (subcommand). Never run `ssc-gen --version` (flag does not exist and exits with an error).
2. **HTML inspection contract**: never use `Read` on raw `.html` files. When an HTML file or URL is available, your **first** tool call must be `ssc-gen scout -i <page.html> --discover -f json` (after `curl -sL <URL> -o <page.html>` if given a URL).
3. **Top-down declaration order (`E302`)**: declare helper `struct` and `json` schemas **above** any struct, `json` field, `nested`, or `jsonify` that references them.
4. **Inline `json` schemas by default**: nest single-use child objects (`field { ... }` / `field Model { ... }`), object arrays (`field (array)ItemModel { ... }` — `ItemModel` name is mandatory, `E001`), and maps (`field (dict) { @key str; @value ... }`) **inline** inside their parent `json` schema. Declare a standalone top-level `json` schema **only** when referenced directly by `@request response=`, `@error`, or `jsonify`, OR when shared across 2+ schemas (declared above callers, `E302`).
5. **Portable `json` field names (`E403`) & GJSON `from="..."` (`E040`, `E041`)**: `json` field names (after stripping `?`) must match `^[A-Za-z_][A-Za-z0-9_]*$` (`snake_case`/`camelCase`; no `kebab-case`, no colons `url: str`, no target keywords like `from`, `type`, `class`, `in`). Map special/reserved wire keys or nested GJSON paths via `from="..."` (e.g. `sender str from="from"`, `tag_names (array)str from="tags.#.name"`). Duplicate field or wire keys in one schema emit `E041`.
6. **Selectors & regex (`E002`)**:
   - Default to **CSS3** (`[attr^=val]`, `:nth-of-type(N)`, `:first-child`, combinators). Prefer `css "sel:nth-of-type(N)"` over `css-all "sel"; index N` for DOM element selection. Use CSS4 (`:not`, `:is`, `:where`, `:has`) or `xpath` only when explicitly requested.
   - `re #"..."#` and `re-all #"..."#` as pipeline ops require **exactly 1** capturing group `(...)` (`E002`; catch no-match `SscRegexError` with `fallback`). Inside `assert {}` / `filter {}` / `match {}`, `re` is a boolean predicate and requires 0 capture groups.
7. **Struct invariants (`E203`, `E401`)**:
   - `(rest)struct` allows **only** `@doc`, `@request`, and `@error[:<suffix>]` (`E203`) and requires $\ge 1$ `@request` (`E401`). `response-join` is forbidden on `(rest)struct` (`E001`; use `response-path` alone).
   - `(raw)struct` / `(raw)fn` start with `STR` and **forbid** all HTML ops (`css*`, `xpath*`, `text`, `attr`, `raw`).
   - `(table)struct` requires `@table`, `@rows`, `@match`, `@value`, and every regular field **must** start with `match { <string-predicates> }`.
   - `(dict)struct` requires `@split-doc`, `@key`, `@value` and forbids regular fields.
8. **KDL `\` line continuation (`E000`/`E203`)**: never place a `//` single-line comment immediately after `\` — `//` consumes the newline and breaks continuation, leaking HTTP lines (`GET`, `POST`, `curl`, `-H`) as stray struct fields.
9. **`@doc` semantics & security**: document base URL, auth, rate limits, and domain constants (auto-dedented via `cleandoc`); never list generated method signatures and never copy live credentials/cookies/tokens into `.kdl` files.

---

## Workflow

### Step 1 — Auto-Detect Source & Choose Construct(s)

Inspect the target (HTTP response `Content-Type` / body root, HAR/cURL captures, or `ssc-gen scout -i page.html --discover -f json`) and select the matching construct(s). Combine multiple structs in one `.kdl` file when a workflow spans HTML + JS/text + REST API:

| Source Signal | Construct in `.kdl` | Required Directives / Key Rules | Reference to Load |
|---|---|---|---|
| **JSON HTTP endpoint** (`application/json`, root `{` or `[`, cURL/HAR API) | `(rest)struct Name` + `json` schemas | 1+ `@request` (`name=` if $>1$, `response=<Schema>\|#null`); `@error[:<suffix>] <status> <Schema> [keys...] [k=v ...]` | `references/rest.md` + `references/json.md` |
| **HTML with embedded JSON** (`scout` reports `json_signals`: `ld+json`, `__NEXT_DATA__`, JS var, `data-*`) | `struct Name` + `json` schemas | Extract via `css ...; raw inner` (or `attr ...; unescape` / `re`) $\to$ `jsonify <Schema> [path="<gjson>"]` | `references/html-raw.md` + `references/json.md` |
| **HTML single object** | `struct Name` / `(item)struct` | 1+ regular fields starting with `css`/`css-all` or `@<init_field>` | `references/html-raw.md` |
| **HTML repeating cards / rows** (`scout` `repeat_containers`) | `(list)struct Name` | `@split-doc { css-all "<item_selector>" }` + item fields | `references/html-raw.md` |
| **HTML key-value table / label-value rows** (`scout` `table_candidates`) | `(table)struct Name` | `@table`, `@rows`, `@match`, `@value`; every field starts with `match { eq\|starts\|contains\|re ... }` | `references/html-raw.md` |
| **HTML dynamic map** (`<meta>` tags, dynamic attrs) | `(dict)struct Name` | `@split-doc`, `@key`, `@value` (no regular fields) | `references/html-raw.md` |
| **HTML flat string list** | `(flat)struct Name [keep-order=#true]` | Fields must return `STR` or `STR[]` | `references/html-raw.md` |
| **Plain text** (JS file, URL query, m3u8 playlist, CSV) | `(raw)struct Name` | Starts with `STR`; optional `@split-doc` auto-switches output from `dict` to `list[dict]`; HTML ops forbidden | `references/html-raw.md` |
| **Single extracted value** | `fn name` / `(raw)fn name` | Standalone function; only `@doc` + pipeline ops allowed | `references/html-raw.md` |

> **CLI JSON Bootstrap:** When sample JSON responses exist on disk, bootstrap inline `json` schemas via:
> `ssc-gen json-to-kdl sample.json -o schema.kdl --name ResponseName [--force]`

### Step 2 — Core Syntax Summary

#### 2.1 `json` Schemas (used by both `(rest)struct` and `jsonify`)
- **Top-level kinds**: `json Name { ... }`, `(array)json Name { ... }`, `(dict)json Name { [@key str|int|float|bool;] @value <TypeOrBlock>; }`.
- **Field syntax**: `<name> <type>[?] [from="<gjson_path>"] [@omitempty] [@skip]`
  - `?`: value may be `null` (`Optional[T]` / `*T` / `Option<T>` / `T|null`).
  - `@omitempty`: key may be absent from JSON object (`NotRequired[T]` / `,omitempty` / `#[serde(default)]`). Combine `T? @omitempty` when both occur.
  - `@skip`: validated by linter, omitted from generated types & projector (`type` defaults to `str`).
  - `from="<gjson_path>"`: maps wire keys (`from="from"`, `from=#"os\.version"#`), nested paths (`from="data.user.0.name"`), array count (`from="items.#"` $\to$ `int`), or array element projection (`from="tags.#.name"` $\to$ `(array)str`).
  - **Inline blocks (hoisted post-order ahead of parent)**:
    - `field[?] { ... }` $\to$ synthesizes `{Parent}{FieldPascal}`
    - `field ModelName[?] { ... }` $\to$ `ModelName`
    - `field (array)ItemModel[?] { ... }` $\to$ `ItemModel` (explicit `ItemModel` is **mandatory**, `E001`)
    - `field (dict)[DictName] { [@key str;] @value [ValModel][?] { ... } }` $\to$ `{DictName}Value` / `{Parent}{FieldPascal}Value`

#### 2.2 `@request` & `@error[:<suffix>]`
- **`@request` formats**: raw `HTTP/1.1` / `HTTP/2`, POSIX `curl`, or scalar `define` constant (`define BASE="https://..."`, `define REQ="curl '{{BASE}}/items/{{id:int}}'"`).
- **Typed placeholders (`{{name[:type][[]][?][|style]}}`)**: `name` must be **lowercase** `^[a-z][a-z0-9_-]*$` (`E002`; uppercase `{{UPPER}}` is only expanded inside top-level `define`, never inside inline `@request """..."""` literals). `type`: `str|int|float|bool`. `[]` (array) and `?` (optional) are forbidden in URL path (`E002`). `|style` (`repeat|csv|bracket|pipe|space`) requires `[]` (`E002`).
- **`@error[:<suffix>] <status:100..599> <Schema> ["pos.key"...] [prop.key=val ...]`** (`(rest)struct` only):
  - Prefer explicit `:suffix` (`@error:rate-limit 429 RateLimitError` $\to$ `<Struct>Err429RateLimit`) for semantic variant names and to avoid `E400` collisions (without `:suffix`, auto-naming uses the leaf non-numeric segment of at most the first **2** condition keys).
  - `@error` on `2xx` requires $\ge 1$ condition. Runtime matchers evaluate in order and safely fall through on non-JSON bodies or failed `<Schema>` projection.

#### 2.3 Unified Hybrid Example (HTML + Embedded JSON + Raw + REST in one `.kdl`)

```kdl
@doc "Unified catalog scraper + player parser + REST API client (https://example.com)."

define BASE-URL="https://example.com"

json HydratedItem {
    id int
    title str
    tag_names (array)str from="tags.#.name"
}

json InboxResponse {
    messages (array)MessageItem {
        id str
        sender str from="from"
        subject str
    }
    errors (dict) @omitempty {
        @key str
        @value (array)str
    }
}

json ApiError { message str }

// 1. Plain-text (raw)struct for JS player config
(raw)struct PlayerConfig {
    stream_url { re #"file:\s*[\"']([^\"']+)[\"']"# }
}

// 2. HTML (list)struct + embedded JSON via jsonify
(list)struct CatalogPage {
    @split-doc { css-all ".product-card" }
    title   { css "h3"; text; normalize-space }
    url     { css "a.card-link"; attr "href"; fmt "{{BASE-URL}}{{}}" }
    payload { css "script.item-json"; raw inner; jsonify HydratedItem }
}

// 3. Typed REST API client
(rest)struct ExampleApi {
    @request name=get-inbox response=InboxResponse """
    POST /api/inbox?limit={{limit:int?}} HTTP/1.1
    Host: api.example.com
    Content-Type: application/json

    {"email": "{{email}}"}
    """

    @error:not-found 404 ApiError
    @error:rate-limit 429 ApiError
}
```

### Step 3 — Iterative Lint & Verification

```bash
# 1. Lint until exit 0 (MANDATORY before presenting .kdl to user; cap 5 retries per line)
ssc-gen check schema.kdl -f json

# 2. Optional runtime test & selector health check for HTML/raw structs
ssc-gen run schema.kdl:CatalogPage -L bs4 -i page.html
ssc-gen health schema.kdl:CatalogPage -i page.html -f json
```

**Completion criteria before returning `.kdl`:**
1. `ssc-gen check` exits 0 with `[]`.
2. Top-down declaration order (`E302`): `@doc` $\to$ `import`/`define`/`extension` $\to$ shared `json` & helper `struct` $\to$ endpoint `json` (with single-use nested models inlined) $\to$ entrypoint `struct` / `(rest)struct`.

---

## Reference Pointers (Load on Demand)

- **HTML/Raw pipelines, `scout --discover` anatomy, predicate context matrix, CSS3/CSS4, `(raw)struct`, `(table)struct`, `import`/`define`/`extension`** $\to$ read `references/html-raw.md`
- **REST `@request` flags, `define` URL composition, typed placeholder matrix, `@error[:<suffix>]` fallthrough, `Result` types & `ssc-gen generate` targets** $\to$ read `references/rest.md`
- **Deep `json` / `(dict)json` / inline `@value` hoisting rules, GJSON path grammar, and `ssc-gen json-to-kdl`** $\to$ read `references/json.md`
- **Linter `ErrorCode` (`E000`–`E403`, `W011`–`W041`) fix table, CLI cheat sheet, and safe repair loop** $\to$ read `references/linter-errors.md`
- **Complete working `.kdl` examples** $\to$ read `references/examples/` (`booksToScrape.kdl`, `hackernews.kdl`, `imdbcom.kdl`, `quotesToScrape.kdl`, `rawParser.kdl`, `regexFallback.kdl`, `example-dummyjson.kdl`, `example-restApiLike.kdl`)
