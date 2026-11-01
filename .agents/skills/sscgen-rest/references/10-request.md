# `@request`, `@error[:<suffix>]`, `Result` & Codegen Targets (DSL v2.1)

## 1. `@request` Formats & Properties

`@request` accepts a raw `HTTP/1.1` / `HTTP/2` string, a POSIX `curl` command, or a scalar `define` name.

| Property | Required in `(rest)struct` | Semantics |
|---|---|---|
| `name="<kebab-id>"` | Required if $>1$ `@request` | Emits `snake_case` (Py/Rust), `camelCase` (JS), `PascalCase` (Go). Single unnamed `@request` $\to$ `fetch`. |
| `response=<Schema>\|#null` | Required (or omit for void) | 2xx JSON schema (`Ok[<Schema>Json]`), or `#null`/omitted for empty 204 (`Ok[None]`). |
| `doc="<text>"` | Optional | Method docstring (normalized via `inspect.cleandoc`). |
| `response-path="<dot.path>"` | Optional | Extracts nested ASCII dot-path (e.g. `"data.items"`) from JSON body before projecting `<Schema>`. (`response-join` is **forbidden** on `(rest)struct`, `E001`.) |

Supported `curl` flags: `-X/--request`, `-H/--header`, `-d/--data/--data-raw`, `--json`, `-u/--user`, `-F/--form`, `--data-urlencode`, `--compressed` (ignored).

### Scalar `define` Composition & Line Continuation Rules
- Scalar defines may interpolate earlier scalar defines via `{{UPPER_NAME}}` while keeping lowercase `{{param}}` as runtime parameters:
  ```kdl
  define API-HOST="https://api.example.com"
  define GET-USER="curl '{{API-HOST}}/users/{{id:int}}?fields={{fields:str[]?|csv}}'"
  ```
- **`E002` rule**: Uppercase `{{UPPER_NAME}}` is **forbidden** directly inside inline `@request """..."""` string literals — compose in a top-level `define` first and pass the define identifier to `@request`.
- **`E000`/`E203` rule**: Never place a `//` single-line comment immediately after `\` in a multi-line `@request` header — `//` consumes the newline and breaks line continuation.

---

## 2. Typed Placeholders (`{{name[:type][[]][?][|style]}}`)

- `name`: lowercase `^[a-z][a-z0-9_-]*$` (`-` converts to `_` in Py/Rust and camelCase in JS).
- `type`: `str` (default) | `int` | `float` | `bool`.
- `[]`: array parameter (forbidden in URL path, `E002`).
- `?`: optional parameter, defaults to `None`/`undefined`/`Option::None` (forbidden in URL path, `E002`).
- `|style` (arrays only, requires `[]`, `E002`; default `repeat`):
  - `repeat`: `?k=1&k=2`
  - `csv`: `?k=1,2`
  - `bracket`: `?k[]=1&k[]=2`
  - `pipe`: `?k=1|2`
  - `space`: `?k=1%202`
- Repeated occurrences of the same `name` in one `@request` must repeat the **exact same full spec** (`E402`), and must not collide with target language keywords (`E403`).

---

## 3. `@error[:<suffix>]` Dispatch & Safe Fallthrough

Syntax: `@error[:<suffix>] <status:100..599> <SchemaName> ["pos.key"...] [prop.key=val ...]`

- **Explicit suffix (`@error:<suffix>`)**: `<suffix>` must match `^[A-Za-z_][A-Za-z0-9_-]*$` (`E002`). Generates `<PascalStruct>Err<Status><PascalSuffix>` in Python/JS/Go and `Err<Status><PascalSuffix>` on `<PascalStruct>Error` in Rust. Use `:suffix` for semantic variant names (`@error:premium-required 403 PremiumError`, `@error:rate-limit 429 RateLimitError`) and to disambiguate multiple rules on the same status.
- **Auto-naming (no `:suffix`)**: extracts the last non-numeric leaf segment from at most the first **2** keys (`required_keys` then `conditions`), e.g. `"data.errors.0.detail"` $\to$ `<Struct>Err404Detail`.
- **Collision & duplicate key lint (`E400`)**: duplicate resolved variant names in the same `(rest)struct` or repeating the same key in both positional args and properties fails `ssc-gen check` with `E400`.
- **Conditions & fallthrough**: positional args check key/dot-path existence; properties check value equality (`AND`-combined). Rules run in declaration order (including `@error 200 ...` before 2xx projection). If a matched response is non-JSON (e.g. CDN HTML 403/502) or fails `<SchemaName>` projection, the runtime catches `SscJsonError` and falls through to the next `@error` rule before falling back to `UnknownErr` / `Unknown`.

---

## 4. Monadic `Result` Contract & Target Codegen

REST methods never throw on HTTP or projection errors; they return a union `Result`:

| Variant | Condition | Fields (`is_ok` / `isOk` on all variants) |
|---|---|---|
| `Ok[T]` | HTTP 2xx (and no `@error 200` matched) | `is_ok=True`, `status: int`, `headers: Mapping[str, str]`, `value: T` |
| `<Struct>Err<Status>[<Suffix>]` | Matched `@error[:<suffix>]` | `is_ok=False`, `status: int`, `headers`, `value: <Schema>Json` |
| `UnknownErr` (Rust `Unknown`) | Unmapped non-2xx or all matched `@error` rules failed projection | `is_ok=False`, `status: int`, `headers`, `value: Any` (raw JSON or `None`) |
| `TransportErr` (Rust `Transport`) | Network / timeout / DNS exception | `is_ok=False`, `status=0`, `headers={}`, `value=None`, `cause: str` |

### Target Signatures & Runtime HTTP Delegation

| Target | CLI Command | Generated Method Signature |
|---|---|---|
| **Python** (`httpx`/`httpx2`/`requests`/`aiohttp`) | `ssc-gen generate python schema.kdl --http-client httpx [-L bs4] [--http-io both\|sync\|async] [-R] -o out/` | `@classmethod def <name>(cls, client, *, ..., **kwargs) -> <Method>Result` (+ `async_<name>`) |
| **JavaScript** (`fetch`/`axios`) | `ssc-gen generate js schema.kdl --http-client fetch -o out/` | `static async <camelName>(client, params = {}, opts = {}) -> Promise<<Method>Result>` |
| **Go** (`net/http` + `gjson`) | `ssc-gen generate go schema.kdl -o out/` | `func (<Struct>) <PascalName>(client *http.Client, ..., opts ...sscReqOpt) (*<Schema>Json, error)` |
| **Rust** (`reqwest` + `serde`) | `ssc-gen generate rust schema.kdl --http-client reqwest -o out/` | `pub async fn <snake_name>(client: &reqwest::Client, ...) -> Result<<Schema>, <Struct>Error>` (+ `_with_opts`) |

Runtime helpers (`ssc_rest_call`, `sscRestCall`, `sscRestCallValue[T]`, `rt::rest_call`) automatically:
1. Omit optional placeholders (`?`) set to `None`/`null`/`undefined` from `params`, `headers`, and `cookies`.
2. Preserve `None`/`null` inside JSON request bodies as `"key": null`.
3. Shallow-merge per-call `**kwargs` / `opts` / `sscReqOpt` / `SscRequestOpts` over schema defaults without mutating the client.
4. Without `--http-client` in Python/JS, `@request` methods are not emitted.
