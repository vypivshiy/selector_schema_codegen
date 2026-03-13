# Adding Linter Rules

> **Audience:** project maintainers  
> **Purpose:** internal guide for adding or changing built-in lint rules  
> **Last Updated:** 2026-03-13

---

## Scope

This document is **not** a user-facing extension guide.

The KDL linter in this project is an internal subsystem. New rules are added by modifying the repository itself, not by asking end users to plug in custom rule packages.

Use this guide when you need to:
- add a new built-in lint rule;
- refine an existing rule;
- move validation between structural checks and type checks;
- introduce new diagnostics for newly added DSL syntax.

---

## High-Level Architecture

The linter lives under:

- `ssc_codegen/kdl/linter/base.py`
- `ssc_codegen/kdl/linter/rules.py`
- `ssc_codegen/kdl/linter/rules_struct.py`
- `ssc_codegen/kdl/linter/type_rules.py`
- `ssc_codegen/kdl/linter/navigation.py`
- `ssc_codegen/kdl/linter/types.py`
- `ssc_codegen/kdl/linter/format_errors.py`

Loading happens via:

- `ssc_codegen/kdl/linter/__init__.py`

That file imports the rule modules for side effects, so decorator-based registration runs at import time.

In practical terms:
- define a rule in one of the rule modules;
- register it with `@LINTER.rule(...)` if it is a syntax/structural rule;
- keep type-flow validation in `type_rules.py`;
- make sure the module is imported by `ssc_codegen.kdl.linter.__init__`.

---

## Execution Model

### 1. Parse phase

`AstLinter.lint()` parses the source with tree-sitter.

If the parse tree contains syntax errors, the linter returns early with parser-level diagnostics.

This means:
- rules are only applied to syntactically valid CSTs;
- grammar recovery diagnostics belong in `base.py`, not in ordinary rules.

### 2. Metadata collection pass

Before walking rules, the linter collects:
- `define` declarations
- `transform` declarations

This metadata is stored on `LintContext` and is available to later rules.

### 3. Rule walk

`AstLinter._walk()` traverses the CST and applies registered rules depending on `WalkContext`.

### 4. Type pass

`type_rules.py` performs pipeline type inference and compatibility checks.

---

## Rule Placement: Which File to Edit

Choosing the correct module is more important than the rule itself.

### `rules.py`

Put a rule here if it validates:
- operation argument counts;
- simple argument syntax;
- regex capture-group constraints;
- predicate keyword placement;
- operation-local semantics that do **not** require full pipeline typing.

Examples:
- `css` requires one selector argument
- `fmt` must contain `{{}}`
- `re` must have exactly one capture group
- `starts` is only valid inside predicate containers

### `rules_struct.py`

Put a rule here if it validates:
- module-level declarations;
- struct shape;
- reserved fields like `@init`, `@split-doc`, `@table`, `@rows`, `@match`, `@value`;
- field placement inside struct/table/list contexts;
- `define` declaration form;
- `transform` declaration form.

Examples:
- `struct` requires a name
- table structs require reserved fields
- `@doc` must have an argument
- block/scalar `define` syntax correctness
- module-level `transform` definition correctness

### `type_rules.py`

Put a rule here if it depends on pipeline input/output types.

Examples:
- `to-int` only after string-like values
- `filter` requires a list type
- `match` must be first in a table pipeline
- `transform NAME` must match declared `accept` / `return`
- typed fallback compatibility

### `base.py`

Edit `base.py` only when the change is about:
- rule registration infrastructure;
- traversal behavior;
- syntax-error diagnostics;
- metadata collection;
- `WalkContext` behavior.

Do **not** add ordinary operation-specific checks in `base.py`.

---

## Rule Registration Model

Rules are registered through:

```python
@LINTER.rule("keyword")
def rule_name(node, ctx):
    ...
```

You can register one function for multiple node names:

```python
@LINTER.rule("css", "css-all")
def rule_css_like(node, ctx):
    ...
```

By default, rules are appended for a keyword.

If you need to replace all existing handlers for that keyword:

```python
@LINTER.rule("css", replace=True)
def replacement_rule(node, ctx):
    ...
```

Use `replace=True` carefully. In most cases you should extend behavior, not wipe out existing validation.

---

## What a Rule Receives

Rule signature:

```python
def my_rule(node: Node, ctx: LintContext) -> None:
    ...
```

### `node`

A tree-sitter node representing the current DSL node.

### `ctx`

`LintContext` is the main facade for rule authors.

Useful methods/properties include:

