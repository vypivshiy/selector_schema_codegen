# Tutorial: Writing Web Scrapers with KDL Schema DSL

> **Learn by example:** From simple extraction to advanced patterns

---

## Why KDL Schema DSL?

Traditional web scraping код quickly becomes imperative mess:

```python
# Traditional approach
soup = BeautifulSoup(html, 'lxml')
books = []
for book_el in soup.select('.book'):
    title = book_el.select_one('.title').text.strip()
    price_text = book_el.select_one('.price').text
    price = float(re.search(r'(\d+\.\d+)', price_text)[1])
    # ... 50 more lines ...
    books.append({'title': title, 'price': price})
```

**KDL Schema DSL approach:**

```kdl
struct Book type=list {
    @split-doc { css-all ".book" }
    title { css ".title"; text; trim }
    price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
}
```

**Advantages:**

✅ **Declarative** - describe *what* to extract, not *how*  
✅ **Type-safe** - compile-time checks catch errors early  
✅ **Type-annotated** - generated code includes TypedDict/interfaces  
✅ **Multi-language** - one DSL → Python, JavaScript, etc.  
✅ **Maintainable** - clear structure, easy to understand  
✅ **Reusable** - compose structures, define transforms once

---

## Getting Started

### Step 1: Install

```bash
pip install selector-schema-codegen
# or
uv pip install selector-schema-codegen
```

### Step 2: Your First Schema

Let's extract a page title:

**HTML:**
```html
<html>
  <head><title>Example Page</title></head>
  <body><h1>Welcome</h1></body>
</html>
```

**Schema (`simple.kdl`):**
```kdl
struct Simple {
    title {
        css "title"
        text
    }
}
```

**Generate code:**
```bash
ssc-kdl generate simple.kdl -t py-bs4
```

**Use it:**
```python
from simple import Simple, SimpleType  # Type annotation available!

html = "<html><head><title>Example Page</title></head></html>"
parser = Simple(html)
result: SimpleType = parser.parse()
# {'title': 'Example Page'}

# IDE autocomplete works!
print(result['title'])  # ✅ Type-checked
```

**Generated types:**
```python
class SimpleType(TypedDict):
    title: str
```

That's it! Now let's explore real-world examples.

---

## Example 1: Books Catalogue

**Source:** https://books.toscrape.com

### 1.1 Single Book

**HTML snippet:**
```html
<article class="book">
  <h3><a href="/book_123.html" title="Product Name">Product Name</a></h3>
  <div class="price">£51.77</div>
  <p class="star-rating Three">...</p>
</article>
```

**Schema:**
```kdl
struct Book type=list {
    @split-doc { css-all ".product_pod" }
    
    name {
        css "h3 a"
        attr "title"
    }
    
    price {
        css ".price_color"
        text
        re #"£(\d+\.\d+)"#
        to-float
    }
}
```

**Key concepts:**
- `type=list` - extract multiple items
- `@split-doc` - split page into elements (one per book)
- `css` - CSS selector
- `text` / `attr` - extract text or attribute
- `re #"pattern"#` - regex with **one capture group**
- `to-float` - type conversion

**Pipeline flow:**
```
Document → css → text → re → to-float → result
```

---

### 1.2 With Star Rating

Add rating using `repl` (dictionary replacement):

```kdl
define REPL-RATING {
    repl {
        One "1"
        Two "2"
        Three "3"
        Four "4"
        Five "5"
    }
}

struct Book type=list {
    @split-doc { css-all ".product_pod" }
    
    name { css "h3 a"; attr "title" }
    price { css ".price_color"; text; re #"£(\d+\.\d+)"#; to-float }
    
    rating {
        css ".star-rating"
        attr "class"
        rm-prefix "star-rating "
        REPL-RATING
        to-int
    }
}
```

**New operations:**
- `rm-prefix` - remove prefix from string
- `REPL-RATING` - apply dictionary mapping
- `to-int` - convert to integer

