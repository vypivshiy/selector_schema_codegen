# Traversal Engine Reference

Language-agnostic AST traversal and code generation state accumulation machinery.

## Base Walker

`BaseWalker` manages the dispatch table mapping AST node types to handler methods across container, pipeline, and predicate traversal modes.

::: ssc_codegen.traversal.walker.BaseWalker

## Walk Context

::: ssc_codegen.traversal.context.WalkContext

## Traversal Utilities

::: ssc_codegen.traversal.utils

## Generation & Runtime Assembly

::: ssc_codegen.generation.builder.ModuleBuilder

::: ssc_codegen.generation.runtime
