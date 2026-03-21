# Adding Linter Rules

> **Audience:** project maintainers
> **Purpose:** internal guide for adding or changing built-in lint rules
> **Last Updated:** 2026-03-21

---

## Scope

This document is **not** a user-facing extension guide.

The KDL linter is an internal subsystem. New rules are added by modifying the repository itself.

Use this guide when you need to:
- add a new built-in lint rule;
- refine an existing rule;
- move validation between structural checks and type checks;
- introduce diagnostics for newly added DSL syntax.

---

## High-Level Architecture

The linter lives under:

```
ssc_codegen/linter/
    __init__.py          # public API, imports rule modules
    _kdl_lang.py         # tree-sitter KDL language loader
    base.py              # AstLinter, LintContext, WalkContext
    errors.py            # ErrorCollector
    format_errors.py     # Rust-style terminal diagnostics
    metadata.py          # ModuleMetadata (defines, transforms, init_fields)
    navigation.py        # NodeNavigator (CST helpers)
    path.py              # PathTracker (breadcrumb for error context)
    rules.py             # operation argument/syntax rules
    rules_struct.py      # struct/module-level rules
    rule_keywords.py     # dsl/expr keyword rules
    type_rules.py        # pipeline type inference & checking
    types.py             # ErrorCode, LintError, RawArg, DefineInfo, etc.
```

Loading: `__init__.py` imports `rules`, `rules_struct`, `rule_keywords`, `type_rules` for side-effect registration.

---

## Execution Model

### 1. Parse phase

`AstLinter.lint()` parses the source with tree-sitter. If the parse tree contains syntax errors, the linter returns early with parser-level diagnostics.

### 2. Metadata collection pass

Before walking rules, the linter collects:
- `define` declarations (scalar and block)
- `transform` declarations
- `dsl` declarations

Stored in `ModuleMetadata` on `LintContext`.

### 3. Rule walk

`AstLinter._walk()` traverses the CST and applies registered rules depending on `WalkContext`:

- `MODULE` - top-level declarations
- `STRUCT_BODY` - inside struct fields
- `INIT_BLOCK` - inside @init
- `PIPELINE` - inside field pipelines
- `JSON_TYPEDEF` - inside json blocks
- `SPECIAL_FIELD` - inside @pre-validate, @split-doc, etc.

### 4. Type pass

`type_rules.py` performs pipeline type inference and compatibility checks.

---

## Rule Placement: Which File to Edit

### `rules.py`

Operation argument/syntax rules:
- argument counts
- regex capture-group constraints
- predicate keyword placement
- operation-local semantics (no full pipeline typing needed)

Examples: `css` requires one selector arg, `fmt` must contain `{{}}`, `re` needs exactly one capture group.

### `rules_struct.py`

Module/struct-level rules:
- `struct` shape (name, type, required fields)
- reserved fields (`@init`, `@split-doc`, `@table`, `@rows`, `@match`, `@value`)
- `define` and `transform` declaration form
- wildcard `*` rule for unknown operations

### `rule_keywords.py`

Rules for newer DSL keywords:
- `dsl` block validation (lang property, import/code children, `{{PRV}}`/`{{NXT}}` markers)
- `expr` operation validation (target must be dsl or block define)
- `define` inside pipeline guard (module-level keyword enforcement)

### `type_rules.py`

Pipeline type inference and checking:
- `accept` -> `return` compatibility
- `filter` requires list type
- `match` must be first op
- `fallback` value type matching
- `transform` and `dsl` accept/return validation
- Block define expansion with cycle detection

### `base.py`

Infrastructure only:
- rule registration
- traversal behavior
- syntax-error diagnostics
- metadata collection

---

## Rule Registration

```python
@LINTER.rule("keyword")
def rule_name(node, ctx):
    ...
```

Multiple keywords:

```python
@LINTER.rule("css", "css-all")
def rule_css_like(node, ctx):
    ...
```

Replace existing handlers:

```python
@LINTER.rule("css", replace=True)
def replacement_rule(node, ctx):
    ...
```

---

## What a Rule Receives

```python
def my_rule(node: Node, ctx: LintContext) -> None:
```

### `node` - tree-sitter CST node

### `ctx` - LintContext facade

