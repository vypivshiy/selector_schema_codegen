# Model-Friendly DSL Workflow

Use this mode for models likely to make KDL syntax mistakes.

## Safe Syntax

- Start with one self-contained file.
- Use simple names and one declaration per line.
- Use ordinary quoted strings first. `#"..."#` raw strings are supported, but mark them advanced.
- Use simple CSS3 selectors and simple regex with one capture group.
- Prefer `css`, `css-all`, `text`, `attr`, `raw`, `trim`, and basic casts.
- To select a specific DOM element, prefer CSS3 pseudo-selectors such as
  `:nth-child()`, `:nth-of-type()`, `:first-child`, and `:last-child` inside
  `css` rather than `css-all` followed by `index`; most HTML backends support
  these standard selectors more reliably.
- Use `index` for other pipeline collections after extraction, such as values
  produced by `split`, `re-all`, or `css-all` when CSS selection cannot express
  the required operation.
- Add advanced operations only after the minimal schema passes `ssc-gen check`.
- Treat CSS4 selectors, imports, defines, complex predicates, embedded JSON, and advanced regex as advanced syntax.
- Do not use `transform`: it is not a current ssc_codegen DSL operation.

## Workflow

1. If URL or HTML file is available, use `ssc-gen scout --discover -f json` to inspect structure. Scout is recommended, not required for schema validity.
2. Write smallest schema covering requested fields.
3. Run `ssc-gen check schema.kdl`.
4. Fix one first diagnostic at a time.
5. Run `ssc-gen generate` only when user names target/backend or asks to validate code generation.

Do not read or save confidential HTML/raw input merely to test a schema. Source testing is user's choice.

## Repair Mode

- Keep last known-good schema text.
- Never rewrite whole schema for one diagnostic.
- After each edit, run `ssc-gen check` again.
- After two identical errors, change syntax form instead of repeating edit.
- Stop after five iterations on the same issue and show minimal conflicting fragment.
- Never loop indefinitely on parser errors or a hanging `kdlquery` process.
