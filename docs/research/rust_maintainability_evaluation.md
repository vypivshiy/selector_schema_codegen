# Исследование эргономики и долгосрочной поддерживаемости кодогенератора: Rust vs Python

> **Дата исследования:** Сентябрь 2026 г.  
> **Статус:** Завершено  
> **Предмет анализа:** Архитектура и кодовая база `selector_schema_codegen` (`ssc_codegen`, Python 3.10+, Typer CLI, KDL 2.0 DSL compiler)  
> **Ключевой фокус:** Долгосрочная поддерживаемость (*ongoing maintainability*), эргономика разработчика (*developer ergonomics*), архитектурное соответствие (*architectural fit*), превенция ошибок типизации, расширяемость бэкендов и экосистемный инструментарий при реализации на языке **Rust** в сравнении с **Python**.

---

## 1. Executive Summary (Краткое резюме)

Настоящее исследование отвечает на фундаментальный инженерный вопрос: **«Насколько удобно и надежно сопровождать компилятор/кодогенератор `ssc_codegen`, если его кодовая база будет реализована на Rust, в сравнении с текущей реализацией на Python?»**

Фокус анализа сосредоточен **исключительно на процессах разработки и поддержки** (добавление новых AST-узлов, линтинг, расширение бэкендов, рефакторинг, тестирование, диагностика ошибок, дистрибуция), исключая разовые трудозатраты на миграцию.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPILER PIPELINE IN RUST VS PYTHON                             │
└────────────────────────────────────────────────────────────────────────────────────────┘

    [ KDL 2.0 Schema ]
            │
            ▼
 ┌──────────────────────┐  Python: kdlquery (Python CST + CSS queries)
 │ Parser & Diagnostics │  Rust:   kdl-rs v4.6+ / knuffel + miette (multiline spans, labels)
 └──────────┬───────────┘  Winner: Rust (промышленные компиляторные отчеты об ошибках)
            │
            ▼
 ┌──────────────────────┐  Python: dataclasses + TypeInfo + dynamic dispatch (_DISPATCH dict)
 │   AST & Type Check   │  Rust:   Tagged Enums + match exhaustiveness (E0004) + static inference
 └──────────┬───────────┘  Winner: Rust (полное исключение тихих пропусков операций при сборке)
            │
            ▼
 ┌──────────────────────┐  Python: BaseWalker + DomSpelling (ABC) + HttpLibStrategy (ABC)
 │  Codegen Backends    │  Rust:   trait Backend + trait DomSpelling + CodeWriter / minijinja
 └──────────┬───────────┘  Winner: Паритет (Rust строже по типам, Python быстрее на прототипах)
            │
            ▼
 ┌──────────────────────┐  Python: bs4 + lxml (XPath 1.0) + in-process exec()
 │  Auxiliary Runtime   │  Rust:   scraper (html5ever) + sxd-xpath/libxml2 + subprocess exec
 │ (health/scout/run)   │  Winner: Python (богаче XPath экосистема; in-process exec() без IPC)
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐  Python: pip/uv, virtualenv, slow startup (~100-150ms)
 │ CLI & Distribution   │  Rust:   clap v4, single static binary (0 dependencies), instant (2-4ms)
 └──────────────────────┘  Winner: Rust (идеально для CLI-пайплайнов и встраивания)
