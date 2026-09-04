# Исследование инструментов и подходов для генерации API Reference документации

> **Дата исследования:** Сентябрь 2026 г.  
> **Статус:** Завершено  
> **Целевой проект:** `selector_schema_codegen` (Python 3.10+, Typer CLI, KDL DSL compiler)  
> **Язык отчёта:** Русский (с сохранением международной технической терминологии)

---

## 1. Введение и цели исследования

Генерация справочной документации по программным интерфейсам (**API Reference**) — ключевой этап создания поддерживаемого и удобного для разработчиков программного обеспечения. Современные инструменты генерации документации решают следующие задачи:

1. **Автоматическое извлечение сигнатур и контрактов:** парсинг аннотаций типов (PEP 484, PEP 585, PEP 604) и строк документации (docstrings в форматах Google, NumPy, Sphinx/reST).
2. **Безопасность сборки:** выбор между динамическим импортом рантайма (интроспекция `inspect`) и статическим анализом AST (Abstract Syntax Tree), предотвращающим выполнение побочных эффектов при сборке.
3. **Бесшовная интеграция с Markdown:** генерация документации в едином контуре с концептуальными руководствами (User Guides, Tutorials, Architecture Guides).
4. **Специализированная документация CLI:** автоматическое формирование справочника флагов, подкоманд, аргументов и переменных окружения для CLI-инструментов (Click, Typer, Argparse).
5. **Интерактивные спецификации REST/HTTP:** рендеринг OpenAPI/Swagger схем с возможностью исполнения тестовых запросов (Try-it-out).
6. **Поддержка многоязычных кодовых баз (Polyglot):** унификация документации для сгенерированных клиентских библиотек (TypeScript, Go, Python и др.).

Данный отчет содержит детальный анализ инструментов во всех категориях, подтвержденный первичными источниками, сравнительные таблицы и архитектурную рекомендацию для проекта `selector_schema_codegen`.

---

## 2. Python Code API Reference (Docstrings + Type Annotations)

В экосистеме Python существует два фундаментальных подхода к извлечению метаданных API:
* **Runtime Introspection (Динамический импорт):** Модуль импортируется интерпретатором Python, после чего исследуются `__doc__`, `__annotations__` и атрибуты объектов. *Плюсы:* поддержка динамически созданных методов и метаклассов. *Минусы:* риск выполнения побочного кода при импорте, необходимость установки всех runtime-зависимостей в окружение сборщика документации.
* **Static AST Analysis (Статический синтаксический анализ):** Код парсится в абстрактное синтаксическое дерево без его непосредственного исполнения. *Плюсы:* безопасность, изоляция, высокая скорость, отсутствие требования устанавливать runtime C-библиотеки.

```
                  ┌──────────────────────────────────────────────┐
                  │          Python Source Code (.py)            │
                  └──────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │ Static AST Parser (Griffe)│                   │ Runtime Import (inspect)  │
   │  - No code execution      │                   │  - Executes top-level code│
   │  - Fast, isolated         │                   │  - Requires dependencies  │
   └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                 │                                               │
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │ mkdocstrings / autoapi    │                   │ Sphinx autodoc / pdoc     │
   └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                 │                                               │
                 ▼                                               ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                       Generated API Reference                             │
   │             (HTML / Markdown / Search / Type Cross-links)                 │
   └───────────────────────────────────────────────────────────────────────────┘
```

---

### 2.1. MkDocs + mkdocstrings (с парсером Griffe)

