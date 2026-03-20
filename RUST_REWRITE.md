# SSC-Codegen: Rust Rewrite Plan

## Motivation

- **WASM target** — интерактивный playground в браузере (KDL → код в реальном времени)
- **Единый бинарник** — дистрибуция без Python-зависимостей
- **Переиспользование** — одно ядро для CLI, WASM, PyO3-биндингов

---

## Architecture Overview

```
ssc-codegen-core (Rust library crate)
├── parser/          — KDL → AST (tree-sitter)
├── ast/             — AST node types
├── linter/          — Static analysis
├── converters/      — AST → code generation
│   ├── py_bs4.rs
│   ├── py_lxml.rs
│   ├── py_parsel.rs
│   ├── py_slax.rs
│   └── js_pure.rs
├── interpreter/     — AST walker для run/health (NEW)
└── lib.rs           — Public API

ssc-codegen-cli (Rust binary crate)
└── main.rs          — CLI (clap)

ssc-codegen-wasm (wasm-bindgen crate)
└── lib.rs           — JS API для playground
```

---

## Phase 0: Project Setup

- [ ] Cargo workspace: `core`, `cli`, `wasm`
- [ ] Подключить `tree-sitter` + `tree-sitter-kdl` (Rust crate)
- [ ] CI: GitHub Actions — build, test, wasm-pack

```toml
[workspace]
members = ["core", "cli", "wasm"]

[workspace.dependencies]
tree-sitter = "0.25"
tree-sitter-kdl = { path = "vendor/tree-sitter-kdl" }
```

---

## Phase 1: AST Types

Прямая трансляция Python dataclasses → Rust enums/structs.

### VariableType

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VariableType {
    Auto, ListAuto,
    Document, ListDocument,
    String, OptString, ListString,
    Int, OptInt, ListInt,
    Float, OptFloat, ListFloat,
    Bool, Null,
    Nested, Json,
}

impl VariableType {
    pub fn optional(self) -> Self { ... }
    pub fn is_list(self) -> bool { ... }
    pub fn scalar(self) -> Self { ... }
    pub fn as_list(self) -> Self { ... }
}
```

### StructType

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StructType {
    Item,   // Single object
    List,   // Array via @split-doc
    Dict,   // Key-value via @key/@value
    Table,  // Tabular data
    Flat,   // Flat string list
}
```

### AST Nodes

Использовать `enum` для полиморфизма вместо Python-наследования:

```rust
pub enum AstNode {
    // Module level
    Module(Module),
    Struct(Struct),
    TypeDef(TypeDef),
    JsonDef(JsonDef),
    TransformDef(TransformDef),

    // Struct level
    Field(Field),
    Init(Init),
    PreValidate(PreValidate),
    SplitDoc(SplitDoc),
    // ...

    // Expression level (pipeline ops)
    CssSelect(CssSelect),
    CssSelectAll(CssSelectAll),
    XpathSelect(XpathSelect),
    Text(Text),
    Attr(Attr),
    Trim(Trim),
    Re(Re),
    Fmt(Fmt),
    // ... (все ~50 типов операций)

    // Predicates
    Filter(Filter),
    Assert(Assert),
    PredEq(PredEq),
    PredContains(PredContains),
    // ...
}
```

**Mapping Python → Rust (ключевые ноды):**

| Python class | Rust struct | Поля |
|---|---|---|
| `Module` | `Module` | `body: Vec<AstNode>` |
| `Struct` | `Struct` | `name, struct_type, keep_order, body` |
| `Field` | `Field` | `name, accept, ret, body: Vec<AstNode>` |
| `JsonDef` | `JsonDef` | `name, is_array, body: Vec<JsonDefField>` |
| `JsonDefField` | `JsonDefField` | `name, ret, is_optional, is_array, ref_name, alias` |
| `TypeDef` | `TypeDef` | `name, struct_type, body: Vec<TypeDefField>` |
| `CssSelect` | `CssSelect` | `query: String` |
| `Fmt` | `Fmt` | `template: String` |
| `Re` | `Re` | `pattern: String` |
| `Fallback` | `Fallback` | `value: FallbackValue` |
| `Nested` | `Nested` | `struct_name: String, is_array: bool` |
| `Jsonify` | `Jsonify` | `schema_name, path, is_array` |
| `TransformDef` | `TransformDef` | `name, accept, ret, targets: Vec<TransformTarget>` |

