# Sscgen DSL syntax explain

## Fileds explain

To begin with, I'll give you a simple scheme for extracting data from a page.

```python
from ssc_codegen import ItemSchema, ListSchema, D, R, N


class MetaTable(ListSchema):
    # TIP: provide all attr keys to selector for increase extract stability
    __SPLIT_DOC__ = D().css_all("meta[property][content]")

    key = D().attr("property")
    value = D().attr("content")


class Page(ItemSchema):
    # alias D().css("title").text()
    title = D().css("title::text")
    # alias:
    # D().default([]).css_all("a[href]").attr("href")
    hrefs = D([]).css_all("a[href]::attr(href)")
    # alias:
    # D().default(False).raw().re(r"(<meta)").to_bool()
    has_meta_tag = R(False).re(r"(<meta[^>]+>)").to_bool()
    meta_count = D(0).css_all("meta").to_len()
    meta_table = N().sub_parser(MetaTable)
```

It will be equivalent to javascript code:

```javascript
class MetaTable {
  constructor(doc) {
    this._doc = doc;
  }
  _splitDoc(v) {
    return Array.from(v.querySelectorAll("meta[property][content]"));
  }
  _parseKey(v) {
    return v.getAttribute("property");
  }
  _parseValue(v) {
    return v.getAttribute("content");
  }
  parse() {
    return Array.from(this._splitDoc(this._doc)).map((e) => ({
      key: this._parseKey(e),
      value: this._parseValue(e),
    }));
  }
}

class Page {
  constructor(doc) {
    this._doc = doc;
  }

  _parseTitle(v) {
    let v0 = v.querySelector("title");
    return typeof v0.textContent === "undefined"
      ? v0.documentElement.textContent
      : v0.textContent;
  }
  _parseHrefs(v) {
    let v0 = v;
    try {
      let v1 = Array.from(v0.querySelectorAll("a[href]"));
      return v1.map((e) => e.getAttribute("href"));
    } catch (Error) {
      return [];
    }
  }
  _parseHasMetaTag(v) {
    let v0 = v;
    try {
      let v1 =
        typeof v0.outerHTML === "undefined"
          ? v0.documentElement.outerHTML
          : v0.outerHTML;
      let v2 = v1.match(/(<meta)/)[1];

      return v2 || v2 === 0 ? true : false;
    } catch (Error) {
      return false;
    }
  }
  _parseMetaCount(v) {
    let v0 = v;
    try {
      let v1 = Array.from(v0.querySelectorAll("meta"));

      return v1.length;
    } catch (Error) {
      return 0;
    }
  }
  _parseMetaTable(v) {
    return new MetaTable(v).parse();
  }
  parse() {
    return {
      title: this._parseTitle(this._doc),
      hrefs: this._parseHrefs(this._doc),
      has_meta_tag: this._parseHasMetaTag(this._doc),
      meta_count: this._parseMetaCount(this._doc),
      meta_table: this._parseMetaTable(this._doc),
    };
  }
}
```

Eexplanation of the syntax:

D() - indicates that the first input element is a Document or Element.

You can set the default value at the beginning if, for example, there may be no value in the field or if the code block may cause an error.

```
D().default([]).css_all("a[href]").attr("href")
# short version
D([]).css_all("a[href]::attr(href)")
```

available pseudoselecors aliases:

| CSS           | XPATH        | fn_call      | desc                    |
| ------------- | ------------ | ------------ | ----------------------- |
| `::text`      | `/text()`    | `.text()`    | extract text (deep)     |
| `::raw`       | `/raw()`     | `.raw()`     | extract outherHtml      |
| `::attr(key)` | `@attr(key)` | `.attr(key)` | extract attribute value |

R() - shortcut of D().raw() - call extract outherHtml
Maybe used for extract anything data by regular expressions and basic string operations

N() - means that the document or selected element will be passed to another parser and it will return the specified structure.:

## Schemas

### ItemSchema

The common way to serialize data

```python
from ssc_codegen import ItemSchema, D

class Page(ItemSchema):
    title = D().css("title:text")
    hrefs = D().css_all("a[href]::attr(href)")
```

returns the structure of the form:

```
{title: ..., hrefs: [...]}
```

### ListSchema

The second common structure, implementations for parsing data in the form of cards and other iterable HTML elements.

Recommended to be used with `ItemSchema` to indicate the entry point:


```python
from ssc_codegen import ItemSchema, ListSchema, D, N


class MetaContent(ListSchema):
    __SPLIT_DOC__ = D().css_all("meta[property][content]")

    proprerty = D().attr("property")
    content = D().attr("content")

class Page(ItemSchema):
    title = D().css("title::text")
    meta = N().sub_parser(MetaContent)
```

returns the structure of the form:

```
{title: ..., meta: [{proprerty: ..., content: ...}, ...]}
```

### DictSchema

Situational structure, creates data with an arbitrary dictionary and value.
The key must always be of type str.

```python
from ssc_codegen import ItemSchema, DictSchema, D, N

class MetaContent(DictSchema):
    __SPLIT_DOC__ = D().css_all("meta[property][content]")

    __KEY__ = D().attr("property")
    __VALUE__ = D().attr("content")

class Page(ItemSchema):
    title = D().css("title::text")
    meta = N().sub_parser(MetaContent)
```

returns the structure of the form:

```
{title: ..., meta: {__KEY__1: __VALUE__1, __KEY__2: __VALUE__2, ...}}
```

### FlatListSchema

Situational structure, creates a flat data list:

```python
from ssc_codegen import ItemSchema, FlatListSchema, D, N

class MetaContent(FlatListSchema):
    __SPLIT_DOC__ = D().css_all("meta[content]")
    __ITEM__ = D().attr("content")


class Page(ItemSchema):
    title = D().css("title::text")
    # alias:
    # D().css_all("meta[content]::attr(content)")
    meta_content = N().sub_parser(MetaContent)
```

returns the structure of the form:

```
{title: ..., meta_content: [...]}
```

### AccUniqueListSchema

A situational structure that parses all the data from a sheet, collects it into one sheet, and then returns unique values.

> The order of the elements is not guaranteed!

```python
from ssc_codegen import ItemSchema, FlatListSchema, D, N

class Socials(AccUniqueListSchema):
    # WARNING:
    # shorten link selectors can be add a side effect
    # and capture urls like `example*x*.com/` or `foobar*x*.com/`.
    # this example not be coverage this corner cases
    twitter = D([]).css_all("[src*='twitter.com'],[href*='twitter.com'],[src*='x.com'],[href*='x.com']::attr(href,src)")
    tiktok = D([]).css_all("[src*='tiktok.com'],[href*='tiktok.com']::attr(href,src)")
    youtube = D([]).css_all("[src*='youtube.com'],[href*='youtube.com']::attr(href,src)")
    # add other socials extractors

class Page(ItemSchema):
    title = D().css("title::text")
    socials = N().sub_parser(Socials)
```

returns the structure of the form:

```
{title: ..., socials: [...]}
```