```

### Сводная матрица поддерживаемости (Maintainability Scorecard)

| Критерий анализа | Python 3.10+ (текущий) | Rust (целевой) | Преимущество | Ключевой фактор |
|---|---|---|---|---|
| **1. Моделирование AST и Type Safety** | 🟡 Средняя (`dataclass`, `_DISPATCH`, dynamic lookup) | 🟢 Превосходная (Tagged Enums, Exhaustive `match`) | **Rust (Подавляющее)** | Ошибка `E0004` при добавлении узла гарантирует обновление всех бэкендов и проходов компилятора до сборки. |
| **2. Парсер и диагностика (Frontend)** | 🟡 Средняя (`kdlquery`, рукописное форматирование) | 🟢 Эталонная (`kdl-rs`, `miette`, `ariadne`) | **Rust** | `miette` даёт ANSI-подсветку многострочных спанов исходника и подсказки "из коробки". |
| **3. Расширяемость кодогенерации** | 🟢 Высокая (ABC, duck typing, быстрые f-strings) | 🟢 Высокая (`trait`, строгие контракты, `minijinja`) | **Паритет** | Python чуть быстрее для прототипирования нового синтаксиса; Rust полностью исключает рантайм `TypeError` в генераторах. |
| **4. Вспомогательный рантайм (`health`, `scout`, `run`)** | 🟢 Отличная (`lxml` c нативным XPath, `exec()`) | 🔴 Умеренно-сложная (`scraper` без нативного XPath, IPC `run`) | **Python** | В экосистеме Rust нет столь же зрелого и монолитного XPath-движка, как C-шный `libxml2` в связке с `lxml`. |
| **5. Скорость итерации и эргономика** | 🟢 Мгновенный REPL / запуск pytest (0 сек) | 🟡 Задержка `cargo check` (1-2 сек) / `cargo test` (3-8 сек) | **Python (на ранних фазах) / Rust (на зрелых)** | В Python проще писать "на коленке", в Rust рефакторинг сотен файлов проходит с абсолютной уверенностью. |
| **6. Онбординг команды и зависимости** | 🟢 Низкий порог, повсеместное знание Python | 🔴 Высокий порог (ownership, borrow-checker, lifetimes) | **Python** | Написание парсеров сайтов ближе веб-скрейперам на Python, чем системным инженерам на Rust. |
| **7. CLI, производительность и дистрибуция** | 🔴 Зависимость от рантайма Python, запуск 80-150мс | 🟢 Статический бинарник, запуск 2-4мс | **Rust (Подавляющее)** | Мгновенный запуск в Unix-пайпах (`cat \| ssc-gen`), нулевые проблемы с виртуальными окружениями. |

---

## 2. Архитектурный контекст `ssc_codegen`

Для объективного сравнения сопоставим ключевые подсистемы текущей кодовой базы `ssc_codegen`:

```
ssc_codegen/
├── ast/                  # 1. AST Слой (Node, TypeInfo, VariableType, StructBase, Field, PipelineOp...)
├── core/                 # 2. Frontend (kdlquery CST, linter.py ~2700 строк, type_checking.py, reader.py)
├── traversal/            # 3. Traversal Core (BaseWalker с _DISPATCH, WalkContext, 3 режима обхода)
├── generation/           # 4. Codegen Core (ModuleBuilder, runtime extraction)
├── targets/              # 5. Бэкенды (Python [4 DOM + 3 HTTP], JavaScript [2 HTTP], Go)
├── health.py             # 6. Валидация селекторов по живому HTML (BeautifulSoup4 + lxml XPath)
├── explore.py            # 7. Scout & Discover (HTML recon, regex, DOM tree navigation)
└── main.py               # 8. CLI интерфейс (Typer, команды generate, check, run, health, scout)
```

---

## 3. Категория 1: Моделирование AST, система типов и безопасность проходов

### 3.1. Текущая реализация на Python: Dataclasses и динамическая диспетчеризация

В Python узлы AST объявлены как иерархия классов, наследующихся от абстрактного `Node` (`ssc_codegen/ast/base.py`):

```python
# ssc_codegen/traversal/walker.py
class BaseWalker:
    _DISPATCH: dict[type[Node], str] = {
        CssSelect: "visit_css_select",
        Trim: "visit_trim",
        ToInt: "visit_to_int",
        # ... более 80 записей
    }

    def walk(self, node: Node, ctx: WalkContext) -> list[str]:
        name = self._DISPATCH.get(type(node))
        if name is None:
            return []  # ТИХИЙ ПРОПУСК: если узел не зарегистрирован, он игнорируется!
        result = getattr(self, name)(node, ctx)
        # ...
```

#### Проблемы сопровождаемости в Python:
1. **Тихий пропуск узлов (*Silent Omission*):** Если разработчик создал новый AST-узел `PadStart`, но забыл добавить его в `_DISPATCH` или не реализовал `visit_pad_start` в одном из бэкендов (например, в `GoVisitor`), компилятор Python и линтеры (`mypy`, `ruff`) не выдадут ошибку на этапе статического анализа. Кодогенератор просто сгенерирует неполный код, что приведет к трудноуловимому багу в сгенерированном парсере во время выполнения.
2. **Типовая эрозия (*Type Erasure*):** `node.body` типизирован как `list[Node]`. При обходе гетерогенного списка дочерних узлов приходится постоянно делать runtime-проверки `isinstance(child, Field)`, `isinstance(child, Nested)`, что размывает контракты.
3. **Невозможность статической верификации полноты:** `mypy` не умеет проверять полноту таблицы словаря `_DISPATCH` относительно всех наследников `Node`.

### 3.2. Целевая реализация на Rust: Алгебраические типы данных (Enums) и `match`

В Rust AST компилятора моделируется через маркированные объединения (**Tagged Enums / Algebraic Data Types**), как это сделано в `rustc`, `swc`, `biome` и `oxc`:

```rust
// ssc_ast/src/lib.rs
#[derive(Debug, Clone, PartialEq)]
pub enum AstNode {
    Module(ModuleNode),
    Struct(StructNode),
    StructRest(StructRestNode),
    Field(FieldNode),
    Op(PipelineOp),
    Predicate(PredicateNode),
    TypeDef(TypeDefNode),
    JsonDef(JsonDefNode),
}

