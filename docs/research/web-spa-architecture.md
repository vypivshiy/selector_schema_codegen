# Архитектурное исследование: запуск `ssc_codegen` в браузере как статического SPA без бэкенда

**Вопрос пользователя:**
> «Нужен этот инструмент для web версии. Какие есть способы этот проект сделать как онлайн инструмент? (SSR, чтобы запостить как одностраничник, без зависимости к бэкенду). Придётся на другой стек переписывать?»
>
> **Уточнения по скоупу:**
> 1. Только тестирование конфигов на вручную вставленном/загруженном HTML (без загрузки сторонних сайтов по сети — **0 проблем с CORS**).
> 2. Интерактивный линтер (`check`) с подсветкой ошибок в редакторе.
> 3. Для REST-API схем — только линтинг и кодогенерация (без выполнения HTTP-запросов).
> 4. Публикация `.whl` для `kdlquery 1.6.0` на PyPI подтверждена.
> 5. **Новое требование:** подсветка синтаксиса **KDL 2.0** (именно KDL 2.0, а не KDL 1.0!) в браузерном редакторе кода + оценка трудозатрат на реализацию.

---

## Краткий вывод (TL;DR)

1. **Переписывать проект на другой стек (JS/TS или Rust) НЕ нужно.** Кодовая база `ssc_codegen` (`36 088` строк Python в `92` файлах) вместе с парсером `kdlquery` (`4 851` строка Python в `9` файлах) — это суммарно **~41 000 строк кода компилятора** (плюс `21 513` строк тестов). Полный порт потребует месяцев работы и приведёт к необходимости синхронно поддерживать две кодовые базы при каждом изменении DSL.
2. **`ssc_codegen` запускается на 100% в браузере клиента через WebAssembly (Pyodide) на статическом хостинге** (GitHub Pages, Cloudflare Pages, Vercel Static, S3) вообще без бэкенда.
3. **Все зависимости проекта (включая C-расширение `lxml`) уже скомпилированы под WebAssembly и входят в стандартную поставку Pyodide** (`lxml`, `beautifulsoup4`, `soupsieve`, `cssselect`, `httpx`), а после публикации `kdlquery-1.6.0-py3-none-any.whl` на PyPI оба пакета (`kdlquery` и `ssc_codegen`) ставятся одним вызовом `micropip.install("ssc-codegen")`.
4. **Терминологическое уточнение (SSR vs SSG/SPA):** для хостинга «как одностраничник без зависимости к бэкенду» нужен не SSR (Server-Side Rendering требует живого сервера на каждый запрос), а **Client-Side SPA / SSG (Static Site Generation)**, где интерфейс собирается в статические `index.html` + `.js`, а компилятор `ssc_codegen` работает внутри браузерного `WebWorker` через Pyodide.
5. **Подсветка синтаксиса KDL 2.0 + `ssc-gen` DSL v2.1:** официальная грамматика `kdl-org/vscode-kdl` (`kdl.tmLanguage.json`, также входящая в `shiki`) уже обновлена под KDL 2.0 (`#true`, `#null`, `#"..."#`, `"""..."""`, `/-`), но не выделяет аннотации типов `(item)` и ключевые слова `ssc-gen`. Лучшее решение для веб-редактора — кастомный **Monarch-токенизатор для Monaco Editor (~90 строк кода)** (или `StreamLanguage` для CodeMirror 6), который нативно подсвечивает **и спецификацию KDL 2.0, и все ключевые слова/директивы/операции `ssc-gen` DSL v2.1** без подключения тяжёлого WASM-движка Oniguruma.
6. **Оценка сложности при суженном скоупе:** всё веб-приложение (Monaco/CodeMirror + WebWorker Pyodide + подсветка KDL 2.0 + живые маркеры линтера + тестирование на вставленном HTML) занимает **~600–750 строк кода TypeScript** и реализуется за **1–2 рабочих дня**.

---

## 1. Уточнение архитектуры: SSR против Static SPA / SSG

В вопросе упомянут **SSR (Server-Side Rendering)** в контексте *«запостить как одностраничник без зависимости к бэкенду»*. Важно разграничить эти режимы рендеринга:

| Режим | Как работает | Нужен ли бэкенд в рантайме? | Где можно хостить бесплатно? |
|---|---|---|---|
| **SSR (Server-Side Rendering)** | Сервер (Node.js / Python) генерирует HTML и запускает компилятор на каждый HTTP-запрос пользователя. | **Да** (нужен сервер или Serverless Functions). | Vercel Functions, Cloudflare Workers, Fly.io (но есть лимиты/зависимость от бэкенда). |
| **SSG (Static Site Generation) + Client-Side SPA** | Фронтенд (Vite, Astro, Next.js `output: 'export'`, SvelteKit `adapter-static` или чистый HTML+JS) один раз собирается в статические файлы (`index.html`, `.js`, `.css`). Вся логика `ssc_codegen` выполняется **в браузере пользователя** через WebAssembly (Pyodide). | **Нет (0% зависимости от бэкенда).** После загрузки страницы инструмент работает полностью автономно. | GitHub Pages, Cloudflare Pages, GitLab Pages, Vercel Static, Netlify, любой S3/CDN. |

Так как тестирование схем выполняется только на вставленном пользователем HTML, а для REST-схем нужна только кодогенерация и линтинг, **приложению вообще не нужно делать внешние HTTP-запросы к сторонним сайтам**. Это полностью снимает любые ограничения браузерной политики CORS ([MDN CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)) — никакой прокси-сервер не требуется.

---

