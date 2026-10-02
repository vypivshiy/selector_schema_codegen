# Spec: Test Suite Deslop & Semantic Cleanup of TDD Bloat

## Problem Statement

As a developer and maintainer of `ssc_codegen`, running the automated test suite locally takes over 90 seconds and runs 6,151 individual test cases. Over 75% of these tests are combinatorial artifacts and intermediate scaffolding accumulated during iterative Test-Driven Development (TDD) and agent correction cycles. 

Specifically:
- Over 4,500 tests repetitively compile pairs of pipeline operations without verifying AST node shapes, field values, or runtime parsing results.
- Dozens of integration tests only assert that a result is not `None`, despite adjacent tests already asserting the exact semantic JSON output across all backend targets.
- Multiple tests verify external third-party library parsers (`kdlquery`) rather than the `ssc_codegen` compiler.
- Tests for REST code generation redundantly permute across four HTML DOM backends (`bs4`, `lxml`, `parsel`, `selectolax`) that have no interaction with the REST transport layer.
- Tautological assertions and checks on absent legacy implementation symbols add noise without providing an independent oracle.

This slows down developer feedback loops, wastes CI compute, and obscures real regressions under thousands of identical permutation failures.

## Solution

Conduct a test-first semantic cleanup (deslop) of the test suite in accordance with repository standards:
1. Remove combinatorial permutation bloat (`test_op_pair_*`) while strictly preserving true property-based fuzzing (Hypothesis random sequence testing) and representative pipeline chain tests (`solo` and `triple`).
2. Eliminate redundant smoke assertions (`assert result is not None`) that are dominated by existing deep-equality cross-target integration tests.
3. Remove third-party parser verification and internal implementation absence checks (`assert "APIType" not in code`).
4. Decouple REST separate-runtime tests from HTML DOM library permutations, fixing the HTML converter while testing HTTP client strategies independently.
5. Consolidate repetitive per-field and per-flag micro-tests into concise parameterized fixtures.

The resulting test suite will shrink by ~76% (to ~1,470 tests), reducing run time from ~95 seconds to under 20 seconds, while maintaining 100% of the repository's domain contracts, failure domains, and safety guardrails.

## User Stories

1. As a core developer, I want `uv run pytest` to finish in under 20 seconds, so that I can maintain a rapid test-driven feedback loop during compiler development.
2. As a CI engineer, I want the test suite to avoid running thousands of tautological AST permutations, so that PR verification runs quickly and uses fewer compute resources.
3. As a compiler maintainer, I want true property-based fuzzing (Hypothesis) preserved for the KDL reader and linter, so that arbitrary syntax and unexpected token sequences continue to be proven crash-free.
4. As a schema author, I want every single pipeline operation tested in isolation across all supported target languages, so that I can trust individual operation syntax.
5. As a compiler developer, I want representative multi-op pipeline transitions (`selector -> extract -> string op`, `selector-all -> extract -> array op`, casts, regex chains) preserved in tests, so that type inference and pipeline transitions remain covered.
6. As a backend developer, I want cross-target parity tests preserved, so that Python (`bs4`, `lxml`, `parsel`, `selectolax`), JavaScript (`DOM API`), Go (`goquery`), and Rust (`dom_query`) produce identical parsed output for identical schemas.
7. As a REST API client author, I want end-to-end REST tests with mocked HTTP transports (`respx`) preserved, so that status code dispatch, error response schemas, headers, query parameters, and placeholder bindings remain verified.
8. As a developer modifying REST runtime generation, I want REST runtime tests decoupled from HTML DOM library permutations, so that tests only exercise HTTP client strategies without running 4x identical HTML matrix permutations.
9. As a security-conscious engineer, I want docstring and comment escaping safety tests preserved, so that malicious input cannot execute code injection attacks in Python or JavaScript.
10. As a CLI user, I want CLI output planning, package name validations, collision rejection, and JSON diagnostic output tests preserved, so that the CLI contract remains stable.
11. As a contributor writing schema imports, I want transitive import, diamond import, and private symbol closure tests preserved, so that dependency resolution invariants cannot regress.
12. As a developer inspecting a test failure, I want test names to localize the exact broken behavior rather than failing hundreds of identical permutation pairs.
13. As a developer reading tests, I want tests to assert meaningful observable behavior (parsed JSON values, emitted diagnostic codes) rather than tautological checks like `assert isinstance(x, T)` on an object already filtered by `isinstance(..., T)`.
14. As a maintainer, I want tests of third-party dependencies (`kdlquery` CST parsing) removed from `ssc_codegen`, so that our suite only tests our own codebase.
15. As a developer working with `(raw)struct`, I want forbidden HTML operation linting tested via clean parameterized fixtures rather than five duplicated test functions.
16. As an HTML reconnaissance tool user, I want `scout` and `discover` tested through public entry points rather than fragile tests of private internal flag-parsing helpers.
17. As a developer maintaining JSON key alias remapping, I want dot-path traversal, strict allowlists, and missing field diagnostics tested end-to-end, without duplicate string-matching tests in the parser test module.

