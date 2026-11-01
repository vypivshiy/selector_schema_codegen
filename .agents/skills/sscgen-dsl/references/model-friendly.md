# Model-Friendly DSL Workflow

Use this mode for models prone to KDL syntax mistakes or runaway retries.

## Safe Syntax

- Start with one self-contained `.kdl` file; declare helper `struct` and `json` schemas **above** callers (`E302`).
- Use ordinary quoted strings and one operation per line (or `;`-separated short pipelines).
- Never place a `//` single-line comment immediately after a `\` line continuation (`E000`/`E203`).
- Use CSS3 selectors (`:nth-child()`, `:nth-of-type()`, `:first-child`, `[attr^=...]`) inside `css` rather than `css-all` + `index` for DOM element selection.
- Ensure every `re` and `re-all` pipeline operation has **exactly 1** capturing group `(...)` (`E002`).
- In `json` blocks, use portable `snake_case` field names and map special/reserved wire keys via `from="..."` (`E403`), nesting single-use child objects and `(array)ItemModel { ... }` blocks inline.
- Treat CSS4 selectors, `xpath`, `import`, `define`, `extension`, and complex nested predicates as advanced syntax.

## Workflow & Repair Loop

1. Check CLI version if needed via `ssc-gen version` (subcommand — NEVER `ssc-gen --version`).
2. When HTML is available, run `ssc-gen scout -i page.html --discover -f json` first (never `Read` raw `.html`).
3. Write the smallest schema covering requested fields and run `ssc-gen check schema.kdl -f json`.
4. Fix one primary diagnostic at a time top-to-bottom; after two identical errors on the same line, switch syntax form.
5. Stop after 5 iterations on the same issue and report the minimal conflicting fragment.