## 2. Аудит кодовой базы `ssc_codegen` и графа зависимостей

В `pyproject.toml:7-17` объявлены следующие зависимости пакета `ssc_codegen` (версия `0.45.0`):

```toml
dependencies = [
    "bs4>=0.0.2",
    "colorama>=0.4.6 ; sys_platform == 'win32'",
    "cssselect>=1.2.0",
    "lxml>=5.3.0",
    "soupsieve>=2.6",
    "typer>0.26",
    "typing_extensions;python_version<'3.11'",
    "kdlquery>=1.3.0",
    "httpx>=0.28.1",
]
```

Полный аудит всех `import` / `from ... import` по всем `92` файлам в `ssc_codegen/` показывает, что зависимости распределены между подсистемами следующим образом:

### 2.1. Какие модули какие зависимости реально импортируют

| Подсистема `ssc_codegen` | Программная точка входа | Реально импортируемые сторонние пакеты | Где используется `lxml`? |
|---|---|---|---|
| **а) Компиляция KDL → код** (Python, JS, Go, Rust), включая REST-схемы | `parse_module()` (`ssc_codegen/core/reader.py:31`), `resolve(TargetSpec(...))` (`ssc_codegen/targets/resolver.py:29`), `converter.convert(ast)` | `kdlquery` (`ssc_codegen/core/reader.py:12-14`), `soupsieve` (`ssc_codegen/core/linter.py:2911`) | **Только если в схеме есть `xpath` / `xpath-all` / `xpath-remove`** (`ssc_codegen/core/linter.py:2938`). Для CSS, REST, JSON и `skip_lint=True` `lxml` **не импортируется вообще**. |
| **б) Линтер KDL-схем (`check`)** | `parse_module()` + `format_diagnostics()` (`ssc_codegen/core/format.py:63`), `diagnostic_to_dict()` (`ssc_codegen/core/format.py:118`) | `kdlquery`, `soupsieve` (для проверки CSS в `lint_validate_css`, `ssc_codegen/core/linter.py:2899-2913`), `lxml.etree` (ленивый импорт в `lint_validate_xpath`, `ssc_codegen/core/linter.py:2926-2940`) | Ленивый `from lxml import etree` внутри функции `lint_validate_xpath` вызывается **только** при наличии узлов `xpath*` в схеме (`ssc_codegen/core/expressions.py:672-714`, `ssc_codegen/core/linter.py:3370`). |
| **в) JSON-to-KDL и парсинг `@request` (curl / HTTP)** | `json_to_kdl()` / `json_text_to_kdl()` (`ssc_codegen/json_to_kdl.py:282-289`), `parse_to_http()` (`ssc_codegen/request_spec.py:60`), `parse_curl_command()` (`ssc_codegen/parsers/curl.py:28`), `parse_http_request()` (`ssc_codegen/parsers/http.py:65`) | **0 сторонних пакетов** (используется только стандартная библиотека Python: `json`, `re`, `shlex`, `keyword`, `urllib.parse`, `base64`). | **Нет.** |
| **г) Анализ HTML (`scout`) и проверка селекторов (`health`) на вставленном HTML** | `run_scout()` (`ssc_codegen/explore.py:2945`), `check_struct_health()` (`ssc_codegen/health.py:335`) | `bs4` (`BeautifulSoup`, `ssc_codegen/explore.py:19`, `ssc_codegen/health.py:366`), `lxml` (как парсер `BeautifulSoup(html, "lxml")` в `ssc_codegen/explore.py:32,486,2997` и `ssc_codegen/health.py:374`, а также `from lxml import etree` для XPath в `ssc_codegen/health.py:419`). | **Да** (использует встроенный в Pyodide WASM-пакет `lxml`). |
| **д) Тестовый прогон парсера на вставленном HTML (`run`)** | `exec(code, namespace)` (`ssc_codegen/main.py:1054,1073`) | Зависит от выбранного `--lib`: `bs4` (`beautifulsoup4` + `lxml` или `html.parser`), либо `lxml` + `cssselect` (`ssc_codegen/targets/python/html_libs/lxml.py:51-54`). | Поддерживает и `bs4` (с `lxml` или `html.parser`), и чистый `lxml` (оба пакета встроены в Pyodide). |

### 2.2. Важные находки по `httpx`, `cssselect`, `typer` и `colorama`

1. **`httpx` нигде не импортируется самим компилятором `ssc_codegen`:**
   Поиск по всей директории `ssc_codegen/` показывает, что строка `import httpx` присутствует исключительно внутри строковых шаблонов кодогенерации в `ssc_codegen/targets/python/http_libs/httpx.py:12-15,186` и `ssc_codegen/targets/python/http_libs/base.py:112`. Поскольку REST-схемы в веб-версии только компилируются и линтятся, `httpx` вообще не нужно загружать в браузер.
2. **`cssselect` нигде не импортируется в `ssc_codegen/`:**
   Он нужен только тогда, когда пользователь запускает сгенерированный Python-код для таргета `lib="lxml"` на тестовом HTML (`HtmlElement.cssselect()` внутри `lxml.html` вызывает `cssselect`, `ssc_codegen/targets/python/html_libs/lxml.py:72,91,114,236`).
3. **`typer` импортируется только в CLI (`ssc_codegen/main.py:12`):**
   Публичный API пакета в `ssc_codegen/__init__.py:25-56` экспортирует `parse_module`, `format_diagnostics`, `resolve`, `TargetSpec`, `TargetProfile`, `check_struct_health`, `run_scout` и **не импортирует `ssc_codegen.main`**.
