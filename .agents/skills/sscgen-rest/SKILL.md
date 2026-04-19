---
name: sscgen-rest
description: >
  Generate KDL Schema DSL configs for REST/JSON HTTP APIs (struct type=rest).
  Use this skill whenever the user wants to: design a `.kdl` schema for an HTTP/JSON
  API client, write `@request` blocks targeting REST endpoints, declare `json`
  schemas for typed responses, define `@error <status>` mappings, work with typed
  placeholders (`{{id:int}}`, `{{tags:str[]?|csv}}`), or fix linter errors in a
  REST-style `.kdl`.
  Trigger on: "rest api", "rest schema", "struct type=rest", "@request", "@error",
  "сгенерировать api клиент", "клиент для api", "json placeholder/dummyjson/reqres"-like
  tasks. For HTML scraping (css/css-all/text/attr pipelines, type=item|list|table|
  flat|dict) use the sibling skill `sscgen-dsl` instead — this skill is REST-only.
---

# sscgen-rest — Skill

Generate valid **KDL Schema DSL** REST API clients (`struct type=rest`) from:
- An **API description** (endpoint list, parameters, response shape, error codes)
- Optionally: an **OpenAPI/Swagger snippet** or sample JSON responses
- Optionally: **linter output** (text or JSON) to fix errors

The generated `.kdl` becomes a typed HTTP client (Python `requests`/`httpx`,
JavaScript `fetch`/`axios`) when run through `ssc-gen generate ... --http-client ...`.

---

## Hard rules (always apply)

These are enforced by the linter (`ssc_codegen/linter/rules_struct.py`). Violating
them produces lint errors.

1. **`type=rest` body allows ONLY** `@request`, `@error`, `@doc`. Regular fields,
   `@init`, `@split-doc`, `@table`, `nested`, `css`/`xpath` are forbidden — output
   shape comes from the `json` schema referenced in `response=`.
2. **At least one `@request`** per `type=rest` struct.
3. **Multiple `@request` → every one needs `name=<kebab-id>`.** A single `@request`
   may omit `name=`, generating `fetch()` / `async_fetch()` / `fetch()` (JS).
4. **`@error <status> <Schema>`**: `status ∈ [100..599]`. Each `(status, field)`
   pair must be unique within the struct.
5. **`@error` on 2xx requires `field="<body-key>"`** — without a discriminator
   every successful response would be misclassified.
6. **Typed placeholders constraints**:
   - `[]` (array) and `?` (optional) are **forbidden in URL path** — only query,
     headers, body.
   - `|style` requires `[]` (style is array-only).
   - Types: `str | int | float | bool` only. Default = `str`.
   - The same name across multiple placeholders must have an identical full spec.
   - Names cannot collide with Python/JS keywords (`class`, `return`, …).
7. **No `parse()` / `nested` is generated** for `type=rest` — the response passes
   straight to the `response=` json schema. Don't try to combine REST methods with
   HTML scraping in the same struct; use a separate `type=item` struct if needed.

---

## Input modes

### Mode 1 — Generate from scratch
Inputs: API description (endpoints, params, response/error shape).
→ Design `json` schemas → assemble `struct Api type=rest` → lint → emit complete file.

### Mode 2 — Add methods to an existing REST struct
Inputs: existing `.kdl` + new endpoint(s).
→ Append `@request name=<unique>` blocks. Add new `@error` only if status is
not yet covered. Re-lint.

### Mode 3 — Fix linter errors
Inputs: existing `.kdl` + linter output (text or JSON).
→ Filter `level=error`, sort by line, fix top-to-bottom, re-emit complete file.

---

## Generation workflow

Execute in this exact order:

### Step 1 — Map the API surface

For each endpoint write down:
```
METHOD path?query  →  request body?  →  2xx response shape  →  documented error statuses
```

Group endpoints that share a host/auth into one `struct type=rest`. Different
APIs (different hosts, different auth schemes) → separate structs.

