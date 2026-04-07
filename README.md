# ssc-codegen

Code generator for web scraping parsers. Describe HTML extraction rules in a declarative KDL 2.0 DSL, then generate ready-to-use parser code for multiple languages and libraries.

```
.kdl schema --> [tree-sitter parser] --> AST --> [linter] --> [converter] --> output code
```

## Features

- Declarative DSL based on KDL 2.0 syntax
- Static type checking and linting before code generation
- Multiple output targets: Python (bs4, lxml, parsel, selectolax), JavaScript (DOM API)
- Struct types: `item`, `list`, `dict`, `table`, `flat`
- LLM-friendly: system prompt + linter loop for AI-assisted schema generation

## Install

```bash
uv tool install git+https://github.com/vypivshiy/selector_schema_codegen@features-kdl
```

## Quick example

`books.kdl`:

```kdl
struct Book type=list {
    @split-doc { css-all ".product-card" }

    title { css ".title"; text }
    price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
    url   { css "a[href]"; attr "href"; fallback #null }
}
```

Generate Python parser:

```bash
ssc-gen generate books.kdl -t py-bs4 -o ./output
```

## Usage

### Generate code

```bash
# single file
ssc-gen generate schema.kdl -t py-bs4 -o ./output

# all .kdl files in a directory
ssc-gen generate examples/ -t js-pure -o ./output

# with custom package name (for Go and other targets)
ssc-gen generate schema.kdl -t go-goquery -o ./parsers --package scraper
```

Targets: `py-bs4`, `py-lxml`, `py-parsel`, `py-slax`, `js-pure`

### Lint schemas

```bash
# human-readable output
ssc-gen check schema.kdl

# JSON output (for LLM pipelines)
ssc-gen check schema.kdl -f json

# check all files in a directory
ssc-gen check examples/
```

### Test schema against HTML

```bash
# from file
ssc-gen run examples/booksToScrape.kdl:MainCatalogue -t py-bs4 -i page.html

# from stdin
curl https://books.toscrape.com/ | ssc-gen run examples/booksToScrape.kdl:MainCatalogue -t py-bs4
```

### Health check (verify selectors match elements)

```bash
# from file
ssc-gen health examples/booksToScrape.kdl:MainCatalogue -i page.html

# from stdin
curl https://books.toscrape.com/ | ssc-gen health examples/booksToScrape.kdl:MainCatalogue
```

## Documentation

- [Quick start](docs2/guide.md)
- [Syntax and file structure](docs2/syntax.md)
- [Type system](docs2/types.md)
- [Pipeline operations](docs2/operations.md)
- [Predicates and logic](docs2/predicates.md)
- [JSON schemas and jsonify](docs2/json.md)
- [Transforms and dsl blocks](docs2/transforms.md)
- [LLM-compact reference](docs2/llm.txt) -- full DSL spec in one file for LLM context
- [Examples](examples/)

## LLM integration

LLM agents can generate and validate `.kdl` schemas automatically using the linter feedback loop.

### In chats (ChatGPT, Claude, etc.)

Use [SYSTEM_PROMPT.md](SYSTEM_PROMPT.md) as system prompt. After generation, run `ssc-gen check -f json` and send errors back to the LLM for correction.

### In AI-powered IDEs (Claude Code, Cursor, etc.)

Use the [kdl-schema-dsl](.agents/skills/kdl-schema-dsl) skill for automatic generation, validation, and iteration.

## Development

```bash
uv sync                  # install dependencies
uv build --wheel         # build (compiles tree-sitter-kdl via hatch hook)
uv run pytest            # run tests
uv run ruff check ssc_codegen/
```
