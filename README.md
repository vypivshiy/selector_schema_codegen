# Selector Schema codegen

## Introduction

ssc-gen - a python-based DSL to describe parsers for html documents, which is translated into a standalone parsing module

### For a better experience using this library, you should know:

- HTML CSS selectors (CSS3 standard min), Xpath
- regular expressions (PCRE)

### Project solving next problems:

- designed for SSR (server-side-render) html pages parsers, **NOT FOR REST-API, GRAPHQL ENDPOINTS**
- decrease boilerplate code
- generates independent modules from the project that can be reused.
- generates docstring documentation and the signature of the parser output.
- for a better IDE experience, generates a typedefs, type annotations (if the target programming language supports it).
- support annotation and parsing of JSON-like strings from a document
- AST API codegen for developing a converter for parsing

## Support converters

Current support converters

| Language                                 | HTML parser lib + dependencies         | XPath | CSS3 | CSS4 | Generated annotations, types, structs | formatter dependency |
| ---------------------------------------- | -------------------------------------- | ----- | ---- | ---- | ------------------------------------- | -------------------- |
| Python (3.8+)                            | bs4, lxml                              | N     | Y    | Y    | TypedDict`1`, list, dict              | ruff                 |
| ...                                      | parsel                                 | Y     | Y    | N    | ...                                   | ...                  |
| ...                                      | selectolax (lexbor)                    | N     | Y    | N    | ...                                   | ...                  |
| ...                                      | lxml                                   | Y     | Y    | N    | ...                                   | ...                  |
| js (ES6)`2`                              | pure (firefox/chrome extension/nodejs) | Y     | Y    | Y    | Array, Map`3`                         | prettier             |
| go (1.10+) **(UNSTABLE)**                | goquery, gjson (`4`)                   | N     | Y    | N    | struct(+json anchors), array, map     | gofmt                |
| lua (5.2+), luajit(2+) **(UNSTABLE)**`5` | lua-htmlparser, lrexlib(opt), dkjson   | N     | Y    | N    | EmmyLua                               | LuaFormatter         |

- **CSS3** means support next selectors:
  - basic: (`tag`, `.class`, `#id`, `tag1,tag2`)
  - combined: (`div p`, `ul > li`, `h2 +p`, `title ~head`)
  - attribute: (`a[href]`, `input[type='text']`, `a[href*='...']`, ...)
  - CSS3 pseudo classes: (`:nth-child(n)`, `:first-child`, `:last-child`)
- **CSS4** means support next selectors:
  - `:nth-of-type()`, `:where()`, `:is()`, `:not()` etc
- `1`this annotation type was deliberately chosen as a compromise reasons:
  Python has many ways of serialization: `namedtuple, dataclass, attrs, pydantic, msgspec, etc`
  - TypedDict is like a build-in dict, but with IDE and linter hint support, and you can easily implement an adapter for the required structure.
- `2`ES8 standart required if needed use PCRE `re.S | re.DOTALL` flag
- `3`js exclude build-in serialization methods, used standard Array and Map types. Focus on the singanutur documentation!
- `4`golang has not been tested much, there may be issues
- **formatter dependency** - optional dependency for prettify and fix codestyle

