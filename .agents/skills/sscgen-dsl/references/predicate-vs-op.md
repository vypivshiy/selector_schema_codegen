# Predicate vs Pipeline Op Disambiguation (DSL v2.1)

Several DSL keywords act as **pipeline operations** (transforming values) at the top level of a field body, and as **boolean predicates** inside `assert {}`, `filter {}`, or `match {}` blocks.

## Dual-Purpose Keywords

| Keyword | As Pipeline Op (top-level field body) | As Predicate (inside `assert` / `filter` / `match`) |
|---|---|---|
| `re #"pat"#` | `STR -> STR`, `STR[] -> STR[]` — **requires exactly 1** capture group `(...)` (`E002`) | `STR -> BOOL` — 0 capture groups required (`re.search` match check) |
| `re-all #"pat"#` | `STR -> STR[]` — **requires exactly 1** capture group `(...)` (`E002`) | `STR[] -> BOOL` (**`assert` only**, `E203` elsewhere) — true iff **every** list item matches |
| `re-any #"pat"#` | *Not a pipeline op* (`E200`) | `STR[] -> BOOL` (**`assert` only**, `E203` elsewhere) — true iff **at least one** list item matches |
| `re-sub #"pat"# "r"` | `STR -> STR`, `STR[] -> STR[]` — replaces matches (0+ groups) | *Not a predicate* (`E203`) |
| `css "<sel>"` | `DOC -> DOC` — selects first matching descendant | `DOC -> BOOL` (**`filter` / `assert` only**) — true if element has matching descendant |
| `xpath "<sel>"` | `DOC -> DOC` — selects first XPath match | `DOC -> BOOL` (**`filter` / `assert` only**) — true if element has XPath match |

## Side-by-Side Example

```kdl
struct ProductCard {
    // Pipeline ops: transform DOC -> STR -> INT
    code {
        css ".sku"
        text
        re #"SKU-(\d+)"#          // pipeline op: 1 capture group required
        to-int
    }

    // Predicates inside filter {} and assert {}: return BOOL (0 capture groups required)
    tags {
        css-all "a.tag"
        filter {
            has-attr "href"
            not { css ".deprecated" }
        }
        text
        assert {
            len-gt 0
            re-all #"^[a-z0-9-]+$"#
        }
        fallback {}
    }
}
```
