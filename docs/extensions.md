# Пользовательские extension operations

**Версия DSL:** 2.1  
**Последнее обновление:** 2026-08-24

`extension` объявляет типизированные target-specific операции pipeline.
Синтаксис остаётся обычным KDL 2.0.

```kdl
extension Utils {
    to-base64 {
        sig str str

        py {
            import "from base64 import b64encode"
            emit #"{{out}} = b64encode({{in}}.encode("utf-8")).decode("ascii")"#
        }

        js {
            emit #"const {{out}} = btoa({{in}});"#
        }

        go {
            import "encoding/base64"
            emit #"{{out}} := base64.StdEncoding.EncodeToString([]byte({{in}}))"#
        }
    }
}
```

Каждый прямой child `extension` является operation declaration. Дополнительный
узел `op` не используется.

## Вызов

```kdl
!Utils.to-base64
```

`!` обязателен и отделяет пользовательский target-код от встроенных операций и
`@init` references.

## Типы

```kdl
sig str str
sig (array)str str
sig T T
sig T bool
```

Доступные concrete types: `doc`, `str`, `int`, `float`, `bool`. Модификаторы:
`(array)` и `?`. Generic `T` связывает полный входной `TypeInfo` и не принимает
модификаторы. Custom operation не применяет неявный map к массивам.

## Templates

| Placeholder | Значение |
|---|---|
| `{{in}}` | предыдущая pipeline variable |
| `{{out}}` | следующая pipeline variable |
| `{{in_type}}` | target-specific входной тип |
| `{{out_type}}` | target-specific выходной тип |

`emit` обязан присваивать `{{out}}`. Multiline source записывается KDL raw
multiline string `#"""..."""#`; generator сохраняет внутренние отступы и
добавляет текущий pipeline indent.

## Imports и helpers

Target-level `import` попадает в generated parser module. Для Go значение
является package path; optional `alias=` поддерживает import alias.

```kdl
go {
    import "example.com/project/utils" alias=utils
    emit #"{{out}} := utils.Normalize({{in}})"#
}
```

Helper генерируется один раз и только при фактическом использовании операции:

```kdl
py {
    helper normalize_value {
        import "import re"
        source #"""
            def normalize_value(value: str) -> str:
                return re.sub(r"\s+", " ", value)
            """#
    }
    emit #"{{out}} = normalize_value({{in}})"#
}
```

Python без `-R` и JavaScript размещают helper в utility section. Python с `-R`
размещает его в общем runtime module. Go размещает helper в
`sscgen_runtime.go`. Helper imports следуют за helper.

## Extension libraries

```kdl
import "./extensions.kdl" { (extension)Utils }
```

Файл, содержащий только extensions, проходит `ssc-gen check`, но не создаёт
output при `generate`. Imports private; dependency closure подключается
автоматически, но не становится видимой caller.

`emit` и `source` содержат произвольный исполняемый код. Используйте только
доверенные schemas.
