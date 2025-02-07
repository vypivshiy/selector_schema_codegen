# demo

This folder provides synthetic documents for demonstrate various cases in tutorial-like style.

all examples usage next convert command:

```shell
ssc-gen py schema.py -i parsel -o . --prefix parser_
```

if you want see how looks ast tokens in output code - add extra flag `--debug`

## examples files structure:

- index.html - synthetic example html input
- main.py - example script usage
- schema.py - config example
- parser_schema.py - generated code from config (schema.py)

## Table of content

1. [basic](1_basic) - high-level simple example usage
2. [string_operations](2_string_operations) string operations cases
3. [default values](3_default_values) default values examples
4. [validation](4_validation) validate document input and fields
5. [schema types](5_schema_types) - demonstration of available struct serialization methods
6. [nested schemas](6_nested_schemas) - inheirence, struct inside a struct of data inside a struct of data
