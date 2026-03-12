# Converters & Code Generation

> **Version:** 2.0  
> **Last Updated:** 2026-03-11

Руководство по конвертерам и генерации кода из KDL Schema DSL.

---

## Table of Contents

- [Overview](#overview)
- [Available Converters](#available-converters)
  - [Python Converters](#python-converters)
  - [JavaScript Converters](#javascript-converters)
- [Converter API](#converter-api)
  - [BaseConverter](#baseconverter)
  - [Inheritance & Extension](#inheritance--extension)
  - [Creating Custom Converters](#creating-custom-converters)
- [CLI Usage](#cli-usage)
- [Generated Code Examples](#generated-code-examples)
- [Advanced Topics](#advanced-topics)

---

## Overview

KDL Schema DSL компилируется в код на разных языках через систему **конвертеров**.

**Архитектура:**
```
KDL Schema → Parser → AST → Converter → Target Code
```

**Ключевые особенности:**
- **Типизированная генерация** - TypedDict для Python, interfaces для TypeScript
- **Мультиязычность** - один DSL → несколько целевых языков
- **Расширяемость** - простое создание новых конвертеров
- **Наследование** - переиспользование логики через `.extend()`

---

## Available Converters

### Python Converters

#### `py-bs4` - BeautifulSoup4

**Описание:** Генерирует Python код с использованием BeautifulSoup4.

**Зависимости:**
```python
beautifulsoup4
lxml  # используется как парсер для bs4
```

**Особенности:**
- `.select()` / `.select_one()` для CSS селекторов
- `.text` для извлечения текста
- `.get_attribute_list()` для атрибутов
- Поддержка всех операций DSL

**Генерируемый код:**
```python
from bs4 import BeautifulSoup, Tag
from typing import TypedDict, List, Union

class MainType(TypedDict):
    title: str
    links: List[str]

class Main:
    def __init__(self, document: Union[str, BeautifulSoup]):
        if isinstance(document, str):
            self._doc = BeautifulSoup(document.strip() or FALLBACK_HTML_STR, features='lxml')
        else:
            self._doc = document
    
    def parse(self) -> MainType:
        return self._parse(self._doc)
    
    def _parse(self, v: Union[Tag, BeautifulSoup]) -> MainType:
        v1 = v.select_one('h1')
        v2 = v1.text
        v3 = v2.strip()
        # ...
```

---

#### `py-lxml` - lxml

**Описание:** Генерирует Python код с использованием lxml (быстрее bs4).

**Зависимости:**
```python
lxml
cssselect  # для CSS селекторов
```

**Особенности:**
- `.cssselect()` для CSS селекторов
- `.xpath()` для XPath
- `.text_content()` для текста
- `.get()` для атрибутов
- Более производительный чем bs4

**Генерируемый код:**
```python
from lxml import html
from lxml.html import HtmlElement
from typing import TypedDict, List

class MainType(TypedDict):
    title: str

class Main:
    def __init__(self, document: Union[str, HtmlElement]):
        if isinstance(document, str):
            self._doc = html.fromstring(document.strip() or FALLBACK_HTML_STR)
        else:
            self._doc = document
    
    def _parse_title(self, v: HtmlElement) -> str:
        v1 = v.cssselect('h1')[0]
        v2 = v1.text_content()
        return v2.strip()
```

**Сравнение с bs4:**

| Операция | bs4 | lxml |
|----------|-----|------|
| CSS select | `.select_one()` | `.cssselect()[0]` |
| CSS all | `.select()` | `.cssselect()` |
| Text | `.text` | `.text_content()` |
| Attr | `.get_attribute_list()` | `.get(name, '')` |
| HTML | `str(el)` | `html.tostring(el)` |
| Has attr | `.has_attr()` | `name in el.attrib` |

---

### JavaScript Converters

#### `js-pure` - Pure JavaScript

**Описание:** Генерирует чистый JavaScript код (browser/Node.js).

**Зависимости:**
```javascript
// Browser: DOMParser встроен
// Node.js: jsdom или cheerio
```

**Особенности:**
- `.querySelector()` / `.querySelectorAll()` для CSS
- `.textContent` для текста
- `.getAttribute()` для атрибутов
- Regex с JS синтаксисом

**Генерируемый код:**
```javascript
class Main {
    constructor(document) {
        if (typeof document === 'string') {
            const parser = new DOMParser();
            this._doc = parser.parseFromString(document, 'text/html');
        } else {
            this._doc = document;
        }
    }
    
    parse() {
        return this._parse(this._doc);
    }
    
    _parse(v) {
        let v1 = v.querySelector('h1');
        let v2 = v1.textContent;
        return v2.trim();
    }
}
```

---

## Converter API

### BaseConverter

Базовый класс для всех конвертеров:

```python
class BaseConverter:
    def __init__(self, var_name: str = "v", indent: str = "    "):
        self.var_name = var_name
        self.indent = indent
        self._pre_callbacks: dict[type, Callable] = {}
        self._post_callbacks: dict[type, Callable] = {}
    
    def __call__(self, node_type: type):
        """Декоратор для регистрации handler'а."""
        def decorator(func: Callable):
            self._pre_callbacks[node_type] = func
            return func
        return decorator
    
    def post(self, node_type: type):
        """Декоратор для post-обработки."""
        def decorator(func: Callable):
            self._post_callbacks[node_type] = func
            return func
        return decorator
    
    def extend(self) -> "BaseConverter":
        """Создать конвертер-наследник."""
        child = BaseConverter(var_name=self.var_name, indent=self.indent)
        child._pre_callbacks = dict(self._pre_callbacks)
        child._post_callbacks = dict(self._post_callbacks)
        return child
```

---

### Inheritance & Extension

**Создание конвертера через наследование:**

```python
from ssc_codegen.kdl.converters import py_bs4
from ssc_codegen.kdl.converters.base import BaseConverter

# Наследуем все handlers от bs4
PY_LXML_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()

# Переопределяем только специфичные для lxml handlers
@PY_LXML_CONVERTER(CssSelect)
def pre_expr_css_select(node: CssSelect, ctx: ConverterContext):
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.cssselect({query})[0]"

@PY_LXML_CONVERTER(Text)
def pre_expr_text(node: Text, ctx: ConverterContext):
    if node.accept == VariableType.DOCUMENT:
        return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.text_content()"
    return f"{ctx.indent}{ctx.nxt} = [i.text_content() for i in {ctx.prv}]"
```

**Иерархия конвертеров:**

```
BaseConverter (базовый)
    ↓
PY_BASE_CONVERTER (общая Python логика)
    ↓
    ├→ PY_BS4_CONVERTER (BeautifulSoup4)
    └→ PY_LXML_CONVERTER (lxml)

JS_BASE_CONVERTER (общая JS логика)
    ↓
    ├→ JS_PURE_CONVERTER (чистый JS)
    ├→ JS_JQUERY_CONVERTER (jQuery - будущее)
    └→ JS_CHEERIO_CONVERTER (Cheerio - будущее)
```

---

### Creating Custom Converters

**Шаги создания кастомного конвертера:**

1. **Наследоваться от существующего конвертера:**

```python
from ssc_codegen.kdl.converters import py_bs4

MY_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()
```

2. **Переопределить необходимые handlers:**

```python
from ssc_codegen.kdl.ast import CssSelect, Text

@MY_CONVERTER(CssSelect)
def my_css_select(node: CssSelect, ctx: ConverterContext):
    # Кастомная реализация
    query = repr(node.query)
    return f"{ctx.indent}{ctx.nxt} = my_custom_select({ctx.prv}, {query})"

@MY_CONVERTER(Text)
def my_text_extract(node: Text, ctx: ConverterContext):
    return f"{ctx.indent}{ctx.nxt} = extract_text({ctx.prv})"
```

3. **Зарегистрировать в main.py:**

```python
# В ssc_codegen/kdl/main.py

class Target(str, enum.Enum):
    PY_BS4 = "py-bs4"
    PY_LXML = "py-lxml"
    MY_CUSTOM = "my-custom"  # Добавить

def _get_converter(target: Target):
    if target == Target.MY_CUSTOM:
        from my_package.converters import MY_CONVERTER
        return MY_CONVERTER
    # ...
```

---

### ConverterContext

Контекст для handlers:

```python
@dataclass
class ConverterContext:
    prv: str        # Имя предыдущей переменной (v1, v2, ...)
    nxt: str        # Имя следующей переменной
    index: int      # Индекс в pipeline
    indent: str     # Отступ (4 пробела по умолчанию)
```

**Пример использования:**

```python
@CONVERTER(Trim)
def pre_expr_trim(node: Trim, ctx: ConverterContext):
    # ctx.prv = "v2", ctx.nxt = "v3"
    return f"{ctx.indent}{ctx.nxt} = {ctx.prv}.strip()"
    # Результат: "    v3 = v2.strip()"
```

---

## CLI Usage

### Basic Commands

```bash
# Генерация с указанием target
python -m ssc_codegen.kdl.main generate schema.kdl -t py-bs4

# Указать выходную директорию
python -m ssc_codegen.kdl.main generate schema.kdl -t py-lxml -o output/

# Генерация из директории
python -m ssc_codegen.kdl.main generate schemas/ -t py-bs4

# Проверка без генерации
python -m ssc_codegen.kdl.main check schema.kdl

# Пропустить линтинг
python -m ssc_codegen.kdl.main generate schema.kdl -t py-bs4 --skip-lint

# Verbose режим
python -m ssc_codegen.kdl.main generate schema.kdl -t py-bs4 -v
```

### Targets

| Target | Description | Output |
|--------|-------------|--------|
| `py-bs4` | Python + BeautifulSoup4 | `.py` |
| `py-lxml` | Python + lxml | `.py` |
| `js-pure` | Pure JavaScript | `.js` |

---

## Generated Code Examples

### Example 1: Simple Item Structure

**DSL:**
```kdl
struct Article {
    title {
        css "h1"
        text
        trim
    }
    author {
        css ".author"
        text
    }
}
```

**Generated (py-bs4):**
```python
from bs4 import BeautifulSoup, Tag
from typing import TypedDict, Union

class ArticleType(TypedDict):
    title: str
    author: str

class Article:
    def __init__(self, document: Union[str, BeautifulSoup]):
        if isinstance(document, str):
            self._doc = BeautifulSoup(document.strip() or FALLBACK_HTML_STR, features='lxml')
        else:
            self._doc = document
    
    def parse(self) -> ArticleType:
        return self._parse(self._doc)
    
    def _parse(self, v: Union[Tag, BeautifulSoup]) -> ArticleType:
        return {
            "title": self._parse_title(v),
            "author": self._parse_author(v),
        }
    
    def _parse_title(self, v: Union[Tag, BeautifulSoup]) -> str:
        v1 = v.select_one('h1')
        v2 = v1.text
        v3 = v2.strip()
        return v3
    
    def _parse_author(self, v: Union[Tag, BeautifulSoup]) -> str:
        v1 = v.select_one('.author')
        v2 = v1.text
        return v2
```

---

### Example 2: List Structure with Nested

**DSL:**
```kdl
struct Book type=list {
    @split-doc { css-all ".book" }
    
    title { css ".title"; text }
    price { css ".price"; text; re #"(\d+)"#; to-float }
}

struct Catalogue {
    books { nested Book }
    total { css-all ".book"; len }
}
```

**Generated (py-lxml):**
```python
from lxml import html
from lxml.html import HtmlElement
from typing import TypedDict, List, Union

class BookType(TypedDict):
    title: str
    price: float

class Book:
    @staticmethod
    def _parse_item(v: HtmlElement) -> BookType:
        return {
            "title": Book._parse_title(v),
            "price": Book._parse_price(v),
        }
    
    @staticmethod
    def _parse_title(v: HtmlElement) -> str:
        v1 = v.cssselect('.title')[0]
        v2 = v1.text_content()
        return v2
    
    @staticmethod
    def _parse_price(v: HtmlElement) -> float:
        v1 = v.cssselect('.price')[0]
        v2 = v1.text_content()
        v3 = re.search(r'(\d+)', v2)[1]
        v4 = float(v3)
        return v4

class CatalogueType(TypedDict):
    books: List[BookType]
    total: int

class Catalogue:
    def __init__(self, document: Union[str, HtmlElement]):
        if isinstance(document, str):
            self._doc = html.fromstring(document.strip() or FALLBACK_HTML_STR)
        else:
            self._doc = document
    
    def parse(self) -> CatalogueType:
        return self._parse(self._doc)
    
    def _parse_books(self, v: HtmlElement) -> List[BookType]:
        v1 = v.cssselect('.book')
        v2 = [Book._parse_item(i) for i in v1]
        return v2
    
    def _parse_total(self, v: HtmlElement) -> int:
        v1 = v.cssselect('.book')
        v2 = len(v1)
        return v2
```

---

### Example 3: Transform with Auto-Imports

**DSL:**
```kdl
transform decode-base64 accept=STRING return=STRING {
    py {
        import "from base64 import b64decode"
        code "{{NXT}} = b64decode({{PRV}}).decode('utf-8')"
    }
}

struct Main {
    content {
        css "#data"
        attr "data-encoded"
        transform decode-base64
    }
}
```

**Generated:**
```python
from base64 import b64decode  # ← Автоматически добавлен
from bs4 import BeautifulSoup, Tag
from typing import TypedDict, Union

class MainType(TypedDict):
    content: str

class Main:
    def _parse_content(self, v: Union[Tag, BeautifulSoup]) -> str:
        v1 = v.select_one('#data')
        v2 = ' '.join(v1.get_attribute_list('data-encoded'))
        v3 = b64decode(v2).decode('utf-8')  # ← Transform применен
        return v3
```

---

## Advanced Topics

### Custom Type Mappings

Добавление кастомных типов для генерации:

```python
MY_CONVERTER = py_bs4.PY_BASE_CONVERTER.extend()

# Добавить кастомный тип
MY_TYPES = py_bs4.PY_TYPES.copy()
MY_TYPES[VariableType.CUSTOM] = "MyCustomType"

@MY_CONVERTER(Field)
def pre_struct_field(node: Field, ctx: ConverterContext):
    ret_type = MY_TYPES.get(node.ret, "Any")
    # ...
```

---

### Post-Processing

Добавление post-обработки для форматирования кода:

```python
@MY_CONVERTER.post(Module)
def post_module(node: Module, generated_code: list[str]):
    # Форматирование через black
    import black
    code_str = "\n".join(generated_code)
    return black.format_str(code_str, mode=black.Mode()).split("\n")
```

---

### Multi-File Generation

Генерация нескольких файлов из одного DSL:

```python
# В конвертере можно генерировать дополнительные файлы
@MY_CONVERTER(Module)
def pre_module(node: Module, ctx: ConverterContext):
    # Генерация основного файла
    main_code = [...]
    
    # Генерация типов в отдельный файл
    types_code = generate_types(node)
    with open("types.py", "w") as f:
        f.write("\n".join(types_code))
    
    return main_code
```

---

### Testing Generated Code

```python
# Пример теста для сгенерированного кода
def test_generated_parser():
    from generated.catalogue import Catalogue
    
    html = """
    <div class="book">
        <span class="title">Book 1</span>
        <span class="price">$25.99</span>
    </div>
    """
    
    parser = Catalogue(html)
    result = parser.parse()
    
    assert result["books"][0]["title"] == "Book 1"
    assert result["books"][0]["price"] == 25.99
```

---

## Summary

**Ключевые моменты:**

1. **Три готовых конвертера:**
   - `py-bs4` - BeautifulSoup4 (универсальный)
   - `py-lxml` - lxml (производительный)
   - `js-pure` - Pure JavaScript

2. **Простое расширение через `.extend()`:**
   - Наследование всех handlers
   - Переопределение только нужных
   - Чистый API

3. **Автоматические фичи:**
   - TypedDict / interfaces для типов
   - Импорты из transforms
   - Error handling с fallback

4. **CLI интеграция:**
   - `generate` - генерация кода
   - `check` - только линтинг
   - Поддержка директорий

**Best Practices:**
- Используйте `py-lxml` для production (быстрее)
- Используйте `py-bs4` для прототипирования (проще отладка)
- Всегда запускайте `check` перед генерацией
- Добавляйте `@doc` для документирования схем