- `ctx.node_name(node)`
- `ctx.get_args(node)`
- `ctx.get_raw_args(node)`
- `ctx.get_arg(node, index)`
- `ctx.get_prop(node, key)`
- `ctx.get_children_nodes(node)`
- `ctx.has_empty_block(node)`
- `ctx.has_single_line_op(node, op_name)`
- `ctx.current_path`
- `ctx.defines`
- `ctx.transforms`
- `ctx.init_fields`
- `ctx.is_define_ref(arg)`
- `ctx.resolve_scalar_arg(arg)`

Use these helpers instead of manually walking CST child nodes whenever possible.

---

## Reporting Diagnostics

Use `ctx.error(...)` for hard failures and `ctx.warning(...)` for non-fatal diagnostics.

Minimal example:

```python
ctx.error(
    node,
    code=ErrorCode.MISSING_ARGUMENT,
    message="'my-op' requires one argument",
    hint="example: my-op value",
)
```

Extended example:

```python
ctx.error(
    node,
    code=ErrorCode.INVALID_ARGUMENT,
    message="invalid regex pattern",
    hint='check regex syntax; raw strings #"..."# are recommended',
    label="invalid regex",
    notes=["compiled at lint time"],
)
```

Available extra fields:
- `label`
- `notes`
- `end_line`
- `end_col`

Those feed the richer terminal formatter in `format_errors.py`.

---

## Choosing the Right `ErrorCode`

Prefer the most specific code that matches the failure class.

### Syntax-ish / shape issues
Use:
- `INVALID_SYNTAX`
- `MISSING_ARGUMENT`
- `INVALID_ARGUMENT`
- `EMPTY_BLOCK`
- `UNEXPECTED_CHILDREN`

Examples:
- wrong arity
- malformed regex literal
- missing required property
- empty required block

### Type issues
Use:
- `TYPE_MISMATCH`
- `INCOMPATIBLE_OPERATION`

Examples:
- applying string op to document
- using `filter` on scalar value
- mismatched transform type signature

### Semantic/reference issues
Use:
- `UNKNOWN_OPERATION`
- `UNKNOWN_FIELD`
- `MISSING_REQUIRED_FIELD`
- `INVALID_FIELD_FOR_TYPE`
- `UNDEFINED_REFERENCE`
- `INIT_FIELD_NOT_FOUND`
- `DEFINE_NOT_FOUND`

Examples:
- unknown keyword
- bad reserved-field placement
- unresolved `@init` reference
- using a scalar define as a block operation

### Structure issues
Use:
- `INVALID_STRUCT_TYPE`
- `MISSING_SPECIAL_FIELD`

Examples:
- invalid `struct type=...`
- missing `@rows` in a table struct

When in doubt, prefer consistency with existing rules over inventing a new interpretation.

---

## Path and Scope Handling

The traversal engine already pushes node names onto the path tracker while walking.

For most rules, `ctx.current_path` is enough.

Use it when:
- building better debug output;
- adding context-sensitive notes;
- understanding where diagnostics land in nested structs.

If a helper needs a temporary nested scope, use the path tracker APIs rather than assembling strings by hand.

---

## Working with `define` and `transform` Metadata

`base.py` collects module-level metadata before rule execution.

### `ctx.defines`

Contains scalar and block defines.

Use it when:
- an argument may refer to a scalar define;
- a pipeline operation may resolve to a block define;
- you need to distinguish scalar-vs-block define behavior.

Relevant helpers:

```python
ctx.is_define_ref(arg)
ctx.resolve_scalar_arg(arg)
```

### `ctx.transforms`

Contains transform definitions collected at module level.

Use it when validating:
- whether `transform NAME` exists;
- whether a transform supports the current pipeline type;
- language implementation requirements in transform declarations.

---

## Structural Rules vs Type Rules

A common mistake is putting type-sensitive logic into ordinary syntax rules.

Use this rule of thumb:

### Structural rule

Ask:
- does the node exist in the right place?
- does it have the right number of args?
- are required props/children present?
- is this keyword allowed in this context?

If yes, it belongs in `rules.py` or `rules_struct.py`.

### Type rule

Ask:
- does this operation accept the current pipeline type?
- what type does it produce?
- does fallback value match the inferred type?
- is this transform call compatible with `accept/return`?

If yes, it belongs in `type_rules.py`.

---

## Adding a New Rule: Recommended Workflow

### Step 1. Decide where the rule belongs

Choose among:
- `rules.py`
- `rules_struct.py`
- `type_rules.py`
- rarely `base.py`