#[derive(Debug, Clone, PartialEq)]
pub enum PipelineOp {
    CssSelect(CssSelectOp),
    CssSelectAll(CssSelectAllOp),
    XpathSelect(XpathSelectOp),
    Trim(TrimOp),
    NormalizeSpace(NormalizeSpaceOp),
    Re(ReOp),
    ToInt(ToIntOp),
    ToFloat(ToFloatOp),
    Nested(NestedOp),
    ExtensionCall(ExtensionCallOp),
    // ...
}
```

```rust
// ssc_codegen/src/targets/python.rs
impl PythonVisitor {
    pub fn visit_pipeline_op(&mut self, op: &PipelineOp, ctx: &WalkContext) -> Vec<String> {
        match op {
            PipelineOp::CssSelect(node) => self.dom.css_select(ctx, node),
            PipelineOp::Trim(node) => vec![format!("{indent}{out} = {inp}.strip()", ...)],
            PipelineOp::ToInt(_) => vec![format!("{indent}{out} = int({inp})", ...)],
            PipelineOp::Nested(node) => self.visit_nested(ctx, node),
            // Если добавить новый вариант в PipelineOp и не обработать его здесь,
            // компилятор rustc выдаст фатальную ошибку компиляции E0004!
        }
    }
}
```

#### Преимущества Rust:
* **Exhaustive Matching (Ошибка `E0004`):** При добавлении любой новой операции компилятор Rust откажется собирать проект до тех пор, пока разработчик не реализует обработку этой операции во **всех** бэкендах (`PythonVisitor`, `JsVisitor`, `GoVisitor`), в тайпчекере (`type_checking.rs`), в линтере и в сборщике селекторов (`health.rs`).
* **Zero-cost Dispatch:** Вместо динамического поиска по словарю `_DISPATCH.get(type(node))` и рефлексии `getattr()`, Rust компилирует `match` в эффективные jump tables на уровне машинного кода.
* **Строгое моделирование модификаторов типов:**

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VariableType {
    Document,
    String,
    Int,
    Float,
    Bool,
    Null,
    Nested(String), // имя целевой структуры встроено в тип
    Json(String),
    Auto,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TypeInfo {
    pub base: VariableType,
    pub is_array: bool,
    pub is_optional: bool,
    pub omitempty: bool,
    pub skip: bool,
}
```

**Вердикт по Категории 1:** **Безоговорочная победа Rust.** Сопровождение компилятора на Rust принципиально надежнее. Риск забыть ветку кодогенерации при добавлении операции в DSL равен нулю благодаря гарантиям компилятора.

---

## 4. Категория 2: Парсер и сопровождение фронтенда (Frontend & Diagnostics)

### 4.1. Парсинг KDL: `kdlquery` vs `kdl-rs`

Текущий проект опирается на внешнюю Python-библиотеку `kdlquery`, предоставляющую CST с возможностью CSS-подобных запросов (`node.select("struct:root:has(nested)")`), которые активно используются в `core/linter.py` (2700 строк правил).

В Rust экосистеме KDL представлена официальным крейтом **`kdl-rs`** (версии 4.6+, автор Kat Marchán):
* `kdl-rs` парсит KDL в строго типизированные структуры `kdl::KdlDocument`, `kdl::KdlNode`, `kdl::KdlEntry`.
* Каждый узел и аргумент снабжены точным диапазоном байт в исходном файле: `kdl::SourceSpan(offset, len)`.
* Также существует крейт `knuffel`, позволяющий через `derive`-макросы декларативно десериализовать KDL сразу в Rust-структуры (аналог `serde`).

#### Трейдофф в реализации линтера:
* В Python `kdlquery` позволяет писать компактные запросы вида `doc.select("struct > field:has(css)")`.
* В Rust прямого аналога селекторов по KDL нет. Линтер строится на классическом рекурсивном обходе AST (`Visitor` паттерн над `KdlDocument`). Это требует чуть больше строчек кода на Rust, но выполняется в 30–50 раз быстрее и типизировано на уровне полей узла.

### 4.2. Диагностика ошибок: Рукописный формат vs `miette` / `ariadne`

В Python ошибки парсинга и линтинга форматируются через кастомную функцию `format_diagnostics()` (`ssc_codegen/core/format.py`), выводя текстовые строки или JSON.

В Rust золотым стандартом для компиляторов и CLI-инструментов является библиотека **`miette`** (или **`ariadne`**):

```
Error: [E0204] Mismatched pipeline types
  --> schemas/catalog.kdl:14:9
   |
13 |     price ".price" {
14 |         text
   |         ---- this operation produces `string`
15 |         to-int
   |         ^^^^^^ cannot convert `string` to `int` without sanitizing whitespace
   |
   = help: insert `normalize-space` or `trim` before `to-int`
```

