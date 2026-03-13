# Implementing a Converter

> **Purpose:** General guide for implementing a new code generator backend  
> **Scope:** Architecture, contracts, traversal model, and implementation checklist  
> **Last Updated:** 2026-03-13

---

## Overview

A converter takes the project AST produced by `ssc_codegen.kdl.parser` and emits source code for some target runtime.

In other words:

```text
KDL schema -> AST -> converter -> generated source code
```

This document is intentionally **language-agnostic**:
- it does **not** assume Python, JavaScript, or any specific runtime library;
- it does **not** prescribe a DOM API;
- it focuses on the **contracts** a converter must satisfy.

A concrete converter decides:
- how a document is represented at runtime;
- how selectors are executed;
- how text/attributes/raw HTML are extracted;
- how fallback / predicates / transforms are rendered;
- how type aliases, imports, helpers, and parser entry points are generated.

---

## What a Converter Is Responsible For

A converter is responsible for turning AST nodes into emitted code.

Typical responsibilities:

1. **Module-level output**
   - prologue / file header
   - imports
   - helper functions
   - generated type declarations
   - generated parser classes / functions

2. **Container nodes**
   - JSON schema declarations
   - type declarations
   - structs
   - init blocks

3. **Field pipelines**
   - selectors
   - extractors
   - transforms
   - casts
   - predicates / control flow
   - return statements

4. **Runtime integration**
   - runtime document type
   - nested parser invocation
   - transform invocation
   - fallback semantics
   - collection handling

A converter is **not** responsible for:
- parsing KDL;
- validating DSL syntax;
- type inference rules;
- semantic AST construction.

Those happen before conversion.

---

## Where the Core API Lives

The generic converter API is implemented in:

- `ssc_codegen/kdl/converters/base.py`
- `ssc_codegen/kdl/converters/helpers.py`

Important types:

- `BaseConverter`
- `ConverterContext`

The converter framework is registry-based:
- a handler is registered for a concrete AST node type;
- the traversal engine walks the AST;
- each handler emits one code fragment or a list of code lines.

---

## Core Converter Contract

At the highest level, a converter must support:

```text
Module AST -> string source code
```

In framework terms:

- `BaseConverter.convert(module_ast)` traverses `module_ast.body`
- registered handlers emit code for each node
- the final result is a single source string

A converter is therefore a combination of:
- traversal rules from `BaseConverter`
- handler registrations for AST node types
- target-specific rendering decisions

---

## ConverterContext

`ConverterContext` carries generation state while walking the AST.

Current fields:

- `index` — pipeline variable index
- `depth` — indentation depth
- `var_name` — base variable name
- `indent_char` — indentation unit

Derived helpers:

- `ctx.prv` — current input variable name
- `ctx.nxt` — next output variable name
- `ctx.indent` — current indentation prefix

Conceptually:

```text
index=0 -> prv=v,  nxt=v1
index=1 -> prv=v1, nxt=v2
index=2 -> prv=v2, nxt=v3
```

This is the standard pipeline model:
- each expression consumes `prv`
- emits into `nxt`
- the pipeline advances after each emitted step

---

## Traversal Model

`BaseConverter` treats AST nodes in three different categories.

### 1. Container nodes

Examples:
- `JsonDef`
- `TypeDef`
- `Struct`
- `Init`

Behavior:
- traversal goes deeper (`depth + 1`)
- pipeline index resets for the container body
- children are emitted as nested declarations/items

Use containers for:
- declarations
- generated type blocks
- parser class/function bodies
- init sections

---

### 2. Pipeline nodes

Examples:
- `Field`
- `InitField`
- `PreValidate`
- `SplitDoc`
- `Key`
- `Value`
- table-reserved fields

Behavior:
- pipeline traversal is explicit
- handlers are expected to call `self._emit_pipeline(...)`
- pipeline index advances between expressions

Use pipeline nodes when the body means:

```text
input -> op1 -> op2 -> op3 -> result
```

---

### 3. Predicate nodes

Examples:
- `Filter`
- `Assert`
- `Match`
- `LogicNot`
- `LogicAnd`
- `LogicOr`

Behavior:
- traversal stays in the same pipeline stage
- nested predicate body is rendered as logical conditions
- predicate blocks do not behave like ordinary field pipelines

Use predicate nodes for:
- boolean conditions
- guards
- validation checks
- filtering conditions

---

## Handler Registration Model

Handlers are registered per AST node type.

The framework supports:

- **pre-handlers** — emitted before traversing a node body
- **post-handlers** — emitted after traversing a node body

Conceptually:

```text
pre(node)
  traverse body
post(node)
```

This is useful for nodes that naturally wrap nested code, for example:
- opening/closing blocks
- function/class boundaries
- try/finally or try/catch wrappers
- condition blocks

### Registration styles

A converter may register handlers through:
- `converter.pre(...)`
- `converter.post(...)`
- `converter(...)` as shorthand for `pre(...)`

### Inheritance / extension

`BaseConverter.extend()` creates a child converter that inherits all handlers.

This is useful when you want:
- a shared base backend family;
- several target dialects;
- incremental override of only a few nodes.

Even though this document is language-agnostic, the pattern is generally:

```text
generic backend base
    -> specialized runtime A
    -> specialized runtime B
```

---

## Output Design Principles

A good converter should make the generated code:

1. **Readable**
   - stable indentation
   - predictable variable names
   - simple control flow

2. **Deterministic**
   - same AST -> same output layout
   - no unstable ordering

3. **Composable**
   - nested structs and transforms are reusable
   - helper functions/imports are centralized

4. **Runtime-minimal**
   - generate only required helpers/imports
   - avoid unnecessary wrappers

5. **Semantically faithful**
   - fallback behavior matches AST semantics
   - predicate logic preserves original DSL meaning
   - return types match converter expectations

---

## What Every New Converter Must Decide

Before implementing handlers, define the following target-level decisions.

### 1. Document model

What is the runtime value for a document node?

Examples of questions:
- Is it a tree object, DOM node, document wrapper, or plain string?
- Are selectors evaluated on a node or on a separate query engine?
- How are nested documents represented?

### 2. Scalar model

How are scalar values represented?

You need clear rules for:
- strings
- numbers
- booleans
- null/none
- arrays/lists
- objects/maps

### 3. Error / fallback behavior

How should fallback be rendered?

Typical strategies:
- try/catch or try/except
- null checks + explicit branching
- sentinel-based recovery

### 4. Type declarations

How should generated result types be represented?

Possible shapes:
- interfaces / type aliases
- structs / records
- plain documentation comments
- no explicit static types at all

### 5. Import / helper management

How are imports/helpers inserted?

You need a strategy for:
- deduplicating imports
- placing utilities before generated parsers
- wiring transform-level imports

---

## Recommended Implementation Order

When adding a new converter, implement handlers in this order.

### Step 1. Module skeleton

Start with nodes that shape the file:
- start/end hooks
- imports
- utility blocks
- docstring/header

Goal: produce a syntactically valid output file.

### Step 2. Type-level declarations

Add support for:
- `JsonDef`
- `TypeDef`
- any result type declarations

Goal: generated code can describe output shapes.

### Step 3. Structs and entry points

Add support for:
- `Struct`
- parser constructor / entry method
- per-field parsing methods
- `Init`

Goal: a simple struct with one field can be emitted end-to-end.

### Step 4. Core pipeline expressions

Implement the smallest usable pipeline subset first:
- selectors
- text/attr/raw extractors
- string cleanup transforms
- return handling

Goal: basic extraction works.

### Step 5. Collections and typed transforms

Add support for:
- list-producing selectors
- list operations (`first`, `last`, `index`, `slice`, `len`, `unique`)
- conversions (`to-int`, `to-float`, `to-bool`)

Goal: common scraping patterns work.

### Step 6. Control and predicates

Add support for:
- `FallbackStart` / `FallbackEnd`
- `Filter`
- `Assert`
- `Match`
- logical predicate containers

Goal: validation and guarded extraction work.

### Step 7. Structured composition

Add support for:
- `Nested`
- `Jsonify`
- `TransformCall`
- table/list struct behavior

Goal: full DSL coverage.

---

## Minimal Viable Converter Checklist

A converter is minimally practical when it can correctly emit:

- module header / imports
- at least one `Struct`
- one simple `Field`
- selector + extractor + return
- fallback handling
- nested struct invocation
- generated type declarations

If any of these are missing, the backend is usually not yet usable for real schemas.

---

## Designing Handlers

Each handler should answer three questions.

### 1. What is the input value?
Usually `ctx.prv`.

### 2. What is the output value?
Usually `ctx.nxt`.

### 3. Does this node open a nested scope?
If yes, use pre/post emission or delegate to `_emit_pipeline()` / nested traversal.

### Good handler properties

A good handler should be:
- small;
- deterministic;
- side-effect free;
- focused on one AST node type;
- explicit about its output variable.

### Avoid

Avoid handlers that:
- inspect unrelated node types;
- duplicate traversal logic already handled by `BaseConverter`;
- manually advance variable names outside `ConverterContext` rules;
- mix import collection, type generation, and pipeline emission in one place.