**Сложность:** низкая — механическая трансляция, ~500 строк.

---

## Phase 2: KDL Parser (tree-sitter → AST)

### Tree-sitter Integration

```rust
use tree_sitter::{Parser, Language};

fn parse_kdl(source: &str) -> Result<KdlDocument, ParseError> {
    let mut parser = Parser::new();
    parser.set_language(&tree_sitter_kdl::LANGUAGE.into())?;
    let tree = parser.parse(source, None).ok_or(ParseError::TreeSitter)?;
    build_kdl_document(tree.root_node(), source)
}
```

### KDL Document → AST (двухпроходный парсер)

Паттерн: **registry of handlers** — в Rust через `HashMap<&str, fn>` или `match`:

```rust
impl AstParser {
    pub fn parse(&self, src: &str, path: Option<&Path>) -> Result<Module, ParseError> {
        let doc = parse_kdl(src)?;
        let mut ctx = ParseContext::new(path);

        // Pass 1: imports
        for node in &doc.nodes {
            if node.name == "import" {
                self.handle_import(node, &mut ctx)?;
            }
        }

        // Pass 2: defines, transforms, json, structs
        for node in &doc.nodes {
            match node.name.as_str() {
                "define" => self.handle_define(node, &mut ctx)?,
                "transform" => self.handle_transform(node, &mut ctx)?,
                "json" => self.handle_json(node, &mut ctx)?,
                "struct" => self.handle_struct(node, &mut ctx)?,
                "import" => {} // already handled
                _ => return Err(ParseError::UnknownKeyword(node.name.clone())),
            }
        }

        Ok(ctx.build_module())
    }
}
```

### ParseContext

```rust
pub struct ParseContext {
    pub property_defines: HashMap<String, Value>,
    pub children_defines: HashMap<String, Vec<KdlNode>>,
    pub transforms: HashMap<String, TransformDef>,
    pub structs: HashMap<String, Struct>,
    pub json_defs: HashMap<String, JsonDef>,
    pub source_path: Option<PathBuf>,
    pub import_registry: ImportRegistry,
}

pub struct ImportRegistry {
    in_progress: HashSet<PathBuf>,
    completed: HashMap<PathBuf, ParseContext>,
}
```

### Expression Parsing (pipeline)

```rust
fn parse_expression(
    &self,
    node: &KdlNode,
    parent_ret: VariableType,
    ctx: &ParseContext,
) -> Result<AstNode, ParseError> {
    match node.name.as_str() {
        "css" => Ok(AstNode::CssSelect(CssSelect { query: node.arg_str(0)? })),
        "css-all" => Ok(AstNode::CssSelectAll(CssSelectAll { query: node.arg_str(0)? })),
        "text" => Ok(AstNode::Text(Text)),
        "attr" => Ok(AstNode::Attr(Attr { keys: node.args_strings()? })),
        "trim" => Ok(AstNode::Trim(Trim { substr: node.arg_str_opt(0) })),
        "re" => Ok(AstNode::Re(Re { pattern: node.arg_str(0)? })),
        "fmt" => Ok(AstNode::Fmt(Fmt { template: node.arg_str(0)? })),
        "to-int" => Ok(AstNode::ToInt(ToInt)),
        "to-float" => Ok(AstNode::ToFloat(ToFloat)),
        "to-bool" => Ok(AstNode::ToBool(ToBool)),
        "fallback" => Ok(AstNode::Fallback(parse_fallback_value(node)?)),
        "jsonify" => self.parse_jsonify(node, ctx),
        "nested" => self.parse_nested(node, ctx),
        "filter" => self.parse_filter(node, ctx),
        "assert" => self.parse_assert(node, ctx),
        name if ctx.children_defines.contains_key(name) => {
            self.inline_define(name, ctx) // expand block define
        }
        _ => Err(ParseError::UnknownExpression(node.name.clone())),
    }
}
```