**Result:**
```json
[
  {"name": "Product Name", "price": 51.77, "rating": 3},
  ...
]
```

---

### 1.3 Nested Structures

Extract book details with nested product info:

**HTML:**
```html
<div class="page">
  <h1>Book Title</h1>
  <table class="table-striped">
    <tr><th>UPC</th><td>abc123</td></tr>
    <tr><th>Price (excl. tax)</th><td>£51.77</td></tr>
  </table>
</div>
```

**Schema:**
```kdl
struct ProductInfo type=table {
    @table { css "table" }
    @rows { css-all "tr" }
    @match { css "th"; text; trim; lower }
    @value { css "td"; text }
    
    upc {
        match { eq "upc" }
    }
    
    price {
        match { starts "price" }
        re #"(\d+\.\d+)"#
        to-float
    }
}

struct BookDetails {
    title {
        css "h1"
        text
    }
    
    product-info {
        nested ProductInfo
    }
}
```

**Key concepts:**
- `type=table` - extract from HTML table
- `-match` - pipeline to extract key from row
- `-value` - pipeline to extract value from row
- `match { eq "..." }` - predicate to filter rows
- `nested` - reference another structure

**Result:**
```json
{
  "title": "Book Title",
  "product_info": {
    "upc": "abc123",
    "price": 51.77
  }
}
```

---

### 1.4 Catalogue with Books

Combine everything:

```kdl
struct Book type=list {
    @split-doc { css-all ".product_pod" }
    name { css "h3 a"; attr "title" }
    price { css ".price_color"; text; re #"£(\d+\.\d+)"#; to-float }
}

struct MainCatalogue {
    title {
        css "h1"
        text
    }
    
    books {
        nested Book
    }
    
    total-books {
        css-all ".product_pod"
        len
    }
}
```

**New operations:**
- `len` - get array length

**Result:**
```json
{
  "title": "All products",
  "books": [
    {"name": "Book 1", "price": 51.77},
    {"name": "Book 2", "price": 20.00}
  ],
  "total_books": 20
}
```

---

## Example 2: Quotes with JSON

**Source:** https://quotes.toscrape.com/js/

This site embeds data in JavaScript - perfect for `jsonify`!

### 2.1 Extracting Embedded JSON

**HTML snippet:**
```html
<script>
  var data = [
    {"text": "Quote 1", "author": "Author 1", "tags": ["tag1"]},
    {"text": "Quote 2", "author": "Author 2", "tags": ["tag2"]}
  ];
  for (var i in data) { ... }
</script>
```

**Schema:**
```kdl
// 1. Define regex to extract JSON
define JSON-PATTERN=#"""
(?xs)
    var\s+data\s*=\s*     # START ANCHOR
    (
        \[                # START ARRAY
        .*                # JSON DATA
        \]                # END ARRAY
    )
    ;\s+for              # END ANCHOR
"""#

// 2. Define JSON structure
json Quote array=#true {
    text str
    author str
    tags (array)str
}

// 3. Extract and parse
struct Main {
    data {
        raw
        re JSON-PATTERN
        jsonify Quote
    }
}
```

**Key concepts:**
- `define` - reusable constants
- `#"""..."""#` - raw string for multiline regex
- `(?xs)` - regex flags: `x` = VERBOSE (comments allowed), `s` = DOTALL
  - **Note:** VERBOSE is auto-converted to inline form during generation
- `json` - define JSON schema
- `array=#true` - mark as array
- `(array)str` - array of strings
- `raw` - extract HTML source
- `re` - extract with regex (captures **first group only**)
- `jsonify` - deserialize JSON using schema

**Regex flags:**
- ✅ `(?i)` - `re.IGNORECASE` / `re.I`
- ✅ `(?s)` - `re.DOTALL` / `re.S`
- ✅ `(?x)` - `re.VERBOSE` / `re.X` (auto-converted to inline)
- ❌ Other flags not supported

**Result:**
```json
{
  "data": [
    {"text": "Quote 1", "author": "Author 1", "tags": ["tag1"]},
    {"text": "Quote 2", "author": "Author 2", "tags": ["tag2"]}
  ]
}
```