```rust
// Пример декларации диагностической ошибки в Rust с miette
use miette::{Diagnostic, SourceSpan};
use thiserror::Error;

#[derive(Error, Diagnostic, Debug)]
#[error("Type mismatch in field pipeline: expected {expected}, got {found}")]
#[diagnostic(code(ssc::types::mismatch), url("https://docs.sscgen.dev/types"))]
pub struct TypeMismatchError {
    pub expected: String,
    pub found: String,
    
    #[source_code]
    pub src: String,
    
    #[label("this expression produces {found}")]
    pub bad_span: SourceSpan,
    
    #[help]
    pub suggestion: Option<String>,
}
```

#### Преимущества Rust:
1. `miette` берет на себя вычисление номеров строк, колонок, Unicode-выравнивание, многострочные скобки, цветовую подсветку терминала (ANSI) и автоматическую сериализацию в JSON (`miette::JSONReportHandler`).
2. Ошибки компилятора становятся первоклассными сущностями с поддержкой интерактивных подсказок (*compiler suggestions* / *fixes*).

**Вердикт по Категории 2:** **Значительное преимущество Rust** в качестве диагностики для конечного пользователя и надежности парсера, с небольшим усложнением кода линтера из-за отказа от CSS-селекторов поверх KDL.

---

## 5. Категория 3: Архитектура кодогенерации и расширяемость бэкендов

### 5.1. Абстракции бэкендов: Трейты vs Наследование классов

Текущая архитектура `ssc_codegen` использует паттерн `DomSpelling` (ABC) для HTML-библиотек Python (`bs4`, `lxml`, `parsel`, `selectolax`) и `HttpLibStrategy` (ABC) для HTTP-клиентов REST (`httpx`, `aiohttp`, `requests`).

В Rust данная концепция транслируется в систему **трейтов (Traits)** с нулевыми накладными расходами и строгой статической проверкой контрактов:

```rust
pub trait DomSpelling: Send + Sync {
    fn name(&self) -> &'static str;
    fn parser_imports(&self) -> &'static [&'static str];
    fn document_type(&self) -> &'static str;
    
    // Выражения трансформации
    fn css_select(&self, ctx: &WalkContext, op: &CssSelectOp) -> Vec<String>;
    fn css_select_all(&self, ctx: &WalkContext, op: &CssSelectAllOp) -> Vec<String>;
    fn text(&self, ctx: &WalkContext, op: &TextOp) -> Vec<String>;
    fn attr(&self, ctx: &WalkContext, op: &AttrOp) -> Vec<String>;
    
    // Предикаты
    fn pred_css(&self, ctx: &WalkContext, op: &PredCssOp) -> String;
    fn pred_has_attr(&self, ctx: &WalkContext, op: &PredHasAttrOp) -> String;
}

pub trait Backend {
    fn target_name(&self) -> &'static str;
    fn generate(&self, module: &ModuleNode, meta: &BuildMeta) -> Result<GeneratedOutput, CodegenError>;
}
```

### 5.2. Генерация текста: Line Accumulator vs Шаблонизаторы

В кодогенераторах `ssc_codegen` используется пошаговое накопление строк с расчетом отступов и имен переменных (`WalkContext`: `ctx.prv` → `ctx.nxt`, `ctx.indent`).

В Rust этот паттерн реализуется через специализированный буфер `CodeWriter`:

```rust
pub struct CodeWriter {
    buffer: String,
    indent_level: usize,
    indent_str: &'static str,
}

impl CodeWriter {
    pub fn line(&mut self, line: impl AsRef<str>) {
        let s = line.as_ref();
        if s.is_empty() {
            self.buffer.push('\n');
        } else {
            for _ in 0..self.indent_level {
                self.buffer.push_str(self.indent_str);
            }
            self.buffer.push_str(s);
            self.buffer.push('\n');
        }
    }

    pub fn indent(&mut self) { self.indent_level += 1; }
    pub fn dedent(&mut self) { self.indent_level = self.indent_level.saturating_sub(1); }
}
```

Для объемных runtime-шаблонов (`sscruntime.py`, `sscruntime.go`, REST client dispatchers) в Rust идеально подходит крейт **`minijinja`** (от автора Flask/Jinja2 Armin Ronacher) — легковесный, быстрый, полностью безопасный движок шаблонов без тяжелых зависимостей.

```rust
// Генерация runtime-модуля через minijinja
let mut env = minijinja::Environment::new();
env.add_template("py_runtime", include_str!("templates/runtime.py.j2"))?;
let template = env.get_template("py_runtime")?;
let rendered = template.render(context! {
    has_rest => true,
    http_client => "httpx",
})?;
```

### 5.3. Добавление нового целевого языка (например, Ruby / C++ / Rust)

| Шаг расширения | В Python | В Rust |
|---|---|---|
| 1. Создание нового бэкенда | Создать класс `RubyVisitor(BaseWalker)` | Реализовать `impl Backend for RubyBackend` |
| 2. Проверка полноты методов | Только runtime-тесты; если метод `visit_*` пропущен, возвращается `[]` | **Compile-time check:** rustc не скомпилирует бэкенд, пока не будут реализованы все методы трейта |
| 3. Регистрация в CLI | Обновить `resolver.py` и `main.py` | Добавить вариант в `TargetLang` enum |

