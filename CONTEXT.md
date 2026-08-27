# ssc_codegen Domain Context

Canonical vocabulary for KDL schemas, source boundaries, and validation levels.

## Schema Types

**HTML schema**:
A KDL schema using regular, item, list, table, dict, or flat structs to extract values from an HTML DOM.
_Avoid_: REST schema, raw schema

**Raw schema**:
A KDL `(raw)struct` or `(raw)fn` that extracts values from plain text without an HTML parser.
_Avoid_: HTML schema

**REST schema**:
A KDL `(rest)struct` that describes JSON HTTP requests, response schemas, and typed error variants.
_Avoid_: HTML client, OpenAPI converter

**Pipeline**:
An ordered sequence of KDL operations that changes an input value into a field result.
_Avoid_: transform (unless referring to a confirmed project operation)

## API Terms

**Request**:
An `@request` declaration describing how a source is obtained, including method, URL, headers, body, and placeholders.
_Avoid_: endpoint schema

**Response schema**:
A `json` declaration describing JSON data returned by a REST request.
_Avoid_: response parser, OpenAPI schema

**JSON field name**:
The canonical field name declared before the type in a `json` field and used
by generated code and its result annotations.
_Avoid_: source key, wire key

**JSON key alias**:
The optional string after a JSON field type that names the source JSON key
when it differs from the canonical field name. For `context str "@context"`,
`context` is the canonical field name and `@context` is the JSON key alias.
_Avoid_: output alias, field rename

**Remapped JSON result**:
A plain mapping containing only declared canonical JSON field names, produced
from source JSON keys by applying JSON key aliases; absent source keys are
omitted and values are not type-validated or cast.
_Avoid_: validated model, deserialized object

## Validation And Access

**Schema validation**:
Successful `ssc-gen check` validation of KDL syntax, structure, symbols, and pipeline types; it does not prove source access or runtime correctness.
_Avoid_: integration test

**Code generation validation**:
Successful `ssc-gen generate` for a user-selected target and backend; it checks code generation but does not prove runtime correctness against a source.
_Avoid_: source validation

**Authenticated source**:
A source requiring cookies, credentials, tokens, or a session established by prior actions.
_Avoid_: public source

**Request preparation**:
Actions required before the target request, such as login, token exchange, cookie setup, special headers, or pagination state.
_Avoid_: request body