---

### 2.2 Using `@init` for Reuse

Extract JSON once, use multiple times:

```kdl
json Quote array=#true {
    text str
    author str
    tags (array)str
}

struct Main {
    @init {
        raw-json {
            raw
            re JSON-PATTERN
        }
    }
    
    all-quotes {
        @raw-json
        jsonify Quote
    }
    
    first-quote {
        @raw-json
        jsonify Quote path="0"
    }
    
    second-quote {
        @raw-json
        jsonify Quote path="1"
    }
}
```

**Key concepts:**
- `@init { ... }` - pre-computed values (calculated once)
- `@name` - reference pre-computed value from `@init`
- `jsonify Quote path="0"` - extract element by index

**Path navigation:**
- `path=""` - apply schema to full result
- `path="0"` - take first element (unwrap array)
- `path="field"` - navigate to object field
- `path="0.author"` - combination: `[0]["author"]`

**Result:**
```json
{
  "all_quotes": [...],
  "first_quote": {"text": "Quote 1", ...},
  "second_quote": {"text": "Quote 2", ...}
}
```

---

### 2.3 Deep Path Navigation

Extract nested field:

```kdl
json Author {
    name str
    slug str
}

json Quote array=#true {
    text str
    author Author
    tags (array)str
}

struct Main {
    @init {
        raw-json { raw; re JSON-PATTERN }
    }
    
    third-author-slug {
        @raw-json
        jsonify Quote path="2.author.slug"
    }
}
```

**Path:** `"2.author.slug"` → `json.loads()[2]["author"]["slug"]`

---

## Advanced: Filters & Predicates

**Source:** Social media links extractor

Extract only specific social links using predicates:

```kdl
struct SocialLinks type=flat {
    @split-doc {
        css-all "a[href]"
        match {
            attr-re "href" #"^https?://(www\.)?(twitter|facebook|instagram|linkedin)"#
        }
    }
    
    url {
        attr "href"
    }
}
```

**Key concepts:**
- `type=flat` - extract flat list (not objects)
- `match { ... }` - filter elements by predicates
- `attr-re "name" #"pattern"#` - attribute matches regex

**Common predicates:**
- `eq "value"` - equals
- `ne "value"` - not equals
- `starts "prefix"` - starts with
- `ends "suffix"` - ends with
- `contains "substring"` - contains
- `re #"pattern"#` - matches regex
- `has-attr "name"` - has attribute
- `attr-eq "name" "value"` - attribute equals
- `attr-re "name" #"pattern"#` - attribute matches regex
- `css "selector"` - has descendant matching CSS
- `xpath "query"` - has descendant matching XPath

**Multiple predicates (AND logic):**
```kdl
match {
    has-attr "href"
    attr-starts "href" "https"
    css ".verified"
}
```

**Result:**
```json
[
  "https://twitter.com/example",
  "https://facebook.com/example"
]
```

---

## Advanced: Custom Transforms

**Source:** Base64 decoding example

Define reusable transformations:

```kdl
transform to-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = str(b64decode({{PRV}}))"
    }
    js {
        import "const atob = require('atob')"
        code "{{NXT}} = atob({{PRV}})"
    }
}

struct Main {
    decoded-title {
        css "title"
        text
        transform to-base64
    }
}
```

**Key concepts:**
- `transform <name> accept=TYPE return=TYPE` - define custom function
- `py { ... }` - Python implementation
- `js { ... }` - JavaScript implementation
- `import "..."` - auto-added to generated code
- `code "..."` - transformation code
- `{{PRV}}` - previous value in pipeline
- `{{NXT}}` - next value (result)
- `accept` / `return` - type checking at compile-time

**Multiple language support:**
```bash
# Generate Python
ssc-kdl generate schema.kdl -t py-bs4

# Generate JavaScript
ssc-kdl generate schema.kdl -t js-pure
```