Methods/properties:
- `ctx.node_name(node)` - first identifier
- `ctx.get_args(node)` - positional arguments as strings
- `ctx.get_raw_args(node)` - arguments with type info (`RawArg`)
- `ctx.get_arg(node, index)` - single arg
- `ctx.get_prop(node, key)` - property value (`key=value`)
- `ctx.get_children_nodes(node)` - child nodes in block
- `ctx.has_empty_block(node)` - empty block check
- `ctx.has_single_line_op(node, op_name)` - single-line bare identifier
- `ctx.current_path` - breadcrumb string
- `ctx.defines` - `dict[str, DefineInfo]`
- `ctx.transforms` - `dict[str, TransformInfo]`
- `ctx.init_fields` - `set[str]`
- `ctx.is_define_ref(arg)` - check if arg references a define
- `ctx.resolve_scalar_arg(arg)` - resolve scalar define value

---

## Reporting Diagnostics

```python
ctx.error(
    node,
    code=ErrorCode.MISSING_ARGUMENT,
    message="'my-op' requires one argument",
    hint='example: my-op "value"',
)

ctx.warning(
    node,
    code=ErrorCode.DEPRECATED_SYNTAX,
    message="'old-op' is deprecated",
    hint="use 'new-op' instead",
)
```

Extra fields: `label`, `notes`, `end_line`, `end_col`.

---

## Error Codes

### Syntax/shape (E000-E004)

| Code | Name | Use for |
|------|------|---------|
| E000 | `INVALID_SYNTAX` | Parser-level syntax errors |
| E001 | `MISSING_ARGUMENT` | Missing required args |
| E002 | `INVALID_ARGUMENT` | Invalid argument values |
| E003 | `EMPTY_BLOCK` | Empty block where content required |
| E004 | `UNEXPECTED_CHILDREN` | Unexpected child nodes |

### Type (E100-E101)

| Code | Name | Use for |
|------|------|---------|
| E100 | `TYPE_MISMATCH` | Type incompatibility in pipeline |
| E101 | `INCOMPATIBLE_OPERATION` | Operation not valid for type |

### Semantic (E200-E302)

| Code | Name | Use for |
|------|------|---------|
| E200 | `UNKNOWN_OPERATION` | Unknown operation name |
| E201 | `UNKNOWN_FIELD` | Unknown field name |
| E202 | `MISSING_REQUIRED_FIELD` | Required field missing |
| E203 | `INVALID_FIELD_FOR_TYPE` | Field invalid for struct type |
| E300 | `UNDEFINED_REFERENCE` | Reference to undefined name |
| E301 | `INIT_FIELD_NOT_FOUND` | @init field not declared |
| E302 | `DEFINE_NOT_FOUND` | Define not declared |

### Structure (E400-E401)

| Code | Name | Use for |
|------|------|---------|
| E400 | `INVALID_STRUCT_TYPE` | Unknown struct type |
| E401 | `MISSING_SPECIAL_FIELD` | Required special field missing |

### Warnings (W001-W002)

| Code | Name | Use for |
|------|------|---------|
| W001 | `DEPRECATED_SYNTAX` | Deprecated syntax usage |
| W002 | `UNUSED_FIELD` | Unused field |

---

## Adding a New Rule: Workflow

1. **Decide placement** - `rules.py`, `rules_struct.py`, `rule_keywords.py`, or `type_rules.py`
2. **Reuse helpers** - check `LintContext`/`NodeNavigator` before writing raw CST code
3. **Register** - `@LINTER.rule("keyword")`
4. **Write diagnostics** - precise message + actionable hint + correct ErrorCode
5. **Add tests** - in the corresponding `tests/linter/test_*.py` file
6. **Verify formatter** - if using custom labels/notes, check terminal output

---

## Testing

Tests live under `tests/linter/`:

- `test_rules.py` - operation argument/syntax rules
- `test_rules_struct.py` - struct/module-level rules
- `test_type_rules.py` - pipeline type checking

For each rule, test:
- Valid cases (no errors)
- Missing args
- Invalid args
- Wrong context
- Edge cases

Assert on `error.code` and key parts of `message`/`hint`.

---

## Common Mistakes

1. **Wrong module** - type-sensitive logic in `rules.py`, or shape checks in `type_rules.py`
2. **Raw CST inspection** - prefer `LintContext` helpers
3. **Vague messages** - bad: "invalid value"; good: "'fmt' template is missing '{{}}' placeholder"
4. **Missing single-line support** - some keywords allow both block and inline form
5. **Missing import** - new rule module must be imported in `__init__.py`

---

## Design Principles

- **Small, specific rules** - one rule validates one invariant
- **Actionable hints** - include corrected syntax or example
- **Don't duplicate parser** - malformed KDL is handled by syntax diagnostics
- **Don't duplicate type engine** - `accept`/`return` logic goes in `type_rules.py`
- **Structural vs type separation** is the most important maintenance rule
