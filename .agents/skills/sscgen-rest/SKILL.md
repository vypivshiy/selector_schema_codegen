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

# sscgen-rest — Skill (REST/JSON API clients)

Generate `struct type=rest` schemas that become typed HTTP clients when run through
`ssc-gen generate ... --http-client requests|httpx|fetch|axios`.

> **REST only.** This skill handles `json` schemas + `@request` + `@error`.
> For HTML scraping (`css`, `text`, `attr`, `nested`, `type=item|list|…`) → `sscgen-dsl`.

---

## Hard rules

1. **`type=rest` body allows ONLY** `@request`, `@error`, `@doc`. No regular fields,
   no `@init`, no `nested`, no `css`/`xpath`.
2. **At least one `@request`** per struct.
3. **Multiple `@request` → every one needs `name=<kebab-id>`** (single may omit).
4. **`@error <status> <Schema> [keys...] [key=value ...]`**: status ∈ [100..599]; positional args after Schema are key-presence checks; properties are value-equality checks; same key in both is a lint error.
5. **`@error` on 2xx requires field-conditions** (key presence or value equality) to avoid false positives.
6. **Typed placeholders**: `[]` and `?` forbidden in URL path; `|style` requires `[]`;
   types: `str|int|float|bool`; same name = same full spec; no keyword collisions.
7. **`@doc` describes the API semantically** (purpose, auth, base URL, rate limits).
   Do NOT list generated method signatures — they are derived from `name=` and
   placeholders and will rot as the schema evolves.

---

## Input modes

### Mode 1 — Generate from scratch
API description → `json` schemas → `struct type=rest` → lint → emit file.

### Mode 2 — Add methods to existing struct
Append `@request name=<unique>` blocks. Add `@error` only for uncovered statuses. Re-lint.

### Mode 3 — Fix linter errors
`ssc-gen check <file> -f json` → filter errors by line → fix top-to-bottom → re-emit full file.

---

## Generation workflow

### Step 1 — Map the API surface

```
METHOD path?query  →  body?  →  2xx response shape  →  error statuses
```

Group endpoints sharing host/auth into one struct. Different APIs → separate structs.

**Mandatory: capture actual response shapes.** For each endpoint, make a real HTTP
request (`curl`, `Invoke-WebRequest`, etc.) and inspect the JSON. If the user
provides a swagger/OpenAPI file, read it first — it is the canonical contract.

Things to determine for every endpoint:
- **Envelope**: bare top-level array `[...]`, data wrapper `{"data":[...]}`, paginated
  `{"data":[...],"meta":{"pagination":{...}}}`, or flat object?
- **Every field** in each response item — do NOT guess or skip fields.
- **Nullability**: which fields can be `null`? Mark them `Type?`.
- **Nested objects**: if a field is a dict, extract ALL its sub-fields into a
  separate `json` schema. Do NOT flatten or skip nested structures.
- **Numeric types**: swagger `type: number` with integer examples → `int`;
  fractional examples (e.g. `12.5`) → `float`.
- **Error response shape**: grab a real 404/422/etc. if possible.

### Step 2 — Design `json` schemas

**Innermost first.** Full syntax in `references/json.md`.

Start from the deepest nested objects and work outward. For each object observed
in the real API response (or defined in the swagger spec), create a `json` schema
with **all** its fields — every single key from the actual JSON, with the correct
type and nullability.

```kdl
json Author { id int; name str }
json Post   { id int; title str; author Author }
json PostList { posts (array)Post; total int }
json ApiError { message str }
```

Field types: `str | int | float | bool | null | <RefName>`.
Modifiers: `(array)Type`, `Type?`.
Alias: `field-name str "originalKey"`.
Top-level array: `(array)json Tags { name str }`.

**Deduplication with `define`.** When multiple `json` schemas share the same set
of base fields, extract them into a block define and reference it as a bare name
(no args) inside the json block:

```kdl
define PET-CORE {
    id int
    name str
    species str
    breed str?
    vaccinated bool
}

json PetSummary {
    PET-CORE
    photo_url str?
}

json PetDetail {
    PET-CORE
    photo_url str?
    owner Owner?
    vet_records (array)VetRecord
}
```

Rules for define in json:
- A bare child node (no args) whose name matches a block define → expanded inline.
- Normal fields always have a type arg (`name str`), so there is no ambiguity.
- Expansion is recursive: a define can reference another define.
- **When to use**: when ≥3 json schemas share ≥4 identical fields.
  Do NOT use for 1–2 shared fields or 2 schemas — the define overhead is not justified.
- **Max define body size**: 30 fields. Larger defines become hard to scan;
  split into multiple focused defines instead.

**Completeness checklist before proceeding:**

1. Does every field from the real response appear in the schema? Compare
   `sorted(response.keys())` against the schema fields.
2. Are nested objects extracted into their own `json` schemas (not flattened)?
3. Are nullable fields (`"field": null` in real data) marked `Type?`?
4. Does the response envelope match? Bare array → `(array)json`; paginated →
   include `Meta`/`Pagination` schemas; data wrapper → envelope schema with
   `data` field.
5. If a swagger is available: cross-reference every response schema
   (`$ref` paths, `allOf` compositions, `properties`) and include all fields
   the swagger defines, even if a single test request happened to have `null`
   for some of them.

### Step 3 — Write the struct

`@request` body: raw HTTP **or** POSIX curl (interchangeable). Full syntax and
typed placeholders in `references/10-request.md`.

```kdl
struct ApiName type=rest {
    @doc """
    Example API — posts and comments.
    Base URL: api.example.com
    Auth: Bearer token (passed via client headers).
    """

    @request name=get-post \
        doc="Fetch one post by id." \
        response=Post \
        """
    GET /posts/{{id:int}} HTTP/1.1
    Host: api.example.com
    Accept: application/json
    """

    @request name=list-posts \
        doc="Paginated list." \
        response=PostList \
        """
    curl 'https://api.example.com/posts?limit={{limit:int?}}&skip={{skip:int?}}' \
      -H 'Accept: application/json'
    """

    @error 404 ApiError
    @error 500 ApiError
}
```

Method naming: `name=get-post` → `get_post()` (Py) / `getPost()` (JS).
Single unnamed `@request` → `fetch()`.

`@request` properties: `name=`, `response=`, `doc=`, `response-path=`, `response-join=`.

### Step 4 — Lint until clean

```bash
uv run ssc-gen check schema.kdl -f json
```

Loop until exit 0. Cap 5 iterations on same line; then explain conflict.

### Step 5 — Generate code (optional)

```bash
uv run ssc-gen generate schema.kdl -t py-bs4 --http-client requests -o out/
uv run ssc-gen generate schema.kdl -t py-bs4 --http-client httpx    -o out/  # +async
uv run ssc-gen generate schema.kdl -t js-pure --http-client fetch    -o out/
uv run ssc-gen generate schema.kdl -t js-pure --http-client axios    -o out/
```

Without `--http-client`, `@request` is silently ignored. Go target unsupported.

---

## Output format

Always emit complete, lintable `.kdl` in this order:

1. `@doc` module docstring (base URL, auth, purpose — no method listings)
2. Leaf `json` schemas (innermost first — primitives, enums, small objects)
3. Mid-level `json` schemas (domain objects referencing leaves)
4. Envelope `json` schemas (paginated responses, wrappers, top-level arrays)
5. Error-body `json` schema(s)
6. `struct ApiName type=rest { ... }`

Fixing lint errors → emit **full corrected file**, not patches.

**Post-lint validation:** after `ssc-gen check` passes, re-verify that every
`json` schema matches the actual API response shape. If a swagger was provided,
spot-check field names and types against it.

---

## When not to use this skill

- **HTML scraping** (css/text/attr, `type=item|list|table|flat|dict`) → `sscgen-dsl`
- **Fetch page + parse HTML** → also `sscgen-dsl`
- **Binary / non-JSON HTTP API** → `type=rest` requires `json` response schema; ask user

---

## Reference files (self-contained)

- `references/10-request.md` — @request syntax, typed placeholders, curl flags, Result type
- `references/json.md` — json schema syntax, aliases, (array)json
- `references/example-dummyjson.kdl` — minimal working example (4 endpoints)
- `references/example-restApiLike.kdl` — comprehensive example (6 endpoints)