Both use the same DSL schema!

---

## Selector Backend Support

Different backends support different selectors:

| Backend | CSS Selectors | XPath | Notes |
|---------|---------------|-------|-------|
| `py-bs4` | ✅ CSS3/4 | ❌ | BeautifulSoup4 |
| `py-lxml` | ✅ CSS3/4 | ✅ | Faster than bs4 |
| `js-pure` | ✅ CSS3/4 | ✅ | Browser/Node.js |

**Best practice:** Use CSS3 selectors for maximum compatibility.

**TODO:** Expanded table when more backends available (selectolax, parsel, cheerio, etc.)

---

## Generating & Using Code

### Check Schema (Linting)

```bash
# Check syntax and types
ssc-kdl check schema.kdl

# Multiple files
ssc-kdl check schemas/

# JSON output for CI/CD
ssc-kdl check schema.kdl -f json
```

### Generate Code

```bash
# Generate Python (BeautifulSoup4)
ssc-kdl generate books.kdl -t py-bs4

# Generate Python (lxml - faster)
ssc-kdl generate books.kdl -t py-lxml

# Generate JavaScript
ssc-kdl generate books.kdl -t js-pure

# Output to specific directory
ssc-kdl generate books.kdl -t py-bs4 -o output/

# Process whole directory
ssc-kdl generate schemas/ -t py-bs4

# Skip linting (for debugging)
ssc-kdl generate books.kdl -t py-bs4 --skip-lint
```

**Use Generated Code

**Python:**
```python
from books import Book, MainCatalogue, MainCatalogueType  # ← Type included!
import requests

# Fetch HTML
response = requests.get('https://books.toscrape.com')
html = response.text

# Parse with type annotation
parser = MainCatalogue(html)
result: MainCatalogueType = parser.parse()

# IDE autocomplete and type checking work!
print(f"Found {result['total_books']} books")  # ✅ Type-checked
for book in result['books']:
    print(f"{book['name']}: £{book['price']}")  # ✅ Autocomplete
```

**Generated code is:**
- ✅ Self-contained (single module)
- ✅ **Type-annotated** (TypedDict for Python, interfaces for TypeScript)
- ✅ IDE-friendly (autocomplete, type checking)
- ✅ Ready to use
- ✅ No runtime dependencies on DSL

---

## Quick Reference

### Structure Types

```kdl
struct Item { ... }              // Single object
struct List type=list { ... }    // Array of objects
struct Flat type=flat { ... }    // Flat array [val1, val2]
struct Table type=table { ... }  // HTML table to object
struct Dict type=dict { ... }    // Key-value map
```

### Common Patterns

**Extract text:**
```kdl
field { css "selector"; text }
```

**Extract attribute:**
```kdl
field { css "selector"; attr "href" }
```

**Extract number:**
```kdl
field { css "selector"; text; re #"(\d+)"#; to-int }
```

**Extract from list:**
```kdl
-split-doc { css-all ".item" }
field { css ".title"; text }
```

**Filter list:**
```kdl
-split-doc {
    css-all "a"
    match { attr-starts "href" "https" }
}
```

**Pre-compute value:**
```kdl
@init {
    raw-json { raw; re PATTERN }
}
field { @raw-json; jsonify Schema }
```

**Nested structure:**
```kdl
field { nested OtherStruct }
```

**Custom transform:**
```kdl
transform my-func accept=STRING return=STRING {
    py {
        import "import something"
        code "{{NXT}} = process({{PRV}})"
    }
}
```

---

## Pipeline Flow

Every field is a **pipeline** of operations:

```
Selector → Extract → Transform → Convert → Result
```

**Example:**
```kdl
price {
    css ".price"        // DOCUMENT → DOCUMENT
    text                // DOCUMENT → STRING
    trim                // STRING → STRING
    re #"(\d+\.\d+)"#   // STRING → STRING
    to-float            // STRING → FLOAT
}
```

**Type checking:**
- Each operation has `accept` and `return` types
- Compiler verifies compatibility
- Errors caught before code generation