### Step 2. Reuse existing helpers first

Before writing CST-level code manually, check whether `LintContext` / `NodeNavigator` already provide what you need.

### Step 3. Register the rule

Add the new decorator-based rule in the correct module.

### Step 4. Write actionable diagnostics

Every new error should include:
- a precise message;
- a fix-oriented hint;
- a consistent error code.

### Step 5. Add tests

Update or add tests under:
- `tests/linter/test_rules.py`
- `tests/linter/test_rules_struct.py`
- `tests/linter/test_type_rules.py`

Choose the file based on the same placement logic as the rule itself.

### Step 6. Verify formatter output if needed

If the new rule uses:
- custom labels,
- notes,
- richer spans,

run a real lint example and inspect the terminal output.

---

## Rule Design Guidelines

### Prefer small, specific rules

Good:
- one rule validates one keyword family or one invariant.

Avoid:
- giant rules that validate unrelated operations.

### Keep messages user-facing

Messages should describe:
- what is wrong;
- which keyword is affected;
- what shape is expected.

### Keep hints actionable

A good hint usually includes:
- corrected syntax;
- a short example;
- the proper enclosing block if relevant.

### Avoid duplicating parser responsibilities

If the issue is malformed KDL itself, let syntax diagnostics handle it.
Do not try to re-detect parse failures in ordinary lint rules.

### Avoid duplicating type engine responsibilities

If a rule is fundamentally about `accept -> return` compatibility, move it to `type_rules.py`.

---

## Testing Expectations

Every non-trivial rule change should come with tests.

### For syntax / argument rules

Add focused tests for:
- missing args;
- too many args;
- malformed props;
- empty required blocks.

### For structural rules

Add tests for:
- wrong declaration placement;
- missing reserved fields;
- invalid struct type combinations;
- bad `define` / `transform` declaration forms.

### For type rules

Add tests for:
- valid pipeline type progression;
- invalid progression;
- fallback typing;
- transform typing;
- `match` / `filter` special cases.

### Prefer exact diagnostics where stable

Assert on:
- `error.code`
- key parts of `message`
- key parts of `hint`

Do not overfit tests to cosmetic formatting unless the formatting itself is the subject of the change.

---

## Common Mistakes

### 1. Putting a rule in the wrong module

Symptom:
- the rule works, but future maintenance becomes confusing.

Fix:
- move syntax/shape checks out of `type_rules.py`;
- move type-flow checks out of `rules.py`.

### 2. Using raw CST inspection unnecessarily

Symptom:
- repeated low-level child traversal logic across rules.

Fix:
- prefer `LintContext` helpers and add navigation helpers if a pattern repeats.

### 3. Emitting vague messages

Bad:
- `invalid value`

Better:
- `'fmt' template is missing the '{{}}' placeholder'`

### 4. Forgetting single-line child syntax

Some rules must support both:
- multiline blocks
- single-line inline child form

If the DSL keyword allows children, check both `ctx.get_children_nodes(node)` and relevant helper logic like `ctx.has_single_line_op(...)` where appropriate.

### 5. Forgetting module import side effects

If a new rule module is added, it must be imported from `ssc_codegen.kdl.linter.__init__`, otherwise registration will never happen.

---

## Example Pattern

A minimal built-in rule typically looks like this:

```python
from tree_sitter import Node

from ssc_codegen.kdl.linter.base import LINTER, LintContext
from ssc_codegen.kdl.linter.types import ErrorCode


@LINTER.rule("my-op")
def rule_my_op(node: Node, ctx: LintContext) -> None:
    args = ctx.get_args(node)
    if len(args) != 1:
        ctx.error(
            node,
            ErrorCode.MISSING_ARGUMENT,
            message="'my-op' requires exactly 1 argument",
            hint='example: my-op "value"',
        )
        return

    value = args[0]
    if not value:
        ctx.error(
            node,
            ErrorCode.INVALID_ARGUMENT,
            message="'my-op' argument must not be empty",
            hint='example: my-op "value"',
        )
```

Use this as a shape template, then adapt the details to the correct rule module.

---

## Summary

When adding a new linter rule:
- decide whether it is structural, syntactic, or type-based;
- place it in the correct module;
- register it with `@LINTER.rule(...)` when applicable;
- use `LintContext` helpers rather than raw CST traversal when possible;
- emit precise diagnostics with actionable hints;
- add tests in the corresponding linter test file.

The most important maintenance rule is:

> Keep parsing concerns, structural validation, and type-flow validation separate.

That separation is what keeps the linter predictable and easy to evolve.
