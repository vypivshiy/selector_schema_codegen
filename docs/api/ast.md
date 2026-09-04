# AST Nodes Reference

The Abstract Syntax Tree (AST) intermediate representation used by `ssc_codegen`. All nodes are strongly-typed dataclasses inheriting from `ssc_codegen.ast.base.Node`.

## Base Node

::: ssc_codegen.ast.base.Node

## Enums & Types

::: ssc_codegen.ast.types.VariableType

::: ssc_codegen.ast.types.TypeInfo

::: ssc_codegen.ast.types.StructType

## Top-Level Module & Function Nodes

::: ssc_codegen.ast.module.Module

::: ssc_codegen.ast.function.FunctionDef

::: ssc_codegen.ast.module.Utilities

::: ssc_codegen.ast.module.CodeStartHook

::: ssc_codegen.ast.module.CodeEndHook

## Schema & Type Models

::: ssc_codegen.ast.jsondef.JsonDef

::: ssc_codegen.ast.jsondef.JsonDefField

::: ssc_codegen.ast.typedef.TypeDef

::: ssc_codegen.ast.typedef.TypeDefField

## Struct & Field Definitions

::: ssc_codegen.ast.struct.StructBase

::: ssc_codegen.ast.struct.Struct

::: ssc_codegen.ast.struct.StructRest

::: ssc_codegen.ast.struct.Field

::: ssc_codegen.ast.struct.Init

::: ssc_codegen.ast.struct.InitField

::: ssc_codegen.ast.struct.InitFieldCall

::: ssc_codegen.ast.struct.PreValidate

::: ssc_codegen.ast.struct.SplitDoc

::: ssc_codegen.ast.struct.Key

::: ssc_codegen.ast.struct.Value

::: ssc_codegen.ast.struct.TableConfig

::: ssc_codegen.ast.struct.TableMatchKey

::: ssc_codegen.ast.struct.TableRows

::: ssc_codegen.ast.struct.CheckMethod

::: ssc_codegen.ast.struct.StartParse

## HTTP & REST Request Declarations

::: ssc_codegen.ast.struct.MethodBase

::: ssc_codegen.ast.struct.MethodFetch

::: ssc_codegen.ast.struct.MethodRest

::: ssc_codegen.ast.struct.RequestHttp

::: ssc_codegen.ast.struct.PlaceholderSpec

::: ssc_codegen.ast.struct.PlaceholderTemplate

::: ssc_codegen.ast.struct.ErrorResponse

## Pipeline Operations

### Selectors
::: ssc_codegen.ast.selectors

### Extraction
::: ssc_codegen.ast.extract

### String Manipulation
::: ssc_codegen.ast.string

### Regular Expressions
::: ssc_codegen.ast.regex

### Array & Slicing
::: ssc_codegen.ast.array

### Type Casting & Jsonify
::: ssc_codegen.ast.cast

### Control Flow
::: ssc_codegen.ast.control

## Predicates & Conditions

::: ssc_codegen.ast.predicate_containers

::: ssc_codegen.ast.predicate_ops

## Extensions & REST Artifacts

::: ssc_codegen.ast.extension

::: ssc_codegen.ast.rest