### Step 2 — Design `json` schemas

Order them top-down (innermost first):

```kdl
json Author { id int; name str }                  // leaf
json Post   { id int; title str; author Author }   // references Author
json PostList { posts (array)Post; total int }    // envelope
json ApiError { code int; message str }            // error body
```

Field types: `str | int | float | bool | null | <RefName>`.
Modifiers: `(array)Type` for arrays, `Type?` for optional.
Alias for non-pythonic JSON keys: `field-name str "originalKey"`.
For top-level array responses (e.g. `GET /tags` returns `["a","b"]`):
`json Tags array=#true { name str }` — but most APIs wrap in an envelope, prefer that.

### Step 3 — Write the `struct type=rest`

The `@request` body accepts **two interchangeable formats** — raw HTTP or POSIX
curl. Pick whichever is more convenient (curl is great for DevTools paste-ins).
You can mix both in one struct.

```kdl
struct ApiName type=rest {
    @doc """
    Short purpose. Generated methods (Python, --http-client requests):
        get_post(client, *, id)
        list_posts(client, *, limit=None, skip=None)
    """

    // raw HTTP form
    @request name=get-post response=Post doc="Fetch one post by id." """
    GET /posts/{{id:int}} HTTP/1.1
    Host: api.example.com
    Accept: application/json
    """

    // POSIX curl form — equivalent, often pasted from DevTools
    @request name=list-posts response=PostList doc="Paginated list." """
    curl 'https://api.example.com/posts?limit={{limit:int?}}&skip={{skip:int?}}' \
      -H 'Accept: application/json'
    """

    @error 404 ApiError
    @error 500 ApiError
}
```

Method-name mapping: `name=get-post` → `get_post()` (Python) / `getPost()` (JS).
Single unnamed `@request` → `fetch()` / `fetch()` (or `fetchPost`-less; just `fetch`).

### Step 4 — Lint until clean

```bash
uv run ssc-gen check schema.kdl -f json
```

Loop until exit 0 / empty array. **Never deliver a `.kdl` until lint is clean.**
Cap at 5 iterations on the same line; otherwise explain the conflict to the user.

### Step 5 — Generate code (optional)

```bash
uv run ssc-gen generate schema.kdl -t py-bs4  --http-client requests -o out/
uv run ssc-gen generate schema.kdl -t py-bs4  --http-client httpx    -o out/  # adds async_fetch
uv run ssc-gen generate schema.kdl -t js-pure --http-client fetch    -o out/
uv run ssc-gen generate schema.kdl -t js-pure --http-client axios    -o out/
```

Without `--http-client`, `@request` is silently ignored — useless for REST. Go
target does NOT support `@request`.

---

## Typed placeholders

Syntax: `{{ NAME [:TYPE] [[]] [?] [|STYLE] }}`

| Placeholder | Python signature | URL fragment (when `tags=[1,2]`) |
|---|---|---|
| `{{id}}` | `id: str` | `.../{id}` |
| `{{id:int}}` | `id: int` | `.../{id}` |
| `{{q:str?}}` | `q: str \| None = None` | omitted if `None` |
| `{{tags:int[]}}` | `tags: list[int]` | `?tags=1&tags=2` (repeat, default) |
| `{{tags:int[]?\|csv}}` | `tags: list[int] \| None = None` | `?tags=1,2` |
| `{{tags:str[]\|bracket}}` | `tags: list[str]` | `?tags[]=a&tags[]=b` |
| `{{tags:str[]\|pipe}}` | `tags: list[str]` | `?tags=a\|b` |
| `{{tags:str[]\|space}}` | `tags: list[str]` | `?tags=a%20b` |
| `{{flag:bool}}` | `flag: bool` | `?flag=true` |

Parameter ordering in generated method: required first, optional (`?`) last
(PEP 3102 keyword-only). Names with `-` auto-convert to `_` for Python / camelCase
for JS.

---

## `@request` properties

