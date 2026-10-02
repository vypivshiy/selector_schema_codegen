# Specification: Generated Symbol Scoping, Target-Aware Validation, and Keyword Portability

## Problem Statement

Following compiler improvements and multi-target symbol validation introduced in version 0.39.0, developers compiling existing `.kdl` schemas encounter false-positive validation errors (`E402` and `E403`) that prevent successful parser code generation for their target language (particularly Python):

1. **False-Positive Placeholder Collisions Across Requests (`E402`)**:
   When a REST API struct declares multiple `@request` methods (such as `list-items` and `get-item`), placeholders representing independent HTTP parameter specifications (for example, `{{id}}`, `{{page}}`, `{{limit}}`, `{{q}}`, `{{fields}}`) in different `@request` blocks within the same struct are incorrectly treated as sharing a single scope. The linter flags them with `error[E402]: python symbol collision: placeholder 'id' and placeholder 'id' both produce 'id'`, even though each request method in the generated target code has its own isolated function signature and parameter scope.

2. **False-Positive Placeholder Collisions Within Single Requests (`E402`)**:
   When a single `@request` uses the same placeholder more than once in its payload or URL (e.g. `GET /video/{{id}}?track_id={{id}}`), the collector creates multiple records for the same placeholder name without deduplication, causing the linter to report that the placeholder collides with itself.

3. **Inappropriate Cross-Target Keyword Blocking During Target-Specific Generation (`E403`)**:
   When executing `ssc-gen generate python ...`, the compilation pipeline runs cross-reference and symbol validation across all four backend targets (`python`, `javascript`, `go`, `rust`) by default. If a field or placeholder matches a keyword in an unused target (such as field `ref` or `type`, or placeholder `pub` in Rust), generation of Python code is blocked by `E403`, despite the names being completely valid in Python.

4. **Overly Restrictive Rust Keyword Rejection (`E403`)**:
   The Rust backend code generator already automatically escapes keywords into Rust raw identifiers (`r#ref`, `r#type`, `r#pub`), which is standard and idiomatic Rust for all keywords except the four non-raw keywords (`crate`, `self`, `super`, `Self`). However, the symbol validator unconditionally marks all Rust reserved words as invalid identifiers, making it impossible to use common field names (`type`, `ref`) even when targetting Rust.

## Solution

1. **Isolate Placeholder Symbols to Their Owning Request Method**:
   Update symbol record collection so that placeholders are scoped to their specific `@request` declaration (`f"{struct_source}#req#{child_index}"`). Within a single request, deduplicate placeholders by name so that repeated occurrences of `{{id}}` in a URL or payload produce exactly one parameter symbol record.

2. **Enable Target-Aware Compilation in the CLI Pipeline**:
   Update `parse_module` and `lint_cross_refs` to accept an optional `targets` parameter. When generating code for a specific target (`ssc-gen generate <target>`), restrict symbol validation to that target (`targets=(target,)`). Add an optional `--target` (`-t`) option to `ssc-gen check` while keeping multi-target validation as the default for `check`.

3. **Align Rust Keyword Validation with Raw Identifier Capabilities**:
   Update Rust symbol validation policy so that keywords escapable via `r#` are recognized as valid generated identifiers, rejecting only the Rust language non-raw keywords (`crate`, `self`, `super`, `Self`) and malformed identifier patterns.

## User Stories

