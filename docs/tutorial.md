# Tutorial: Writing Web Scrapers with KDL Schema DSL

> **Learn by example:** From simple extraction to advanced patterns

---

## Why KDL Schema DSL?

Traditional web scraping code quickly becomes imperative mess:

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
- **Declarative** - describe *what* to extract, not *how*
- **Type-safe** - compile-time checks catch errors early
- **Type-annotated** - generated code includes TypedDict/interfaces
- **Multi-language** - one DSL generates Python, JavaScript, etc.
- **Reusable** - compose structures, share defines across files

---

## Getting Started

### Step 1: Install

```bash
uv tool install git+https://github.com/vypivshiy/selector_schema_codegen@features-kdl
```

### Step 2: Your First Schema

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
ssc-gen generate simple.kdl -t py-bs4
```

**Use it:**
```python
from simple import Simple, SimpleType

html = "<html><head><title>Example Page</title></head></html>"
parser = Simple(html)
result: SimpleType = parser.parse()
# {'title': 'Example Page'}
```

---

## Example 1: Books Catalogue

**Source:** https://books.toscrape.com

### 1.1 Single Book

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
        re #"(\d+\.\d+)"#
        to-float
    }
}
```

**Key concepts:**
- `type=list` - extract multiple items
- `@split-doc` - split page into elements (one per book)
- `re #"pattern"#` - regex with **one capture group**
- `to-float` - type conversion

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
    price { css ".price_color"; text; re #"(\d+\.\d+)"#; to-float }

    rating {
        css ".star-rating"
        attr "class"
        rm-prefix "star-rating "
        REPL-RATING
        to-int
    }
}
```

**Result:**
```json
[{"name": "Product Name", "price": 51.77, "rating": 3}, ...]
```

---

### 1.3 Nested Structures

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
    title { css "h1"; text }
    product-info { nested ProductInfo }
}
```

---

### 1.4 Catalogue with Books

```kdl
struct Book type=list {
    @split-doc { css-all ".product_pod" }
    name { css "h3 a"; attr "title" }
    price { css ".price_color"; text; re #"(\d+\.\d+)"#; to-float }
}

struct MainCatalogue {
    title { css "h1"; text }
    books { nested Book }
    total-books { css-all ".product_pod"; len }
}
```

---

## Example 2: Quotes with JSON

**Source:** https://quotes.toscrape.com/js/

### 2.1 Extracting Embedded JSON

```kdl
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

json Quote array=#true {
    text str
    author str
    tags (array)str
}

struct Main {
    data {
        raw
        re JSON-PATTERN
        jsonify Quote
    }
}
```

**Key concepts:**
- `#"""..."""#` - raw string for multiline regex
- `(?xs)` - regex flags: VERBOSE + DOTALL (auto-converted to inline form)
- `json` - define JSON schema
- `jsonify` - deserialize JSON using schema

---

### 2.2 Using `@init` for Reuse

```kdl
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
}
```

**Path navigation:**
- `path=""` - full result
- `path="0"` - first element
- `path="0.author.slug"` - deep navigation

---

## Example 3: Filters & Predicates

Extract only specific social links:

```kdl
struct SocialLinks type=flat {
    @split-doc {
        css-all "a[href]"
        match {
            attr-re "href" #"^https?://(www\.)?(twitter|facebook|instagram)"#
        }
    }

    url { attr "href" }
}
```

**Common predicates:**

| Predicate | Description |
|-----------|-------------|
| `eq "value"` | Equals |
| `ne "value"` | Not equals |
| `starts "prefix"` | Starts with |
| `ends "suffix"` | Ends with |
| `contains "sub"` | Contains substring |
| `has-attr "name"` | Has attribute |
| `attr-eq "name" "value"` | Attribute equals |
| `attr-re "name" #"pat"#` | Attribute matches regex |
| `css "selector"` | Has descendant |
| `not { ... }` | Negate |
| `or { ... }` | OR logic |

Full predicates reference: [predicates.md](predicates.md)

---

## Example 4: Custom Transforms

### Using `transform` (multi-language)

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

### Using `dsl` + `expr` (single-language)

