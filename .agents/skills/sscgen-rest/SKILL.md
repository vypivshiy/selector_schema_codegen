---
name: sscgen-rest
version: "2.6"
dsl_version: "2.1"
description: >
  Generate KDL Schema DSL (v2.1) REST/JSON API client configs (`(rest)struct`, `json`, `(array)json`, `(dict)json`, `@request`, `@error[:<suffix>]`, typed placeholders `{{id:int}}`, `ssc-gen json-to-kdl`).
  Use when designing or fixing `.kdl` schemas for HTTP/JSON endpoints, mapping status/body errors, or resolving REST linter diagnostics (`E400`, `E403`, `E040`, `E041`).
  For HTML DOM or plain-text scraping (`(item|list|table|flat|dict|raw)struct`, `css`, `xpath`, `re`), use `sscgen-dsl`.
---

# sscgen-rest — REST/JSON API Schemas (DSL v2.1)

Compile `.kdl` REST schemas into standalone typed HTTP clients via `ssc-gen generate python|js|go|rust`.

## Hard Rules

1. **CLI version check**: run `ssc-gen version` (subcommand). Never run `ssc-gen --version` (flag does not exist and errors out).
2. **`(rest)struct` body**: allows **only** `@doc`, `@request`, and `@error[:<suffix>]` (`E203`). Requires $\ge 1$ `@request` (`E401`).
3. **`@request` contract**: multiple `@request` blocks require unique `name=<kebab-id>` (single block may omit `name=`, defaulting to `fetch`). Specify `response=<Schema>` for 2xx JSON bodies, or `response=#null` (or omit `response=`) for empty/204 responses. `response-join` is **forbidden** on `(rest)struct` (`E001`; use `response-path="<dot.path>"` alone).
4. **KDL `\` line continuation (`E000`/`E203`)**: never place a `//` comment immediately after `\` in `@request` headers — `//` consumes the newline and breaks continuation, leaking HTTP lines (`GET`, `POST`, `curl`, `-H`) as stray struct fields.
5. **Inline `json` schemas by default**: nest single-use child objects (`field { ... }` / `field Model { ... }`), object arrays (`field (array)ItemModel { ... }` — `ItemModel` name is mandatory, `E001`), and maps (`field (dict) { @key str; @value ... }`) **inline** inside their parent `json` schema. Declare a standalone top-level `json` schema **only** when referenced directly by `response=` / `@error` OR shared across 2+ schemas/endpoints (declared **above** callers, `E302`).
6. **Portable `json` field names (`E403`) & GJSON `from="..."` (`E040`, `E041`)**: field names (after stripping `?`) must match `^[A-Za-z_][A-Za-z0-9_]*$` (`snake_case`/`camelCase`; no `kebab-case`, no colons `url: str`, no target keywords like `from`, `type`, `class`, `in`). Map special/reserved wire keys or nested GJSON paths via `from="..."` (e.g. `sender str from="from"`, `tag_names (array)str from="tags.#.name"`). Duplicate field or wire keys in one schema emit `E041`.
7. **`@error[:<suffix>] <status:100..599> <Schema> ["pos.key"...] [prop.key=val ...]`**:
   - Prefer explicit `:suffix` (`^[A-Za-z_][A-Za-z0-9_-]*$`, `E002`) for semantic variant names (`@error:rate-limit 429 RateLimitError` → `<Struct>Err429RateLimit` / Rust `Err429RateLimit`) and to prevent variant collisions (`E400`).
   - Without `:suffix`, auto-naming appends the leaf non-numeric segment of at most the first **2** keys (`required_keys` then `conditions`).
   - Positional args check nested key/index presence (`"error.details.0.code"`); properties check value equality (`upgrade_required=#true`, `status=#false`); same key in both emits `E400`.
   - `@error` on `2xx` requires at least one condition. Runtime matchers evaluate in declaration order and safely fall through on non-JSON bodies or failed `<Schema>` projection before falling back to `UnknownErr` / `Unknown`.
8. **Typed placeholders (`{{name[:type][[]][?][|style]}}`)**: `name` must be **lowercase** `^[a-z][a-z0-9_-]*$` (`E002`). Uppercase `{{UPPER_NAME}}` is resolved only inside top-level `define` strings and is **forbidden** inside inline `@request """..."""` literals (`E002`). `[]` and `?` are forbidden in URL path (`E002`); `|style` (`repeat|csv|bracket|pipe|space`) requires `[]` (`E002`); repeated names in one `@request` must repeat the identical spec (`E402`).
9. **`@doc` semantics**: document base URL, auth, rate limits, and domain constants (auto-dedented via `cleandoc`). Never list generated method signatures.

---

## Workflow

### Step 1 — Capture API Evidence
Inspect real HTTP responses, HAR dumps, raw HTTP captures, or OpenAPI contracts (verify real payloads for unannotated `null` values). Never copy live tokens, cookies, or secrets into `.kdl` files.
- If sample JSON files exist on disk, bootstrap inline schemas via:
  `ssc-gen json-to-kdl sample.json -o schema.kdl --name ResponseName [--force]`

