# Расширение линтера KDL DSL

Линтер поддерживает добавление пользовательских правил и модификацию существующих.

## Добавление пользовательских правил

### Простое правило

```python
from ssc_codegen.kdl.linter import LINTER, ErrorCode

@LINTER.rule("my-custom-op")
def rule_my_custom_op(node, ctx):
    """Проверка пользовательской операции"""
    args = ctx.get_args(node)
    if not args:
        ctx.error(
            node,
            code=ErrorCode.MISSING_ARGUMENT,
            message="'my-custom-op' requires an argument",
            hint="example: my-custom-op value"
        )
```

### Правило для нескольких операций

```python
@LINTER.rule("op1", "op2", "op3")
def rule_multiple_ops(node, ctx):
    """Одно правило для нескольких операций"""
    name = ctx.node_name(node)
    args = ctx.get_args(node)
    
    if len(args) == 0:
        ctx.error(
            node,
            code=ErrorCode.MISSING_ARGUMENT,
            message=f"'{name}' requires at least one argument",
            hint=f"example: {name} value"
        )
```

## Замена существующих правил

### Использование параметра `replace=True`

```python
@LINTER.rule("css", replace=True)
def strict_css_rule(node, ctx):
    """Более строгая проверка CSS селекторов"""
    args = ctx.get_args(node)
    
    if args and not args[0].startswith((".", "#", "[")):
        ctx.warning(
            node,
            code=ErrorCode.INVALID_ARGUMENT,
            message="CSS selector should start with ., #, or [",
            hint="use class, id, or attribute selectors"
        )
```

## Удаление правил

### Удалить все правила для операции

```python
# Отключить все проверки для deprecated-op
LINTER.remove_rule("deprecated-op")
```

### Удалить конкретное правило

```python
# Сначала определяем правило
@LINTER.rule("css")
def my_custom_css_check(node, ctx):
    pass

# Позже удаляем именно это правило
LINTER.remove_rule("css", my_custom_css_check)
```

## Просмотр зарегистрированных правил

```python
# Получить количество правил для каждой операции
rules = LINTER.list_rules()

print(f"CSS rules: {rules.get('css', 0)}")
print(f"Total operations with rules: {len(rules)}")

# Вывести все операции
for op_name, count in sorted(rules.items()):
    print(f"{op_name}: {count} rule(s)")
```

## Доступ к контексту в правилах

### Навигация по CST

```python
@LINTER.rule("my-op")
def rule_my_op(node, ctx):
    # Получить имя узла
    name = ctx.node_name(node)
    
    # Получить аргументы
    args = ctx.get_args(node)  # list[str]
    raw_args = ctx.get_raw_args(node)  # list[RawArg] с is_identifier
    
    # Получить property
    value = ctx.get_prop(node, "key")
    
    # Получить дочерние узлы
    children = ctx.get_children_nodes(node)
    
    # Проверить пустой блок
    if ctx.has_empty_block(node):
        ctx.error(node, ErrorCode.EMPTY_BLOCK, "Block is empty", "")
```

### Работа с defines

```python
@LINTER.rule("my-op")
def rule_with_defines(node, ctx):
    args = ctx.get_args(node)
    
    if args:
        arg = args[0]
        
        # Проверить, является ли аргумент ссылкой на define
        if ctx.is_define_ref(arg):
            # Разрешить scalar define
            value = ctx.resolve_scalar_arg(arg)
            if value:
                print(f"Define {arg} = {value}")
```

### Работа с путем (breadcrumb)

```python
@LINTER.rule("my-op")
def rule_with_path(node, ctx):
    # Получить текущий путь (например, "struct MyStruct > field > css")
    path = ctx.current_path
    
    # Использовать context manager для автоматического push/pop
    with ctx.path.scope("sub-section"):
        # Путь автоматически обновлен
        # После выхода из блока путь восстановлен
        pass
```

### Reporting errors

```python
@LINTER.rule("my-op")
def rule_with_errors(node, ctx):
    # Error
    ctx.error(
        node,
        code=ErrorCode.MISSING_ARGUMENT,
        message="Required argument missing",
        hint="add argument: my-op value"
    )
    
    # Warning
    ctx.warning(
        node,
        code=ErrorCode.DEPRECATED_SYNTAX,
        message="This syntax is deprecated",
        hint="use new-op instead"
    )
```

## Коды ошибок (ErrorCode)

Доступные категории:

### Syntax errors (E001-E099)
- `MISSING_ARGUMENT` (E001)
- `INVALID_ARGUMENT` (E002)
- `EMPTY_BLOCK` (E003)
- `UNEXPECTED_CHILDREN` (E004)

### Type errors (E100-E199)
- `TYPE_MISMATCH` (E100)
- `INCOMPATIBLE_OPERATION` (E101)

### Semantic errors (E200-E299)
- `UNKNOWN_OPERATION` (E200)
- `UNKNOWN_FIELD` (E201)
- `MISSING_REQUIRED_FIELD` (E202)
- `INVALID_FIELD_FOR_TYPE` (E203)

### Reference errors (E300-E399)
- `UNDEFINED_REFERENCE` (E300)
- `INIT_FIELD_NOT_FOUND` (E301)
- `DEFINE_NOT_FOUND` (E302)

### Structure errors (E400-E499)
- `INVALID_STRUCT_TYPE` (E400)
- `MISSING_SPECIAL_FIELD` (E401)

### Warnings (W001-W999)
- `DEPRECATED_SYNTAX` (W001)
- `UNUSED_FIELD` (W002)

## Примеры использования

### Кастомный валидатор для URL

```python
import re
from ssc_codegen.kdl.linter import LINTER, ErrorCode

URL_PATTERN = re.compile(r'^https?://')

@LINTER.rule("validate-url")
def rule_validate_url(node, ctx):
    """Проверить что аргумент является URL"""
    args = ctx.get_args(node)
    
    if not args:
        ctx.error(
            node,
            code=ErrorCode.MISSING_ARGUMENT,
            message="'validate-url' requires a URL argument",
            hint="example: validate-url \"https://example.com\""
        )
        return
    
    url = args[0]
    if not URL_PATTERN.match(url):
        ctx.error(
            node,
            code=ErrorCode.INVALID_ARGUMENT,
            message=f"Invalid URL: {url}",
            hint="URL must start with http:// or https://"
        )
```

### Проверка минимального количества дочерних элементов

```python
@LINTER.rule("my-container")
def rule_my_container(node, ctx):
    """Контейнер должен иметь минимум 2 дочерних элемента"""
    children = ctx.get_children_nodes(node)
    
    if len(children) < 2:
        ctx.error(
            node,
            code=ErrorCode.MISSING_REQUIRED_FIELD,
            message="'my-container' requires at least 2 children",
            hint="add more child operations"
        )
```

## Best Practices

1. **Используйте подходящие ErrorCode** - выбирайте код, который лучше всего описывает ошибку
2. **Пишите полезные hint-сообщения** - включайте примеры исправления
3. **Проверяйте все условия** - не предполагайте, что данные всегда корректны
4. **Используйте `replace=True` осторожно** - это полностью заменяет существующие правила
5. **Документируйте кастомные правила** - добавляйте docstring к функциям правил
