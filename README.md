# Selector Schema Codegen

> ssc_codegen - converter configs to HTML parsers in various programming languages.

>[!note]
> 
> its experimental project, please expect breaking changes

## Why?

If you have ever reverse engineered http, written unofficial API interfaces based on html parsers, 
then you have encountered the following problems:

- A lot of boilerplate code: css/xpath selectors, regular expressions, basic strings operations
- difficult to maintain: usually, such projects with unofficial API are written without designing the architectureЖ
  - Often, documentation is missing
  - Often, there is no serialization of data into convenient data structures
- it is difficult to port ready-made parsers to other projects or to other programming languages

## Features

- Declarative style: describe in a chain HOW you want to extract values, not HOW to program it
- Minimum code in configuration: easy to read and modify
- Portability: code output does not cohesion to the project, it easily reuses to another projects
- Minimal chain syntax and strategies: CSS, XPath, regex, minimal string formatting operations*
  - **if your know about selectors, regular expressions***
- The documentation of the schemes is transferred to the generated code: in the IDE you will see how to use it!
  - Field signature documentation for schemas is also generated!
- if the target language supports it: types, annotations, structures are created for more convenient use
- translate CSS to XPATH
- generating code to various programming languages 

## Overview

### How to read Schema code

Before reading, make sure you are know about:

- CSS (optional XPath) selectors
- Regular expressions
- basic string operations

### Quickstart usage

See [examples](examples)

### Supported convert programming languages and libraries backends 

| Language      | Library                                                      | XPath Support | CSS Support | generated types                          | Formatter   |
|---------------|--------------------------------------------------------------|---------------|-------------|------------------------------------------|-------------|
| Python (3.8+) | bs4                                                          | NO            | YES         | TypedDict*, list, dict                   | ruff        |
| -             | parsel                                                       | YES           | YES         | -                                        | -           |
| -             | selectolax (modest)                                          | NO            | YES         | -                                        | -           |
| -             | scrapy (possibly use parsel - pass Response.selector object) | YES           | YES         | -                                        | -           |
| Dart (3)      | universal_html                                               | NO            | YES         | record, List, Map                        | dart format |
| js (ES6)      | pure (browsers firefox/chrome)                               | YES           | YES         | Array, Map**                             | -           |
| go (1.10+)    | goquery                                                      | NO            | YES         | struct(json anchors include), array, map | gofmt       |

- *this annotation type was deliberately chosen as a compromise reasons. Python has many ways of serialization: `dataclass, namedtuple, attrs, pydantic`
  - TypedDict is like a build-in dict, but with IDE and linter hint support, and you can easily implement an adapter for the required structure.
- **js not exists build-in serialization methods

## Install

|               | shell cmd                  |
|---------------|----------------------------|
| uv            | `uv add ssc_codegen`       |
| uv (cli tool) | `uv tool add ssc_codegen`  |
| pipx          | `pipx install ssc_codegen` |
| pip           | `pip install ssc_codegen`  |



## Recommendations

