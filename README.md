# ssc-codegen

Code generator for web scraping parsers. Describe HTML extraction rules in a declarative KDL 2.0 DSL, then generate ready-to-use parser code for multiple languages and libraries.

```
.kdl schema --> [kdl parser] --> AST --> [linter] --> [converter] --> output code
```

## Features

- Declarative DSL based on KDL 2.0 syntax
- Static type checking and linting before code generation
- Multiple output targets: Python (bs4, lxml, parsel, selectolax), JavaScript (DOM API)
- Struct types: `item`, `list`, `dict`, `table`, `flat`
- LLM-friendly: system prompt + linter loop for AI-assisted schema generation

## Install

```bash
uv tool install ssc_codegen
```

## Quick example

`books.kdl`:

```kdl
(list)struct Book {
    @split-doc { css-all ".product-card" }

    title { css ".title"; text }
    price { css ".price"; text; re #"(\d+\.\d+)"#; to-float }
    url   { css "a[href]"; attr "href"; fallback #null }
}
```

Generate Python parser:

```bash
ssc-gen generate python books.kdl -L bs4 -o ./output
```

## Usage

### Generate code

```bash
# single file (Python + bs4)
ssc-gen generate python schema.kdl -L bs4 -o ./output

# all .kdl files in a directory (JavaScript)
ssc-gen generate js examples/ -o ./output

# Go (goquery + net/http)
ssc-gen generate go schema.kdl -o ./output

# Go package defaults to main; override explicitly when generating a library
ssc-gen generate go schema.kdl -o ./output --package scraper

# with custom package name
ssc-gen generate python schema.kdl -L bs4 -o ./parsers --package scraper

# with @request support (REST/HTTP codegen)
ssc-gen generate python schema.kdl -L bs4 -o ./out --http-client httpx

# extract helper functions into a separate runtime module
ssc-gen generate python schema.kdl -L bs4 -o ./out -R
```

Languages: `generate python`, `generate js`, `generate go`.
HTML libraries (`--lib / -L`, Python only): `bs4` (default), `lxml`, `parsel`, `slax`.

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
ssc-gen run examples/booksToScrape.kdl:MainCatalogue -L bs4 -i page.html

# from stdin
curl https://books.toscrape.com/ | ssc-gen run examples/booksToScrape.kdl:MainCatalogue -L bs4
```

`ssc-gen run` executes generated Python in-process. Run only trusted schema files.

### Health check (verify selectors match elements)

```bash
# from file
ssc-gen health examples/booksToScrape.kdl:MainCatalogue -i page.html

# from stdin
curl https://books.toscrape.com/ | ssc-gen health examples/booksToScrape.kdl:MainCatalogue
```

## Documentation

- [Quick start](docs/guide.md)
- [Syntax and file structure](docs/syntax.md)
- [Type system](docs/types.md)
- [Pipeline operations](docs/operations.md)
- [Predicates and logic](docs/predicates.md)
- [JSON schemas and jsonify](docs/json.md)
- [@request — HTTP constructor + REST clients](docs/learn/10-request.md)
- [LLM-compact reference](docs/llm.txt) -- full DSL spec in one file for LLM context
- [Examples](examples/)

## LLM integration

LLM agents can generate and validate `.kdl` schemas automatically using the
linter feedback loop.

### In chats (ChatGPT, Claude, etc.)

Use [SYSTEM_PROMPT.md](SYSTEM_PROMPT.md) as system prompt. After generation,
run `ssc-gen check -f json` and send errors back to the LLM for correction.

### In AI-powered IDEs (Claude Code, Cursor, opencode, etc.)

Use the skills under [.agents/skills/](.agents/skills/):

- **`sscgen-dsl`** — HTML scraping schemas (`css`, `text`, `(item)struct`,
  `(list)struct`, `(table)struct`, predicates, `jsonify`).
- **`sscgen-rest`** — REST/JSON API clients (`(rest)struct`, `@request`,
  `@error`, typed placeholders).
- **`sscgen-openapi`** — convert OpenAPI/Swagger specs into `.kdl`.

## Development

```bash
uv sync                  # install dependencies
uv build --wheel         # build wheel
uv run pytest            # run tests
uv run ruff check ssc_codegen/
```

### Test dependencies

Python tests require only `uv sync`. JS integration tests additionally need:

```bash
npm install      # installs jsdom (dev dependency in package.json)
```

Node.js must be installed and available as `node` in PATH. JS tests are automatically skipped if Node.js is not found.
```
