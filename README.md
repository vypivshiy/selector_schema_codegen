# Selector Schema Codegen

[RU](README_RU.md) [EN](README.md)

ssc_codegen is a generator for HTML parsers in various programming languages.

# Why?

- For convenient development of web scrapers, unofficial API interfaces, CI/CD integration
- Support for API interfaces in various programming languages **(currently available: Dart, Python)**
- Easy configuration files reading
- auto documentation how to use it and generate parse structure signature
- Portability: generated parsers are not tied to a specific project and can be reused
- Simple syntax similar to jQuery, ORM frameworks, and data serialization libraries

# Features

- Declarative style: describe WHAT you want to do, not HOW to program it
- Standardization: the generated code has minimal dependencies
- Ability to rebuild in other programming languages
- CSS, XPath, regex, minimal string formatting operations
- Field validation, CSS/XPath/regex expressions
- Documentation transfer into the generated code
- Conversion of CSS to XPath queries

## Install

### pipx

```shell
pipx install ssc_codegen
```

### pip

```shell
pip install ssc_codegen
```

## Usage

See [examples](examples)

## Supported Libraries and Programming Languages

| Language | Library                                                      | XPath Support | CSS Support | Formatter   |
|----------|--------------------------------------------------------------|---------------|-------------|-------------|
| Python   | bs4                                                          | NO            | YES         | black       |
| -        | parsel                                                       | YES           | YES         | -           |
| -        | selectolax (modest)                                          | NO            | YES         | -           |
| -        | scrapy (based on parsel, but class init argument - Response) | YES           | YES         | -           |
| Dart     | universal_html                                               | NO            | YES         | dart format |

### Recommendations