---

## Fallback Semantics

Fallback is special because it affects control flow.

In `BaseConverter._emit_pipeline(...)`:
- `FallbackStart` opens a protected region
- inner nodes are emitted at deeper indentation
- `FallbackEnd` closes the region and syncs the outer pipeline index

This means a converter must treat fallback as a **structural control-flow node**, not as a simple one-line expression.

If your target runtime has exceptions, fallback often maps naturally to protected execution.
If it does not, implement equivalent branching behavior explicitly.

---

## Nested and Structured Parsing

Two structured operations deserve separate design attention.

### `Nested`

`Nested` invokes another generated parser/entity on the current runtime value.

Your converter must define:
- how a nested parser is called;
- how list-nested vs scalar-nested is represented;
- whether nested parsing is static, instance-based, or helper-based.

### `Jsonify`

`Jsonify` converts a string value into structured data and maps it to a declared JSON schema.

Your converter must define:
- how raw string input becomes parsed JSON/runtime data;
- how `path=...` navigation is rendered;
- how arrays vs single objects are handled.

---

## Transform Support

`TransformDef` and `TransformCall` are the extension points for user-defined operations.

A converter must decide:
- how transform implementations are emitted;
- how transform imports are collected;
- how transform calls are invoked from pipelines;
- how typed `accept` / `ret` expectations map to runtime code.

Good practice:
- treat transform code as backend-owned runtime snippets;
- keep transform invocation consistent with ordinary pipeline variable flow;
- deduplicate imports/helpers introduced by transforms.

---

## Suggested Test Strategy

A new converter should be validated at three levels.

### 1. AST unit coverage

Test small schemas covering:
- scalar extraction
- list extraction
- fallback
- predicates
- nested
- jsonify
- transforms

### 2. Golden output tests

Given a schema, assert that generated code contains the expected structure:
- imports
- type declarations
- parser entry points
- field methods
- transform helpers

### 3. Runtime smoke tests

If the target backend can run in CI, execute generated code on small inputs and verify:
- output values
- fallback behavior
- predicate behavior
- nested parsing

---

## Practical Implementation Checklist

When creating a new backend, use this order:

- [ ] Create a new `BaseConverter` instance or extend an existing one
- [ ] Implement module/file skeleton handlers
- [ ] Implement type declaration handlers
- [ ] Implement `Struct` / `Init` / `Field` handlers
- [ ] Implement core selector + extractor handlers
- [ ] Implement string and regex transforms
- [ ] Implement type conversion handlers
- [ ] Implement fallback nodes
- [ ] Implement predicate containers and predicate operations
- [ ] Implement `Nested`
- [ ] Implement `Jsonify`
- [ ] Implement `TransformCall` / transform import wiring
- [ ] Register the converter in CLI target selection
- [ ] Add parser-to-output tests
- [ ] Add runtime smoke tests if possible

---

## Common Failure Modes

Watch for these issues when implementing a converter.

### Variable chain drift

Symptoms:
- generated code uses `v3` before it exists;
- fallback body and outer pipeline lose sync.

Cause:
- handler bypasses `ConverterContext` model.

### Wrong traversal depth

Symptoms:
- nested blocks are emitted with broken indentation;
- predicate code is rendered as pipeline code.

Cause:
- handler duplicates traversal incorrectly or assumes wrong node category.

### Mixing structural and scalar semantics

Symptoms:
- `Nested` or `Jsonify` treated as plain string transforms;
- `Filter` rendered as ordinary pipeline assignment.

Cause:
- missing distinction between pipeline nodes and structural/control nodes.

### Duplicated imports/helpers

Symptoms:
- same helper emitted multiple times;
- transform imports repeated per field.

Cause:
- no centralized import/helper emission strategy.

---

## Recommended Style for New Backends

Prefer this approach:

1. start from the smallest working converter;
2. keep handlers focused and mechanical;
3. centralize target-specific naming/helpers in one place;
4. use `.extend()` when a backend is a dialect of another backend;
5. keep AST traversal policy in `BaseConverter`, not in ad-hoc handler code.

---

## Summary

A converter in this project is:
- a registry of AST-node handlers;
- driven by `BaseConverter` traversal;
- guided by `ConverterContext` variable and indentation state;
- responsible for emitting valid target source code from semantic AST.

The most important design rule is:

> Keep the converter focused on **rendering AST semantics**, not on reparsing DSL details.

If that boundary is kept clean, new backends stay predictable, testable, and easy to evolve.