**Сложность:** средняя — самая большая часть (~1500 строк Python → ~2000 строк Rust).
Главная трудность — правильная трансляция type inference логики (accept/ret propagation).

---

## Phase 3: Code Generation (Converters)

### Converter Trait

Заменяет Python BaseConverter с callback-registry:

```rust
pub struct ConverterContext {
    pub index: usize,
    pub depth: usize,
    pub var_name: String,
    pub indent_char: String,
}

impl ConverterContext {
    pub fn prv(&self) -> String { ... }
    pub fn nxt(&self) -> String { ... }
    pub fn indent(&self) -> String { ... }
    pub fn advance(&self) -> Self { ... }
    pub fn deeper(&self) -> Self { ... }
}

pub trait Converter {
    fn convert(&self, module: &Module) -> String;

    // Per-node handlers (default impls where possible)
    fn emit_module(&self, node: &Module, ctx: &mut ConverterContext) -> Vec<String>;
    fn emit_struct(&self, node: &Struct, ctx: &mut ConverterContext) -> Vec<String>;
    fn emit_field(&self, node: &Field, ctx: &mut ConverterContext) -> Vec<String>;
    fn emit_css_select(&self, node: &CssSelect, ctx: &mut ConverterContext) -> Vec<String>;
    fn emit_text(&self, node: &Text, ctx: &mut ConverterContext) -> Vec<String>;
    // ... (~80 методов, по одному на тип ноды)
}
```

### Наследование конвертеров

Python `extend()` → Rust: базовый конвертер + trait override:

```rust
pub struct PyBs4Converter;
pub struct PyLxmlConverter;

impl Converter for PyBs4Converter {
    fn emit_css_select(&self, node: &CssSelect, ctx: &mut ConverterContext) -> Vec<String> {
        vec![format!("{}{}= {}.select_one(\"{}\")",
            ctx.indent(), ctx.nxt(), ctx.prv(), node.query)]
    }
    // ... все обработчики
}

impl Converter for PyLxmlConverter {
    fn emit_css_select(&self, node: &CssSelect, ctx: &mut ConverterContext) -> Vec<String> {
        vec![format!("{}{}= {}.cssselect(\"{}\")[0]",
            ctx.indent(), ctx.nxt(), ctx.prv(), node.query)]
    }
    // только переопределённые обработчики, остальные делегируют PyBs4
}
```

**Альтернатива** — enum dispatch вместо trait objects:

```rust
pub enum Target {
    PyBs4, PyLxml, PyParsel, PySlax, JsPure,
}

fn emit_css_select(target: Target, node: &CssSelect, ctx: &ConverterContext) -> Vec<String> {
    match target {
        Target::PyBs4 => vec![...],
        Target::PyLxml => vec![...],
        Target::PyParsel => vec![...],
        Target::PySlax => vec![...],
        Target::JsPure => vec![...],
    }
}
```

Enum dispatch проще для WASM (нет dyn, всё статическое).

**Сложность:** средняя-высокая — много строковой генерации, ~3000 строк.
Каждый конвертер ~600 строк Python → ~800 строк Rust (больше из-за `format!`).

---

## Phase 4: Linter

### Структура

```rust
pub struct Linter {
    navigator: NodeNavigator,
    errors: Vec<LintError>,
    path: PathTracker,
    metadata: ModuleMetadata,
}

pub struct LintError {
    pub code: ErrorCode,
    pub message: String,
    pub hint: String,
    pub path: String,
    pub severity: Severity,
    pub start_row: usize,
    pub start_col: usize,
}

pub struct LintResult {
    pub errors: Vec<LintError>,
    pub source: String,
    pub filepath: Option<PathBuf>,
}
```