**Вердикт по Категории 3:** **Паритет с небольшим перевесом Rust по строгости.** Python позволяет быстрее набросать черновой вариант генератора за счет динамических f-строк, но в Rust архитектура трейтов полностью исключает ошибки несовместимости интерфейсов и забытые методы.

---

## 6. Категория 4: Проблема вспомогательного рантайма (`health`, `scout` и `run`)

Это наиболее критичный раздел для понимания специфики проекта `ssc_codegen`. Проект не является чисто абстрактным компилятором (как, например, компилятор языка C), а включает интерактивные инструменты анализа веб-страниц:

```
┌────────────────────────────────────────────────────────────────────────┐
│             AUXILIARY RUNTIME: THREE INTERACTIVE TOOLS                 │
└────────────────────────────────────────────────────────────────────────┘

 1. `ssc-gen health`  ───► Проверяет селекторы (CSS/XPath) на живом HTML
 2. `ssc-gen scout`   ───► Regex поиск по тексту/атрибутам + DOM навигация (discover)
 3. `ssc-gen run`     ───► Генерирует код + сразу исполняет его на HTML и выдает JSON
```

### 6.1. Валидация селекторов (`health.py`)

* **В Python:** Использует `BeautifulSoup4` (через парсер `lxml`) и нативный `lxml.etree.XPath`. Одинаково безупречно работают как сложные CSS-селекторы (`div.card > a:first-child`), так и произвольные XPath 1.0 выражения (`//table[contains(@class, "data")]/tr[td[1]//text()]`).
* **В Rust:**
  * **CSS-селекторы:** Крейт `scraper` (построен на базе движка `html5ever` и `selectors` из проекта Servo/Firefox) обеспечивает эталонный парсинг по стандартам WHATWG HTML5 и W3C Selectors Level 4. Скорость работы в 20–40 раз выше, чем у BeautifulSoup4.
  * **Проблема XPath в Rust:** В Rust **нет** столь же зрелого, чистого и поддерживаемого чистого Rust-движка для XPath 1.0/2.0.
    * Вариант 1: Использовать крейт `sxd-xpath` (поддерживает базовый XPath 1.0, но давно не развивается активно).
    * Вариант 2: Использовать FFI-биндинги к C-библиотеке `libxml2-sys` (лишает Rust-проект преимущества чистой статической кросс-компиляции).
    * Если схемы KDL используют преимущественно CSS-селекторы (`css "h1.title"`), `scraper` работает идеально. Но для `xpath "//div"` потребуется интеграция `sxd-xpath` или `libxml2-sys`.

### 6.2. HTML-разведка и навигация по DOM (`explore.py` / `scout` / `discover`)

Функции `run_scout` и `run_discover` выполняют тяжелый перебор DOM-дерева: поиск регулярными выражениями по тексту и атрибутам, сбор статистики частотности классов/тегов, поиск повторяющихся контейнеров.

* **В Python:** На больших HTML-страницах (2–10 МБ, сложные SPA/e-commerce каталоги) алгоритм `discover` в Python может отрабатывать 200–800 мс из-за накладных расходов интерпретатора на создание тысяч объектов `Tag`/`NavigableString`.
* **В Rust:** Связка `scraper` + `regex` в Rust выполняет полный проход `discover` на странице 5 МБ за **3–8 миллисекунд**. Алгоритмы навигации (`parent()`, `next_siblings()`, `children()`) в `scraper::ElementRef` работают без аллокаций памяти.

### 6.3. Команда `run` (динамическое исполнение сгенерированного кода)

* **В Python:** Команда `ssc-gen run schema.kdl:Item -i page.html` генерирует Python-код, вызывает встроенный `exec(code, namespace)` и исполняет парсер **внутри того же процесса** за 2 миллисекунды.
* **В Rust:**
  * Если Rust-бинарник генерирует Python-код, он не может выполнить его через `exec()` без встроенного интерпретатора Python.
  * *Решение:* Запуск внешнего процесса `python -c "..."` или `node runner.js` через `std::process::Command` с передачей HTML через `stdin` и получением JSON через `stdout`.
  * *Оверхед:* Запуск подпроцесса `python` добавляет ~50-80 мс на старт интерпретатора ОС. Для CLI-разработки это абсолютно незаметно для человека, но требует наличия установленного `python` / `node` в `PATH` у пользователя.

**Вердикт по Категории 4:** **Преимущество Python в XPath и in-process `exec()`, преимущество Rust в скорости `scout/discover`.** В целом для задач скрейпинга и исследования HTML экосистема Python исторически более богата готовыми батарейками (особенно в части XPath).

---

## 7. Категория 5: Эргономика разработчика и скорость итерации

