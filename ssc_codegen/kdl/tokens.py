from enum import IntEnum, auto


class VariableType(IntEnum):
    """Типы данных в пайплайне."""
    ANY = auto()

    # Документы
    DOCUMENT = auto()
    LIST_DOCUMENT = auto()

    # Строки
    STRING = auto()
    LIST_STRING = auto()

    # Числа
    INT = auto()
    LIST_INT = auto()
    FLOAT = auto()
    LIST_FLOAT = auto()

    # Логический
    BOOL = auto()

    # Специальные
    NULL = auto()
    NESTED = auto()    # ссылка на вложенную схему
    JSON = auto()      # JSON структура
    LIST_ANY = auto()  # любой список (для generic-операций: Index, Len)


class StructType(IntEnum):
    """Типы схем (стратегии парсинга)."""
    ITEM = auto()    # одиночный объект
    LIST = auto()    # список объектов
    DICT = auto()    # словарь (ключ-значение)
    TABLE = auto()   # таблица (ключ-значение из <table>)


class TokenType(IntEnum):
    """
    Список токенов для AST.
    Принцип: один токен + модификаторы в kwargs вместо отдельных токенов.
    """

    # ========== MODULE LEVEL ==========
    MODULE = auto()               # Корень AST
    DEFINE = auto()               # Константы / text substitution (было const)
    DOCSTRING = auto()            # Документация
    IMPORTS = auto()              # Импорты
    UTILITIES = auto()            # Хелпер-функции

    # ========== STRUCT LEVEL ==========
    STRUCT = auto()               # Схема (ITEM, LIST, DICT, TABLE)
    STRUCT_INIT = auto()          # Конструктор
    STRUCT_FIELD = auto()         # Поле схемы
    STRUCT_SPLIT = auto()         # __SPLIT_DOC__
    STRUCT_PRE_VALIDATE = auto()  # Валидация документа перед парсингом
    STRUCT_PARSE = auto()         # Метод parse()
    STRUCT_NESTED = auto()        # Вложенная схема (ссылка по имени)

    # ========== TABLE SPECIAL ==========
    TABLE_CONFIG = auto()         # Конфиг таблицы (css-селектор таблицы)
    TABLE_ROW = auto()            # Селектор строк (-row)
    TABLE_MATCH_KEY = auto()      # Критерий поиска строки (-match)
    TABLE_MATCH_VALUE = auto()    # Извлечение значения из строки (-value)

    # ========== TYPE DEFINITIONS ==========
    TYPEDEF = auto()              # Определение типа
    TYPEDEF_FIELD = auto()        # Поле типа

    # ========== JSON MAPPING ==========
    # json Author { name str } / json Quote array=#true
    JSON_DEF = auto()             # Определение JSON-маппинга (top-level)
    JSON_DEF_FIELD = auto()       # Поле JSON-маппинга (с типом и опциональностью)

    # ========== JSON OUTPUT (struct field result) ==========
    JSON_STRUCT = auto()          # JSON-структура как результат поля
    JSON_FIELD = auto()           # Поле JSON-структуры

    # ========== STANDALONE FILTER DEFINE ==========
    # filter F-NAME { ... } — define-подобный, только для inline-распаковки в DSL
    FILTER_DEF = auto()           # Определение именованного фильтра

    # ========== CONTROL FLOW ==========
    DEFAULT = auto()              # Значение по умолчанию (?? оператор)
    DEFAULT_START = auto()        # Начало блока default
    DEFAULT_END = auto()          # Конец блока default
    RETURN = auto()               # Return expression

    # ========== SELECTORS ==========
    # kwargs: mode="css"|"xpath", query: str, is_all: bool
    SELECT = auto()               # CSS/XPath селектор (универсальный)
    REMOVE = auto()               # Удаление элементов из документа

    # ========== DATA EXTRACTION ==========
    # kwargs: mode="text"|"attr"|"raw"|"attrs_map", key: str | None
    EXTRACT = auto()              # Извлечение данных (универсальный)

    # ========== STRING OPERATIONS ==========
    # kwargs: op="trim"|"ltrim"|"rtrim"|"rm_prefix"|"rm_suffix"|"rm_prefix_suffix"
    STRING = auto()               # Строковые операции (универсальный)
    FORMAT = auto()               # Форматирование (fmt)
    REPLACE = auto()              # Замена подстроки (repl)
    REPLACE_MAP = auto()          # Замена по мапе (repl_map)
    JOIN = auto()                 # Join списка в строку
    UNESCAPE = auto()             # Unescape строки

    # ========== REGEX ==========
    # kwargs: mode="re"|"re_all"|"re_sub", pattern: str, group: int, repl: str
    REGEX = auto()                # Regex операции (универсальный)

    # ========== ARRAY OPERATIONS ==========
    INDEX = auto()                # Индекс (index, first, last)
    LEN = auto()                  # Длина массива (to_len)
    UNIQUE = auto()               # Уникальные значения (дубликаты убираются)

    # ========== TYPE CASTS ==========
    # kwargs: target="int"|"float"|"bool"|"list_int"|"list_float"
    CAST = auto()                 # Каст типов (универсальный)
    JSONIFY = auto()              # Десериализация JSON-строки в структуру
    JSONIFY_DYNAMIC = auto()      # Динамический JSON (без схемы)
    NESTED = auto()               # Вложенная схема (cast → NESTED тип)

    # ========== FILTERS — STRING ==========
    FILTER = auto()               # Filter блок для строк
    FILTER_CMP = auto()           # Сравнение (eq, ne, gt, lt, ge, le)
    FILTER_STR = auto()           # Строковые (starts, ends, contains, in)
    FILTER_RE = auto()            # Regex фильтр
    FILTER_LEN = auto()           # Фильтр по длине строки

    # ========== FILTERS — DOCUMENT ==========
    FILTER_DOC = auto()           # Filter блок для документов
    FILTER_DOC_SELECT = auto()    # Селектор-фильтр (css, xpath)
    FILTER_DOC_ATTR = auto()      # Атрибут-фильтр (eq, starts, ends, contains, re)
    FILTER_DOC_TEXT = auto()      # Текст-фильтр (has_text, is_regex_text)
    FILTER_DOC_RAW = auto()       # Raw-фильтр (has_raw, is_regex_raw)
    FILTER_DOC_HAS_ATTR = auto()  # Has-attribute фильтр

    # ========== LOGIC OPERATORS ==========
    LOGIC_AND = auto()            # Логическое И
    LOGIC_OR = auto()             # Логическое ИЛИ
    LOGIC_NOT = auto()            # Логическое НЕ (инверсия)

    # ========== VALIDATION / ASSERTS ==========
    ASSERT = auto()               # Assert блок
    ASSERT_CMP = auto()           # Сравнение (is_equal, is_not_equal)
    ASSERT_RE = auto()            # Regex-валидация (is_re, any_re, all_re)
    ASSERT_SELECT = auto()        # Селектор-валидация (is_css, is_xpath)
    ASSERT_HAS_ATTR = auto()      # Has-attribute валидация
    ASSERT_CONTAINS = auto()      # Contains-валидация

    # ========== TRANSFORMS ==========
    TRANSFORM = auto()            # Кастомная трансформация
    TRANSFORM_IMPORTS = auto()    # Импорты для трансформаций

    # ========== TABLE FIELD MATCH ==========
    TABLE_MATCH = auto()          # Match-блок внутри поля таблицы