### Правила

Tree-sitter обход → проверка keyword'ов, типов, структуры:

```rust
impl Linter {
    pub fn lint(&mut self, src: &str, path: Option<&Path>) -> LintResult {
        let tree = parse_tree_sitter(src);
        self.collect_imports(&tree, path);
        self.collect_defines(&tree);
        self.walk_module(&tree.root_node());
        LintResult { errors: self.errors.drain(..).collect(), ... }
    }

    fn walk_module(&mut self, node: &TSNode) { ... }
    fn walk_struct(&mut self, node: &TSNode) { ... }
    fn walk_field(&mut self, node: &TSNode) { ... }
    fn check_keyword(&mut self, name: &str, context: WalkContext) { ... }
    fn check_type_compat(&mut self, accept: VariableType, ret: VariableType) { ... }
}
```

**Сложность:** средняя — ~1000 строк, правила переносятся 1:1.

---

## Phase 5: AST Interpreter (run/health)

**Новый модуль** — вместо Python `exec()`.
Прямой обход AST с выполнением операций над HTML.

### Зависимости

```toml
[dependencies]
scraper = "0.22"      # CSS selectors (Servo-based)
sxd-document = "0.3"  # XPath
sxd-xpath = "0.4"
regex = "1"
```

### Interpreter

```rust
pub enum Value {
    Document(Html),
    Documents(Vec<Html>),
    String(String),
    Strings(Vec<String>),
    Int(i64),
    Float(f64),
    Bool(bool),
    Null,
    Json(serde_json::Value),
}

pub fn interpret_struct(
    struct_def: &Struct,
    html: &str,
    module: &Module,
) -> Result<serde_json::Value, RuntimeError> {
    let document = Html::parse_document(html);
    let mut fields = HashMap::new();

    for field in &struct_def.fields() {
        let result = eval_pipeline(&field.body, Value::Document(document.clone()))?;
        fields.insert(&field.name, result.to_json());
    }

    Ok(serde_json::Value::Object(fields))
}

fn eval_pipeline(ops: &[AstNode], input: Value) -> Result<Value, RuntimeError> {
    let mut current = input;
    for op in ops {
        current = eval_op(op, current)?;
    }
    Ok(current)
}

fn eval_op(op: &AstNode, value: Value) -> Result<Value, RuntimeError> {
    match op {
        AstNode::CssSelect(n) => css_select(&value, &n.query),
        AstNode::CssSelectAll(n) => css_select_all(&value, &n.query),
        AstNode::Text(_) => extract_text(&value),
        AstNode::Attr(n) => extract_attr(&value, &n.keys),
        AstNode::Trim(n) => trim_value(&value, n.substr.as_deref()),
        AstNode::Re(n) => regex_first(&value, &n.pattern),
        AstNode::Fmt(n) => format_value(&value, &n.template),
        AstNode::ToInt(_) => to_int(&value),
        AstNode::Fallback(n) => Ok(value), // handled in pipeline runner
        AstNode::Nested(n) => { /* recursive interpret_struct */ },
        AstNode::Jsonify(n) => json_parse(&value, &n.path),
        _ => Err(RuntimeError::UnsupportedOp),
    }
}
```

### Health Check

```rust
pub fn check_health(
    struct_def: &Struct,
    html: &str,
    module: &Module,
) -> HealthResult {
    let document = Html::parse_document(html);
    let mut checks = Vec::new();

    for (path, selector) in collect_selectors(struct_def) {
        let matches = match &selector {
            Selector::Css(q) => count_css(&document, q),
            Selector::Xpath(q) => count_xpath(&document, q),
        };
        checks.push(SelectorCheck {
            path, query: selector.query(),
            matches, status: if matches > 0 { "ok" } else { "fail" },
            ..
        });
    }

    HealthResult { struct_name: struct_def.name.clone(), checks }
}
```

