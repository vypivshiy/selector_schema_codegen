# Model-Friendly REST Workflow

Use this mode for models likely to confuse KDL syntax or omit response fields.

## Safe Syntax

- Build one small `(rest)struct` first.
- Use ordinary quoted strings and one property per line (never place a `//` comment immediately after a `\` line continuation).
- Nest single-use child objects (`field { ... }`), object arrays (`field (array)ItemModel { ... }`), and dictionaries (`field (dict) { @key str; @value ... }`) **inline** inside their parent `json` schema; only declare a standalone top-level `json` schema when shared across 2+ schemas/endpoints (declared above callers, `E302`) or referenced directly in `response=` / `@error`.
- Start with one `@request`; add `name=` when adding more.
- Use simple lowercase placeholders (`{{id:int}}`) before optional, array, CSV, or custom forms.
- Name error variants semantically with `@error:<suffix>` (e.g. `@error:not-found 404 ApiError`, `@error:bad-request 400 BadRequestError`).
- Treat `define`, polymorphic JSON, complex typed placeholders, `response-path`, and conditional `@error` rules as advanced syntax.

## Source Evidence

Describe schema from strongest available evidence, in this order:

1. request-response recording;
2. HAR dump;
3. raw HTTP request/response records;
4. request made by agent when URL is accessible and safe;
5. prose API description as fallback.

Compare every response key, nested object, array, nullable value, envelope, and error shape. If a sample JSON file is available, bootstrap with `ssc-gen json-to-kdl sample.json -o schema.kdl --name ResponseName`. OpenAPI/Swagger may be used as external contract information, but CLI does not convert it automatically.

For authenticated sources, document request preparation and never copy credentials, cookies, or tokens into schema, examples, or logs.

## Validation

1. Check CLI version if needed via `ssc-gen version` (subcommand — NEVER `ssc-gen --version`).
2. Run `ssc-gen check schema.kdl -f json` after each structural change.
3. Run `ssc-gen generate` only when user names target/backend or asks for code-generation validation.
4. Do not require live, fixture, or raw-source testing. User chooses source testing method.

## Repair Mode

- Preserve last known-good file.
- Fix one primary diagnostic per iteration.
- After two identical errors, switch syntax form.
- Stop after five iterations on one issue; report minimal conflicting fragment.
- Never retry a hanging parser indefinitely.

## Minimal Multi-Step Pattern

```kdl
json Token { access_token str }
json TokenResponse { data Token }
json ApiError { error_code int; error_msg str }

(rest)struct Auth {
    @request name=get-token response=TokenResponse "POST /token HTTP/1.1\nHost: auth.example\n"
    @error 200 ApiError error
}
```

Use separate REST structs when one request prepares credentials for another. Model HTTP 200 errors with field conditions when API uses an error envelope, as VK does.