```kdl
dsl upper-py lang=py {
    code "{{NXT}} = {{PRV}}.upper()"
}

dsl decode-b64 lang=py accept=STRING return=STRING {
    import "from base64 import b64decode"
    code "{{NXT}} = b64decode({{PRV}}).decode()"
}

struct Main {
    title {
        css "title"
        text
        expr upper-py
    }
    encoded {
        css "#data"
        attr "data-encoded"
        expr decode-b64
    }
}
```

`dsl` is a simpler alternative to `transform` when you only need one language.

---

## Example 5: File Imports

Split schemas across multiple files:

**shared_defines.kdl:**
```kdl
define BASE-URL="https://example.com"
define FMT-URL="https://example.com/{{}}"
```

**shared_struct.kdl:**
```kdl
struct Header {
    title { css "h1"; text }
}
```

**main_schema.kdl:**
```kdl
import "./shared_defines.kdl"
import "./shared_struct.kdl"

struct Page {
    header { nested Header }
    link { css "a"; attr "href"; fmt FMT-URL }
}
```

---

## Selector Backend Support

| Backend | CSS | XPath | Notes |
|---------|-----|-------|-------|
| `py-bs4` | CSS3/4 | - | BeautifulSoup4 |
| `py-lxml` | CSS3/4 | XPath 1.0 | Fast |
| `py-parsel` | CSS3/4 | XPath 1.0 | Scrapy-based |
| `py-slax` | CSS3/4 | - | Selectolax |
| `js-pure` | CSS3/4 | XPath 1.0 | Browser/Node.js |

**Best practice:** Use CSS3 selectors for maximum compatibility.

---

## CLI Commands

### Check (Linting)

```bash
# Check syntax and types
ssc-gen check schema.kdl

# Multiple files / directory
ssc-gen check schemas/

# JSON output for CI/CD
ssc-gen check schema.kdl -f json
```

### Generate Code

```bash
# Generate Python (BeautifulSoup4)
ssc-gen generate schema.kdl -t py-bs4

# Output to specific directory
ssc-gen generate schema.kdl -t py-bs4 -o output/

# Process whole directory
ssc-gen generate schemas/ -t py-bs4
```

### Test Schema

```bash
# Test with HTML file
ssc-gen run schema.kdl:StructName -t py-bs4 -i page.html

# Test from stdin
curl https://example.com | ssc-gen run schema.kdl:StructName -t py-bs4

# Health check selectors
ssc-gen health schema.kdl:StructName -i page.html
```

---

## Quick Reference

### Structure Types

```kdl
struct Item { ... }              // Single object (default)
struct List type=list { ... }    // Array of objects
struct Flat type=flat { ... }    // Flat array [val1, val2]
struct Table type=table { ... }  // HTML table to object
struct Dict type=dict { ... }    // Key-value map
```

### Common Patterns

```kdl
// Text extraction
field { css "selector"; text }

// Attribute extraction
field { css "selector"; attr "href" }

// Number extraction
field { css "selector"; text; re #"(\d+)"#; to-int }

// List extraction
@split-doc { css-all ".item" }
field { css ".title"; text }

// Filter
filter { not { contains "spam" } }

// Pre-compute
@init { cached { raw; re PATTERN } }
field { @cached; jsonify Schema }

// Nested
field { nested OtherStruct }

// Optional (with fallback null)
field { css ".maybe"; text; fallback #null }
```

---

## Pipeline Flow

Every field is a **pipeline** of operations:

```
Selector -> Extract -> Transform -> Convert -> Result
```

Each operation has `accept` and `return` types. The compiler verifies compatibility.

Full type system documentation: [types.md](types.md)

---

## Debugging Tips

1. **Start simple** - build incrementally, one operation at a time
2. **Use linter** - `ssc-gen check schema.kdl` catches type errors, bad args, missing fields
3. **Test with `run`** - `ssc-gen run schema.kdl:Struct -t py-bs4 -i page.html`
4. **Check HTML** - use browser DevTools to verify selectors

---

## Next Steps

- [syntax.md](syntax.md) - Complete DSL syntax reference
- [operations.md](operations.md) - All operations with type signatures
- [predicates.md](predicates.md) - Predicates and logic containers
- [types.md](types.md) - Type system and pipeline type flow
- [imp_converters.md](imp_converters.md) - Implementing new backends
- `examples/` - Real-world schemas
