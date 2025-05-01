# Selector Schema codegen

## Introduction

ssc-gen - based-python DSL language for writing html parsers in dataclass style for translating to targeting language.

Project solving next problems:

- decrease boilerplate code
- generation DDD-like modules independent of the project
- generate types or type annotations if possible and documentation 
- simplify code support
- portability to other languages and HTML parser backends
- designed for SSR (server-side-render) pages parsers. 
For REST-API, GRAPHQL endpoints use tools like [mitmproxy2swagger](https://github.com/alufers/mitmproxy2swagger)


## Support converters

Current support converters

| Language      | HTML parser backend          | XPath | CSS3 | CSS4 | Generated types, structs          | formatter dependency |
|---------------|------------------------------|-------|------|------|-----------------------------------|----------------------|
| Python (3.8+) | bs4                          | N     | Y    | Y    | TypedDict*, list, dict            | ruff                 |
| ...           | parsel                       | Y     | Y    | N    | ...                               | ...                  |
| ...           | selectolax (lexbor)          | N     | Y    | N    | ...                               | ...                  |
| js (ES6)      | pure (firefox/chrome/nodejs) | Y     | Y    | Y    | Array, Map**                      | prettier             |
| go (1.10+)    | goquery (WIP)                | N     | Y    | N    | struct(+json anchors), array, map | gofmt                |

- **CSS3** means support next selectors:
  - basic: (`tag`, `.class`, `#id`, `tag1,tag2`)
  - combined: (`div p`, `ul > li`, `h2 +p`, `title ~head`)
  - attribute: (`a[href]`, `input[type='text']`, `a[href*='...']`, ...)
  - basic pseudo classes: (`:nth-child(n)`, `:first-child`, `:last-child`)
- **CSS4** means support next selectors:
  - `:has()`, `:nth-of-type()`, `:where()`, `:is()` etc
- *this annotation type was deliberately chosen as a compromise reasons. 
Python has many ways of serialization: `namedtuple, dataclass, attrs, pydantic, msgspec, etc`
  - TypedDict is like a build-in dict, but with IDE and linter hint support, and you can easily implement an adapter for the required structure.
- **js exclude build-in serialization methods, used standard Array and Map structures 
- **formatter** - optional dependency for prettify and fix codestyle

### Limitations

For maximum portability of the configuration to the target language:

- Use CSS selectors: they are guaranteed to be converted to XPATH
- Unlike javascript, most html parse libs implement [CSS3 selectors standard](https://www.w3.org/TR/selectors-3/). 
Check the html parser lib documentation before implement CSS selectors

1. Several libs not support `+` operations (eg: [selectolax(modest)](https://github.com/rushter/selectolax), [dart.universal_html](https://pub.dev/packages/universal_html))
2. HTML parser libs maybe not supports attribute operations like `*=`, `~=`, `|=`, `^=` and `$=`
3. Several libs not support pseudo classes (eg: standard [dart.html](https://dart.dev/libraries/dart-html) lib miss this feature). 
This project will not implement converters with such a cons

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

as cli converter tool:

| package manager | command                       |
|-----------------|-------------------------------|
| pipx            | `pipx install ssc_codegen`    |
| uv              | `uv tool install ssc_codegen` |

## Example

### Create a file `schema.py` with:

```python
from ssc_codegen import ItemSchema, D

class HelloWorld(ItemSchema):
    title = D().css('title').text()
    a_hrefs = D().css_all('a').attr('href')
```

### try it in cli

>[!note]
> this tools developed for testing purposes, not for web-scraping tasks

### from file

>[!warning]
> DO NOT PASS CONFIGS FROM UNKNOWN SOURCES: 
> 
> PYTHON CODE FROM CONFIGS COMPILE IN RUNTIME WOUT SECURITY CHECKS!!!

Download any html file and pass as argument:

```shell
ssc-gen parse-from-file index.html -t schema.py:HelloWorld  
```

Short options descriptions:

- `-t --target` - config schema file and class from where to start the parser

![out1](docs/assets/parse_from_file.gif)

### from url

```shell
ssc-gen parse-from-url https://example.com -t schema.py:HelloWorld  
```

![out1](docs/assets/parse_from_url.gif)
### from Chromium browser (CDP protocol)


```shell
ssc-gen parse-from-chrome https://example.com -t schema.py:HelloWorld
```

>[!note]
> if script cannot found chrome executable - provide it manually:

```shell
ssc-gen parse-from-chrome https://example.com -t schema.py:HelloWorld -sc /usr/bin/chromium
```


### Convert to code

Convert to code for use in projects:

>[!note]
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
        if (typeof doc === 'string') {
            this._doc = new DOMParser().parseFromString(doc, 'text/html');
        } else if (doc instanceof Document || doc instanceof Element) {
            this._doc = doc;
        } else {
            throw new Error("Invalid input: Expected a Document, Element, or string");
        }
    }

    _parseTitle(v) {
        let v0 = v.querySelector('title');
        return typeof v0.textContent === "undefined" ? v0.documentElement.textContent : v0.textContent;
    }

    _parseAHrefs(v) {
        let v0 = Array.from(v.querySelectorAll('a'));
        return v0.map(e => e.getAttribute('href'));
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
alert(JSON.stringify((new HelloWorld(document).parse())))
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