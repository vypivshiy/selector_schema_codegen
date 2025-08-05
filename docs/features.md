# Features

- DSL-style implement html parsers, simply support, prototype
- convert schemas to another languages to a standalone modules for maximum reuse!
- documentation translates too, auto doc parsers signature
- generates types, if target languages supports

## Converters

Current support converters

| Language      | HTML parser backend          | XPath | CSS3 | CSS4 | Generated types, structs          | formatter dependency |
|---------------|------------------------------|-------|------|------|-----------------------------------|----------------------|
| Python (3.8+) | bs4                          | N     | Y    | Y    | TypedDict*, list, dict            | ruff                 |
| -             | parsel                       | Y     | Y    | N    | -                                 | -                    |
| -             | selectolax (lexbor)          | N     | Y    | N    | -                                 | -                    |
| js (ES6)      | pure (firefox/chrome/nodejs) | Y     | Y    | Y    | Array, Map**                      | prettier             |
| go (1.10+)    | goquery (WIP)                | N     | Y    | N    | struct(+json anchors), array, map | gofmt                |

- **CSS3** means support next selectors:
  - basic: (`tag`, `.class`, `#id`, `tag1,tag2`)
  - combined: (`div p`, `ul > li`, `h2 +p`, `title ~head`)
  - attribute: (`a[href]`, `input[type='text']`, `a[href*='...']`, ...)
  - basic pseudo classes: (`:nth-child(n)`, `:first-child`, `:last-child`)
- **CSS4** means support next selectors:
  - `:has()`, `:nth-of-type()`, `:where()`, `:is()`, `not()` etc
- *this annotation type was deliberately chosen as a compromise reasons. 
Python has many ways of serialization: `namedtuple, dataclass, attrs, pydantic, msgspec, etc`
  - TypedDict is like a build-in dict, but with IDE and linter hint support, and you can easily implement an adapter for the required structure.
- **js exclude build-in serialization methods, used standard Array and Map structures 
- **formatter** - optional dependency for prettify and fix codestyle