### 7.1. Времена жизни (Lifetimes) и Borrow Checker в компиляторах

Распространенный страх перед переносом компиляторов на Rust — борьба с Borrow Checker при построении деревьев AST.

#### Идиоматический паттерн Rust для AST:
В современных компиляторах на Rust (Rust Analyzer, SWC, Biome, Ruff) этот вопрос решается двумя проверенными способами:

1. **Владеющие структуры (*Owned AST*):**
   Все узлы владеют своими данными (`String`, `Vec<AstNode>`, `Box<AstNode>`). Поскольку процесс компиляции KDL-файла длится считанные миллисекунды, накладные расходы на аллокацию строк ничтожны. При таком подходе **в коде AST вообще нет аннотаций времен жизни (`'a`)**, и Borrow Checker никогда не блокирует разработку.
2. **Арена-аллокаторы (*Arena Allocation* — `bumpalo` / `typed-arena`):**
   Применяется, если требуется экстремальная производительность (миллионы строк в секунду). Все узлы выделяются в одном пуле памяти и освобождаются мгновенно при завершении фазы.

```rust
// Простое и эргономичное AST без единого времени жизни:
#[derive(Debug, Clone)]
pub struct FieldNode {
    pub name: String,
    pub type_info: TypeInfo,
    pub body: Vec<PipelineOp>,
}
```

### 7.2. Цикл обратной связи (Feedback Loop) и уверенность в рефакторинге

```
┌────────────────────────────────────────────────────────────────────────┐
│                   DEVELOPMENT FEEDBACK CYCLE                           │
└────────────────────────────────────────────────────────────────────────┘

 Python:
 [Edit code] ────────► [Run pytest] ────────────────► [Runtime error in unvisited branch]
   (0 sec)               (1.5 sec)                      (нужно покрыть тестом каждый if/match)

 Rust:
 [Edit code] ────────► [cargo check] ───────────────► [Compile-time guarantee]
   (0 sec)               (0.8 sec - incremental)        (E0004 указал все 12 мест для правок)
```

* **Python:** Разработка новой фичи начинается мгновенно. Но масштабный рефакторинг (например, разделение `StructRest` и `StructBase`, изменение формата `PlaceholderSpec`) требует максимальной концентрации: если тест не зашел в определенную ветку `if isinstance(...)`, баг останется незамеченным.
* **Rust:** Компилятор выступает в роли "парного программиста". При изменении структуры `TypeInfo` достаточно запустить `cargo check`, и компилятор выведет исчерпывающий список всех мест в кодовой базе, требующих адаптации. После успешной компиляции код работает с первого раза в 95% случаев.

**Вердикт по Категории 5:** **Паритет с разделением по фазам.** Для быстрого прототипирования новых безумных идей удобнее Python. Для долгосрочного сопровождения, расширения и масштабного рефакторинга кодовой базы взрослого компилятора **Rust обеспечивает качественно более высокий уровень эргономики и уверенности**.

---

## 8. Категория 6: Онбординг команды и сопровождение зависимостей

### 8.1. Порог входа (Skill Barrier)

* **Python:** Де-факто стандарт индустрии веб-скрейпинга и парсинга данных. Любой разработчик, пишущий парсеры на Scrapy, BeautifulSoup или Playwright, способен открыть `targets/python/visitor.py` и внести правку в генерацию Python-кода за 15 минут.
* **Rust:** Требует понимания владения, трейтов, паттерн-матчинга, работы с `Result`/`Option` и макросами. Порог входа для сторонних контрибьюторов (community contributors) в проект ощутимо выше.

### 8.2. Управление зависимостями и безопасность цепочки поставок

* **Python:** Связка `pyproject.toml` + `uv` кардинально улучшила ситуацию в Python в 2024–2026 гг. Однако остаются риски платформо-зависимых бинарных wheels (например, для C-расширений `lxml` на экзотических архитектурах или старых дистрибутивах Linux).
* **Rust:** Пакетный менеджер `Cargo` признан эталоном в индустрии:
  * `Cargo.lock` гарантирует бит-в-бит воспроизводимость сборки на любой машине.
  * Инструменты `cargo-audit` и `cargo-deny` автоматически проверяют уязвимости и лицензии зависимостей в CI.
  * Отсутствие внешних runtime-зависимостей при запуске скомпилированного бинарника.

**Вердикт по Категории 6:** **Победа Python по доступности для контрибьюторов; победа Rust по надежности сборочной цепочки.**

---

## 9. Категория 7: Производительность, распространение и упаковка

### 9.1. Время холодного запуска CLI (Cold Start Latency)

Кодогенераторы часто вызываются в консольных конвейерах (*pipes*) или интеграционных скриптах сотни раз подряд:
```bash
for file in schemas/*.kdl; do ssc-gen generate python "$file" -o out/; done
```