---

## Common Patterns & Tips

### 1. Cleaning HTML

Remove ads/scripts before extraction:
```kdl
content {
    css-remove ".ads"
    css-remove "script"
    css ".content"
    text
}
```

### 2. Handling Missing Elements

Use `fallback`:
```kdl
optional-field {
    css ".maybe-present"
    text
    fallback ""
}
```

### 3. Complex Regex

Use VERBOSE for readability:
```kdl
define COMPLEX=#"""
(?xs)
    start_anchor\s+     # Comment explaining
    (capture_group)     # What we want
    end_anchor
"""#
```

**Remember:** Only **one capture group** supported!

### 4. Multiple Values

Concatenate attributes:
```kdl
classes {
    css "div"
    attr "class" "data-extra"  // Joined with space
}
```

### 5. Conditional Extraction

Use `assert` to validate:
```kdl
in-stock {
    css ".availability"
    text
    assert { contains "In stock" }
    to-bool
    fallback #false
}
```

---

## Debugging Tips

### 1. Start Simple

Build incrementally:
```kdl
// Step 1: Just select
field { css "selector" }

// Step 2: Add extraction  
field { css "selector"; text }

// Step 3: Add transformations
field { css "selector"; text; trim; upper }
```

### 2. Use Linter

```bash
ssc-kdl check schema.kdl
```

Catches:
- Type mismatches
- Invalid operations
- Missing arguments
- Regex syntax errors

### 3. Test Generated Code

```python
parser = MyStruct(html)
result = parser.parse()
print(result)  # Inspect output
```

### 4. Check HTML Structure

Use browser DevTools to verify selectors work.

---

## Next Steps

**📖 Full Documentation:**
- [`syntax.md`](syntax.md) - Complete DSL syntax reference
- [`nodes.md`](nodes.md) - All AST nodes explained
- [`ops.md`](ops.md) - All operations with examples
- [`imp_converters.md`](imp_converters.md) - Converters & custom backends

**💡 More Examples:**
- `examples2/` - Real-world schemas
  - `booksToScrape.kdl` - E-commerce scraping
  - `quotesToScrape.kdl` - JSON extraction
  - `socialsExtractor.kdl` - Link filtering
  - `hackernews.kdl` - News aggregator
  - `imdbcom.kdl` - Movie database

**🛠 Advanced Topics:**
- Creating custom converters (`.extend()` API)
- Multi-file generation
- CI/CD integration

---

## Generated Type Annotations

**Every structure gets a TypedDict:**

```kdl
struct Book type=list {
    @split-doc { css-all ".book" }
    name { css ".title"; text }
    price { css ".price"; text; re #"(\d+)"#; to-float }
}
```

**Generated Python:**
```python
class BookType(TypedDict):
    name: str
    price: float

class Book:
    @staticmethod
    def _parse_item(v: Union[Tag, BeautifulSoup]) -> BookType:
        # Implementation...
```

**Benefits:**
- ✅ IDE autocomplete
- ✅ Type checking (mypy, pyright)
- ✅ Self-documenting code
- ✅ Refactoring safety

**JavaScript/TypeScript:**
```typescript
interface BookType {
    name: string;
    price: number;
}
```

---

## Summary

**You learned:**

✅ Why KDL Schema DSL (declarative, type-safe, multi-language, **auto-typed**)  
✅ Basic extraction (CSS selectors, text, attributes)  
✅ Lists and nested structures (`type=list`, `nested`)  
✅ JSON parsing (`jsonify`, path navigation)  
✅ Filters and predicates (`match`, `assert`)  
✅ Custom transforms (multi-language support)  
✅ Code generation and usage (**with TypedDict/interfaces**)

**Remember:**
- 🎯 Focus on *what* to extract, not *how*
- 🔍 Use CSS selectors for compatibility
- 📝 One regex capture group only
- ✅ Always `check` before `generate`
- 🚀 One DSL → multiple languages

**Happy scraping!** 🎉