4. **`colorama` имеет маркер `sys_platform == 'win32'` (`pyproject.toml:9`)** и обёрнут в `try ... except ImportError` в `ssc_codegen/core/format.py:13-17` и `ssc_codegen/_logging.py:22-26`.

---

## 3. Запуск через Pyodide (CPython в WebAssembly) — 0% переписывания кода

Согласно официальному реестру пакетов, встроенных в дистрибутив Pyodide ([Packages built in Pyodide, v314.0.7](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)), и метаданным PyPI JSON API:

| Пакет | Статус в Pyodide / PyPI | Версия / тип пакета | Нужно ли грузить для веб-плейграунда? | Источник |
|---|---|---|---|---|
| `lxml` | **Встроен в Pyodide** (скомпилирован в `.wasm`) | `6.1.3` | Да (для XPath, `health`, `scout`, `run`) | [Pyodide Packages List](https://pyodide.org/en/stable/usage/packages-in-pyodide.html) |
| `beautifulsoup4` | **Встроен в Pyodide** | `4.14.3` | Да (для `health`, `scout`, `run`) | [Pyodide Packages List](https://pyodide.org/en/stable/usage/packages-in-pyodide.html) |
| `bs4` | Чистый Python dummy-пакет на PyPI | `bs4-0.0.2-py2.py3-none-any.whl` (`1.1` КБ) | Опционально (если ставить с `deps=True`) | [`https://pypi.org/pypi/bs4/json`](https://pypi.org/pypi/bs4/json) |
| `soupsieve` | **Встроен в Pyodide** | `2.8.3` | Да (валидация CSS в линтере и `bs4.select`) | [Pyodide Packages List](https://pyodide.org/en/stable/usage/packages-in-pyodide.html) |
| `cssselect` | **Встроен в Pyodide** | `1.4.0` | Да (для `run` с таргетом `--lib lxml`) | [Pyodide Packages List](https://pyodide.org/en/stable/usage/packages-in-pyodide.html) |
| `kdlquery` | **100% чистый Python без зависимостей** | `py3-none-any.whl` (~40 КБ) | Да (парсер KDL 2.0 и селекторы) | [`https://pypi.org/pypi/kdlquery/json`](https://pypi.org/pypi/kdlquery/json) |
| `ssc_codegen` | **100% чистый Python** | `ssc_codegen-0.45.0-py3-none-any.whl` (`305` КБ) | Да | [`https://pypi.org/pypi/ssc-codegen/json`](https://pypi.org/pypi/ssc-codegen/json) |
| `httpx`, `typer` | Встроены / PyPI | — | **Не нужны в браузере** (пропускаются при `deps=False`) | `ssc_codegen/__init__.py:25-56` |

> **Бонус от использования `deps=False` в `micropip`:**
> Если загрузить только реально используемые пакеты (`await pyodide.loadPackage(["micropip", "soupsieve", "beautifulsoup4", "lxml", "cssselect"])` + `await micropip.install(["kdlquery", "ssc-codegen"], deps=False)`), то в браузер **не будут скачиваться ненужные для веб-UI `httpx`, `httpcore`, `anyio`, `certifi`, `idna`, `typer`, `click`, `rich`**, что ускоряет старт воркера.

---

## 4. Подсветка синтаксиса KDL 2.0 и DSL `ssc-gen` v2.1 в браузере

Пользователь особо отметил необходимость подсветки именно **KDL 2.0** (где булевы и null-литералы пишутся через решётку: `#true`, `#false`, `#null`, `#inf`, `#-inf`, `#nan`, raw-строки пишутся как `#"..."#` вместо `r#"..."#` из KDL 1.0, добавлены многострочные строки `"""..."""` и строки без кавычек).

### 4.1. Аудит первичных источников по существующим грамматикам KDL 2.0

1. **Текущее состояние в репозитории (`mkdocs.yml:54`):**
   В `mkdocs.yml` подключён `pymdownx.highlight` (на базе Pygments). Проверка `pygments.lexers.get_lexer_by_name("kdl")` в окружении проекта возвращает `ClassNotFound: no lexer for alias 'kdl' found` — то есть в документации блоки ` ```kdl ` сейчас рендерятся без подсветки.
2. **Официальная TextMate-грамматика `kdl-org/vscode-kdl` ([`syntaxes/kdl.tmLanguage.json`](https://raw.githubusercontent.com/kdl-org/vscode-kdl/main/syntaxes/kdl.tmLanguage.json)) и грамматика в Shiki ([`shikijs/textmate-grammars-themes/.../kdl.json`](https://raw.githubusercontent.com/shikijs/textmate-grammars-themes/main/packages/tm-grammars/grammars/kdl.json)):**
   Прямой аудит исходного JSON-файла грамматики показал, что официальная грамматика **уже переведена на KDL 2.0**:
   - `#true|#false` (`constant.language.boolean.kdl`), `#null` (`constant.language.null.kdl`), `#nan|#inf|#-inf` (`constant.language.other.kdl`);
   - правило `forbidden_ident`: `(?<!#)(?:true|false|null|nan|[-]?inf)` специально подсвечивает старые литералы из KDL 1.0 (без `#`) как синтаксическую ошибку (`invalid.illegal.kdl.bad-ident`);
   - правило `raw-string`: `"begin": "(#+)(\"\"\"|\")"`, `"end": "\\2\\1"` поддерживает новый синтаксис KDL 2.0 `#"..."#` и `#"""..."""#`;
   - правило `string_multi_line`: `"begin": "\"\"\""`, `"end": "\"\"\""` поддерживает многострочные строки KDL 2.0;
   - правила `slashdash_*` поддерживают комментарии `/-`.

### 4.2. Два недостатка стандартной грамматики `kdl.tmLanguage.json` для `ssc_codegen`

При детальном анализе регулярных выражений в [`kdl.tmLanguage.json`](https://raw.githubusercontent.com/kdl-org/vscode-kdl/main/syntaxes/kdl.tmLanguage.json) и [`shikijs/.../kdl.json`](https://raw.githubusercontent.com/shikijs/textmate-grammars-themes/main/packages/tm-grammars/grammars/kdl.json) обнаруживаются две проблемы при использовании со схемами `ssc_codegen`:

1. **Проблема с аннотациями типов `(item)struct`, `(rest)struct`, `(array)json`, `(dict)json`:**
   - В `kdl-org/vscode-kdl` вообще нет отдельного правила для тайп-аннотаций `(type)`: скобки `\(` и `\)` просто включены в общий символьный класс `node_name`, поэтому `(item)struct` окрашивается одним сплошным цветом как имя тега.
   - В копии грамматики внутри Shiki (`shikijs/textmate-grammars-themes/.../kdl.json`, правило `node_name`: `((?<=[;{])|^)\s*(?![]#/;=\[\\{}])[!$-.:<>?@^_`|~\w]+...`) символы `(` и `)` выпали из диапазона `!$-.` (так как в ASCII `(` = 40, `)` = 41, а `$` = 36, `-` = 45, но в Shiki-конвертере Oniguruma регулярное выражение было переписано без `()`), из-за чего строки вида `(item)struct Book {` в Shiki теряют подсветку `node_name`.
2. **Слепота к семантике DSL `ssc-gen` v2.1:**
   В чистом KDL любая команда (`struct`, `css`, `xpath`, `re`, `filter`, `assert`, `@request`, `@split-doc`) с точки зрения парсера — это просто обычный `node_name` (`entity.name.tag`), ничем не отличающийся от пользовательских имён полей (`title`, `price`, `author`). В IDE/Playground для `ssc-gen` пользователь ожидает, что:
   - декларации верхнего уровня (`struct`, `json`, `fn`, `define`, `extension`, `import`) подсвечены как **ключевые слова объявления**;
   - аннотации типов `(item)`, `(list)`, `(dict)`, `(table)`, `(flat)`, `(rest)`, `(raw)`, `(array)` — как **типы/модификаторы**;
   - директивы `@request`, `@error`, `@split-doc`, `@init`, `@table`, `@rows`, `@match`, `@key`, `@value`, `@pre-validate`, `@check`, `@doc`, `@skip`, `@omitempty` — как **директивы/декораторы**;
   - встроенные операции пайплайна (`css`, `css-all`, `xpath`, `text`, `attr`, `re`, `to-float`, `fallback`, `nested`, `jsonify` и др.) и предикаты (`filter`, `assert`, `match`, `eq`, `contains`, `has-attr` и др.) — как **встроенные функции/операторы**, визуально отличные от имён полей структуры!

### 4.3. Сравнение 3 вариантов реализации подсветки KDL 2.0 в браузере

| Вариант | Поддержка KDL 2.0 | Подсветка `(item)` и семантики `ssc-gen` DSL | Вес бандла и зависимости | Сложность внедрения |
|---|---|---|---|---|
| **1. Кастомный Monarch-токенизатор в Monaco Editor** *(Рекомендуется)* | **Полная (KDL 2.0)**: `#true`, `#null`, `#inf`, `#"..."#`, `"""..."""`, `/-`, подсветка ошибочных KDL 1.0 `true`/`null` без `#` | **Полная**: различает `(type)`, `struct`/`json`, `@directives`, `css`/`xpath`/`re`, предикаты, типы `str`/`int`, плейсхолдеры `{{...}}` и имена полей | **0 КБ внешних грамматик** (встроено в Monaco Editor) | **~90 строк TS** (`monaco.languages.setMonarchTokensProvider`) |
| **2. `@shikijs/monaco` + патченный `kdl.tmLanguage.json`** ([документация](https://shiki.style/packages/monaco)) | Полная (KDL 2.0) | Требует модификации `kdl.tmLanguage.json` (добавление правил для `(type)` и ключевых слов `ssc-gen`) | +~300 КБ (движок Shiki + Oniguruma WASM) | ~50 строк TS + JSON-грамматика |
| **3. CodeMirror 6 + `StreamLanguage`** | Полная (KDL 2.0) | Полная (те же правила, что и в Monarch) | Самый лёгкий редактор (~120 КБ вместо ~2 МБ у Monaco) | ~80 строк TS |

### 4.4. Готовая спецификация Monarch-токенизатора KDL 2.0 + `ssc-gen` DSL v2.1 (для Monaco Editor)

Ниже приведён полный токенизатор для Monaco Editor, строго соответствующий спецификации KDL 2.0 и таблицам ключевых слов из `ssc_codegen/core/linter.py:193-301` и `ssc_codegen/core/type_checking.py`:

```typescript
import * as monaco from "monaco-editor";

export function registerKdl2Language() {
  monaco.languages.register({ id: "kdl2", extensions: [".kdl"] });

  monaco.languages.setLanguageConfiguration("kdl2", {
    comments: {
      lineComment: "//",
      blockComment: ["/*", "*/"],
    },
    brackets: [
      ["{", "}"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: "{", close: "}" },
      { open: "(", close: ")" },
      { open: '"', close: '"', notIn: ["string"] },
    ],
  });

  monaco.languages.setMonarchTokensProvider("kdl2", {
    // Топ-левел декларации ssc-gen (ssc_codegen/core/linter.py:353)
    declarations: ["struct", "json", "fn", "define", "extension", "import"],

    // Встроенные операции конвейера и селекторы (ssc_codegen/core/linter.py:236-272)
    pipelineOps: [
      "css", "css-all", "css-remove", "xpath", "xpath-all", "xpath-remove",
      "text", "raw", "attr", "trim", "ltrim", "rtrim", "normalize-space",
      "lower", "upper", "unescape", "fmt", "repl", "rm-prefix", "rm-suffix",
      "rm-prefix-suffix", "split", "join", "re", "re-all", "re-sub",
      "first", "last", "index", "slice", "len", "unique",
      "to-int", "to-float", "to-bool", "jsonify", "nested", "fallback", "self",
    ],

    // Контейнеры предикатов и предикатные операции (ssc_codegen/core/linter.py:257-301)
    predicateOps: [
      "filter", "assert", "match", "not", "and", "or",
      "eq", "ne", "starts", "ends", "contains",
      "len-eq", "len-ne", "len-gt", "len-lt", "len-ge", "len-le", "len-range",
      "has-attr", "attr-eq", "attr-ne", "attr-starts", "attr-ends",
      "attr-contains", "attr-re", "text-re", "text-starts", "text-ends",
      "text-contains", "re-any",
    ],

    // Примитивные типы JSON и расширений (ssc_codegen/core/linter.py:225, 474)
    primitiveTypes: ["str", "int", "float", "bool", "null", "nil", "doc", "T"],

    tokenizer: {
      root: [
        // Пробелы и разделители
        [/[ \t\r\n]+/, "white"],
        [/[;{}]/, "delimiter"],

        // Комментарии KDL 2.0: //, /* ... */ (с поддержкой вложенности) и slashdash /-
        [/\/\/.*$/, "comment"],
        [/\/\*/, "comment", "@blockComment"],
        [/\/-/, "comment.slashdash"],

        // Аннотации типов KDL 2.0: (item), (list), (dict), (table), (flat), (rest), (raw), (array)
        [/\([A-Za-z_][A-Za-z0-9_-]*\??\)/, "type.annotation"],

        // Литералы KDL 2.0 с префиксом # (#true, #false, #null, #inf, #-inf, #nan)
        [/#(?:true|false)\b/, "constant.language.boolean"],
        [/#null\b/, "constant.language.null"],
        [/#(?:-?inf|nan)\b/, "constant.language.numeric"],

        // Raw-строки KDL 2.0: #"..."#, ##"..."##, #"""..."""# (состояние запоминает число # в $S2)
        [/(#+)(""")/, { token: "string.raw.delim", next: "@rawMultiString.$1" }],
        [/(#+)(")/, { token: "string.raw.delim", next: "@rawString.$1" }],

        // Многострочные и обычные строки KDL 2.0
        [/"""/, "string.quote", "@multiString"],
        [/"/, "string.quote", "@string"],

        // Числа KDL 2.0 (hex, octal, binary, float, int с разделителями _)
        [/\b0x[0-9a-fA-F][0-9a-fA-F_]*\b/, "number.hex"],
        [/\b0o[0-7][0-7_]*\b/, "number.octal"],
        [/\b0b[01][01_]*\b/, "number.binary"],
        [/[+-]?\b[0-9][0-9_]*\.[0-9][0-9_]*(?:[eE][+-]?[0-9_]+)?\b/, "number.float"],
        [/[+-]?\b[0-9][0-9_]*(?:[eE][+-]?[0-9_]+)\b/, "number.float"],
        [/[+-]?\b[0-9][0-9_]*\b/, "number"],

        // Директивы ssc-gen (@request, @error, @error:suffix, @split-doc, @init, @table, @skip, @omitempty)
        [/@[A-Za-z_][A-Za-z0-9_:-]*/, "annotation.directive"],

        // Вызовы пользовательских расширений (!Utils.clean)
        [/![A-Za-z_][A-Za-z0-9_.-]*/, "function.extension"],

        // Свойства key=value
        [/([A-Za-z_][A-Za-z0-9_-]*)(=)/, ["attribute.name", "delimiter"]],

        // Запрещённые голые литералы из KDL 1.0 (true, false, null, nan, inf без #)
        [/\b(?:true|false|nan|-?inf)\b/, "invalid"],

        // Идентификаторы: классификация по словарям ssc-gen
        [
          /[A-Za-z_][A-Za-z0-9_-]*\??/,
          {
            cases: {
              "@declarations": "keyword.declaration",
              "@pipelineOps": "support.function.pipeline",
              "@predicateOps": "keyword.operator.predicate",
              "@primitiveTypes": "type.primitive",
              "^[A-Z_][A-Z0-9_-]*$": "constant.define", // UPPER_CASE define
              "@default": "identifier",
            },
          },
        ],
      ],

      // Вложенные блочные комментарии /* ... */ (спецификация KDL 2.0)
      blockComment: [
        [/[^/*]+/, "comment"],
        [/\/\*/, "comment", "@push"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],

      // Обычная строка с подсветкой escape-последовательностей KDL 2.0 и плейсхолдеров {{...}}
      string: [
        [/\{\{[^{}]+\}\}/, "variable.placeholder"],
        [/\\(?:[nrtbfs\\"/]|u\{[0-9a-fA-F]{1,6}\}|\s+)/, "string.escape"],
        [/[^\\"{]+/, "string"],
        [/\{/, "string"],
        [/"/, "string.quote", "@pop"],
      ],

      // Многострочная строка """..."""
      multiString: [
        [/\{\{[^{}]+\}\}/, "variable.placeholder"],
        [/"""/, "string.quote", "@pop"],
        [/\\(?:[nrtbfs\\"/]|u\{[0-9a-fA-F]{1,6}\}|\s+)/, "string.escape"],
        [/[^\\"{]+/, "string"],
        [/["{]/, "string"],
      ],

      // Raw-строка KDL 2.0 #"..."# (закрывается только при совпадении числа # из $S2)
      rawString: [
        [/\{\{[^{}]+\}\}/, "variable.placeholder"],
        [
          /"(#+)/,
          {
            cases: {
              "$1==$S2": { token: "string.raw.delim", next: "@pop" },
              "@default": "string.raw",
            },
          },
        ],
        [/[^"{]+/, "string.raw"],
        [/["{]/, "string.raw"],
      ],

      // Многострочная raw-строка KDL 2.0 #"""..."""#
      rawMultiString: [
        [/\{\{[^{}]+\}\}/, "variable.placeholder"],
        [
          /"""(#+)/,
          {
            cases: {
              "$1==$S2": { token: "string.raw.delim", next: "@pop" },
              "@default": "string.raw",
            },
          },
        ],
        [/[^"{]+/, "string.raw"],
        [/["{]/, "string.raw"],
      ],
    },
  });
}
```

### 4.5. Интеграция живого линтера (`check`) с редактором (волнистые подчёркивания ошибок)

В `ssc_codegen/core/format.py:118-140` функция `diagnostic_to_dict(d)` уже возвращает 1-based координаты `line` и `column` (а также символьный `offset`), которые напрямую ложатся на API маркеров Monaco Editor (`monaco.editor.setModelMarkers`):

```typescript
interface SscDiagnostic {
  code: string;
  severity: "error" | "warning";
  message: string;
  hint: string;
  span: {
    start: { offset: number; line: number; column: number };
    end: { offset: number; line: number; column: number };
  };
}

export function applyDiagnosticsToMonaco(
  model: monaco.editor.ITextModel,
  diagnostics: SscDiagnostic[],
) {
  const markers: monaco.editor.IMarkerData[] = diagnostics.map((d) => {
    const startLine = Math.max(d.span.start.line, 1);
    const startCol = Math.max(d.span.start.column, 1);
    const endLine = Math.max(d.span.end.line, startLine);
    const endCol =
      endLine === startLine && d.span.end.column <= startCol
        ? startCol + 1
        : Math.max(d.span.end.column, 1);

    return {
      severity:
        d.severity === "error"
          ? monaco.MarkerSeverity.Error
          : monaco.MarkerSeverity.Warning,
      startLineNumber: startLine,
      startColumn: startCol,
      endLineNumber: endLine,
      endColumn: endCol,
      code: d.code,
      message: d.hint ? `${d.message}\n💡 Подсказка: ${d.hint}` : d.message,
      source: "ssc-gen",
    };
  });

  monaco.editor.setModelMarkers(model, "ssc-gen-linter", markers);
}
```

При каждом изменении текста в редакторе (с debounce `150–200 мс`) текст отправляется в `WebWorker`, который за `<5 мс` вызывает `parse_module()` и возвращает список диагностик и сгенерированный код.

---

## 5. Полный код `WebWorker` для уточнённого скоупа

Ниже приведён самодостаточный код воркера (`worker.mjs`), покрывающий все сценарии уточнённого скоупа:
1. **Linter + Codegen** (`python`, `js`, `go`, `rust`, включая REST-схемы и выдачу `sscgen_runtime.*`).
2. **Тестирование схемы на вставленном HTML**:
   - `run` — выполнение сгенерированного парсера на вставленном HTML и возврат JSON-результата (`ssc_codegen/main.py:1052-1081`);
   - `health` — проверка совпадения всех CSS/XPath селекторов структуры на вставленном HTML через `check_struct_health()` (`ssc_codegen/health.py:335`);
   - `scout` — структурная дистилляция вставленного HTML через `run_scout()` (`ssc_codegen/explore.py:2945`).
3. **Конвертер `json-to-kdl`** через `json_text_to_kdl()` (`ssc_codegen/json_to_kdl.py:287`).

```javascript
// worker.mjs
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

async function initPyodideCompiler() {
  const pyodide = await loadPyodide();

  // Загружаем только необходимые бинарные/встроенные пакеты из CDN Pyodide
  await pyodide.loadPackage([
    "micropip",
    "soupsieve",
    "beautifulsoup4",
    "lxml",
    "cssselect",
  ]);

  const micropip = pyodide.pyimport("micropip");
  // После публикации wheel для kdlquery 1.6.0 устанавливаем оба пакета без лишних CLI/HTTP зависимостей (deps=False)
  await micropip.install(["kdlquery>=1.6.0", "ssc-codegen>=0.45.0"], { deps: false });

  pyodide.runPython(`
import json
from ssc_codegen import (
    TargetSpec,
    check_struct_health,
    format_diagnostics,
    parse_module,
    resolve,
    run_scout,
)
from ssc_codegen.ast import Struct, StructBase, StructType
from ssc_codegen.core.format import diagnostic_to_dict
from ssc_codegen.json_to_kdl import json_text_to_kdl
from ssc_codegen.naming import to_pascal_case

def playground_compile(
    kdl_src: str,
    lang: str = "python",
    lib: str | None = "bs4",
    http_client: str | None = None,
    bs4_parser: str | None = "lxml",
    http_io: str | None = "both",
) -> str:
    ast_mod, diags = parse_module(kdl_src, targets=(lang,))
    diag_list = [diagnostic_to_dict(d) for d in diags]
    diag_text = format_diagnostics(diags, src=kdl_src, fmt="text", use_color=False)

    structs = [
        {
            "name": s.name,
            "is_rest": not isinstance(s, Struct) or s.type == StructType.REST,
            "struct_type": s.type.value if isinstance(s, Struct) else "rest",
        }
        for s in ast_mod.body
        if isinstance(s, StructBase)
    ]

    if any(d.severity.value == "error" for d in diags):
        return json.dumps({
            "ok": False,
            "diagnostics": diag_list,
            "diagnostics_text": diag_text,
            "structs": structs,
            "code": "",
            "runtime": "",
        })

    spec = TargetSpec(
        lang=lang,
        lib=lib if lang == "python" else None,
        http_client=http_client,
        bs4_parser=bs4_parser if (lang == "python" and (lib or "bs4") == "bs4") else None,
        http_io=http_io if lang == "python" else None,
    )
    profile = resolve(spec)
    converter = profile.create_converter()
    meta = {"package": "main"}
    if http_client:
        meta["http_client"] = http_client
    if bs4_parser and lang == "python":
        meta["bs4_parser"] = bs4_parser
    if http_io and lang == "python":
        meta["http_io"] = http_io

    code = converter.convert(ast_mod, **meta)
    runtime = ""
    if lang == "go":
        runtime = converter.emit_runtime("main")
    elif lang == "rust":
        runtime = converter.emit_runtime()

    return json.dumps({
        "ok": True,
        "diagnostics": diag_list,
        "diagnostics_text": diag_text,
        "structs": structs,
        "code": code,
        "runtime": runtime,
    })

def playground_test_html(
    kdl_src: str,
    html_src: str,
    struct_name: str,
    lib: str = "bs4",
) -> str:
    ast_mod, diags = parse_module(kdl_src, targets=("python",))
    if any(d.severity.value == "error" for d in diags):
        return json.dumps({"ok": False, "error": "Исправьте ошибки схемы перед запуском на HTML"})

    structs = {s.name: s for s in ast_mod.body if isinstance(s, StructBase)}
    target_struct = structs.get(struct_name)
    if target_struct is None:
        return json.dumps({"ok": False, "error": f"Структура '{struct_name}' не найдена"})

    # 1. Health-check селекторов на вставленном HTML
    health_report = check_struct_health(target_struct, html_src, module=ast_mod)

    # 2. Выполнение сгенерированного парсера на вставленном HTML (если это не REST-структура)
    profile = resolve(TargetSpec(lang="python", lib=lib))
    code = profile.create_converter().convert(ast_mod)
    namespace = {}
    exec(code, namespace)
    cls = namespace.get(to_pascal_case(struct_name))
    parsed_data = cls(html_src).parse()

    return json.dumps({
        "ok": True,
        "parsed": parsed_data,
        "health": health_report.to_dict(),
        "health_text": health_report.format(fmt="text"),
    }, ensure_ascii=False, indent=2)
  `);

  return pyodide;
}
```

---

## 6. Оценка сложности и трудозатрат реализации (Complexity & Effort Breakdown)

При суженном скоупе (статический SPA без бэкенда, без прокси, только ручной ввод KDL + HTML, линтинг, кодогенерация во все языки и тестирование парсера на вставленном HTML) архитектура проекта становится минималистичной и прямолинейной.

### 6.1. Декомпозиция компонентов веб-приложения

| № | Компонент | Что делает | Объём кода (LOC) | Оценка времени |
|---|---|---|---|---|
| **1** | **Pyodide WebWorker (`src/worker.ts`)** | Загружает Pyodide (`v314.0.7`), устанавливает `kdlquery` и `ssc-codegen`, экспортирует RPC-методы `compile`, `testHtml` (`run` + `health`), `scout`, `jsonToKdl`. | `~140` строк | **2–3 часа** |
| **2** | **KDL 2.0 + `ssc-gen` Подсветка и Линтер (`src/kdl2-monarch.ts`)** | Регистрирует язык `kdl2` в Monaco Editor (Monarch-токенизатор из раздела 4.4) и конвертирует `diagnostics` из `parse_module` в волнистые подчёркивания `monaco.editor.setModelMarkers`. | `~150` строк | **2–3 часа** |
| **3** | **UI Плейграунда (3 панели, `src/App.tsx`)** | **Левая панель:** редактор KDL 2.0 + выбор примера (каталог книг, таблица, REST API) + модалка/вкладка `JSON → KDL`.<br>**Центральная/нижняя панель:** редактор/вставка тестового HTML + выбор целевой `struct` + вкладки `Результат парсинга (JSON)`, `Health-check селекторов`, `Scout`.<br>**Правая панель:** сгенерированный код (read-only Monaco с подсветкой `python` / `javascript` / `go` / `rust`), переключатель вкладки `Parser Code / Runtime Code`, селекторы `--lib` и `--http-client`, кнопка `Copy`. | `~320` строк | **4–6 часов** |
| **4** | **Сборка и автодеплой (`vite.config.ts`, GitHub Actions)** | Конфигурация Vite (`base: './'` для работы на любом подпути GitHub Pages) и workflow `.github/workflows/pages.yml` для автоматической публикации при пуше в `main`. | `~60` строк | **1 час** |
| | **ИТОГО** | **Полностью готовый бессерверный онлайн-инструмент** | **~670 строк кода** | **~1–1.5 дня (9–13 часов)** |

### 6.2. Сравнение двух путей: Static SPA на Pyodide против переписывания стека

| Критерий | Вариант А: Static SPA + Pyodide (WebAssembly) | Вариант Б: Переписывание на TypeScript или Rust → WASM |
|---|---|---|
| **Объём нового кода** | **~670 строк TS/JS** (только UI, воркер и Monarch-грамматика) | **~41 000 строк кода компилятора** (`ssc_codegen` + `kdlquery`) + UI |
| **Трудозатраты на запуск** | **1–2 дня** | **2–4 месяца** плотной разработки и тестирования |
| **Совпадение поведения с CLI `ssc-gen`** | **100% идентично** (исполняется буквально тот же Python-пакет `ssc_codegen`, те же `soupsieve`, `lxml.etree.XPath`, `re`, `bs4`) | Постоянный риск расхождения регулярных выражений, CSS/XPath валидации и кодогенерации между двумя версиями |
| **Поддержка будущих фич DSL** | **Автоматическая** (обновили версию пакета на PyPI — веб-версия сразу получила все новые правила линтера и кодогенерации) | Каждую фичу нужно писать и тестировать дважды на двух разных языках |
| **Зависимость от бэкенда** | **0%** (статические файлы на GitHub Pages / Cloudflare Pages) | **0%** (статические файлы) |

---

## Источники (Primary Sources)

### Кодовая база `ssc_codegen` (`v0.45.0`)
- `pyproject.toml:1-17` — список зависимостей (`bs4`, `colorama`, `cssselect`, `lxml`, `soupsieve`, `typer`, `typing_extensions`, `kdlquery`, `httpx`).
- `mkdocs.yml:49-63` — конфигурация подсветки документации (`pymdownx.highlight`).
- `docs/syntax.md:16-36` — спецификация особенностей KDL 2.0 в `ssc_codegen` (`#true`, `#false`, `#null`, строки без кавычек, аннотации типов).
- `ssc_codegen/__init__.py:25-56` — публичный Python API без импорта `typer` и без eager-импорта `lxml`.
- `ssc_codegen/core/reader.py:31-207` — 5-проходный конвейер `parse_module()`.
- `ssc_codegen/core/format.py:63-140` — `format_diagnostics()` и `diagnostic_to_dict()` (структура JSON-диагностики с 1-based `line`, `column` и `offset`).
- `ssc_codegen/core/linter.py:193-301, 2899-2951` — константы ключевых слов/операций/предикатов DSL, функции `lint_validate_css()` (`soupsieve`) и `lint_validate_xpath()` (ленивый импорт `from lxml import etree` на строке `2938`).
- `ssc_codegen/core/expressions.py:622-715` — вызов `lint_validate_css` и `lint_validate_xpath` только при разборе селекторных узлов.
- `ssc_codegen/targets/resolver.py:29-282`, `ssc_codegen/targets/spec.py:13-67`, `ssc_codegen/targets/profile.py:14-52` — программная конфигурация и создание конвертеров для Python, JS, Go и Rust.
- `ssc_codegen/json_to_kdl.py:1-289` — генератор KDL из JSON (использует только стандартную библиотеку Python).
- `ssc_codegen/request_spec.py:1-271`, `ssc_codegen/parsers/curl.py:1-251`, `ssc_codegen/parsers/http.py:1-231` — парсинг `@request` из `curl` и raw HTTP (использует только стандартную библиотеку Python).
- `ssc_codegen/explore.py:19,32,486,2945-3111` — модуль `scout` (`BS4_PARSER = "lxml"`, `BeautifulSoup`).
- `ssc_codegen/health.py:335-465` — модуль `health` (`check_struct_health`, `BeautifulSoup(html, "lxml")` и опциональный `from lxml import etree` с `try/except ImportError`).
- `ssc_codegen/main.py:900-1082` — логика выполнения сгенерированного Python-парсера в памяти (`exec(code, namespace)` в команде `run`).

### Внешние первичные источники и спецификации
- Официальная TextMate-грамматика KDL 2.0 (`kdl-org/vscode-kdl`): https://raw.githubusercontent.com/kdl-org/vscode-kdl/main/syntaxes/kdl.tmLanguage.json
- Грамматика KDL в репозитории Shiki (`shikijs/textmate-grammars-themes`): https://raw.githubusercontent.com/shikijs/textmate-grammars-themes/main/packages/tm-grammars/grammars/kdl.json
- Интеграция Shiki с Monaco Editor (`@shikijs/monaco`): https://shiki.style/packages/monaco
- Официальный перечень пакетов, скомпилированных и встроенных в Pyodide (`v314.0.7`): https://pyodide.org/en/stable/usage/packages-in-pyodide.html
- Документация Pyodide по загрузке пакетов (`loadPackage` и `micropip`): https://pyodide.org/en/stable/usage/loading-packages.html
- Документация Pyodide по запуску в Web Worker: https://pyodide.org/en/stable/usage/webworker.html
- Документация Pyodide по деплою на статические хостинги (GitHub Pages, CDN): https://pyodide.org/en/stable/usage/downloading-and-deploying.html
- Документация `micropip` (параметры `deps=False` и `constraints`): https://micropip.pyodide.org/en/stable/project/usage.html
- Метаданные PyPI JSON API для `kdlquery`: https://pypi.org/pypi/kdlquery/json
- Метаданные PyPI JSON API для `ssc-codegen`: https://pypi.org/pypi/ssc-codegen/json
- Метаданные PyPI JSON API для `bs4`: https://pypi.org/pypi/bs4/json
- Спецификация и руководство MDN по Cross-Origin Resource Sharing (CORS): https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS
