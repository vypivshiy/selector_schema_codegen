---
name: sscgen-openapi
description: >
  Convert OpenAPI 3.x / Swagger 2.x specifications (YAML or JSON) into valid
  KDL Schema DSL files (`struct type=rest` + `json` schemas).
  Use this skill whenever the user provides an OpenAPI/Swagger spec and wants
  a `.kdl` REST API client, or asks to convert `swagger.yaml` / `openapi.json`
  to KDL DSL.
  Trigger on: "openapi", "swagger", "open api spec", "convert openapi",
  "swagger to kdl", "api spec to schema", "openapi to kdl",
  "конвертировать openapi", "swagger в kdl", "спецификация api".
  Do NOT use for: HTML scraping (use `sscgen-dsl`), ad-hoc REST schema design
  from prose descriptions (use `sscgen-rest`), non-OpenAPI API descriptions.
---

# sscgen-openapi — Skill

Convert an **OpenAPI/Swagger specification** (YAML or JSON) into a valid
**KDL Schema DSL** REST API client file (`struct type=rest` + `json` schemas).

This is a **deterministic transformation**, not creative generation. Given the
same OpenAPI spec, the output should be identical every time.

---

## Hard rules (always apply)

1. **Resolve all `$ref`** before generating output. No unresolved references.
2. **`json` schemas are ordered bottom-up**: leaves first, then composites,
   then envelopes, then error schemas.
3. **Form-urlencoded POST bodies** MUST use curl `--data-urlencode` format
   (not raw HTTP). JSON POST bodies SHOULD use raw HTTP format.
4. **GET requests** SHOULD use curl format for brevity.
5. **Group endpoints** sharing the same `servers` URL into one `struct type=rest`.
6. **Strict spec compliance**: if a schema has no `required` array, ALL fields
   are optional (`Type?`). No heuristics.
7. **Lint must pass** (`uv run ssc-gen check <file> -f json`) before delivery.
8. **Every `json` schema must be declared above** the `struct` that references it.

---

## Input modes

### Mode 1 — Full spec conversion
Inputs: complete OpenAPI YAML/JSON file.
→ Convert all paths, schemas, responses. Emit complete `.kdl`.

### Mode 2 — Partial conversion
Inputs: OpenAPI spec + subset of endpoints.
→ Convert only requested paths. Emit complete `.kdl`.

### Mode 3 — Fix conversion errors
Inputs: converted `.kdl` + linter output.
→ Fix errors, re-emit complete `.kdl`.

---

## Conversion workflow

Execute in this exact order:

### Step 1 — Parse and resolve

Read the OpenAPI spec. Resolve all `$ref` pointers:
- `#/components/schemas/Name` → schema object
- `#/definitions/Name` (Swagger 2) → schema object
- `#/components/responses/Name` → unwrap `content.*.schema` → recurse
- `allOf` → merge all properties into one flat object
- `oneOf` / `anyOf` → use first variant (document limitation)
- Inline anonymous objects → extract to named `json` with PascalCase name

Build a flat map: `{ SchemaName → resolved schema object }`.

### Step 2 — Design `json` schemas

For each resolved schema, emit a `json` block using the type mapping:

| OpenAPI type | KDL type |
|---|---|
| `string` | `str` |
| `integer` | `int` |
| `number` | `float` |
| `boolean` | `bool` |
| `array` + `items` | `(array)<ItemType>` |
| `$ref` / `object` | `<SchemaName>` |

Modifiers:
- Property NOT in `required` array → `Type?`
- `nullable: true` → `Type?`
- Non-snake_case JSON key → alias: `field_name Type "originalKey"`

Order: leaves first (no sub-references), then composites, then envelopes.

### Step 3 — Generate `@request` blocks

For each path + method:

**GET with query params** → curl format:
```kdl
@request name=list-items response=ItemList """
curl 'https://api.example.com/v1/items?limit={{limit:int?}}'
"""
```

**GET with path params** → curl format:
```kdl
@request name=get-item response=Item """
curl 'https://api.example.com/v1/items/{{item_id:int}}'
"""
```

**POST with JSON body** → raw HTTP:
```kdl
@request name=create-item response=Item """
POST /v1/items HTTP/1.1
Host: api.example.com
Content-Type: application/json

{"name": "{{name}}", "price": {{price:float}}}
"""
```

**POST with form-urlencoded** → curl `--data-urlencode`:
```kdl
@request name=search response=SearchResult """
curl -X POST 'https://api.example.com/v1/search' \
  --data-urlencode 'query={{query}}'
"""
```

Placeholder derivation:
- Path params: `{{name:type}}` (always required)
- Query params, required: `{{name:type}}`
- Query params, optional: `{{name:type?}}`
- Body params: inline in JSON or `--data-urlencode`

Method names: `name=<verb>-<resource>` (e.g. `list-pets`, `get-pet`, `create-pet`).

### Step 4 — Map error responses

For each non-2xx response with a schema:
```kdl
@error 404 ErrorSchema
```

Non-2xx without schema → omit (universal `UnknownErr` handles it).
Multiple endpoints sharing the same error status + schema → one `@error` entry.

### Step 5 — Lint until clean

```bash
uv run ssc-gen check <file> -f json
```

Loop until exit 0. Cap at 5 iterations per line. Never deliver with lint errors.

---

## Struct naming

Derive from `info.title`: PascalCase, strip spaces/special chars.
- `"Pet Store API"` → `struct PetStoreApi type=rest`
- `"Animevost"` → `struct AnimevostApi type=rest`

---

## Swagger 2 vs OpenAPI 3 differences

| Feature | OpenAPI 3 | Swagger 2 |
|---|---|---|
| Schema location | `components/schemas` | `definitions` |
| Response location | `components/responses` | `responses` |
| Body specification | `requestBody.content` | `parameters` with `in: body` |
| Content type | per-response `content` | global `produces` / `consumes` |
| File upload | `requestBody` + `multipart` | `type: file` |

Handle both. The conversion logic is the same after $ref resolution.

---

## Edge cases

- **No response schema** (empty 200): omit `response=` → method returns void.
- **Shared schemas** across endpoints: declare once, reference from multiple `response=`.
- **Pagination** (`limit`/`offset`, `page`/`size`): optional query params.
- **Auth headers**: `-H 'Authorization: Bearer {{token}}'` placeholder.
- **`type` as JSON field name**: valid in KDL `json` blocks (not a KDL keyword).
- **`id` as placeholder name**: valid (not in Python/JS reserved set).

---

## Iterative lint loop

```
1. Write the .kdl file
2. Run: uv run ssc-gen check <file> -f json
3. If empty / exit 0 → DONE
4. Parse JSON, filter level=error, sort by line, fix top-to-bottom
5. Goto 2. Cap at 5 iterations on the same line.
```

### Conversion-specific error fixes

| Error message | Cause | Fix |
|---|---|---|
| `regular field ... not allowed in struct type='rest'` | Schema fields in struct body | Move to `json` blocks, reference via `response=` |
| `define not found: NAME` | Undeclared schema | Declare `json Name { ... }` above the struct |
| `duplicate @error <status>` | Same status mapped twice | Keep one `@error` per status |
| `placeholder ... [] forbidden in path` | Array placeholder in URL | Move to query string |
| `placeholder ... ? forbidden in path` | Optional in URL path | Make required or move to query |
| `placeholder name ... collides with keyword` | Python/JS reserved word | Rename the placeholder |

---

## Output format

Always emit a complete `.kdl` file in this order:

1. `@doc` module docstring (API title, base URL, auth notes)
2. `json` schemas (leaves → composites → envelopes)
3. Error-body `json` schema(s)
4. `struct <Name> type=rest { ... }`

If fixing errors, emit the **full corrected file**, not just changed lines.

---

## When not to use this skill

- User describes an API in prose (no formal spec) → use `sscgen-rest`.
- User wants to scrape HTML → use `sscgen-dsl`.
- User has Postman collection, GraphQL schema, gRPC proto → not supported.

---

## Reference files

- `references/openapi-mapping-rules.md` — type/modifier mapping tables, $ref
  resolution, format selection logic, naming rules.
- `references/example-petclinic.kdl` — obfuscated Petstore-like example
  (GET/POST/PUT/DELETE, path+query params, JSON body, aliases, errors).

Authoritative upstream (read if anything is ambiguous):
- `references` in sibling skill `sscgen-rest` — REST DSL syntax details.
- `docs/learn/10-request.md` — full `@request` / typed placeholders spec.
- `docs/json.md` — `json` schema syntax + alias rules.
- `ssc_codegen/linter/rules_struct.py` — authoritative lint rules.