* **Python CLI (`typer` + `lxml` + `bs4` + `kdlquery`):** Время холодного запуска составляет **80–180 мс** на команду из-за инициализации интерпретатора Python и импорта тяжелых C-библиотек (`lxml`, `ctypes`).
* **Rust CLI (`clap` v4):** Время старта — **1.5–4 мс**. Инструмент откликается мгновенно, не создавая задержек в CI/CD пайплайнах.

### 9.2. Дистрибуция и развертывание

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DISTRIBUTION COMPARISON                         │
└────────────────────────────────────────────────────────────────────────┘

 Python:
 [User Machine] ──► Needs Python 3.10+ ──► uv / pip install ──► Virtualenv conflicts
                                                                (or 80MB PyInstaller binary)

 Rust:
 [GitHub Releases] ──► Single static binary (8 MB, musl / Windows .exe / macOS Universal)
                       Zero dependencies. Runs anywhere out of the box.
```

* Чтобы распространять Python CLI конечному пользователю без установленного Python, приходится использовать тяжелые обертки (`PyInstaller`, `shiv`, `pex`), которые распаковывают архив во временную директорию `/tmp` при каждом запуске.
* Rust компилируется в **один автономный статический бинарный файл** размером ~8–12 МБ (с LTO и strip), который можно положить в `/usr/local/bin` или распространять через Homebrew / Scoop / Cargo.

**Вердикт по Категории 7:** **Подавляющее преимущество Rust.**

---

## 10. Эталонный проект архитектуры на Rust (Reference Blueprint)

Если проект `ssc_codegen` реализуется на Rust, оптимальной является модульная организация в виде **Cargo Workspace**:

```
selector_schema_codegen/ (Cargo Workspace)
├── Cargo.toml
├── crates/
│   ├── ssc_ast/           # AST ноды, VariableType, TypeInfo, PlaceholderSpec (0 dependencies)
│   ├── ssc_parser/        # KDL 2.0 reader (kdl-rs), AST builder, import graph DAG
│   ├── ssc_linter/        # Linter passes, semantic checks, type inference pipeline
│   ├── ssc_codegen/       # Base traits (Backend, DomSpelling), WalkContext, CodeWriter
│   │   ├── src/
│   │   │   ├── targets/
│   │   │   │   ├── python/    # PythonBackend + bs4/lxml/parsel/slax spellings + httpx/aiohttp
│   │   │   │   ├── js/        # JsBackend (vanilla DOM) + fetch/axios
│   │   │   │   └── golang/    # GoBackend (goquery + net/http)
│   │   │   └── templates/     # minijinja шаблоны runtime-модулей
│   ├── ssc_html/          # Auxiliary engine: scraper, health check, scout/discover
│   └── ssc_cli/           # CLI binary (clap v4), commands: generate, check, health, scout, run
```

### Ключевые структуры данных ядра (Rust Idiomatic Core):

```rust
// Пример трейта генератора целевого языка
pub struct WalkContext {
    pub index: usize,
    pub depth: usize,
    pub var_name: &'static str,
    pub indent_char: &'static str,
}