## Implementation Decisions

- **Pipeline Fuzzing Module Decoupling**: Retain the catalog of pipeline operations, the solo operation tests across all targets, the representative triple pipeline tests, and the Hypothesis property-based fuzzers. Delete the $O(N^2)$ static Cartesian pair generator tests (`test_op_pair_py` and `test_op_pair_js`).
- **Elimination of Dominated Smoke Tests in Integration Suite**: In the end-to-end codegen execution suite, remove tests that merely check `result is not None`. The comprehensive cross-target test (`test_all_targets_produce_same_result`) and the specific field validation classes dominate this check with exact value assertions.
- **Assertion-Free Test Cleanup**: In the integration test suite, eliminate or equip with meaningful assertions any tests that execute schemas without verifying their output.
- **Consolidation of Progressive Type Checks**: Where tests incrementally check `isinstance(list)` -> `key in item` -> `isinstance(val, str)` for the exact same schema across four targets, consolidate them into a single comprehensive test per target.
- **Removal of 3rd-Party Parser Verification**: In the parser test suite, remove tests that directly instantiate the upstream CST parser (`KDL2CSTParser`) to check basic literal decoding, relying instead on `parse_module` and real `.kdl` schema fixtures.
- **Consolidation of JSON Field Type Fixtures**: In the parser test module, replace the 10 separate disk-loaded `.kdl` fixture files for single-field JSON types with an in-memory parameterized test table checking `VariableType` mappings.
- **REST Runtime Parametrization Normalization**: In the REST API test module, remove the 4-way HTML converter parametrization (`PyBs4`, `PyLxml`, `PyParsel`, `PySlax`) from tests verifying `sscgen_runtime.py` and `-R` mode imports. Pin the HTML converter to one standard instance and preserve parametrization only across HTTP client strategies (`httpx`, `aiohttp`, `requests`).
- **Pruning of Implementation-Detail Absence Checks**: Remove negative string assertions checking for the absence of internal symbols from previous development iterations (such as `APIType` or `RestApiError`), retaining assertions on active contracts.
- **Consolidation of Forbidden Operations Linter Tests**: In the `(raw)struct` test module, replace the 5 separate test functions for forbidden HTML operations (`css`, `text`, `raw`, `attr`, `xpath`) with a single parameterized test.
- **Removal of Private Helper Tests in Exploration Module**: In the HTML reconnaissance module, prune unit tests that only verify internal flag tokenizers (`parse_attr_flag`, `compile_filters`), relying on the existing public `run_scout` and `run_discover` tests that exercise these code paths.

## Testing Decisions

- **Good Test Standard**: A good test exercises a meaningful public contract, failure mode, security boundary, or numerical/serialization invariant using an independent oracle. It asserts exact observable results (parsed dictionaries, emitted diagnostic codes, compiler exit statuses) rather than intermediate implementation mechanics or absence of arbitrary historical strings.
- **Seams Tested**:
  1. *Schema Validation & AST Seam (`parse_module`)*: Diagnostics, linter codes (`E*`, `W*`), and AST node representations are verified with known inputs.
  2. *Property-Based Robustness Seam (Hypothesis)*: Random op sequences, filter predicates, and assertion blocks are verified to produce structured error diagnostics without unhandled compiler crashes.
  3. *Code Generation Validation Seam (`Converter.convert`)*: Syntax validity and import resolution (`compile(code, "exec")`, `node --check`, `go vet`, `cargo check`).
  4. *End-to-End Parser Execution Seam (`cls(html).parse()`)*: Generated parsers are executed against real HTML fixtures and mock HTTP servers (`respx`), verifying exact data extraction.
- **Verification Protocol**:
  - Run `uv run pytest --collect-only` before and after cleanup to verify node reduction from ~6,151 to ~1,470 without unexpected test dropouts.
  - Run full `uv run pytest` to ensure 0 failures and 0 regressions across the entire surviving suite.
  - Run `uv run ruff check` and `uv run mypy ssc_codegen/` to verify code standards.

## Out of Scope

- Modifying any production compiler, reader, linter, or converter source code in `ssc_codegen/`.
- Removing genuine Hypothesis fuzz testing (`test_parser_never_crashes_*`).
- Modifying or removing cross-language toolchain validation tests (`go vet`, `go build`, `cargo check`, `node --check`).
- Removing mock HTTP integration tests (`test_rest_codegen.py`, `test_html_fetch_codegen.py`).
- Changing KDL Schema DSL syntax or diagnostic error codes.

## Further Notes

- The project was developed strictly under TDD, which naturally produced fine-grained micro-assertions and exploratory permutation matrices. Removing the scaffolding while keeping the safety net is standard post-stabilization cleanup.
- If in the future an operation's code generator needs target-specific pair-interaction logic, focused tests should be added specifically for that semantic interaction rather than re-introducing a full Cartesian product.