### Step 2 — Declare `json` Schemas
Generated allowlist projectors (`_project_<schema>`) validate container types, extract only declared fields, and **silently ignore undeclared or commented-out (`//`) wire keys**.

| Construct | Syntax | Notes & Target Types (`Py / Go / Rust / JS`) |
|---|---|---|
| Scalar field | `name str\|int\|float\|bool\|null` | Space-separated (`name str`, never `name: str`) |
| Nullable (`?`) | `name str?` (`field? { ... }`) | Key present, value may be `null` (`Optional[T]` / `*T` / `Option<T>` / `T\|null`) |
| Absent key | `name str @omitempty` | Key may be omitted from JSON (`NotRequired[T]` / `*T,omitempty` / `#[serde(default)]`) |
| Nullable + absent | `name str? @omitempty` | Key may be absent OR `null` |
| Ignored wire key | `name [Type] @skip` | Validated by linter, omitted from types & projector (`Type` defaults to `str`) |
| Array field | `tags (array)str` | `List[T]` / `[]T` / `Vec<T>` / `Array<T>` |
| Inline object | `author [ModelName][?] { ... }` | Anonymous synthesizes `{Parent}{FieldPascal}`; hoisted ahead of parent |
| Inline object array | `items (array)ItemModel[?] { ... }` | Explicit `ItemModel` name is **mandatory** (`E001` if omitted) |
| Top-level array | `(array)json ItemList { ... }` | Root JSON payload is `[ {...}, ... ]` |
| Dict (top / inline) | `(dict)json Map { [@key int;] @value ... }` / `field (dict)[Name] { ... }` | `@key`: `str` (default) \| `int` \| `float` \| `bool`. `@value`: type or inline `[Model] { ... }` (`{Dict}Value` / `{Parent}{Field}Value`) |
| Key alias / GJSON | `val str from="<gjson_path>"` | `a.b.0.c`, escaped dot `#"a\.b"#`, count `items.#` (`int`), projection `tags.#.name` (`(array)T`). No `*`, `#[...]`, or negative index (`E040`) |
| Shared field block | `define CORE-FIELDS { ... }` | Bare `CORE-FIELDS` inside `json` expands inline (use when $\ge 3$ schemas share $\ge 4$ fields; max 30 fields) |

### Step 3 — Declare `(rest)struct`

```kdl
@doc """
Emailnator temporary email REST API (https://api.emailnator.com).
Auth: Public or optional header `x-revenuecat-app-user-id` on HTTP client.
"""

define API-HOST="https://api.emailnator.com"
define DELETE-REQ="curl -X DELETE '{{API-HOST}}/api/email/{{email}}'"

json InboxResponse {
    status str
    messages (array)InboxMessageItem {
        id str
        sender str from="from"
        subject str
        timestamp int
    }
    message_count int from="messages.#"
}

json ValidationError {
    message str
    errors (dict) {
        @key str
        @value (array)str
    }
}

json ApiError { message str }

(rest)struct EmailnatorApi {
    @doc "Disposable email generation and inbox client."

    @request name=get-inbox \
        doc="Fetch inbox messages for an email address." \
        response=InboxResponse \
        """
    POST /api/email/inbox HTTP/1.1
    Host: api.emailnator.com
    Content-Type: application/json
    Accept: application/json

    {"email": "{{email}}"}
    """

    @request name=delete-inbox \
        doc="Delete disposable inbox (empty 204 response)." \
        response=#null \
        DELETE-REQ

    @error:validation 422 ValidationError "errors"
    @error:rate-limit 429 ApiError
    @error:bad-request 400 ApiError
}
```

### Step 4 — Lint & Emit
Run `ssc-gen check <file.kdl> -f json` and fix diagnostics top-to-bottom until exit 0 (`[]`). Cap at 5 iterations on the same line.

**Completion criteria before returning `.kdl`:**
1. `ssc-gen check` exits 0 with zero errors.
2. Module order: `@doc` → optional `import`/`define` → shared top-level `json` (above callers, `E302`) → endpoint `json` (with single-use nested objects/arrays/dicts inlined) → error `json` → `(rest)struct`.
3. Every multi-status or domain-specific error uses `@error:<suffix>` without `E400` collisions.

---

## Reference Pointers (Load on Demand)

- **Complex `json` / `(dict)json` / inline `@value` hoisting / GJSON paths** → read `references/json.md`
- **`@request` curl flags, `define` composition, `Result` types, or running `ssc-gen generate python|js|go|rust`** → read `references/10-request.md`
- **Linter error codes (`E000`–`E403`, `W011`–`W041`), CLI cheat sheet, and placeholder matrix** → read `references/rest-dsl-cheatsheet.md`
- **Repeated lint failures / safe incremental mode** → read `references/model-friendly.md`
- **Full working `.kdl` examples** → read `references/example-dummyjson.kdl` and `references/example-restApiLike.kdl`