- `5`lua
  - Experimental Research PoC, performance and stability are not guaranteed
  - Priority on generation to pure lua without C-libs dependencies. using [mva/htmlparser](https://luarocks.org/modules/mva/htmlparser) and [dhkolf/dkjson](https://luarocks.org/modules/dhkolf/dkjson)
  - Translates unsupported CSS3 selectors into the equivalent in the form of function calls:
    - for example, `div +p` is equivalent to `CssExt.combine_plus(root:select("div"), "p")`
  - Translates PCRE regex to [string pattern matching](https://www.lua.org/manual/5.4/manual.html#6.4.1) (with restrictions) for more information in [lua_re_compat.py ](ssc_codegen/converters/templates/lua_re_compat.py)

### Limitations

For maximum portability of the configuration to the target language:

- If possible, use CSS selectors: they are guaranteed to be converted to XPATH
- Unlike javascript, most html parse libs implement [CSS3 selectors standard](https://www.w3.org/TR/selectors-3/). They may not fully implement the functionality!
  Check the html parser lib documentation aboud CSS selectors before implement code. Examples:
  1. Several libs not support `+` operations (eg: [selectolax(modest)](https://github.com/rushter/selectolax), [dart.universal_html](https://pub.dev/packages/universal_html))
  2. For research purpose, lua_htmlparser include converter for unsupported CSS3 query syntax
2. HTML parser libs maybe not supports attribute selectors: `*=`, `~=`, `|=`, `^=`, `$=`
3. Several libs not support pseudo classes (eg: standard [dart.html](https://dart.dev/libraries/dart-html) lib miss this feature).

## Getting started

ssc_gen required python 3.10 version or higher

### Install

pip:

```shell
pip install ssc_codegen
```

uv:

```shell
uv pip install ssc_codegen
```

## Example

### Create a file `schema.py` with:

```python
from ssc_codegen import ItemSchema, D

class HelloWorld(ItemSchema):
    title = D().css('title').text()
    a_hrefs = D().css_all('a').attr('href')
```

### try it in cli

> [!note]
> this tools developed for testing purposes, not for web-scraping tasks

### eval from file

Download any html file and pass as argument:

```shell
ssc-gen parse-from-file index.html -t schema.py:HelloWorld
```

Short options descriptions:

- `-t --target` - config schema file and class from where to start the parser

![out1](docs/assets/parse_from_file.gif)

### send GET request to url and parse response

```shell
ssc-gen parse-from-url https://example.com -t schema.py:HelloWorld
```

![out1](docs/assets/parse_from_url.gif)

### send request via Chromium browser (CDP protocol)

```shell
ssc-gen parse-from-chrome https://example.com -t schema.py:HelloWorld
```

> [!note]
> if script cannot found chrome executable - provide it manually:

```shell
ssc-gen parse-from-chrome https://example.com -t schema.py:HelloWorld -sc /usr/bin/chromium
```

### Convert to code

Convert to code for use in projects:

> [!note]
> for example, used js: it can be fast test in developer console

```shell
ssc-gen js schema.py -o .
```

Code output looks like this:

```javascript
// autogenerated by ssc-gen DO NOT_EDIT
/***
 *
 * {
 *     "title": "String",
 *     "a_hrefs": "Array<String>"
 * }*/
class HelloWorld {
  constructor(doc) {
    if (typeof doc === "string") {
      this._doc = new DOMParser().parseFromString(doc, "text/html");
    } else if (doc instanceof Document || doc instanceof Element) {
      this._doc = doc;
    } else {
      throw new Error("Invalid input: Expected a Document, Element, or string");
    }
  }

  _parseTitle(v) {
    let v0 = v.querySelector("title");
    return typeof v0.textContent === "undefined"
      ? v0.documentElement.textContent
      : v0.textContent;
  }

  _parseAHrefs(v) {
    let v0 = Array.from(v.querySelectorAll("a"));
    return v0.map((e) => e.getAttribute("href"));
  }

  parse() {
    return {
      title: this._parseTitle(this._doc),
      a_hrefs: this._parseAHrefs(this._doc),
    };
  }
}
```

### Copy code output and past to developer console:

Print output:

```javascript
alert(JSON.stringify(new HelloWorld(document).parse()));
```

![example](docs/assets/example.png)

You can use any html source:

- parse from html files
- parse from http responses
- parse from browsers: playwright, selenium, chrome-cdp, etc.
- call curl in shell and parse STDIN
- use in STDIN pipelines with third-party tools like [projectdiscovery/httpx](https://github.com/projectdiscovery/httpx)

## See also

- [Brief](docs/brief.md) about css selectors and regular expressions.
- [Tutorial](docs/tutorial.md) basic usage ssc-gen
- [Reference](docs/reference.md) about lib API
- [AST reference](docs/ast_reference.md) about generation code from AST