| Property | Purpose | When required |
|---|---|---|
| `name=<kebab-id>` | method-name suffix | required when struct has ≥2 `@request` |
| `response=<JsonSchema>` | typed `Ok[T]` body | almost always (omit → method returns void) |
| `doc="..."` | per-method docstring | recommended |
| `response-path="a.b.c"` | dot-path into JSON envelope to unwrap | when API wraps payload |
| `response-join="\n"` | join when path resolves to `list[str]` | rare |

The body of `@request` is a triple-quoted multiline string. **Two interchangeable
formats** — pick whichever is more convenient. The generator normalises both into
the same internal representation; the produced HTTP code is identical.

### Format A — Raw HTTP

Convenient when you have a spec / RFC-style description (start-line + headers
+ blank line + body):

```kdl
@request name=create-post response=Post """
POST /posts HTTP/1.1
Host: api.example.com
Content-Type: application/json
Accept: application/json

{"title": "{{title}}", "tags": {{tags:str[]|csv}}}
"""
```

### Format B — POSIX curl

Convenient for **copy-paste from browser DevTools** (Network tab → right-click
request → Copy → Copy as cURL (POSIX)) or from API documentation. Just paste,
then replace concrete values with typed placeholders.

```kdl
// GET — single line
@request name=get-post response=Post """
curl 'https://api.example.com/posts/{{id:int}}' -H 'Accept: application/json'
"""

// GET with query params (typed + optional)
@request name=list-posts response=PostList """
curl 'https://api.example.com/posts?limit={{limit:int?}}&skip={{skip:int?}}'
"""

// POST with JSON body (-H + -d, body auto-detected as JSON)
@request name=create-post response=Post """
curl -X POST 'https://api.example.com/posts' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"title": "{{title}}", "price": {{price:float}}}'
"""

// Multi-line copy from DevTools — backslash continuations are supported
@request name=auth-login response=AuthToken """
curl -X POST 'https://api.example.com/auth/login' \
  -H 'Content-Type: application/json' \
  -H 'X-Client-Id: {{client_id}}' \
  --json '{"username": "{{username}}", "password": "{{password}}"}'
"""
```

#### Supported curl flags (POSIX, not Windows cmd `^` continuations)

| Flag | Purpose |
|---|---|
| `-X` / `--request` METHOD | HTTP method (default GET). Supported: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS |
| `-H` / `--header` "K: V" | Add request header |
| `-d` / `--data` / `--data-raw` STR | Request body (auto-parsed as JSON if valid) |
| `--json` STR | Explicit JSON body |
| `-u` / `--user` user:pass | HTTP basic auth |
| `-F` / `--form` k=v | multipart/form-data field |
| `--data-urlencode` k=v | URL-encoded query/body param |
| `--compressed` | Silently ignored |

Unsupported flags (`-o`, `-I`, `-v`, `--cacert`, `-k`, `--resolve`, etc.) raise a
parse error at codegen time. Strip them before pasting, or switch to raw HTTP.

#### When to choose which

| Use raw HTTP when… | Use curl when… |
|---|---|
| Writing from a spec / OpenAPI snippet | Copying from browser DevTools |
| You want explicit `Host:` separation | Copying from API docs / cookbook |
| Body needs precise byte-level control | One-liner GETs without headers |
| Mixing path + headers + body in fixed order | You already debugged the call in `curl` locally |

You can mix both in a single `struct` — each `@request` is independent.

---

## `@error` syntax

```kdl
@error 404 ApiError                          // status-routed err variant
@error 200 field="error_code" ApiError       // 2xx discriminator
```

Generated class names: `<PascalStruct>Err<Status>[<FieldPascal>]`
- `@error 404 ApiError` in `struct DummyJsonApi` → `DummyJsonApiErr404`
- `@error 200 field="error_code" ApiError` → `DummyJsonApiErr200ErrorCode`

Universal variants are always emitted (no `@error` needed):
- `UnknownErr` — status outside declared `@error` set
- `TransportErr` — network/timeout/DNS (`status=0`, has `cause: str`)