1. As a REST client developer, I want to declare `{{page}}` and `{{limit}}` placeholders in multiple `@request` methods within the same struct, so that pagination parameters are idiomatic in each generated endpoint method.
2. As a REST client developer, I want to declare `{{id}}` in both a search endpoint and a detail endpoint in the same struct, so that I do not have to invent artificial unique parameter names across methods.
3. As a REST client developer, I want to use the same placeholder `{{id}}` in both the URL path and query parameters of a single `@request`, so that the generated method takes a single `id` parameter without self-collision errors.
4. As a scraper developer, I want to define HTML struct fields named `ref` and `type` when generating Python parsers, so that existing scraper schemas continue to compile cleanly without false Rust-related errors.
5. As a REST client developer, I want to define request placeholders named `pub` when generating Python parsers, so that query parameters like `?pub={{pub}}` are supported.
6. As a Rust parser developer, I want fields named `ref` and `type` to compile to `r#ref` and `r#type` in Rust structs, so that standard Serde field names matching Rust keywords work smoothly.
7. As a Rust client developer, I want request parameters named `pub` to compile to `r#pub` in Rust methods, so that external API parameter names are preserved.
8. As a schema author, I want placeholder name collisions within the *same* request (such as `{{page-num}}` and `{{page_num}}` both producing `page_num` in Python) to still be detected and reported with `E402`.
9. As a schema author, I want truly invalid identifiers (such as `class` in Python or `func` in Go or `self` in Rust) to still be detected and reported with `E403` for the relevant target.
10. As a CLI user running `ssc-gen generate python`, I want symbol validation to evaluate rules for Python only, so that changes or constraints in unrelated languages do not break my Python builds.
11. As a CLI user running `ssc-gen check`, I want multi-target symbol validation by default, so that I can ensure my schema is portable across all supported backends.
12. As a CLI user running `ssc-gen check -t python`, I want the ability to check schema validity specifically for Python, so that I can inspect target-specific issues without cross-target noise.

## Implementation Decisions

1. **Placeholder Scope and Identity**:
   - In symbol collection, `SymbolScope.PLACEHOLDER` records will have their `source` attribute set to the specific `@request` node's scoped key (e.g. `f"{local_source}#req#{child_index}"`).
   - Placeholder collection within a `@request` node will deduplicate by placeholder name (`spec.name`) before registering symbol records, ensuring multiple token references to the same parameter in a request payload yield exactly one symbol record per target.
   - Genuine collisions within the same request (two different placeholder names mapping to the same target identifier, e.g. `user_id` and `user-id`) remain scoped to that request and are reported as `E402`.

2. **Rust Symbol Validation Rules**:
   - Rust supports raw identifiers (`r#<ident>`) for all keywords except `crate`, `self`, `super`, and `Self`.
   - The Rust code generator already prefixes keywords with `r#`.
   - The symbol validation policy for Rust will treat identifiers matching `^[A-Za-z_][A-Za-z0-9_]*$` as valid unless they belong to `frozenset({"crate", "self", "super", "Self"})`.

3. **Target Parameter Propagation**:
   - `parse_module(src, *, source_path=None, targets=None)` will accept `targets: Iterable[str] | None = None` and forward it to `lint_cross_refs(..., targets=targets)`.
   - `_run_codegen` in the CLI compilation pipeline will pass `targets=(profile.language,)` to `parse_module`, ensuring code generation validates only against the target language being emitted.
   - `health.py` and `ssc-gen run` will pass `targets=("python",)`.
   - `ssc-gen check` will add an optional `--target` (`-t`) option, passing `(target,)` if supplied, or `None` (checking all targets) by default.

## Testing Decisions

- **Good Test Criteria**: Tests must verify external behavior (diagnostics returned by `parse_module`, CLI execution exit codes, and output code generated by visitors) without depending on internal helper structure.
- **Modules Tested**:
  - `tests/test_parser.py`: Verify that multiple `@request` declarations with shared placeholder names parse without `E402`; verify that repeated placeholders within one request parse without `E402`; verify that conflicting placeholder names in the same request still trigger `E402`.
  - `tests/test_symbols.py`: Unit tests for `is_valid_symbol` for Rust raw-escapable keywords versus non-escapable keywords.
  - `tests/test_cli.py`: Test target-specific generation and check commands.
  - Integration tests verifying generation of Python and Rust code for schemas containing `ref`, `type`, and `pub`.
- **Prior Art**:
  - `tests/test_symbols.py`: Existing tests for `target_symbol_plan` and `normalize_targets`.
  - `tests/test_parser.py`: Existing tests for `test_keyword_and_placeholder_collisions_are_rejected` and `test_normalized_names_are_checked_for_every_target`.

## Out of Scope

- Modifying the user's `.kdl` schema files directly (the user stated they will fix their `.kdl` files independently).
- Re-architecting the AST or converter visitor dispatch system.
- Adding raw identifier escaping to targets that do not support it (Python, JavaScript, Go).

## Further Notes

- The fixes are fully backwards-compatible with existing valid schemas.
- All existing 1,485 tests must continue to pass.