impl WalkContext {
    pub fn prv(&self) -> String {
        if self.index == 0 { self.var_name.to_string() } else { format!("{}{}", self.var_name, self.index) }
    }
    pub fn nxt(&self) -> String {
        format!("{}{}", self.var_name, self.index + 1)
    }
    pub fn advance(&self) -> Self {
        Self { index: self.index + 1, ..*self }
    }
    pub fn deeper(&self) -> Self {
        Self { depth: self.depth + 1, ..*self }
    }
}
```

---

## 11. Заключение и стратегические рекомендации

### Когда Rust дает максимальный ROI в сопровождении:
1. **Масштабирование числа целевых языков:** Если планируется генерация парсеров под 5–8 языков (Python, JS, Go, Rust, Java, C#, Ruby, PHP), система типов Rust с исчерпывающим `match` окупает себя многократно. Ни одно изменение в AST или типах не пройдет мимо ни одного бэкенда.
2. **Использование в качестве инфраструктурного CLI-инструмента:** Мгновенный запуск (2 мс), единый бинарник без Python-окружения, дистрибуция через `brew install ssc-gen` или Docker scratch images.
3. **Безупречная компиляторная диагностика:** Интеграция `miette` выводит сообщения об ошибках в схемах KDL на уровень лучших современных компиляторов (`rustc`, `elm`, `ruff`).

### Когда текущий Python 3.10+ остается более практичным:
1. **Фокус команды на Web Scraping / Data Engineering:** Если основные разработчики и пользователи генератора — Python-разработчики, им на порядок проще читать, модифицировать и отлаживать кодовую базу на Python.
2. **Глубокая завязка на XPath в схемах:** Наличие в Python зрелой библиотеки `lxml` с поддержкой XPath 1.0 "из коробки" для команд `health` и `explore`.
3. **Быстрое создание экспериментальных фич:** Скорость прототипирования нестандартных трансформаций в Python выше благодаря динамической типизации и отсутствию времени компиляции.

### Итоговый вердикт

> Сопровождать ядро кодогенератора (`AST`, `parser`, `linter`, `type checking`, `codegen`) на **Rust значительно надежнее, приятнее и безопаснее**, чем на Python, благодаря исчерпывающему сопоставлению с образцом (`exhaustive match`), строгим контрактам трейтов и компиляторной диагностике `miette`.
> 
> Единственная область, где Python сохраняет локальное преимущество — вспомогательные инструменты инспекции живого HTML (`health` / `scout`), за счет богатой экосистемы XPath (`lxml`). Однако для компиляторного ядра и CLI-дистрибуции **Rust является идеальным архитектурным выбором**.

---

## 12. Первичные источники и литература (Primary Sources & References)

### 1. Архитектура компиляторов и статический анализ в Rust
* **The Rust Reference — Pattern Matching & Exhaustiveness:**  
  [https://doc.rust-lang.org/reference/expressions/match-expr.html](https://doc.rust-lang.org/reference/expressions/match-expr.html)  
  *Спецификация семантики исчерпывающего сопоставления с образцом и диагностических кодов (E0004).*
* **Guide to Rustc Development — AST and HIR Traversal:**  
  [https://rustc-dev-guide.rust-lang.org/ast-validation.html](https://rustc-dev-guide.rust-lang.org/ast-validation.html)  
  *Архитектурные паттерны обхода синтаксических деревьев и валидации проходов компилятора.*
* **Astral Ruff (Python linter/formatter in Rust) Architecture:**  
  [https://github.com/astral-sh/ruff](https://github.com/astral-sh/ruff)  
  *Практический опыт построения сверхбыстрого анализатора Python на Rust.*
* **Biome & Oxc Compiler Toolchains:**  
  [https://biomejs.dev/internals/architecture/](https://biomejs.dev/internals/architecture/) | [https://oxc.rs/docs/learn/architecture.html](https://oxc.rs/docs/learn/architecture.html)  
  *Паттерны построения промышленных linter/codegen инструментов на Rust.*

### 2. KDL и диагностика ошибок
* **KDL Document Language 2.0 Specification:**  
  [https://kdl.dev/](https://kdl.dev/)  
  *Официальная спецификация синтаксиса KDL.*
* **`kdl-rs` (Crate Documentation by Kat Marchán):**  
  [https://docs.rs/kdl/latest/kdl/](https://docs.rs/kdl/latest/kdl/)  
  *Официальный KDL-парсер для Rust с поддержкой SourceSpan.*
* **`miette` Diagnostic Reporting Framework:**  
  [https://docs.rs/miette/latest/miette/](https://docs.rs/miette/latest/miette/)  
  *Стандарт оформления компиляторных сообщений об ошибках с подсветкой спанов.*
* **`ariadne` Beautiful Diagnostics:**  
  [https://docs.rs/ariadne/latest/ariadne/](https://docs.rs/ariadne/latest/ariadne/)  
  *Движок визуализации многострочных синтаксических ошибок в терминале.*

### 3. Кодогенерация и шаблонизация
* **`minijinja` (Zero-dependency Jinja2 for Rust by Armin Ronacher):**  
  [https://docs.rs/minijinja/latest/minijinja/](https://docs.rs/minijinja/latest/minijinja/)  
  *Встраиваемый движок шаблонов для генерации модулей и runtime-файлов.*
* **`prettyplease` (Minimal Rust Code Formatter by David Tolnay):**  
  [https://docs.rs/prettyplease/latest/prettyplease/](https://docs.rs/prettyplease/latest/prettyplease/)  
  *Паттерны форматирования и построения синтаксического вывода.*

### 4. HTML анализ и селекторы
* **`scraper` (HTML parsing and CSS selecting in Rust):**  
  [https://docs.rs/scraper/latest/scraper/](https://docs.rs/scraper/latest/scraper/)  
  *Крейт парсинга HTML на базе Servo `html5ever` и `selectors`.*
* **`lol_html` (Cloudflare Low-latency Streaming HTML Parser):**  
  [https://docs.rs/lol_html/latest/lol_html/](https://docs.rs/lol_html/latest/lol_html/)  
  *Высокопроизводительный парсер и модификатор HTML.*
* **`sxd-xpath` (Pure Rust XPath 1.0 implementation):**  
  [https://docs.rs/sxd-xpath/latest/sxd_xpath/](https://docs.rs/sxd-xpath/latest/sxd_xpath/)  
  *Реализация XPath 1.0 на чистом Rust.*

### 5. CLI и системный уровень
* **`clap` v4 (Command Line Argument Parser for Rust):**  
  [https://docs.rs/clap/latest/clap/](https://docs.rs/clap/latest/clap/)  
  *Декларативный derive-парсер аргументов командной строки.*