**Сложность:** средняя — ~800 строк. Самая приятная часть — чистый Rust без строковой генерации.

---

## Phase 6: CLI

```toml
[dependencies]
clap = { version = "4", features = ["derive"] }
```

```rust
#[derive(Parser)]
#[command(name = "ssc-gen")]
enum Cli {
    Generate {
        schema: PathBuf,
        #[arg(short, long)]
        target: Target,
        #[arg(short, long)]
        output: Option<PathBuf>,
        #[arg(long)]
        skip_lint: bool,
    },
    Check {
        schema: PathBuf,
        #[arg(short, long, default_value = "text")]
        format: OutputFormat,
    },
    Run {
        scope: String, // "schema.kdl:StructName"
        #[arg(short, long)]
        input: Option<PathBuf>,
    },
    Health {
        scope: String,
        #[arg(short, long)]
        input: Option<PathBuf>,
        #[arg(short, long, default_value = "text")]
        format: OutputFormat,
    },
}
```

**Сложность:** низкая — ~200 строк, обёртка над core.

---

## Phase 7: WASM

```rust
// ssc-codegen-wasm/src/lib.rs
use wasm_bindgen::prelude::*;
use ssc_codegen_core::{parse, convert, lint, Target};

#[wasm_bindgen]
pub fn generate(kdl_source: &str, target: &str) -> Result<String, JsValue> {
    let target = Target::from_str(target).map_err(|e| JsValue::from_str(&e))?;
    let module = parse(kdl_source, None)?;
    Ok(convert(&module, target))
}

#[wasm_bindgen]
pub fn check(kdl_source: &str) -> Result<String, JsValue> {
    let result = lint(kdl_source, None);
    Ok(result.format_json())
}

#[wasm_bindgen]
pub fn run(kdl_source: &str, struct_name: &str, html: &str) -> Result<String, JsValue> {
    let module = parse(kdl_source, None)?;
    let result = interpret(&module, struct_name, html)?;
    Ok(serde_json::to_string(&result)?)
}
```

**Playground фронтенд:**
- Monaco Editor (KDL input + generated code output)
- HTML input panel для run/health
- Табы: py-bs4 | py-lxml | py-parsel | py-slax | js-pure
- Размер WASM бандла: ~300-500KB (gzip ~100-200KB)

**Сложность:** низкая — тонкая обёртка, основная работа в core.

---

## Summary

| Phase | Что | Строк (оценка) | Сложность |
|-------|-----|----------------|-----------|
| 0 | Project setup | ~50 | Низкая |
| 1 | AST types | ~500 | Низкая |
| 2 | KDL Parser | ~2000 | Средняя |
| 3 | Code generation | ~4000 | Средняя-Высокая |
| 4 | Linter | ~1000 | Средняя |
| 5 | Interpreter | ~800 | Средняя |
| 6 | CLI | ~200 | Низкая |
| 7 | WASM | ~100 + frontend | Низкая |

**Итого ядро: ~8500 строк Rust**

### Рекомендуемый порядок

```
Phase 1 (AST) → Phase 2 (Parser) → Phase 3 (Converters) → Phase 7 (WASM)
                                  ↘ Phase 4 (Linter)
                                  ↘ Phase 5 (Interpreter) → Phase 6 (CLI)
```

MVP для playground: **Phase 1 + 2 + 3 + 7** — парсинг KDL и кодогенерация в браузере.
CLI с run/health: добавить Phase 5 + 6.

### Критический путь к MVP (playground)

1. AST types — 1-2 дня
2. Parser — 3-5 дней
3. Один конвертер (py-bs4) — 2-3 дня
4. WASM binding — 1 день
5. Простой фронтенд — 1-2 дня

**MVP playground: ~2 недели**

Остальные конвертеры, линтер, интерпретатор — параллельно или после MVP.
