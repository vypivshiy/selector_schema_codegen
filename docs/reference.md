# Reference

## Variable types

In ssc_gen, types used for static analyze AST before generate code.

Field assigns inner class, inherited from:
- [ItemSchema](#itemschema)
- [ListSchema](#listschema) 
- [FlatListSchema](#flatlistschema) 
- [DictSchema](#dictschema)

#### Shortcuts (aliases)

- `D()` - Document, provide standard selector, regexp, string and simple converter operations 
- `R()` - DocumentRaw, shortcut get raw string html document or element 
- `N()` - DocumentNested, shortcut send document or element to another configured schema

### Document

First expression always have type `DOCUMENT`. It stands for some abstract html document or element 

Allowed methods:

- [css](#css)
- [xpath](#xpath)
- [css_all](#css_all)
- [xpath_all](#xpath_all)
- [attr](#attr)
- [text](#text)
- [raw](#raw)
- [sub_parser](#sub_parser)

### ListDocument


`LIST_DOCUMENT` returned from the following expressions

- [css_all](#css_all)
- [xpath_all](#xpath_all)

Allowed methods

- [attr](#attr)
- [text](#text)
- [raw](#raw)
- [index](#index)
- [first](#first)
- [last](#last)

### String

Allowed methods

- [trim](#trim)
- [ltrim](#ltrim)
- [rtrim](#rtrim)
- [fmt](#fmt)
- [re](#re)
- [re_all](#re_all)
- [re_sub](#re_sub)
- [re_trim](#re_trim)
- [to_int](#to_int)
- [to_float](#to_float)
- [jsonify](#jsonify)

### ListString

Allowed methods

- [trim](#trim)
- [ltrim](#ltrim)
- [rtrim](#rtrim)
- [fmt](#fmt)
- [re_sub](#re_sub)
- [re_trim](#re_trim)
- [to_int](#to_int)
- [to_float](#to_float)

### Nested

Special type for passing a document or element to another schema

See [sub_parser](#sub_parser) example

### Json

Special type for passing a string to json parse struct

See [jsonify](#jsonify) example

### Int, ListInt, Float, ListFloat

Special types for marking converted types


### OptionalString, OptionalInt, OptionalFloat

Special types for marking value can be null

## Expressions

### default

Accept string, int, float or None. Should be a first expression else raise SyntaxError

```python
from ssc_codegen import D

# OK
D().default(None).css('title').text()
# short version
D(default=None).css('title').text()
D(None).css('title').text()

# SyntaxError, should be a first
D().css('title').text().default(None)
```

Last type should be same as default or None

```python
from ssc_codegen import D

# OK
D(1).css('.some_int').text().to_int()
D(3.14).css('.some_int').text().to_float()
D("Sample title").css('title').text()
# can be null
D(None).css('.some_int').text().to_int()
D(None).css('.some_int').text().to_float()

# Error, wrong default value type
D(1).css('.some_int').text()
D(3.14).css('.some_int').text()
D("Sample title").css('title').to_int()
```

### css

Css query. returns first founded element

- accept: `DOCUMENT`, return `DOCUMENT`

```python
from ssc_codegen import D

# OK
D().css('title')
D().css('head').css('title')

# Error
D().css('head').text().css('title')
# Error its XPATH selector
D().css('//head')
```

### css_all

Css query. returns all founded elements

- accept: `DOCUMENT`, return: `LIST_DOCUMENT`

```python
from ssc_codegen import D

# ok
D().css_all('a')

# Error (cannot select collections of elements)
D().css_all('.card').css('a')
```

### xpath

XPath query. returns first founded element

- accept: `DOCUMENT`, return `DOCUMENT`

```python
from ssc_codegen import D
# ok
D().xpath('//title')
# can be combined with css 
D().xpath('//head').css('title')

# Error
D().xpath('//head').text().xpath('//title')
# Error, its CSS selector
D().xpath('head > title')
```

### xpath_all

Xpath query. returns all founded elements

- accept: `DOCUMENT`, return: `LIST_DOCUMENT`

```python
from ssc_codegen import D

# OK
D().xpath_all('//a')

# Error (cannot select collections of elements)
D().xpath_all('//div').xpath('//a')
# Error (its CSS selector
D().xpath_all('div > a')
```

### text

Extract text from current document/element.

- accept `DOCUMENT`, return `STRING`
- accept `LIST_DOCUMENT`, return `LIST_STRING`

```python
from ssc_codegen import D

# OK
D().css('title').text()
# OK, extract all text from <p> tag
D().css_all('p').text()
```

### attr

Extract attribute value by name

- accept `DOCUMENT`, return `STRING`
- accept `LIST_DOCUMENT`, return `LIST_STRING`

>[!warning]
> maybe throw exception in runtime, if attribute name not exists in selected element

```python
from ssc_codegen import D

D().css('a').attr('href')

# extract all attr values from selected tags
D().css_all('a').attr('href')
```

### raw

Extract full html text in selected element(s) or document

- accept `DOCUMENT`, return `STRING`
- accept `LIST_DOCUMENT`, return `LIST_STRING`

```python
from ssc_codegen import D, R

# OK, convert html document to string
D().raw()
R()  # shortcut as D().raw()
D().css('title').raw()
# OK, collections of tags as raw html
D().css_all('a').raw()
```

### index

Extract item from sequence by index, 

Index starts from 0, end index marks as -1

- accept LIST_DOCUMENT, return DOCUMENT
- accept LIST_STRING, return STRING
- accept LIST_INT, return INT
- accept LIST_FLOAT, return FLOAT

```python
from ssc_codegen import D

# first
D().css_all('a').index(0)
# last
D().css_all('a').index(-1)
D().css_all('a').attr('href').index(0)
# convert elements to number types, extract by index
D().css_all('p').text().to_int().index(0)
D().css_all('p').text().to_float().index(0)
```

### first

Alias of [index(0)](#index)

```python
from ssc_codegen import D

D().css_all('a').first()
# same as
D().css_all('a').index(0)
```

### last

Alias of [index(-1)](#index)

```python
from ssc_codegen import D

D().css_all('a').last()
# same as
D().css_all('a').index(-1)
```

### join

Concatenate sequence of string to one by substr

- accept `LIST_STRING`, return `STRING`

```python
from ssc_codegen import D

D().css_all('p').text().join(' ')  # el1 el2, ...
D().css_all('p').text().join(', ') # el1, el2, ...
```

### trim

Trim LEFT and RIGHT string chars by substr

- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# remove LEFT and RIGHT '_' chars
D().css('title').text().trim('_') 
# remove LEFT and RIGHT '"' chars
D().css_all('a').attr('href').trim('"')
```

### ltrim

Trim LEFT string chars by substr

- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# remove LEFT '_' chars
D().css('title').text().ltrim('_') 
# remove LEFT 'href://' substr from all items
D().css_all('a').attr('href').ltrim('https://')
```

### rtrim

Trim RIGHT string chars by substr

- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# remove RIGHT '_' chars
D().css('title').text().rtrim('_') 
# remove RIGHT '"' chars from all items
D().css_all('a').attr('href').rtrim('"')
```

### split

Split string by sep substring

- accept `STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# spilt extracted text by ',', return array of strings
D().css('p').text().split(',')
```

### fmt

Format string by template.
Template placeholder should be included `{{}}` marker

- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# you can provide constant template and reuse
FMT_URL = "https://example.com{{}}"

# case for concatenate url with path 
D().css('a').attr('href').fmt(FMT_URL)
# format all items
D().css_all('a').attr('href').fmt(FMT_URL)

# ERROR, missing {{}} template marker
D().css('a').attr('href').fmt('example.com')
```

### repl

Replace all `old` substring with `new` in current string.

- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# replace single string
D().css('title').text().repl('a', 'O!')

# replace all items
D().css_all('a').attr('href').repl('https://', '')
```

### re

Extract first finding result by regexp.

- accept `STRING`, return `STRING`


>[!warning]
> Raise Error, if pattern groups is empty
> Maybe throw exception in runtime if regex does not match
> Extract only one group, you can manually set index (default extract \[1])

```python
from ssc_codegen import R

# OK
R().re(r'(\d+)')
# extract second groups
R().re(r'(\d+) (\w+)', 2) 
# recommended mark group as non-capturing '?:' 
R().re(r'(?:\d+) (\w+)')

# ERROR
# missing group capture
R().re(r'\w+')
# pattern syntax error
#       vvv
R().re(r'(\w+')
# empty regex pattern
R().re('')
```

### re_all

Extract all matched regex results.

- accept `STRING`, return `LIST_STRING`

>[!warning]
> Raise Error, if pattern groups is empty
> Maybe throw exception in runtime if regex does not match
> Extract only by singe group


```python
from ssc_codegen import R
# OK
R().re_all(r'(\d+)')
# non-capturing groups, OK
R().re_all(r'(?:\d+) (\w+)')

# ERROR
# missing group capture
R().re(r'\w+')
# pattern syntax error
#       vvv
R().re(r'(\w+')
# empty regex pattern
R().re('')
# too many pattern groups
R().re(r'(\d+) (\w+)')
```

### re_sub

Replace all substrings by `pattern` to `repl`.

- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import R

# OK
R().re_sub("<title>(.*)</title>", "Cool Title")
R().re_sub("<title>.*</title>", "Where is title?")
# regexp sub all items
R().re_all(r'(\d+)').re_sub(r'\d+', "NUMBER")

# ERROR
# pattern syntax error
#       vvv
R().re_sub(r'(\w+')
# empty regex pattern
R().re_sub('')
```

### re_trim

Shortcut of [re_sub('^' + pattern).re_sub(pattern + '$')](#re_sub)
        
As default, trim LEFT and RIGHT whitespace chars by regular expression.
        
- accept `STRING`, return `STRING`
- accept `LIST_STRING`, return `LIST_STRING`

```python
from ssc_codegen import D

# remove all whitespaces in title LEFT and RIGHT
D().css('title').text().re_trim()

# remove all `_` chars in title LEFT and RIGHT
D().css('title').text().re_trim('_')
```

### is_css

Assertion that css selector will find element else throw exception. 
Exception can be rescued by [default](#default)
Does not modify variable.

- accept `DOCUMENT`, return `DOCUMENT`

```python
from ssc_codegen import D

# check exists title element
D().is_css('title').css('title').text()

# rescue exception
D().default('titled tag. rly?').is_css('titled').css('titled').text()
```


### is_xpath

Assertion that xpath selector will find element else throw exception. 
Exception can be rescued by [default](#default)
Does not modify variable.

- accept `DOCUMENT`, return `DOCUMENT`

```python
from ssc_codegen import D

# check exists title element
D().is_xpath('//title').xpath('//title').text()

# rescue exception
D().default('titled tag. rly?').is_xpath('//titled').xpath('//titled').text()
```


### is_equal

Assertion that variable equal by string, int or float else throw exception. 
Exception can be rescued by [default](#default)
Does not modify variable.

- accept `STRING`, return `STRING`
- accept `INT`, return `INT`
- accept `FLOAT` return `FLOAT`

```python
from ssc_codegen import D, R

# OK
D().css('title').text().is_equal("Example Page")
R().re('(\d+)').to_int().is_equal(1)
R().re('(\d+)').to_float().is_equal(3.14)
# rescue exception
D().default('Not equal').css('title').text().is_equal('O!')
```


### is_not_equal

Assertion that variable not equal by string, int or float else throw exception. 
Exception can be rescued by [default](#default)
Does not modify variable.

- accept `STRING`, return `STRING`
- accept `INT`, return `INT`
- accept `FLOAT`, return `FLOAT`

```python
from ssc_codegen import D, R

# OK
D().css('title').text().is_not_equal("O!")
R().re('(\d+)').to_int().is_not_equal(1)
R().re('(\d+)').to_float().is_not_equal(3.14)
# rescue exception
D().default('Not equal').css('title').text().is_not_equal('Not equal')
```

### is_contains

Assertion that variable contains this string, int or float else throw exception. 
Exception can be rescued by [default](#default)
Does not modify variable.

- accept `STRING`, return `STRING`
- accept `INT`, return `INT`
- accept `FLOAT`, return `FLOAT`

```python
from ssc_codegen import D, R

# OK
D().css_all('p').text().is_contains('text')
R().re_all('(\d+)').to_int().is_contains(1)
R().re_all('(\d+)').to_float().is_contains(3.14)
# rescue exception
# note: default does not support array-like variables
D().default(None).css_all('title').text().is_contains('Not contains')
```

### is_regex

Assertion that variable matched by pattern else throw exception. 
Exception can be rescued by [default](#default)
Does not modify variable.

- accept `STRING`, return `STRING`

```python
from ssc_codegen import D, R

# OK
D().css_all('p').text().is_contains('text')
R().is_regex(r'<title>')
# rescue exception
R(None).is_regex('<titled>')
```

### to_int

Convert string or sequence of strings to integer

>[!warning]
> maybe throw exception in runtime (or add sideeffect) if input is not a real integer

- accept `STRING`, return `INT`
- accept `LIST_STRING`, return `LIST_INT`

```python
from ssc_codegen import D, R


R().re(r'(\d+)').to_int()
R().re_all(r'(\d+)').to_int()
# something tag where contains digits
# for avoid exceptions and side effects, extra sanitize
# input before convert
D().css('p').text().re_sub(r'\D').to_int()
D().css_all('p').text().re_sub(r'\D').to_int()
```

### to_float

Convert string or sequence of strings to float(64)

>[!warning]
> maybe throw exception in runtime (or add sideeffect) if input is not a real integer

- accept `STRING`, return `FLOAT`
- accept `LIST_STRING`, return `LIST_FLOAT`

```python
from ssc_codegen import D, R


R().re(r'(\d+\.\d+)').to_float()
R().re_all(r'(\d+\.\d+)').to_float()
# something tag where contains digits
# for avoid exceptions and side effects, extra sanitize
# input before convert
D().css('p').text().re_sub('[^0-9.]').to_float()
D().css_all('p').text().re_sub('[^0-9.]').to_float()

```

### sub_parser

Marks send part of element or document to another schema. used marker `N()`
used to reduce the length of selectors and split data into structures

- accept `DOCUMENT`, return `NESTED`

```python
from ssc_codegen import D, N, ItemSchema


class Head(ItemSchema):
    title = D().css('title').text()
    meta = D().css_all('meta').raw()

    
class Main(ItemSchema):
    head = N().css('head').sub_parser(Head)

```

### jsonify

Marshal json string to object. Serialization used special mark [Json](#json)

>[!note]
> Do not use for parse rest-api responses.
> This expression designed parse json-like objects from html pages

- accept ``STRING``, return `JSON`

```python
from ssc_codegen import D, Json

# looks like this or json-like data for 
# jquery/htmx js libs
# <script type="application/json">{"a": ["b", "c"]}</script>

class Demo(Json):
    a: list[str]

D().css('script').text().jsonify(Demo)

# if contains in Array json:
# all items should be have same structures
# <script type="application/json">[{"a": 1}, {"a": 2}, {"a", 3}]</script>
class Demo2(Json):
    __IS_ARRAY__ = True
    a: int

D().css('script').text().jsonify(Demo2)
```

>[!tip]
> You can generate part of the config from json to reduce manual typing

From file:

```shell
ssc-gen json-gen jsitem.json -o tmp_schema.py
```

From stdin:

```shell
echo '{"a": ["b", "c"]}' | ssc-gen json-gen -o tmp_schema.py
```

## Struct types

### ItemSchema

Represent structure as dict object

MAGIC methods:

- `__PRE_VALIDATE__` - **optional** pre validate input document. If check not passed - throw error. Does not modify input.
- `__SIGNATURE__` - **optional** override schema signature in generated code docstring output

```python
from ssc_codegen import D, ItemSchema


class Main(ItemSchema):
    title = D().css('title').text()
    meta = D().css_all('meta').raw()
    hrefs = D().css_all('a').attr('href')

# generated code output:
# {title: str, meta: list[str], hrefs: list[str]
```

### ListSchema

Represent collections of dict.

MAGIC methods:

- `__SPLIT_DOC__` - **required** instruction how to part document or element input. 
Each part is transferred to the fields. Should be returns [LIST_DOCUMENT](#listdocument)
- `__PRE_VALIDATE__` - **optional** pre validate input document. If check not passed - throw error. Does not modify input.
- `__SIGNATURE__` - **optional** override schema signature in generated code docstring output

```python
from ssc_codegen import D, ListSchema


# http://books.toscrape.com/ cards parse example
class Main(ListSchema):
    # 1. get all books cards
    __SPLIT_DOC__ = D().css_all('.col-lg-3')    
    # 2. extract metadata from card element scope
    name = D().css(".thumbnail").attr("alt")
    image_url = D().css(".thumbnail").attr("src").fmt("https://{{}}")
    url = D().css(".image_container > a").attr("href")
    rating = D().css(".star-rating").attr("class").ltrim("star-rating ")
    price = D().default(0).css(".price_color").text().re(r"(\d+)").to_int()

# generated code output:
# [{name: str, image_url:str, url:str, rating:str, price:int}, ...]
```

### FlatListSchema

Represent array of items

- `__SPLIT_DOC__` - **required** expression how to part document or element input. 
Each part is transferred to the fields. Should be returns [LIST_DOCUMENT](#listdocument)
- `__ITEM__` - **required** expression how to represent item in array output.
- `__PRE_VALIDATE__` - **optional** pre validate input document. If check not passed - throw error. Does not modify input.
- `__SIGNATURE__` - **optional** override schema signature in generated code docstring output

```python
from ssc_codegen import D, FlatListSchema


class Urls(FlatListSchema):
    __SPLIT_DOC__ = D().css_all('a')
    # prettify docstring signature
    __SIGNATURE__ = ["url1", "url_2", ...]

    __ITEM__ = D().attr('href').re_sub(r'^https?://').fmt("https://{{}}")

# generated code output
# [url_1, url_2, ...]
```

### DictSchema

Represent dict with arbitrary string key


- `__SPLIT_DOC__` - **required** instruction how to part document or element input. 
Each part is transferred to the fields.Should be returns [LIST_DOCUMENT](#listdocument)
- `__KEY__` - **required** expression how to parse key. Should be returns [STRING](#string)
- `__VALUE__` - **required** expression how to parse value.
- `__PRE_VALIDATE__` - **optional** pre validate input document. If check not passed - throw error. Does not modify input.
- `__SIGNATURE__` - **optional** override schema signature in generated code docstring output


```python
from ssc_codegen import D, DictSchema

# http://books.toscrape.com/ cards parse example
class BooksDict(DictSchema):
    __SPLIT_DOC__ = D().css_all('.col-lg-3')
    __SIGNATURE__ = {"book_name": "url", "book_name2": "..."}
    
    __KEY__ = D().css('.thumbnail').attr('alt')
    __VALUE__ = D().css('.image_container > a').attr('href')    

# generate code output
# {book_name_1: url_1, book_name_2: url_2, ...}
```

### Json

Special marker for json marshalling structures

- `__IS_ARRAY__` - marks if entrypoint start as sequence of map types

>[!note]
> in current version (0.6.2) key names have destruction:
> key cannot be named as reserved keywords (class, def, etc)
> key should be matched a `[_a-zA-Z][_a-zA-Z0-9]*` expr

support types:

- `T`
  - str
  - int
  - float
  - bool
  - None
  - str | None - optional str (can be null)
  - int | None - optional int (can be null)
  - float | None - optional float (can be null)
  - bool | None - optional bool (can be null)

- `Array[T | Json]` array of types
- `Json` - mark as dict/map type with key-values

>[!tip]
> You can create template schema by ssc-gen


```shell
ssc-gen json-gen example.js -o template.py
```

or from stdin

```shell
echo '{"a": ["b", "c"]}' | ssc-gen json-gen -o template.py
```

example:

```python
from ssc_codegen import R, Json, ItemSchema
# http://quotes.toscrape.com/js/

class Author(Json):
    name: str
    goodreads_links: str
    slug: str

class Quote(Json):
    # mark as array entrypoint
    # if object (map/dict) contains in document - do not add it
    # in current case, quotes contains in array of dicts and render by jquery
    # <script>
    # var data = [
    # {
    #     "tags": [
    #         "change",
    #         "deep-thoughts",
    #         "thinking",
    #         "world"
    #     ],
    #     "author": {
    #         "name": "Albert Einstein",
    #         "goodreads_link": "/author/show/9810.Albert_Einstein",
    #         "slug": "Albert-Einstein"
    #     },
    #     "text": "..."
    # }, ... ]
    __IS_ARRAY__ = True

    tags: list[str]
    author: Author
    text: str



class Main(ItemSchema):
    data = R().re(r'var\s+\w+\s*=\s*(\[[\s\S]*?\]);').jsonify(Quote)
```