- Use any Chromium-base browser and the [SelectorGadget](https://chromewebstore.google.com/detail/selectorgadget/mhjhnkcfbdhnjickkkdbjoemdmbfginb) extension to get CSS selectors efficiently.
- Use CSS selectors: they can be **guaranteed** convert to XPath.
- Use CSS2 standard and simple queries: some libraries do not support the full CSS2 specification.
  - E.G: the selector `#product_description+ p` works in `python.parsel` and `javascript`, 
  - but not in the `dart.universal_html` and `selectolax` libraries.
  - the standard `dart.html` library does not support `:nth-child()` 😭
- Project include XPath to CSS converter, but its functionality **is not guaranteed**. 
  - E.G: CSS2 has no equivalent `contains` query from XPath

## Docs

### Shortcuts

Variable notations in the code:

- D() — mark a `Document`|`Element` object
- N() — mark operations with nested structures. useful, for attach structure to different field
- R() — shortcut for `D().raw()`. Useful if you only need operations with regular expressions and strings, not with selectors

### Built-in Schemas

#### ItemSchema
Parses the structure according to the rules `{<field1> = <value>, <field2> = <value>, ...}`, returns a hash table.

```python
from ssc_codegen import ItemSchema, D

class Head(ItemSchema):
    title = D().css("title").text()
    all_metas = D().css_all("meta").raw()
    styles = D().default("").css("styles").text()
    
# pseudocode generate structure:
# Head:
#   title: str
#   all_metas: list[str]
#   styles: str
```

#### DictSchema

Parses the structure according to the rule `{<key_parsed1> = <value_parsed1>, <key_parsed2> = <value_parsed2>, ...}`, returns a hash table.

```python
from ssc_codegen import DictSchema, D

class LinksDict(DictSchema):
    __SPLIT_DOC__ = D().css_all("a")
    
    __KEY__ = D().text()
    __VALUE__ = D().attr("href")
    
# pseudocode generate structure:
# LinksDict:
# {
#   "key1": "value1", 
#   "key2": "value2", ...
# }
```

#### ListSchema

Parses the structure according to the rule `[{<key1> = <value1>, <key2> = <value2>, ...}, {<key1> = <value1>, <key2> = <value2>, ...}]`, returns a list of hash tables.

#### FlatListSchema

Parses the structure according to the rule `[<item1>, <item2>, ...]`, returns a list of objects.

```python
from ssc_codegen import FlatListSchema, D

class LiTextList(FlatListSchema):
    __SPLIT_DOC__ = D().css_all("li")
    
    __ITEM__ = D().text()
    
# pseudocode generate structure:
# LiTextList:
# ["item1", "item2", ...]
```

### Types

| TYPE          | DESCRIPTION                                                              |
|---------------|--------------------------------------------------------------------------|
| DOCUMENT      | 1 element/object of the document. Always the first argument in the field |
| LIST_DOCUMENT | Collection of elements                                                   |
| STRING        | Tag string/attribute/tag text                                            |
| LIST_STRING   | Collection of strings/attributes/text                                    |
| INT           | integer                                                                  |
| LIST_INT      | Collection of integers                                                   |
| FLOAT         | float/double                                                             |
| LIST_FLOAT    | Collection of floats/doubles                                             |
| NESTED        | nested schema in field                                                   |


### Magic Methods

- `__SPLIT_DOC__` - splits the document into elements for easier parsing
- `__PRE_VALIDATE__` - pre-validation of the document using `assert`. Throws an error if validation fails
- `__KEY__`, `__VALUE__` - magic methods for initializing `DictSchema` structure
- `__ITEM__` - magic method for initializing `FlattenListSchema` structure

### Operators

| Method       | Accepts            | Returns            | Example                                                  |   | Description                                                                                               |
|--------------|--------------------|--------------------|----------------------------------------------------------|:--|-----------------------------------------------------------------------------------------------------------|
| default      | None/str/int/float | DOCUMENT           | `D().default(None)`                                      |   | Default value if an error occurs. Must be the first                                                       |
| sub_parser   | Schema             | -                  | `N().sub_parser(Books)`                                  |   | Passes the document/element to another parser object. Returns the obtained result                         |
| css          | CSS query          | DOCUMENT           | `D().css('a')`                                           |   | Returns the first found element of the selector result                                                    |
| xpath        | XPATH query        | DOCUMENT           | `D().xpath('//a')`                                       |   | Returns the first found element of the selector result                                                    |
| css_all      | CSS query          | LIST_DOCUMENT      | `D().css_all('a')`                                       |   | Returns all elements of the selector result                                                               |
| xpath_all    | XPATH query        | LIST_DOCUMENT      | `D().xpath_all('//a')`                                   |   | Returns all elements of the selector result                                                               |
| raw          |                    | STRING/LIST_STRING | `D().raw()`                                              |   | Returns the raw HTML of the document/element. Works with DOCUMENT, LIST_DOCUMENT                          |
| text         |                    | STRING/LIST_STRING | `D().css('title').text()`                                |   | Returns the text from the HTML document/element. Works with DOCUMENT, LIST_DOCUMENT                       |
| attr         | ATTR-NAME          | STRING/LIST_STRING | `D().css('a').attr('href')`                              |   | Returns the attribute from the HTML tag. Works with DOCUMENT, LIST_DOCUMENT                               |
| trim         | str                | STRING/LIST_STRING | `R().trim('<body>')`                                     |   | Trims the string from the LEFT and RIGHT. Works with STRING, LIST_STRING                                  |
| ltrim        | str                | STRING/LIST_STRING | `D().css('a').attr('href').ltrim('//')`                  |   | Trims the string from the LEFT. Works with STRING, LIST_STRING                                            |
| rtrim        | str                | STRING/LIST_STRING | `D().css('title').rtrim(' ')`                            |   | Trims the string from the RIGHT. Works with STRING, LIST_STRING                                           |
| repl         | old, new           | STRING/LIST_STRING | `D().css('a').attr('href').repl('//', 'https://')`       |   | Replaces the string. Works with STRING, LIST_STRING                                                       |
| fmt          | template           | STRING/LIST_STRING | `D().css('title').fmt("title: {{}}")`                    |   | Formats the string according to the template. Must have the `{{}}` marker. Works with STRING, LIST_STRING |
| re           | pattern            | STRING/LIST_STRING | `D().css('title').re('(\w+)')`                           |   | Finds the first matching result of the regex pattern. Works with STRING, LIST_STRING                      |
| re_all       | pattern            | LIST_STRING        | `D().css('title').re('(\w+)')`                           |   | Finds all matching results of the regex pattern. Works with STRING                                        |
| re_sub       | pattern, repl      | STRING/LIST_STRING | `D().css('title').re_sub('(\w+)', 'wow')`                |   | Replaces the string according to the regex pattern. Works with STRING, LIST_STRING                        |
| index        | int                | STRING/DOCUMENT    | `D().css_all('a').index(0)`                              |   | Takes the element by index. Works with LIST_DOCUMENT, LIST_STRING                                         |
| first        |                    | -                  | `D().css_all('a').first`                                 |   | Alias for index(0)                                                                                        |
| last         |                    | -                  | `D().css_all('a').last`                                  |   | Alias for index(-1). Or implementation of a negative index                                                |
| join         | sep                | STRING             | `D().css_all('a').text().join(', ')`                     |   | Collects the collection into a string. Works with LIST_STRING                                             |
| assert_in    | str                | NONE               | `D().css_all('a').attr('href').assert_in('example.com')` |   | Checks if the string is in the collection. The checked argument must be LIST_STRING                       |
| assert_re    | pattern            | NONE               | `D().css('a').attr('href').assert_re('example.com')`     |   | Checks if the regex pattern is found. The checked argument must be STRING                                 |
| assert_css   | CSS query          | NONE               | `D().assert_css('title')`                                |   | Checks the element by CSS. The checked argument must be DOCUMENT                                          |
| assert_xpath | XPATH query        | NONE               | `D().assert_xpath('//title')`                            |   | Checks the element by XPath. The checked argument must be DOCUMENT                                        |