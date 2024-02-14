# Selector schema codegen

ssc_codegen - generator of parsers for various programming languages (for html priority) using
python-DSL configurations with built-in declarative language.

Designed to port parsers to various programming languages and libs

## Install

### pipx (recommended)

```shell
pipx install ssc_codegen
```

### pip

```shell
pip install ssc_codegen
```

## Supported libs and languages

| language | lib                                                          | xpath | css | formatter   |
|----------|--------------------------------------------------------------|-------|-----|-------------|
| python   | bs4                                                          | NO    | YES | black       |
| -        | parsel                                                       | YES   | YES | -           |
| -        | selectolax (modest)                                          | NO    | YES | -           |
| -        | scrapy (based on parsel, but class init argument - Response) | YES   | YES | -           |
| dart     | universal_html                                               | NO    | YES | dart format |

### Quickstart

see [example](example) and read code with comments

### Recommendations

- usage css selector: they can be **guaranteed** converted to xpath (if target language not support CSS selectors)
- usage simple operations for more compatibility other libraries. 
  - Some libraries may not fully support selector specifications
  - for example, `#product_description+ p` selector in `parsel` works fine, but not works in `selectolax`, `dart` libs
- there is a xpath to css converter for simple queries **without guarantees of functionality**. 
For example, in css there is no analogue of `contains` from xpath, etc.