* **Официальный сайт:** [https://mkdocstrings.github.io/](https://mkdocstrings.github.io/)
* **Репозиторий mkdocstrings:** [https://github.com/mkdocstrings/mkdocstrings](https://github.com/mkdocstrings/mkdocstrings)
* **Репозиторий mkdocstrings-python:** [https://github.com/mkdocstrings/python](https://github.com/mkdocstrings/python)
* **Парсер Griffe:** [https://mkdocstrings.github.io/griffe/](https://mkdocstrings.github.io/griffe/) | [https://github.com/mkdocstrings/griffe](https://github.com/mkdocstrings/griffe)
* **Тема Material for MkDocs:** [https://squidfunk.github.io/mkdocs-material/](https://squidfunk.github.io/mkdocs-material/)

#### Ключевые возможности:
* **Инжекция в Markdown (Markdown-native):** В отличие от традиционных генераторов, создающих отдельные изолированные страницы, `mkdocstrings` позволяет вставлять автогенерируемые блоки в произвольное место любого Markdown-документа с помощью синтаксиса `::: path.to.module.object`.
* **Парсер Griffe (Static AST + Fallback Inspection):** Griffe обходит AST исходного кода Python для извлечения сигнатур, аннотаций типов, атрибутов классов/модулей и docstrings. При необходимости он может переключаться в режим динамической интроспекции, если исходный код скомпилирован (C-extensions).
* **Поддержка стилей docstrings:** Нативная поддержка Google Docstrings, NumPy Docstrings и Sphinx (reST) Docstrings с автоматическим преобразованием блоков `Note:`, `Warning:`, `Tip:` в красивые выноски (admonitions).
* **Глубокая поддержка Type Hints:** Автоматически парсит аннотации типов (включая сложные объединения `X | Y`, дженерики `list[T]`, `TypedDict`, `Literal`) и превращает имена типов в кликабельные кросс-ссылки.
* **Перекрестные ссылки (Cross-references) и Intersphinx-инвентари:** Плагин `mkdocstrings-autorefs` автоматически связывает идентификаторы между страницами. Поддерживается загрузка удаленных инвентарей `objects.inv` (аналог Sphinx intersphinx) для создания ссылок на официальную документацию Python, Pydantic, FastAPI, LXML и других библиотек.
* **Интеграция с Material for MkDocs:** Поддержка сворачиваемого исходного кода функций/классов (Collapsible Source Code), мгновенного поиска (Lunr.js/Search Worker), светлой/темной темы, адаптивной навигации и генерации оглавления (TOC) для каждого объекта.

#### Пример использования:

В файле `docs/api/converters.md`:
```markdown
# Справочник конвертеров AST

::: ssc_codegen.converters.base
    options:
      show_root_heading: true
      show_source: true
      docstring_style: google
      members:
        - BaseWalker
        - AstVisitor
```

#### Достоинства:
* Идеально гармонирует с Markdown-ориентированной документацией проекта.
* Превосходный современный UI "из коробки" в связке с `mkdocs-material`.
* Высокая скорость сборки и качественный локальный сервер с Hot Reload.
* Используется ведущими проектами экосистемы Python: **FastAPI, Pydantic, Prefect, Textual, Google Jax, Microsoft Presidio, Apache Airflow / Apache StreamPipes**.

#### Недостатки:
* Для сложных многостраничных структур API требует либо явного перечисления модулей в `.md` файлах, либо использования вспомогательного генератора страниц (например, `mkdocs-gen-files` / `mkdocstrings-gallery`).

---

### 2.2. Sphinx Ecosystem (`autodoc`, `autosummary`, `sphinx-autoapi`, MyST)

* **Официальный сайт Sphinx:** [https://www.sphinx-doc.org/](https://www.sphinx-doc.org/)
* **Sphinx AutoAPI:** [https://sphinx-autoapi.readthedocs.io/](https://sphinx-autoapi.readthedocs.io/) | [https://github.com/readthedocs/sphinx-autoapi](https://github.com/readthedocs/sphinx-autoapi)
* **MyST Parser:** [https://myst-parser.readthedocs.io/](https://myst-parser.readthedocs.io/)
* **Read the Docs:** [https://about.readthedocs.com/](https://about.readthedocs.com/)

#### Архитектурные компоненты:
1. **`sphinx.ext.autodoc` + `sphinx.ext.autosummary`:**
   * Классический механизм Python. Импортирует модули во время выполнения, считывает атрибуты и генерирует reStructuredText (reST) директивы.
   * `autosummary` создает сводные таблицы функций/классов со ссылками на полные описания.
2. **`sphinx-autoapi`:**
   * Разработан командой Read the Docs как альтернатива `autodoc`.
   * **Не импортирует код**, а выполняет статический парсинг AST через библиотеки `astroid` / `griffe`.
   * Автоматически обходит все дерево пакетов и строит иерархическую структуру страниц документации без необходимости писать файлы-заглушки вручную.
3. **`myst-parser` (Markedly Structured Text):**
   * Расширение docutils/Sphinx, позволяющее писать документацию на Markdown (CommonMark + расширения MyST), сохраняя доступ ко всем директивам и ролям Sphinx (`{ref}`, `{doc}`, `{autoclass}`).

#### Достоинства:
* Стандарт де-факто для крупных академических и enterprise-библиотек (CPython, NumPy, SciPy, PyTorch).
* Непревзойденная мощь индексации, поддержки C/C++ расширений и мультиязычной документации.
* Богатая экосистема современных тем (Furo, PyData Sphinx Theme, Sphinx Book Theme).
* Нативная интеграция с платформой хостинга ReadTheDocs.

#### Недостатки:
* Высокий порог входа и сложность конфигурации (`conf.py`, управление расширениями).
* Историческая привязка к reStructuredText (reST). Даже с MyST синтаксис директив более громоздкий, чем в нативном Markdown/MkDocs.
* Медленный live reload при разработке по сравнению с MkDocs и pdoc.

---

### 2.3. pdoc (современный pdoc.dev)

* **Официальный сайт:** [https://pdoc.dev/](https://pdoc.dev/)
* **Репозиторий:** [https://github.com/mitmproxy/pdoc](https://github.com/mitmproxy/pdoc) *(сопровождается командой mitmproxy)*
* **PyPI:** `pip install pdoc` *(важно: не путать с устаревшими форками `pdoc3` и `pdoc2`)*

#### Ключевые возможности:
* **Zero Configuration:** Генерация полноценного сайта документации одной командой: `pdoc ssc_codegen`.
* **Встроенный Live Server:** Запуск `pdoc ssc_codegen` поднимает веб-сервер с мгновенным авто-обновлением при изменении исходников.
* **Автоматическая типизация и перекрестные ссылки:** Автоматически анализирует `__annotations__` и docstrings (Google, NumPy, reST), связывая типы гиперссылками.
* **Экспорт:** Вывод в один HTML-файл, дерево HTML-файлов или чистый Markdown (`pdoc --format markdown`).
* **Интегрированный поиск:** Быстрый клиентский полнотекстовый поиск на JavaScript.

#### Достоинства:
* Самый быстрый старт: не требует написания конфигурационных файлов (`mkdocs.yml`, `conf.py`).
* Минималистичный, адаптивный, чистый HTML/CSS интерфейс.
* Отлично подходит для внутреннего использования в командах и для средних библиотек.

#### Недостатки:
* Жесткая привязка к структуре модулей Python (нельзя произвольно комбинировать обучающие статьи и справочник API в едином меню без кастомизации шаблонов Jinja2).
* Ограниченные возможности расширения темами по сравнению с MkDocs/Sphinx.

---

### 2.4. Quartodoc

* **Официальный сайт:** [https://machow.github.io/quartodoc/](https://machow.github.io/quartodoc/)
* **Репозиторий:** [https://github.com/machow/quartodoc](https://github.com/machow/quartodoc)
* **Платформа Quarto:** [https://quarto.org/](https://quarto.org/)

#### Ключевые возможности:
* **Интеграция с научной издательской системой Quarto:** Генерирует страницы формата `.qmd` (Quarto Markdown).
* **Использование Griffe:** Под капотом использует `griffe` для AST-парсинга docstrings и типов.
* **Разделы и фильтрация:** Позволяет гибко группировать функции и классы в манифесте `_quarto.yml`.

#### Достоинства:
* Идеальный выбор для Data Science, ML и научных проектов, где документация содержит исполняемые Jupyter-ноутбуки, интерактивные графики и формулы LaTeX.

#### Недостатки:
* Требует установки внешней CLI-утилиты Quarto (написанной на Deno/Pandoc).
* Избыточен для классических CLI-утилит и парсеров общего назначения.

---

### 2.5. Традиционные и полиглот-инструменты (pydoctor, Doxygen)

* **pydoctor:** [https://pydoctor.readthedocs.io/](https://pydoctor.readthedocs.io/) | [https://github.com/twisted/pydoctor](https://github.com/twisted/pydoctor)
  * Разработан проектом Twisted. Выполняет статический анализ через AST. Исторически ориентирован на Epytext и reST.
  * *Вердикт:* Устаревший интерфейс, уступает Griffe/mkdocstrings по возможностям типизации и экосистеме.
* **Doxygen:** [https://www.doxygen.nl/](https://www.doxygen.nl/) | [https://github.com/doxygen/doxygen](https://github.com/doxygen/doxygen)
  * Мощный классический полиглот-генератор (C++, C, Java, Python, C#, Rust). Генерирует графы наследования и вызовов с помощью Graphviz.
  * *Вердикт:* Отличен для C/C++ кодовых баз, но вывод для современного Python выглядит устаревшим и не поддерживает современные идиомы PEP 585/604.

---

## 3. CLI Reference Documentation (для Typer / Click)

Для генерации справочной документации по интерфейсам командной строки (CLI) ручное ведение документации крайне неэффективно: флаги, алиасы, типы аргументов и значения по умолчанию часто изменяются в коде.

Поскольку **Typer построен поверх Click**, любой объект `typer.Typer` конвертируется в команду или группу Click через функцию `typer.main.get_command(app)`. Это обеспечивает полную совместимость со всеми инструментами Click-экосистемы.

```
┌─────────────────────────────────┐
│     Typer App (app = Typer())   │
└────────────────┬────────────────┘
                 │ typer.main.get_command(app)
                 ▼
┌─────────────────────────────────┐
│       Click Group / Command     │
└───────┬─────────────────┬───────┘
        │                 │
        ▼                 ▼
┌──────────────┐   ┌──────────────┐
│ mkdocs-click │   │ sphinx-click │
└───────┬──────┘   └──────┬───────┘
        │                 │
        ▼                 ▼
 Markdown CLI Doc   reST / Sphinx Doc
```

---

### 3.1. mkdocs-click

* **Репозиторий:** [https://github.com/mkdocs/mkdocs-click](https://github.com/mkdocs/mkdocs-click) (ранее DataDog/mkdocs-click)
* **PyPI:** [https://pypi.org/project/mkdocs-click/](https://pypi.org/project/mkdocs-click/)

#### Ключевые возможности:
* Markdown-расширение для MkDocs. Динамически извлекает структуру команд, опций, аргументов, docstrings и контекстной помощи из объектов Click/Typer.
* Поддержка вложенных подкоманд (`Multi-command / Groups`): автоматически рекурсивно генерирует документацию по всем подкомандам дерева.
* Стили отображения опций: `plain` или структурированная таблица `table`.
* Формирование заголовков и якорных ссылок для глубокой навигации (`:depth:`, интеграция с `attr_list`).

#### Синтаксис подключения:
В `mkdocs.yml`:
```yaml
markdown_extensions:
  - attr_list
  - mkdocs-click
```

В Markdown-файле (`docs/cli.md`):
```markdown
# Справочник интерфейса командной строки ssc-gen

::: mkdocs-click
    :module: ssc_codegen.main
    :command: cli
    :prog_name: ssc-gen
    :style: table
    :depth: 1
```

*Примечание для Typer:* если в `ssc_codegen.main` объект называется `app = typer.Typer()`, создается Click-обертка `cli = typer.main.get_command(app)`.

---

### 3.2. sphinx-click

* **Официальный сайт:** [https://sphinx-click.readthedocs.io/](https://sphinx-click.readthedocs.io/)
* **Репозиторий:** [https://github.com/click-contrib/sphinx-click](https://github.com/click-contrib/sphinx-click)

#### Ключевые возможности:
* Расширение для Sphinx, предоставляющее директиву `.. click::`.
* Автоматически парсит дерево команд Click/Typer и формирует блоки reST.
* Поддерживает мокирование зависимостей и переопределение названий исполняемых файлов (`:prog:`).

#### Синтаксис:
```rst
.. click:: ssc_codegen.main:cli
   :prog: ssc-gen
   :nested: full
```

---

### 3.3. Typer встроенный экспорт и Rich-Click

* **Typer CLI / Rich:** [https://typer.tiangolo.com/](https://typer.tiangolo.com/) | [https://github.com/fastapi/typer](https://github.com/fastapi/typer)
* **rich-click:** [https://github.com/ewels/rich-click](https://github.com/ewels/rich-click)
* **Программная генерация Markdown:** Typer/Click позволяет через `click.testing.CliRunner` или утилиту `rich-click` форматировать справку в ANSI/SVG/Markdown для включения в README репозитория.

---

## 4. REST / HTTP API Reference (OpenAPI / AsyncAPI)

Для документирования веб-сервисов и HTTP API стандартом де-факто является спецификация **OpenAPI (OAS 3.0 / 3.1)**. Инструменты визуализации отображают эндпоинты, схемы входных/выходных данных, модели ошибок и предоставляют интерактивную консоль для отправки запросов.

---

### 4.1. Scalar

* **Официальный сайт:** [https://scalar.com/](https://scalar.com/)
* **Репозиторий GitHub:** [https://github.com/scalar/scalar](https://github.com/scalar/scalar) (16k+ Stars)
* **Демо:** [https://docs.scalar.com/swagger-editor](https://docs.scalar.com/swagger-editor)

#### Ключевые возможности:
* **Современный UI нового поколения:** Ультрабыстрый, высокоэстетичный интерфейс с адаптивной 3-колоночной версткой.
* **Встроенный интерактивный API-клиент:** Полноценная замена Postman прямо в браузере (поддержка переменных окружения, авторизации, сохранения истории, пресетов).
* **Генерация примеров кода:** Автоматическое формирование сниппетов на десятках языков и библиотек (Python `requests`/`httpx`, JavaScript `fetch`/`axios`, cURL, Go, Rust, C#, PHP и др.).
* **Интеграции:**
  * Автономный HTML-файл через CDN: `<script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>`.
  * Пакеты для фреймворков: FastAPI, Litestar, Express, Hono, Django Ninja, ElysiaJS.
  * Встраивание в статические генераторы (Docusaurus, VitePress, MkDocs через iframe или веб-компонент `@scalar/api-reference`).

---

### 4.2. Redoc / Redocly

* **Официальный сайт:** [https://redocly.com/docs/redoc](https://redocly.com/docs/redoc)
* **Репозиторий GitHub:** [https://github.com/Redocly/redoc](https://github.com/Redocly/redoc) (24k+ Stars)

#### Ключевые возможности:
* **Классический 3-панельный дизайн:** Навигация слева, документация по центру, примеры запросов и ответов справа.
* **Строгое соответствие OpenAPI 3.0/3.1:** Безупречная визуализация сложных схем `oneOf`, `anyOf`, `allOf`, дискриминаторов и глубокой вложенности JSON Schema.
* **Redocly CLI:** Сборка всей документации и OpenAPI спецификации в единый автономный HTML файл без внешних зависимостей (`redocly build-docs openapi.yaml -o index.html`).
* *Ограничение:* Отсутствует интерактивная кнопка "Try it out" (фокус исключительно на чтении документации).

---

### 4.3. Swagger UI

* **Официальный сайт:** [https://swagger.io/tools/swagger-ui/](https://swagger.io/tools/swagger-ui/)
* **Репозиторий GitHub:** [https://github.com/swagger-api/swagger-ui](https://github.com/swagger-api/swagger-ui) (26k+ Stars)

#### Ключевые возможности:
* Исторический стандарт интерактивной документации. Встроен по умолчанию в FastAPI, Springfox, Swashbuckle.
* Поддержка "Try it out", генерации cURL и авторизации OAuth2/Bearer.
* *Недостатки:* Устаревший визуальный дизайн (стиль начала 2010-х годов), громоздкий DOM, относительно медленная загрузка больших спецификаций (5+ МБ).

---

### 4.4. Stoplight Elements

* **Официальный сайт:** [https://stoplight.io/open-source/elements](https://stoplight.io/open-source/elements)
* **Репозиторий GitHub:** [https://github.com/stoplightio/elements](https://github.com/stoplightio/elements)

#### Ключевые возможности:
* Набор Web Components (`<elements-api ... />`) и React-компонентов.
* Два режима отображения: 3-панельный (как Redoc) и стековый (как Swagger).
* Встроенная интерактивная консоль тестирования API.
* Легко интегрируется в Gatsby, Next.js, Docusaurus, MkDocs.

---

### 4.5. Платформы документации: Mintlify и Fern

* **Mintlify:** [https://mintlify.com/](https://mintlify.com/)
  * Современная SaaS-платформа для документации на базе MDX с синхронизацией через GitHub.
  * Интерактивные интерактивные компоненты API playground прямо в теле статей.
* **Fern:** [https://buildwithfern.com/](https://buildwithfern.com/) | [https://github.com/fern-api/fern](https://github.com/fern-api/fern)
  * Инструментарий "API-first": генерация не только сайтов документации по OpenAPI, но и типизированных клиентских SDK (TypeScript, Python, Go, Java).

---

## 5. Мультиязычная документация (Polyglot Projects: TS/JS, Go)

Для проектов с мульти-языковыми SDK или генерацией кода под разные целевые платформы необходимы специализированные генераторы.

---

### 5.1. TypeScript / JavaScript: TypeDoc

* **Официальный сайт:** [https://typedoc.org/](https://typedoc.org/)
* **Репозиторий GitHub:** [https://github.com/TypeStrong/typedoc](https://github.com/TypeStrong/typedoc)
* **Плагин Markdown:** [https://typedoc-plugin-markdown.org/](https://typedoc-plugin-markdown.org/)

#### Ключевые возможности:
* Извлекает структуру типов, интерфейсов, классов и функций непосредственно из TypeScript компилятора (`tsc`).
* Понимает аннотации TSDoc / JSDoc (`@param`, `@returns`, `@deprecated`, `@example`).
* Через `typedoc-plugin-markdown` компилирует всю документацию в чистые Markdown-файлы, которые затем можно скормить MkDocs, Docusaurus или VitePress.

---

### 5.2. Go: pkgsite, godoc, gomarkdoc

* **pkgsite (pkg.go.dev):** [https://go.googlesource.com/pkgsite](https://go.googlesource.com/pkgsite) — официальный сервер документации для Go-модулей.
* **godoc:** [https://pkg.go.dev/golang.org/x/tools/cmd/godoc](https://pkg.go.dev/golang.org/x/tools/cmd/godoc) — классический локальный HTTP-сервер документации Go.
* **gomarkdoc:** [https://github.com/princjef/gomarkdoc](https://github.com/princjef/gomarkdoc)
  * Утилита командной строки для генерации Markdown-документации из комментариев Go-пакетов.
  * Поддерживает режим встраивания (`gomarkdoc -e -o README.md .`) и пользовательские Go-шаблоны.
  * Идеально для сборки статических сайтов на MkDocs/GitHub Pages для Go-библиотек.

---

## 6. Сравнительная матрица инструментов

В таблице ниже приведено комплексное сравнение ведущих решений для документирования:

| Критерий | MkDocs + mkdocstrings | Sphinx (autodoc/autoapi) | pdoc (pdoc.dev) | Scalar | TypeDoc | gomarkdoc |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Основной стек** | Python / Markdown | Python / reST / MyST | Python / HTML | OpenAPI / REST | TypeScript / JS | Go |
| **Механизм анализа** | Static AST (Griffe) | Runtime (autodoc) / AST (autoapi) | Runtime inspect + AST | JSON/YAML Schema | TS Compiler AST | Go AST (`go/doc`) |
| **Сложность настройки** | Низкая / Средняя | Высокая | Нулевая (Zero-config) | Минимальная | Низкая | Низкая |
| **Формат контента** | Чистый Markdown | reST / MyST Markdown | Автономный HTML | OpenAPI JSON/YAML | TS комментарии | Go комментарии |
| **Поддержка Type Hints** | Отличная (кросс-линки) | Отличная (через плагины) | Отличная | N/A (JSON Schema) | Родная (TS types) | Родная (Go types) |
| **Интеграция с CLI** | Да (`mkdocs-click`) | Да (`sphinx-click`) | Нет | Нет | Нет | Нет |
| **Интерактивный Try-It** | Нет | Нет | Нет | Да (полноценный клиент) | Нет | Нет |
| **Полнотекстовый поиск** | Быстрый (клиентский JS)| Встроенный | Встроенный | Встроенный | Встроенный | Внешний |
| **Качество тем/UI** | Превосходное (`material`)| Варьируется (Furo, RTD) | Минималистичное | Ультрасовременное | Стандартное | Markdown |
| **Скорость Hot-Reload** | Очень высокая (<0.5s) | Средняя (1-3s) | Мгновенная (<0.2s) | Мгновенная (SPA) | Средняя | CLI экспорт |

---

## 7. Рекомендации по сценариям использования

### Сценарий 1: Python-библиотека с активным использованием Type Hints и Markdown
* **Выбор:** **MkDocs + mkdocstrings (с темой `mkdocs-material`)**
* **Обоснование:** Бесшовная работа с Markdown-файлами, современный внешний вид, развитая экосистема плагинов, статическое чтение типов через Griffe без сайд-эффектов при импорте.

### Сценарий 2: CLI-инструмент на Python (Click / Typer)
* **Выбор:** **MkDocs + `mkdocs-click`** (или Sphinx + `sphinx-click`)
* **Обоснование:** Автоматическая генерация документации по всем командам и опциям из дерева приложения, устранение расхождений между справкой `--help` и сайтом документации.

### Сценарий 3: REST API / OpenAPI спецификации
* **Выбор:** **Scalar**
* **Обоснование:** Современный дизайн, встроенный клиент тестирования запросов, генерация сниппетов кода на 15+ языках, легкая интеграция в статические сайты и фреймворки (FastAPI/Litestar/Django).

### Сценарий 4: Мультиязычный SDK (Python + TS + Go)
* **Выбор:** Единый портал на **MkDocs (Material)**:
  * Python: `mkdocstrings-python`
  * TypeScript: `typedoc` с плагином `typedoc-plugin-markdown`
  * Go: `gomarkdoc`
  * REST API: встраивание `@scalar/api-reference` через HTML-компонент.

---

## 8. Архитектурная рекомендация для репозитория `selector_schema_codegen`

### 8.1. Текущий контекст проекта
* **Язык и зависимости:** Python 3.10+, пакетный менеджер `uv`, Typer CLI (`ssc-gen`), KDL Query, BeautifulSoup4, Lxml, Httpx.
* **Существующая документация:** Обширный набор готовых Markdown-файлов в `docs/` (`docs/types.md`, `docs/syntax.md`, `docs/learn/*`, `docs/maintainers/*`).
* **Инструменты контроля качества:** `ruff`, `mypy`, `pytest`.

### 8.2. Оптимальный стек документации
Рекомендуется внедрение связки **Material for MkDocs + mkdocstrings (Python/Griffe) + mkdocs-click**.

#### Преимущества для проекта:
1. **Сохранение существующей базы знаний:** Все 20+ файлов из папки `docs/` подключаются в `mkdocs.yml` без конвертации разметки.
2. **Автоматический справочник CLI `ssc-gen`:** С помощью `mkdocs-click` создается всегда актуальная страница документации для CLI-утилиты, отражающая все флаги компилятора и линтера.
3. **API Reference для разработчиков и мейнтейнеров:** Модули `ssc_codegen.ast`, `ssc_codegen.converters`, `ssc_codegen.linter` документируются прямо из их type annotations и docstrings с генерацией перекрестных ссылок.
4. **Быстрый локальный превью:** `uv run mkdocs serve` обеспечивает мгновенную обратную связь при редактировании документации и кода.

---

### 8.3. Пошаговый план внедрения в `selector_schema_codegen`

#### Шаг 1: Добавление dev-зависимостей в `pyproject.toml`
```bash
uv add --group dev mkdocs-material mkdocstrings[python] mkdocs-click
```

#### Шаг 2: Создание конфигурации `mkdocs.yml` в корне репозитория
```yaml
site_name: selector_schema_codegen
site_description: Python-dsl code converter to HTML/REST parsers for web scraping
site_url: https://vypivshiy.github.io/selector_schema_codegen/
repo_url: https://github.com/vypivshiy/selector_schema_codegen
repo_name: vypivshiy/selector_schema_codegen

theme:
  name: material
  language: ru
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.code.annotate
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Переключить на темную тему
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Переключить на светлую тему

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_root_toc_entry: false
            show_object_full_path: false
            separate_signature: true
            merge_init_into_class: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - attr_list
  - mkdocs-click

nav:
  - "Главная": README.md
  - "Руководство (Guide)": guide.md
  - "Учебник (Learn)":
      - "Обзор": learn/overview.md
      - "01. Генерация": learn/01-generation.md
      - "02. Поля": learn/02-fields.md
      - "03. Проверки": learn/03-check.md
      - "04. Запуск": learn/04-run.md
      - "05. Здоровье схемы": learn/05-health.md
      - "06. Рецепты": learn/06-recipes.md
      - "07. Определение функций": learn/07-define.md
      - "08. Scout": learn/08-scout.md
      - "09. Импорты": learn/09-imports.md
      - "10. HTTP Request": learn/10-request.md
      - "11. Фильтры": learn/11-filters.md
      - "12. Ассерты": learn/12-asserts.md
  - "Спецификация DSL":
      - "Синтаксис": syntax.md
      - "Типы данных": types.md
      - "Операции": operations.md
      - "Предикаты": predicates.md
      - "JSON": json.md
      - "Расширения": extensions.md
  - "Справочник CLI": cli_reference.md
  - "API Reference":
      - "AST структуры": api/ast.md
      - "Конвертеры (Code Generators)": api/converters.md
      - "Линтер (Linter)": api/linter.md
  - "Для разработчиков":
      - "AST Spec": maintainers/ast_spec.md
      - "Converters": maintainers/converters.md
      - "KDL Query": maintainers/kdlquery.md
      - "Linter": maintainers/linter.md
```

#### Шаг 3: Создание страницы `docs/cli_reference.md`
```markdown
# Справочник интерфейса командной строки (CLI Reference)

Утилита `ssc-gen` предоставляет команды для компиляции, валидации и тестирования схем KDL.

::: mkdocs-click
    :module: ssc_codegen.main
    :command: cli
    :prog_name: ssc-gen
    :style: table
    :depth: 1
```

*(В `ssc_codegen/main.py` объявляется `cli = typer.main.get_command(app)`)*.

#### Шаг 4: Создание страниц Python API Reference
В файле `docs/api/ast.md`:
```markdown
# AST Models & Types

::: ssc_codegen.ast
    options:
      members: true
```

В файле `docs/api/converters.md`:
```markdown
# Code Converters

::: ssc_codegen.converters
    options:
      members: true
```

#### Шаг 5: Команды сборки и деплоя в GitHub Pages
```bash
# Локальный просмотр с автообновлением
uv run mkdocs serve

# Сборка статического сайта в папку site/
uv run mkdocs build --strict

# Деплой в ветку gh-pages
uv run mkdocs gh-deploy
```

---

## 9. Список первичных источников (Primary Sources Citations)

1. **mkdocstrings:**
   * Документация mkdocstrings: [https://mkdocstrings.github.io/](https://mkdocstrings.github.io/)
   * Документация Python Handler: [https://mkdocstrings.github.io/python/](https://mkdocstrings.github.io/python/)
   * Парсер Griffe: [https://mkdocstrings.github.io/griffe/](https://mkdocstrings.github.io/griffe/)
   * Тема Material for MkDocs: [https://squidfunk.github.io/mkdocs-material/](https://squidfunk.github.io/mkdocs-material/)
2. **Sphinx:**
   * Документация Sphinx: [https://www.sphinx-doc.org/en/master/](https://www.sphinx-doc.org/en/master/)
   * Sphinx AutoAPI: [https://sphinx-autoapi.readthedocs.io/en/latest/](https://sphinx-autoapi.readthedocs.io/en/latest/)
   * MyST Parser: [https://myst-parser.readthedocs.io/en/latest/](https://myst-parser.readthedocs.io/en/latest/)
3. **pdoc:**
   * Официальный сайт pdoc: [https://pdoc.dev/](https://pdoc.dev/)
   * Исходный код pdoc на GitHub: [https://github.com/mitmproxy/pdoc](https://github.com/mitmproxy/pdoc)
4. **Quartodoc & Quarto:**
   * Документация Quartodoc: [https://machow.github.io/quartodoc/get-started/overview.html](https://machow.github.io/quartodoc/get-started/overview.html)
   * Официальный сайт Quarto: [https://quarto.org/](https://quarto.org/)
5. **CLI Documentation Tools:**
   * mkdocs-click: [https://github.com/mkdocs/mkdocs-click](https://github.com/mkdocs/mkdocs-click)
   * sphinx-click: [https://sphinx-click.readthedocs.io/en/latest/](https://sphinx-click.readthedocs.io/en/latest/)
   * Typer Documentation: [https://typer.tiangolo.com/](https://typer.tiangolo.com/)
6. **REST / OpenAPI Viewers:**
   * Scalar: [https://scalar.com/](https://scalar.com/) | [https://github.com/scalar/scalar](https://github.com/scalar/scalar)
   * Redoc: [https://redocly.com/docs/redoc](https://redocly.com/docs/redoc) | [https://github.com/Redocly/redoc](https://github.com/Redocly/redoc)
   * Swagger UI: [https://swagger.io/tools/swagger-ui/](https://swagger.io/tools/swagger-ui/) | [https://github.com/swagger-api/swagger-ui](https://github.com/swagger-api/swagger-ui)
   * Stoplight Elements: [https://stoplight.io/open-source/elements](https://stoplight.io/open-source/elements) | [https://github.com/stoplightio/elements](https://github.com/stoplightio/elements)
   * Fern: [https://buildwithfern.com/](https://buildwithfern.com/)
   * Mintlify: [https://mintlify.com/](https://mintlify.com/)
7. **Polyglot & Other Languages:**
   * TypeDoc (TypeScript): [https://typedoc.org/](https://typedoc.org/)
   * TypeDoc Markdown Plugin: [https://typedoc-plugin-markdown.org/](https://typedoc-plugin-markdown.org/)
   * gomarkdoc (Go): [https://github.com/princjef/gomarkdoc](https://github.com/princjef/gomarkdoc)
   * pydoctor: [https://pydoctor.readthedocs.io/](https://pydoctor.readthedocs.io/)
   * Doxygen: [https://www.doxygen.nl/](https://www.doxygen.nl/)
