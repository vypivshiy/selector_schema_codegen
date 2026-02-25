"""TypedDict definitions for AST node kwargs."""
from typing import TypedDict, Literal
from typing_extensions import NotRequired

# ========== SELECTOR MODES ==========
SelectorMode = Literal["css", "xpath"]

# ========== EXTRACT MODES ==========
ExtractMode = Literal["text", "attr", "raw", "attrs_map"]

# ========== STRING OPERATIONS ==========
StringOpMode = Literal[
    "trim", "ltrim", "rtrim",
    "rm_prefix", "rm_suffix", "rm_prefix_suffix",
]

# ========== REGEX MODES ==========
RegexMode = Literal["re", "re_all", "re_sub"]

# ========== CAST TYPES ==========
CastTarget = Literal["int", "float", "bool", "list_int", "list_float"]

# ========== FILTER OPERATORS ==========
FilterCompareOp = Literal["eq", "ne", "gt", "lt", "ge", "le"]
FilterStringOp = Literal["starts", "ends", "contains", "in"]

# ========== STRUCT TYPES ==========
StructTypeLiteral = Literal["item", "list", "dict", "table"]

# ========== ASSERT OPERATORS ==========
AssertCmpOp = Literal["eq", "ne"]

# ========== JSON FIELD TYPES ==========
# Примитивные типы для полей json-маппинга
JsonFieldType = Literal["str", "int", "float", "bool", "null", "any"]


# ========== KWARGS TYPE DEFINITIONS ==========

class KwargsSelect(TypedDict):
    """Селекторы CSS/XPath."""
    mode: SelectorMode       # "css" | "xpath"
    query: str               # строка-селектор (без псевдоэлементов)
    is_all: bool             # False → один элемент, True → все


class KwargsExtract(TypedDict):
    """Извлечение данных из элемента."""
    mode: ExtractMode        # "text" | "attr" | "raw" | "attrs_map"
    key: NotRequired[str]    # имя атрибута (только для mode="attr")


class KwargsStringOp(TypedDict):
    """Строковые операции."""
    op: StringOpMode
    substr: NotRequired[str]              # для rm_prefix / rm_suffix / rm_prefix_suffix
    old: NotRequired[str]                 # для replace (устаревший путь, см. Replace)
    new: NotRequired[str]                 # для replace (устаревший путь)
    replacements: NotRequired[dict[str, str]]  # для repl_map


class KwargsRegex(TypedDict):
    """Regex операции."""
    mode: RegexMode
    pattern: str
    group: NotRequired[int]          # номер группы (для re/re_sub)
    repl: NotRequired[str]           # строка замены (для re_sub)
    ignore_case: NotRequired[bool]
    dotall: NotRequired[bool]


class KwargsCast(TypedDict):
    """Каст типов."""
    target: CastTarget


class KwargsFilterCompare(TypedDict):
    """Фильтры сравнения."""
    op: FilterCompareOp
    value: str | int | float
    is_len: NotRequired[bool]   # True → сравниваем длину строки


class KwargsFilterString(TypedDict):
    """Строковые фильтры."""
    op: FilterStringOp
    values: tuple[str, ...]     # один или несколько вариантов (OR семантика)


class KwargsFilterDef(TypedDict):
    """Именованный filter-define (только для inline-распаковки в DSL)."""
    name: str                   # идентификатор фильтра, напр. "F-IMAGE-PNG"


class KwargsStruct(TypedDict):
    """Парсер структуры."""
    name: str
    struct_type: StructTypeLiteral
    docstring: NotRequired[str]


class KwargsField(TypedDict):
    """Поле структуры / typedef / json."""
    name: str


class KwargsTable(TypedDict):
    """Конфигурация таблицы (css-селектор самой таблицы)."""
    selector: str


class KwargsTableMatchKey(TypedDict):
    """
    -match: критерий поиска нужной строки таблицы.
    body содержит пайплайн фильтрации (css → text → eq "UPC" и т.п.)
    """
    pass  # нет обязательных kwargs, всё в body


class KwargsTableMatchValue(TypedDict):
    """
    -value: пайплайн извлечения значения из найденной строки.
    body содержит пайплайн (css → text → trim и т.п.)
    """
    pass  # нет обязательных kwargs, всё в body


class KwargsTableMatch(TypedDict):
    """Match-блок внутри поля таблицы (условия отбора строки)."""
    conditions: list[str]


class KwargsAssert(TypedDict):
    """Assert операция."""
    op: AssertCmpOp
    value: str | int | float
    msg: NotRequired[str]


class KwargsDefault(TypedDict):
    """Default значение (?? оператор)."""
    value: str | int | float | bool | list | None


class KwargsJsonDef(TypedDict):
    """
    Определение JSON-маппинга (top-level).
    json Author { ... } / json Quote array=#true { ... }
    """
    name: str
    is_array: NotRequired[bool]   # array=#true → список объектов


class KwargsJsonDefField(TypedDict):
    """
    Поле JSON-маппинга.
    name str / tags str {} / author Author
    """
    name: str
    type_name: str               # "str", "int", "float", "bool", "null", "any" или имя другого JsonDef
    is_optional: NotRequired[bool]  # type_name содержит "|null"
    is_array: NotRequired[bool]     # поле является массивом (body не пустой)
    ref_name: NotRequired[str]      # если type_name ссылается на другой JsonDef


class KwargsDocstirng(TypedDict):
    value: str