- For quickly obtaining effective CSS selectors, it is recommended to use **any** Chromium-based browser 
and the [SelectorGadget](https://chromewebstore.google.com/detail/selectorgadget/mhjhnkcfbdhnjickkkdbjoemdmbfginb) 
extension.
- Use CSS selectors: they can be **guaranteed** convert to XPath.
- For maximum support across most programming languages, use simple queries for the following reasons:
    - Some libraries do not support the full CSS specification. 
For example, the selector `#product_description+ p` works in `python.parsel` and `javascript`, but not in the `dart.universal_html` and `selectolax` libraries.
- There is an XPath to CSS converter, but its functionality is not guaranteed. For example, CSS has no equivalent to `contains` from XPath.

### How to Read Schema Code

Before reading, make sure you are familiar with:

- CSS selectors
- XPath selectors
- Regular expressions

### Shortcuts

Variable notations in the code:

- D() — mark a `Document`/`Element` object
- N() — mark operations with nested structures
- R() — shortcut for `D().raw()`. Useful if you only need operations with regular expressions and strings, not with selectors

### Built-in Schemas

#### ItemSchema
Parses the structure according to the rules `{<key1> = <value1>, <key2> = <value2>, ...}`, returns a hash table.

#### DictSchema

Parses the structure according to the rule `{<key1> = <value1>, <key2> = <value2>, ...}`, returns a hash table.

#### ListSchema

Parses the structure according to the rule `[{<key1> = <value1>, <key2> = <value2>, ...}, {<key1> = <value1>, <key2> = <value2>, ...}]`, returns a list of hash tables.

#### FlattenListSchema

Parses the structure according to the rule `[<item1>, <item2>, ...]`, returns a list of objects.


### Types

Currently, there are 5 types

| TYPE          | DESCRIPTION                                               |
|---------------|-----------------------------------------------------------|
| DOCUMENT      | 1 element/object of the document. Always the first argument in the field |
| LIST_DOCUMENT | Collection of elements                                     |
| STRING        | Tag string/attribute/tag text                             |
| LIST_STRING   | Collection of strings/attributes/text                     |
| NESTED        | Collection of strings/attributes/text                     |


### Magic Methods

- `__SPLIT_DOC__` - splits the document into elements for easier parsing
- `__PRE_VALIDATE__` - pre-validation of the document using `assert`. Throws an error if validation fails
- `__KEY__`, `__VALUE__` - magic methods for initializing `DictSchema` structure
- `__ITEM__` - magic method for initializing `FlattenListSchema` structure

### Operators

| Method             | Accepts        | Returns           | Example                                                   |   | Description                                                                                   |
|-------------------|---------------|--------------------|----------------------------------------------------------|:--|--------------------------------------------------------------------------------------------|
| default(None/str) | None/str      | DOCUMENT           | `D().default(None)`                                      |   | Default value if an error occurs. Must be the first                                           |
| sub_parser        | Schema        | -                  | `N().sub_parser(Books)`                                  |   | Passes the document/element to another parser object. Returns the obtained result            |
| css               | CSS query     | DOCUMENT           | `D().css('a')`                                           |   | Returns the first found element of the selector result                                        |
| xpath             | XPATH query   | DOCUMENT           | `D().xpath('//a')`                                       |   | Returns the first found element of the selector result                                        |
| css_all           | CSS query     | LIST_DOCUMENT      | `D().css_all('a')`                                       |   | Returns all elements of the selector result                                                   |
| xpath_all         | XPATH query   | LIST_DOCUMENT      | `D().xpath_all('//a')`                                   |   | Returns all elements of the selector result                                                   |
| raw               |               | STRING/LIST_STRING | `D().raw()`                                              |   | Returns the raw HTML of the document/element. Works with DOCUMENT, LIST_DOCUMENT              |
| text              |               | STRING/LIST_STRING | `D().css('title').text()`                                |   | Returns the text from the HTML document/element. Works with DOCUMENT, LIST_DOCUMENT           |
| attr              | ATTR-NAME     | STRING/LIST_STRING | `D().css('a').attr('href')`                              |   | Returns the attribute from the HTML tag. Works with DOCUMENT, LIST_DOCUMENT                   |
| trim              | str           | STRING/LIST_STRING | `R().trim('<body>')`                                     |   | Trims the string from the LEFT and RIGHT. Works with STRING, LIST_STRING                      |
| ltrim             | str           | STRING/LIST_STRING | `D().css('a').attr('href').ltrim('//')`                  |   | Trims the string from the LEFT. Works with STRING, LIST_STRING                                |
| rtrim             | str           | STRING/LIST_STRING | `D().css('title').rtrim(' ')`                            |   | Trims the string from the RIGHT. Works with STRING, LIST_STRING                               |
| replace/repl      | old, new      | STRING/LIST_STRING | `D().css('a').attr('href').repl('//', 'https://')`       |   | Replaces the string. Works with STRING, LIST_STRING                                           |
| format/fmt        | template      | STRING/LIST_STRING | `D().css('title').fmt("title: {{}}")`                    |   | Formats the string according to the template. Must have the `{{}}` marker. Works with STRING, LIST_STRING |
| re                | pattern       | STRING/LIST_STRING | `D().css('title').re('(\w+)')`                           |   | Finds the first matching result of the regex pattern. Works with STRING, LIST_STRING         |
| re_all            | pattern       | LIST_STRING        | `D().css('title').re('(\w+)')`                           |   | Finds all matching results of the regex pattern. Works with STRING                           |
| re_sub            | pattern, repl | STRING/LIST_STRING | `D().css('title').re_sub('(\w+)', 'wow')`                |   | Replaces the string according to the regex pattern. Works with STRING, LIST_STRING           |
| index             | int           | STRING/DOCUMENT    | `D().css_all('a').index(0)`                              |   | Takes the element by index. Works with LIST_DOCUMENT, LIST_STRING                             |
| first             |               | -                  | `D().css_all('a').first`                                 |   | Alias for index(0)                                                                            |
| last              |               | -                  | `D().css_all('a').last`                                  |   | Alias for index(-1). Or implementation of a negative index                                   |
| join              | sep           | STRING             | `D().css_all('a').text().join(', ')`                     |   | Collects the collection into a string. Works with LIST_STRING                                |
| assert_in         | str           | NONE               | `D().css_all('a').attr('href').assert_in('example.com')` |   | Checks if the string is in the collection. The checked argument must be LIST_STRING          |
| assert_re         | pattern       | NONE               | `D().css('a').attr('href').assert_re('example.com')`     |   | Checks if the regex pattern is found. The checked argument must be STRING                    |
| assert_css        | CSS query     | NONE               | `D().assert_css('title')`                                |   | Checks the element by CSS. The checked argument must be DOCUMENT                             |
| assert_xpath      | XPATH query   | NONE               | `D().assert_xpath('//title')`                            |   | Checks the element by XPath. The checked argument must be DOCUMENT                           |