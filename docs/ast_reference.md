# AST reference

## High-level AST structure schema overview

```
ModuleProgram
    Docstring
    ModuleImports
    JsonStruct
        JsonStructField
        ...
    ...
    
    TypeDef
        TypeDefField
        ...
    ...
    
    StructParser
        Docstring
        StructInit
        PreValidateFunction
            BaseExpression
            ...
           
        PartDocFunction
            BaseExpression
            ...
            
        StructFieldFunction...
            BaseExpression
            ...
        StartParseFunction
            CallStructFunctionExpression
            ...
    ...
```

to see which block of code belongs to a node you can add the `--debug` flag

- ModuleProgram - first Node, contains all nodes
- Docstring - mark generate docstring. in StructParser, can be mark place top (C-like languages) or bottom (python)
- JsonStruct - if language required types or support typing, generate types for json output
  - JsonStructField - field for JsonStruct
- TypeDef - if language required types or support typing, generate types for StructParser output
  - TypeDefField - field for TypeDef
- StructParser - main generated parser class
  - StructInit - constructor (if required)
  - BaseExpression - single expression inner PreValidateFunction, PartDocFunction, StructFieldFunction, StartParseFunction
  - CallStructFunctionExpression - call methods inner generated class
  - PreValidateFunction - pre validate document method
  - PartDocFunction - split document to elements method
  - StructFieldFunction - method for parse field with expressions
  - StartParseFunction - method for accumulate fields to structure