**Methods never raise.** Return type is the union:
`Ok[ResponseSchema] | <Struct>Err<N> | ... | UnknownErr | TransportErr`.

All variants share `is_ok: bool`, `status: int`, `headers: Mapping[str,str]`, `value`.
JS exposes `isOk` (boolean literal narrowing).

---

## Iterative lint loop

```
1. Write/update the .kdl file
2. Run: uv run ssc-gen check <file> -f json
3. If empty / exit 0 → DONE
4. Otherwise: parse JSON, filter level=error, sort by line, fix top-to-bottom
5. Goto 2. Cap at 5 iterations on the same line.
```

Never present `.kdl` to the user with lint errors remaining. After 5 iterations on
the same location, stop and explain the conflict.

### REST-specific error fixes

| Error message contains | Cause | Fix |
|---|---|---|
| `regular field ... not allowed in struct type='rest'` | Wrote a non-`@request`/`@error`/`@doc` field | Remove it; describe its data inside a `json` schema referenced by `response=` |
| `struct type='rest' is missing required field '@request'` | Empty REST struct | Add at least one `@request` |
| `@request in struct type='rest' with multiple requests requires name=` | ≥2 `@request` and one (or more) lacks `name=` | Add `name="<kebab-id>"` to every `@request` |
| `duplicate @request name="..."` | Two `@request` resolved to the same method name | Rename one |
| `'@error' requires status code and schema name` | Bare `@error` | Use `@error <status> <SchemaName>` |
| `'@error' status ... out of range [100..599]` | Status outside HTTP range | Use a real HTTP status |
| `'@error' on 2xx status ... requires field= discriminator` | `@error 200/201/...` without `field=` | Add `field="<body-key-name>"` |
| `duplicate @error <status>` | Same `(status, field?)` declared twice | Drop the duplicate or differentiate by `field=` |
| `style requires array [] modifier` | `{{x:str\|csv}}` | Make it array: `{{x:str[]\|csv}}` |
| `placeholder ... [] forbidden in path` | Array placeholder in URL path | Move it to query string |
| `placeholder ... ? forbidden in path` | Optional placeholder in URL path | Make it required, or move to query |
| `placeholder ... conflicting type` | Same name used with different types | Pick one spec and use it everywhere |
| `define not found: NAME` / `unknown operation '...'` | Typo or undeclared schema | Check spelling; declare `json <Name> { ... }` above the struct |

---

## Output format

Always emit a complete, lintable `.kdl` file in this order:

1. `@doc` module docstring (API base URL, auth notes, rate-limit notes if any)
2. Inner `json` schemas (leaves first)
3. Aggregate / envelope `json` schemas
4. Error-body `json` schema(s)
5. `struct ApiName type=rest { ... }`

If fixing lint errors, emit the **full corrected file**, not just changed lines.

---

## When not to use this skill

- The user wants to **scrape HTML** (css/text/attr pipelines, `type=item|list|
  table|flat|dict`) → use `sscgen-dsl` instead.
- The user just wants to fetch a page and parse HTML out of it → that is also
  `sscgen-dsl` (with optional `@request` on a non-rest struct).
- The user is working with a binary or non-JSON HTTP API → `type=rest` requires
  a `json` response schema; bail out and ask for clarification.

---

## Reference files

- `references/rest-dsl-cheatsheet.md` — placeholders matrix, `@error` naming,
  Result-monad shape per target.
- `references/example-dummyjson.kdl` — minimal end-to-end working example
  (DummyJSON, 4 endpoints, one `@error`).

Authoritative upstream (read these if anything below is ambiguous):
- `docs/learn/10-request.md` — full `@request` / typed placeholders / Result spec
- `docs/json.md` — `json` schema syntax + alias rules
- `examples/restApiLike.kdl` — exhaustive 6-endpoint example
- `ssc_codegen/linter/rules_struct.py` — authoritative lint rules
