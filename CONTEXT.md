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
