# Selector schema codegen

ssc_codegen - html parser code generator for different programming languages using class attribute annotations.


# Features
- easy read, write, documentation
- standardization: generate classes with minimal dependencies and documented parsed signature
- decrease boilerplate code
- write once — convert to other mainstream http parser libs
- include css, xpath, get attributes, regex, minimal string formatting operations
- pre validate types, css/xpath queries
- pre validate css/xpath queries and logic before generate code

## Install

### pipx (recommended for CLI usage)

```shell
pipx install ssc_codegen
```

### pip

```shell
pip install ssc_codegen
```

## Usage

see [example](example)

## Supported libs and languages

| language | lib                                                          | xpath | css | formatter   |
|----------|--------------------------------------------------------------|-------|-----|-------------|
| python   | bs4                                                          | NO    | YES | black       |
| -        | parsel                                                       | YES   | YES | -           |
| -        | selectolax (modest)                                          | NO    | YES | -           |
| -        | scrapy (based on parsel, but class init argument - Response) | YES   | YES | -           |
| dart     | universal_html                                               | NO    | YES | dart format |



### Recommendations

- usage css selector: they can be **guaranteed** converted to xpath (if target language does not support CSS selectors)
- usage simple operations for more compatibility with other libraries. 
  - Some libraries may not fully support selector specifications
  - for example, `#product_description+ p` selector in `parsel` works fine, but not works in `selectolax`, `dart` libs
- there is a xpath to css converter for simple queries **without guarantees of functionality**. 
For example, in css there is no analogue of `contains` from xpath, etc.
