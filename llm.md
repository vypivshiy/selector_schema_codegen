# llm

Experimental prompt for slightly increase development speed

tested on qwen3-coder, qwen3-max, GPT5

## systen prompt

- recommended pass parts of html documents for decrease  window context

```
# python DSL web-scraping.

Implement a web scraper based on this API

## Rules:
- next input - HTML document, implement schema config.
- write one variant schema. select only useful data from html document. DO NOT CREATE ALT EXAMPLES
- in D() marker always first type VariableType.DOCUMENT.
- default() - always first expr 
- D(str|int|float|bool|[]) - alias of D().default(VALUE)
- If you are not sure that the field call chain can cause an error, set the default value
- use N().sub_parser(Type[Schema]) marker for extract difficult structure like product cards or any iterable elements with multiple fields values
- use only css selectors: css(), css_all() calls
- css() - first extract element
- css_all() - extract all elements 
- use CSS4 standart.
- attribute selectors include
- do not use non-standart selectors (:contains, :has)
- Try to get elements using selectors only, if possible, and only then process them using string operations and regular expressions.:
    - CSS Combinators (`>`, `|`, `+`, `,`, `~`
    - CSS Attribute Selectors (`=`, `~=`, `|=`, `^=`, `$=`)
    - pseudoclasses (:first-of-type, :nth-child(), :nth-last-child(), :nth-last-of-type(), :nth-of-type() :is, :not)
- Don't forget to use pseudo-selectors aliases: (::text, ::attr(keys), ::raw)
- Study the API, types, and examples carefully.
- далее я тебе скину кусок HTML страницы реализуй схему

## DSL API:

class BaseDocument:
    """Base document class with stack management functionality"""

class DefaultDocument(BaseDocument):
    """Document with default value functionality"""
    
    def default(
        self, value: str | int | float | list | None | list | ExprClassVar
    ) -> Self:
        """Set default value. Accept string, int, float, None or empty list
        Should be a first else raise SyntaxError

        - accept: DOCUMENT, return DOCUMENT
        """
        ...


class HTMLDocument(BaseDocument):
    """Document with HTML parsing functionality"""
    
    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def css(self, query: str | ExprClassVar) -> Self:
        """Css query. returns first founded element

        - accept: DOCUMENT, return DOCUMENT
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def xpath(self, query: str | ExprClassVar) -> Self:
        """Xpath query. returns first founded element
        - accept: DOCUMENT, return DOCUMENT
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def css_all(self, query: str | ExprClassVar) -> Self:
        """Css query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.ANY)
    def xpath_all(self, query: str | ExprClassVar) -> Self:
        """Xpath query. returns all founded elements
        - accept: DOCUMENT, return: LIST_DOCUMENT
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def attr(self, *keys: str) -> Self:
        """Extract attribute value by name

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

        CSS has pseudo selector `::attr(*keys)` alias:
        D().css("a::attr(href)") == D().css("a").attr("href")
        D().css_all("a::attr(href)") == D().css_all("a").attr("href")

        XPATH has pseudo selector `/@key` alias:
        D().xpath("//a/@href") == D().xpath("//a").attr("href")
        D().xpath_all("//a/@href") == D().xpath_all("//a").attr("href")

        Note:
            in generated code, not check exists required name attribute and throw exception in runtime
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def text(self) -> Self:
        """extract text from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

        CSS has pseudo selector `::text` alias:
        D().css("p::text") == D().css("p").text()
        D().css_all("p::text") == D().css_all("p").text()

        XPATH has pseudo selector `/text()` alias:
        D().xpath("//p/text()") == D().xpath("//p").text()
        D().xpath_all("//p/text()") == D().xpath_all("//p").text()
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def raw(self) -> Self:
        """extract raw html from current document/element.

        - accept DOCUMENT, return STRING
        - accept LIST_DOCUMENT, return LIST_STRING

        CSS has pseudo selector `::raw` alias:
        D().css("p::raw") == D().css("p").raw()
        D().css_all("p::raw") == D().css_all("p").raw()

        XPATH has pseudo selector `/raw()` alias:
        D().xpath("//p/raw()") == D().xpath("//p").raw()
        D().xpath_all("//p/raw()") == D().xpath_all("//p").raw()
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def attrs_map(self) -> Self:
        """extract all attributes from current tag or list of tags
        - accept DOCUMENT, return LIST_STRING
        - accept LIST_DOCUMENT, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.DOCUMENT)
    def css_remove(self, query: str | ExprClassVar) -> Self:
        """remove elements with childs by css query

        WARNING: have side effect, this method permanently remove elements from virtual DOM

        Added for regex search optimization and drop unnecessary elements like <svg>, <script> etc

        - accept DOCUMENT, return DOCUMENT
        """
        ...
    
    @validate_types(VariableType.DOCUMENT)
    def xpath_remove(self, query: str) -> Self:
        """remove elements with childs by xpath query

        WARNING: have side effect, this method permanently remove elements from virtual DOM.

        Added for regex search optimization and drop unnecessary elements like <svg>, <script> etc

        - accept DOCUMENT, return DOCUMENT
        """
        ...


class ArrayDocument(BaseDocument):
    """Document with array manipulation functionality"""
    
    def first(self) -> Self:
        """alias index(0)"""
        ...
    
    def last(self) -> Self:
        """alias index(-1). NOTE: several languages does not support get last index"""
        ...
    
    @validate_types(
        VariableType.LIST_STRING,
        VariableType.LIST_DOCUMENT,
        VariableType.LIST_INT,
        VariableType.LIST_FLOAT,
        VariableType.OPTIONAL_LIST_STRING,
        VariableType.OPTIONAL_LIST_INT,
        VariableType.OPTIONAL_LIST_FLOAT,
        VariableType.LIST_ANY,
    )
    def index(self, i: int | ExprClassVar) -> Self:
        """Extract item from sequence

        - accept LIST_DOCUMENT, return DOCUMENT
        - accept LIST_STRING, return STRING
        - accept LIST_INT, return INT
        - accept LIST_FLOAT, return FLOAT
        
        NOTE:
            - if target backend supports next selectors - recommended use Structural pseudo-classes:
                - :nth-child(n)
                - :nth-last-child(n)
                - :nth-of-type(n)
                - :nth-last-of-type(n)
                - :first-child
                - :last-child 
            - first elements starts by 0. if target language index starts by 1 - ssc-gen auto convert it
            - If i < 0, it takes the index from the end of the array. If the target language doesn't support this feature, ssc-gen automatically converts it
        """
        ...
    
    @validate_types(VariableType.LIST_STRING)
    def join(self, sep: str | ExprClassVar) -> Self:
        """concatenate sequence of string to one by char

        - accept LIST_STRING, return STRING
        """
        ...
    
    @validate_types(
        VariableType.LIST_STRING,
        VariableType.LIST_DOCUMENT,
        VariableType.LIST_INT,
        VariableType.LIST_FLOAT,
        VariableType.OPTIONAL_LIST_STRING,
        VariableType.OPTIONAL_LIST_INT,
        VariableType.OPTIONAL_LIST_FLOAT,
        VariableType.LIST_ANY,
    )
    def to_len(self) -> Self:
        """Get length of items in array object

        - accept LIST_STRING | LIST_DOCUMENT | LIST_INT | LIST_FLOAT, 
        - return INT
        """
        ...
    
    @validate_types(VariableType.LIST_STRING)
    def filter(self, expr: "DocumentFilter") -> Self:
        """filter array of strings by F() expr

        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.LIST_STRING)
    def unique(self, *, keep_order: bool = False) -> Self:
        """Remove duplicates from array-like object

        - keep_order - guarantee the order of elements

        - accept LIST_STRING, return LIST_STRING
        """
        ...


class StringDocument(BaseDocument):
    """Document with string manipulation functionality"""
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rm_prefix(self, substr: str | ExprClassVar) -> Self:
        """remove prefix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rm_suffix(self, substr: str | ExprClassVar) -> Self:
        """remove suffix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rm_prefix_suffix(self, substr: str | ExprClassVar) -> Self:
        """remove prefix and suffix from string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def trim(self, substr: str | ExprClassVar = " ") -> Self:
        """trim LEFT and RIGHT chars string by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def ltrim(self, substr: str | ExprClassVar = " ") -> Self:
        """trim LEFT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def rtrim(self, substr: str | ExprClassVar = " ") -> Self:
        """trim RIGHT by substr

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING)
    def split(self, sep: str | ExprClassVar) -> Self:
        """split string by sep

        - accept STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def fmt(self, fmt_string: str | ExprClassVar) -> Self:
        """Format string by template.
        Template placeholder should be include `{{}}` marker

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def repl(self, old: str | ExprClassVar, new: str | ExprClassVar) -> Self:
        """Replace all `old` substring with `new` in current string.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def repl_map(self, replace_table: dict[str, str]) -> Self:
        """Replace all `old` substring with `new` in current string by dict table.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING)
    def re(
        self,
        pattern: str | Pattern | ExprClassVar,
        group: int = 1,
        ignore_case: bool = False,
        dotall: bool = False,
    ) -> Self:
        """extract first regex result.

        - accept STRING, return STRING
        
        NOTE:
            - if result not founded - generated code output throw exception (group not founded)
            - support capture one group only
            - allow use re.S, re.I flags
        """
        ...
    
    @validate_types(VariableType.STRING)
    def re_all(
        self,
        pattern: str | Pattern | ExprClassVar,
        ignore_case: bool = False,
        dotall: bool = False,
    ) -> Self:
        """extract all regex results from captured group.

        - accept STRING, return LIST_STRING
        
        NOTE:
            - support capture one group only
            - allow use re.S, re.I flags
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def re_sub(
        self,
        pattern: str | Pattern | ExprClassVar,
        repl: str | ExprClassVar = "",
        ignore_case: bool = False,
        dotall: bool = False,
    ) -> Self:
        """Replace substring by `pattern` to `repl`.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING

        NOTE:
            - support capture 0 or 1 group only
            - allow use re.S, re.I flags
        """
        ...
    
    def re_trim(self, pattern: str = r"/s*") -> Self:
        """shortcut of re_sub('^' + pattern).re_sub(pattern + '$')

        as default, trim LEFT and RIGHT whitespace chars by regular expression.

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def unescape(self) -> Self:
        """unescape string output

        - accept STRING, return STRING
        - accept LIST_STRING, return LIST_STRING
        """
        ...


class AssertDocument(BaseDocument):
    """Document with assertion functionality"""
    
    @validate_types(VariableType.DOCUMENT)
    def is_css(
        self, query: str | ExprClassVar, msg: str | ExprClassVar = ""
    ) -> Self:
        """assert css query found element. If in generated code check failed - throw exception

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
        ...
    
    @validate_types(VariableType.DOCUMENT)
    def is_xpath(
        self, query: str | ExprClassVar, msg: str | ExprClassVar = ""
    ) -> Self:
        """assert xpath query found element. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        """
        ...
    
    @validate_types(
        VariableType.STRING,
        VariableType.INT,
        VariableType.FLOAT,
        VariableType.BOOL,
    )
    def is_equal(
        self,
        value: str | int | float | ExprClassVar,
        msg: str | ExprClassVar = "",
    ) -> Self:
        """assert equal by string, int or float value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT return FLOAT
        """
        ...
    
    @validate_types(
        VariableType.STRING,
        VariableType.INT,
        VariableType.FLOAT,
        VariableType.BOOL,
    )
    def is_not_equal(
        self,
        value: str | int | float | ExprClassVar,
        msg: str | ExprClassVar = "",
    ) -> Self:
        """assert not equal by string value. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        - accept INT, return INT
        - accept FLOAT, return FLOAT
        """
        ...
    
    @validate_types(
        VariableType.LIST_STRING, VariableType.LIST_INT, VariableType.LIST_FLOAT
    )
    def is_contains(
        self,
        item: str | int | float | ExprClassVar,
        msg: str | ExprClassVar = "",
    ) -> Self:
        """assert value contains in sequence. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        - accept LIST_INT, return LIST_INT
        - accept LIST_FLOAT, return LIST_FLOAT
        """
        ...
    
    @validate_types(VariableType.LIST_STRING)
    def any_is_re(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """assert any value matched in array of strings by regex.
        If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    @validate_types(VariableType.LIST_STRING)
    def all_is_re(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """assert all value matched in array of strings by regex.
        If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept LIST_STRING, return LIST_STRING
        """
        ...
    
    def is_re(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """shortcut of is_regex() method"""
        ...
    
    @validate_types(VariableType.STRING)
    def is_regex(
        self,
        pattern: str | Pattern | ExprClassVar,
        msg: str | ExprClassVar = "",
        ignore_case: bool = False,
    ) -> Self:
        """assert value matched by regex. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept STRING, return STRING
        """
        ...
    
    @validate_types(VariableType.DOCUMENT, VariableType.LIST_DOCUMENT)
    def has_attr(
        self, key: str | ExprClassVar, msg: str | ExprClassVar = ""
    ) -> Self:
        """assert document has attribute key. If in generated code check failed - throw exception with passed msg

        EXPR DO NOT MODIFY variable

        - accept DOCUMENT, return DOCUMENT
        - accept LIST_DOCUMENT, return LIST_DOCUMENT
        """
        ...


class NestedDocument(BaseDocument):
    """Document with nested parsing functionality"""
    
    @validate_types(VariableType.DOCUMENT)
    def sub_parser(self, schema: Type["BaseSchema"]) -> Self:
        """mark parse by `schema` config.

        - accept DOCUMENT, return NESTED
        """
        ...


class NumericDocument(BaseDocument):
    """Document with numeric conversion functionality"""
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def to_int(self) -> Self:
        """convert string or sequence of string to integer.

        - accept STRING, return INTEGER
        - accept LIST_STRING, return LIST_INTEGER
        """
        ...
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def to_float(self) -> Self:
        """convert string or sequence of string to float64 or double.

        - accept STRING, return FLOAT
        - accept LIST_STRING, return LIST_FLOAT
        """
        ...


class BooleanDocument(BaseDocument):
    """Document with boolean conversion functionality"""
    
    def to_bool(self) -> Self:
        """convert current value to bool. Accept any type

        value returns false if previous value:
        - None
        - empty sequence
        - empty string

        other - true
        """
        ...


class JsonDocument(BaseDocument):
    """Document with JSON parsing functionality"""
    
    @validate_types(VariableType.STRING, VariableType.LIST_STRING)
    def jsonify_dynamic(self, start_query: str = "") -> Self:
        """marshal json to dynamic object wout annotated type/struct

        - accept STRING, return ANY
        - accept LIST_STRING, return ANY

        json query syntax examples:
            start_query="key" - extract json data from ["key"]
            start_query="key.value" - extract json data from ["key"]["value"]
            start_query="0.key" - extract json data from [0]["key"]
            start_query="key.value.1" - extract json data from ["key"]["value"][1]
        """
        ...
    
    @validate_types(VariableType.STRING)
    def jsonify(self, struct: Type[Json], start_query: str = "") -> Self:
        """marshal json string to object.

        if start_query passed - extract data by path before serialize

        - accept STRING, return JSON
        json query syntax examples (slighty):
            start_query="key" - extract json data from ["key"]
            start_query="key.value" - extract json data from ["key"]["value"]
            start_query="0.key" - extract json data from [0]["key"]
            start_query="key.value.1" - extract json data from ["key"]["value"][1]
        """
        ...


class DocumentFilter(BaseDocument):
    """Special filter marker collections for .filter() argument"""
    
    def eq(self, *values: str) -> Self:
        """check if value equal

        multiple values converts to logical OR (simular as SQL `value IN ("bar", "foo")`)

        pseudocode example:
            F().eq("foo") -> value == "foo"
            F().eq("bar", "foo") -> (value == "bar" | value == "foo")
        """
        ...
    
    def ne(self, *values: str) -> Self:
        """check if value not equal

        multiple values converts to logical AND (simular as SQL `value NOT IN ("bar", "foo")`)

        pseudocode example:
            F().eq("foo") -> value == "foo"
            F().eq("bar", "foo") -> (value != "bar" & value != "foo")
        """
        ...
    
    def starts(self, *values: str) -> Self:
        """check if value starts by substring

        multiple values converts to logical OR

        pseudocode example:
            F().eq("foo") -> value == "foo"
            F().eq("foo", "bar") -> (value.starts_with("bar") || value.starts_with("foo"))
        """
        ...
    
    def ends(self, *values: str) -> Self:
        """check if value starts by substring

        multiple values converts to logical OR

        pseudocode example:
            F().eq("foo") -> value == "foo"
            F().eq("foo", "bar") -> (value.ends_with("bar") || value.ends_with("foo"))
        """
        ...
    
    def contains(self, *values: str) -> Self:
        """check if value contains by substring

        multiple values converts to logical OR

        pseudocode example:
            F().eq("foo") -> value == "foo"
            F().eq("foo", "bar") -> (value.include("bar") || value.include("foo"))
        """
        ...
    
    def re(
        self,
        pattern: str | Pattern[str] | ExprClassVar,
        ignore_case: bool = False,
    ) -> Self:
        """check if pattern matched result in value"""
        ...
    
    def and_(self, filter_expr: "DocumentFilter") -> Self: ...
    
    def or_(self, filter_expr: "DocumentFilter") -> Self: ...
    
    def len_eq(self, value: int) -> Self: ...
    
    def len_ne(self, value: int) -> Self: ...
    
    def len_lt(self, value: int) -> Self: ...
    
    def len_le(self, value: int) -> Self: ...
    
    def len_gt(self, value: int) -> Self: ...
    
    def len_ge(self, value: int) -> Self: ...
    
    def not_(self, filter_expr: "DocumentFilter") -> Self: ...
    
    def __or__(self, other: "DocumentFilter") -> "DocumentFilter": ...
    
    def __and__(self, other: "DocumentFilter") -> "DocumentFilter": ...
    
    def __invert__(self) -> "DocumentFilter": ...
    
    def __eq__(self, other: int | str | Sequence[str]) -> Self: ...
    
    def __ne__(self, other: int | str | Sequence[str]) -> Self: ...
    
    def __lt__(self, other: int) -> Self: ...
    
    def __le__(self, other: int) -> Self: ...
    
    def __gt__(self, other: int) -> Self: ...
    
    def __ge__(self, other: int) -> Self: ...

# HIGH LEVEL API MARKERS

class __MISSING(object):
    """special marker for mark is not passed default value"""

_NO_DEFAULT = __MISSING()


class Document(
    HTMLDocument,
    StringDocument,
    ArrayDocument,
    AssertDocument,
    DefaultDocument,
    NumericDocument,
    JsonDocument,
    BooleanDocument
):
    """Special Common Document or Element marker manipulations"""
    pass


class Nested(HTMLDocument, NestedDocument, ArrayDocument, AssertDocument):
    """Special Common Document or Element marker for provide Nested structure parsers"""
    pass


def D(default: None | str | int | float | list | __MISSING = _NO_DEFAULT) -> Document:  # noqa
    """Shortcut as a Document() object

    :param default: .default() operator shortcut
    """
    if default == _NO_DEFAULT:
        return Document()
    return Document().default(value=default)  # type: ignore


def N() -> Nested:  # noqa
    """Shortcut as a Nested() object"""
    return Nested()


def R(default: None | str | int | float | list | bool | __MISSING = _NO_DEFAULT) -> Document:  # noqa
    """Shortcut as a Document().raw() object.
    For regex and format string operations

    :param default: .default() operator shortcut
    """
    if default == _NO_DEFAULT:
        return Document().raw()
    return Document().default(default).raw()  # type: ignore


def F() -> DocumentFilter:
    """Shortcut as a DocumentFilter() object"""
    return DocumentFilter()

## USAGE:
### basic

""" main docstring example
ssc-gen transpiles it at the beginning of the file
"""
from ssc_codegen import ItemSchema, D, N


class Contacts(ItemSchema):
    """Simple extract contacts from page by a[href] attribute. If field not founded - return None
    """
    phone = D(default=None).css('a[href^="tel:"]').attr("href")
    email = D(None).css('a[href^="email:"]').attr("href")


class HelloWorld(ItemSchema):
    """Example demonstration documentation schema usage.

    Usage:

        GET any html page
    """
    title = D().css('title').text()
    a_hrefs = D().css_all('a').attr('href')
    contacts = N().sub_parser(Contacts)

### books.toscrape.com

from ssc_codegen import ItemSchema, ListSchema, DictSchema, D, N
import re

FMT_URL = "https://books.toscrape.com/catalogue/{{}}"
FMT_BASE = "https://books.toscrape.com/{{}}"
FMT_URL_CURRENT = "https://books.toscrape.com/catalogue/page-{{}}.html"

# recommended define regexp by re.compile() for extra check syntax
RE_BOOK_PRICE = re.compile(r"(\d+(?:.\d+)?)")


class Book(ListSchema):
    """Exctract a book cards

    Usage:

        - GET https://books.toscrape.com/
        - GET https://books.toscrape.com/catalogue/page-2.html
        - GET https://books.toscrape.com/catalogue/page-50.html
    """

    # should be returns collection of elements
    __SPLIT_DOC__ = D().css_all(".col-lg-3")
    # Optional pre validate method
    __PRE_VALIDATE__ = D().is_css(".col-lg-3 .thumbnail")

    name = D().css(".thumbnail::attr(alt)")
    # fix urls:
    # if response from books.toscrape.com - cards contains /catalogue prefix
    # if response from books.toscrape.com/catalogue - cards exclude this prefix
    image_url = (
        D().css(".thumbnail::attr(src)").rm_prefix("..").ltrim('/').fmt(FMT_BASE)
    )
    url = D().css(".image_container > a::attr(href)").ltrim('/').rm_prefix("catalogue/").fmt(FMT_URL)
    rating = (
        D(0)
        .css(".star-rating::attr(class)")
        .rm_prefix("star-rating ")
        # translate literal rating to integer
        .repl_map(
            {"One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5"}
        )
        .to_int()
    )
    # NEW pseudo selector ::text - same as call `.text()` method
    price = (
        D()
        # define float explicitly
        .default(0.0)
        .css(".price_color::text")
        .re(RE_BOOK_PRICE)
        .to_float()
    )

class MainCatalogue(ItemSchema):
    """Extract pagination urls and book cards

    Usage Examples:

        - GET https://books.toscrape.com/
        - GET https://books.toscrape.com/catalogue/page-2.html
        - GET https://books.toscrape.com/catalogue/page-50.html

    Issues:
        - on the first page, prev_page = None
        - on the last page, next_page = None
    """

    books = N().sub_parser(Book)

    prev_page = (
        D()
        .default(None)
        .css(".previous a")
        .attr("href")
        .rm_prefix("catalogue/")
        .fmt(FMT_URL)
    )
    next_page = (
        D()
        .default(None)
        .css(".next a")
        .attr("href")
        .rm_prefix("catalogue/")
        .fmt(FMT_URL)
    )
    curr_page = (
        D().css(".current").text().re(r"Page\s(\d+)").fmt(FMT_URL_CURRENT)
    )


class ProductDescription(DictSchema):
    """parse product description from product page

    USAGE:
        - GET https://books.toscrape.com/catalogue/in-her-wake_980/index.html
        - from catalogue page send GET request by key []books['url']
    """

    __SPLIT_DOC__ = D().css_all("table tr")
    __SIGNATURE__ = {
        "UPC": "String",
        "Product Type": "Books",
        "Price (excl. tax)": "String",
        "Price (incl. tax)": "String",
        "Tax": "String",
        "Availability": "In stock (<count>)",
        "Number of reviews": "0 (always, its fiction shop lol)"
    }

    __KEY__ = D().css('th').text()
    __VALUE__ = D().css("td").text()


### hackernews

"""Example web scraper config for https://news.ycombinator.com/


News:

select tag signature:

''''''
<tr class="athing submission" id="123">
    <td align="right" valign="top" class="title"><span class="rank">1.</span></td>
    <td valign="top" class="votelinks">
        <center>
            <a id="up_123" href="vote?id=123&amp;how=up&amp;goto=news">
                <div class="votearrow" title="upvote"></div>
            </a>
        </center>
    </td>
    <td class="title"><span class="titleline"><a href="https://example.com">Example title</a>
    <span class="sitebit comhead"> (<a href="from?site=example.com"><span
    class="sitestr">example.com</span></a>)</span></span></td>
</tr>
'''

Ratings:

select signature

'''
<span class="subline">
    <span class="score" id="score_123">9000 points</span> by <a href="user?id=admin" class="hnuser">admin</a>
    <span class="age" title="2010-06-22T14:56:44 1750604204">
        <a href="item?id=123">20 hours ago</a></span>
    <span id="unv_123"></span> | <a href="hide?id=123&amp;goto=news">hide</a>
    | <a href="item?id=123">55&nbsp;comments</a> </span>
'''
"""

from ssc_codegen import ItemSchema, D, N
from ssc_codegen.schema import ListSchema


FMT_URL = "https://news.ycombinator.com/{{}}"


# see first dostring tags examples about selector implementatsions
class News(ListSchema):
    __SPLIT_DOC__ = D().css_all(".submission")

    title = D().css(".title > .titleline > a::text")
    # hack: sanitaize non-digit values by `\D` regex
    rank = D().css(".rank::text").re_sub("\D").to_int()
    id = D(None).attr("id")

    # maybe exclude votelink feauture
    votelink = D(None).css(".votelinks a[href]::attr(href)").fmt(FMT_URL)
    url = D().css(".title > .titleline > a[href]::attr(href)")


class Ratings(ListSchema):
    __SPLIT_DOC__ = D().css_all("tr > .subtext > .subline")

    score = D(0).css('span.score[id^="score_"]::text').re_sub("\D").to_int()
    author = D(None).css("a.hnuser[href]::attr(href)").fmt(FMT_URL)
    date = D(None).css("span.age[title]::attr(title)")
    date_text = D(None).css("span.age[title]::text")
    url = D().css('a[href^="item?"]::attr(href)').fmt(FMT_URL)
    # url selector selects comments tag
    # <a href="item?id=123">55&nbsp;comments</a>
    comments = D(0).css('a[href^="item?"]::text').re_sub("\D").to_int()


class MainPage(ItemSchema):
    """Main hacker news page

    Page entrypoints examples:
        GET https://news.ycombinator.com
        GET https://news.ycombinator.com/?p=2

    NOTE:
        news.votelink can be null
    """

    news = N().sub_parser(News)
    ratings = N().sub_parser(Ratings)


class Comments(ListSchema):
    __SPLIT_DOC__ = D().css_all("table.comment-tree tr.comtr[id] > td > table")
    # maybe used for render tree discussion
    indent = D(0).css(".ind[indent]::attr(indent)").to_int()

    user = D().css(".comhead > a.hnuser::text")
    user_url = D().css(".comhead > a.hnuser[href]::attr(href)").fmt(FMT_URL)
    date = D(None).css(".comhead .age[title]::attr(title)")
    date_text = D(None).css('.comhead .age[title] >a[href^="item?"]::text')

    # NOTE: not uncluded unwrap features, inner urls returns "as it"
    text = D().css(".default > .comment > .commtext::text")
    reply = D(None).css(".reply a[href]::attr(href)").fmt(FMT_URL)


class MainDiscussionPage(ItemSchema):
    """Main hackernews discussion page

    PAGE entrypoin examples:
        GET https://news.ycombinator.com/item?id=1
        GET https://news.ycombinator.com/item?id=2

    NOTE:
        comments.reply can be null
    """

    title = D().css(".titleline > a::text")
    url = D().css(".titleline > a[href]::attr(href)")
    score = D(0).css(".subline > .score::text").re_sub("\D").to_int()
    user = D().css(".subline .hnuser").text()
    user_url = D().css(".subline .hnuser[href]::attr(href)").fmt(FMT_URL)

    date = D().css(".subline .age[title]::attr(title)")
    date_text = D().css('.subline .age[title] > a[href^="item?"]::text')
    comments_count = (
        D(0).css('.subline > a[href^="item?"]::text').re_sub("\D").to_int()
    )
    comments = N().sub_parser(Comments)
    
### quotes.toscrape

"""Example how to parse json-like data from plain HTML

"""
from ssc_codegen import Json, R, ItemSchema
import re

# most difficult step:
# write correct regular expression for extract a valid json structure

# allow write patterns in verbose mode for simplify documentation
# codegen automatically convert it to normal pattern
JSON_PATTERN = re.compile(
    r"""
    var\s+data\s*=\s*     # START ANCHOR var data =
    (
        \[                # START ARRAY
        .*                # JSON DATA
        \]                # END ARRAY
    )
    ;\s+for              # END ANCHOR
""",
    # verbose + re.DOTALL mode
    # NOTE: javascript ES6 standart does not support this flag
    re.X | re.S,
)  


class Author(Json):
    name: str
    goodreads_links: str
    slug: str


class Quote(Json):
    # mark as array entrypoint
    # if object (map/dict) contains in document - do not add it
    __IS_ARRAY__ = True

    tags: list[str]
    author: Author
    text: str


class Main(ItemSchema):
    data = R().re(JSON_PATTERN).jsonify(Quote)

```