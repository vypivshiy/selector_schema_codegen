# Model-Friendly REST Workflow

Use this mode for models likely to confuse KDL syntax or omit response fields.

## Safe Syntax

- Build one small `(rest)struct` first.
- Use ordinary quoted strings and one property per line.
- Declare leaf `json` schemas before nested schemas, then envelopes, then errors.
- Start with one `@request`; add `name=` when adding more.
- Use simple placeholders (`{{id:int}}`) before optional, array, CSV, or custom forms.
- Treat `define`, polymorphic JSON, complex typed placeholders, `response-path`, `response-join`, and conditional `@error` rules as advanced syntax.

## Source Evidence

Describe schema from strongest available evidence, in this order:

1. request-response recording;
2. HAR dump;
3. raw HTTP request/response records;
4. request made by agent when URL is accessible and safe;
5. prose API description as fallback.

Compare every response key, nested object, array, nullable value, envelope, and error shape. OpenAPI/Swagger may be used as external contract information, but CLI does not convert it automatically. Manually describe resulting KDL.

For authenticated sources, document request preparation and never copy credentials, cookies, or tokens into schema, examples, or logs.

## Validation

1. Run `ssc-gen check schema.kdl` after each structural change.
2. Run `ssc-gen generate` only when user names target/backend or asks for code-generation validation.
3. Do not require live, fixture, or raw-source testing. User chooses source testing method.

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
