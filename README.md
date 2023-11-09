# Selector schema codegen

Парсер yaml-DSL конфигурации со встроенным декларативным языком-спецификацией
для генерации схем парсеров (преимущественно под html) на различные языки программирования.

## Минимальные требования к целевому портируемому ЯП:
- есть регулярные выражения
- есть css/xpath библиотека
- базовые методы работы со строками

## Рекомендации
- использовать css селекторы: их можно **гарантированно** конвертировать в xpath
- есть конвертер xpath в css простых запросов: например, в css нет аналога `contains` из xpath и тд

## Спецификация синтаксиса

### Особенности языка

- Декларативный (отсутствия присвоения, арифметики, операций приоритетов)
- Процедурный
- Минималистичный синтаксис, для работы с селекторами, регулярными выражениями и простыми операциями со строками
- Принимает на вход **один** аргумент и он всегда selector-like типа
- Есть 3 типа данных: 
  - `SELECTOR` - инстанс класс для работы с css/xpath селекторами.
  - `TEXT` - строка
  - `ARRAY` - динамический массив строк
- Синтаксис регулярных выражений как в python. Для максимальной совместимости используйте, например, `[0-9]` вместо `\d`
- Пустые строки и комментарии (`//`) игнорируются анализатором.

### Описание типов
Для данного скриптового языка существуют 3 типа данных

| Тип      | Описание                                                                           |
|----------|------------------------------------------------------------------------------------|
| SELECTOR | инстанс класса, из которого вызываются css/xpath селекторы. Всегда первый аргумент |
| TEXT     | строка                                                                             |
| ARRAY    | динамический массив строк.                                                         |


### Описание директив
| Оператор | Аргументы                 | Описание                                                                                                                                          | Возвращаемое значение | Пример                              |
|----------|---------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------|-------------------------------------|
| default  | <value>                   | Значение по умолчанию, если произошла ошибка во время парсинга. **Указывается первым**                                                            | -                     | default "empty"                     |
| xpath    | "<expr>"                  | xpath селектор, возвращает первое найденное значение                                                                                              | SELECTOR              | xpath "//title"                     |
| xpathAll | "<expr>"                  | xpath селектор, возвращает все значения                                                                                                           | SELECTOR              | xpathAll "//div"                    |
| css      | "<expr>"                  | css селектор, возвращает первое найденное значение                                                                                                | SELECTOR              | css "title"                         |
| cssAll   | "<expr>"                  | css селектор, возвращает все значения                                                                                                             | SELECTOR              | cssAll "div > a"                    |
| attr     | "<tag attr>"              | получить тег(и). Вызывается после xpath/xpathAll/css/cssAll                                                                                       | TEXT/ARRAY            | attr "href"                         |
| text     |                           | получить текст внутри тега. Вызывается после xpath/xpathAll/css/cssAll. Может быть вызван первым для полного перевода объекта `SELECTOR` в `TEXT` | TEXT/ARRAY            | text                                |
| raw      |                           | получить сырой тег в виде текста. Вызывается после xpath/xpathAll/css/cssAll                                                                      | TEXT/ARRAY            | raw                                 |
| re       | "<exrp>"                  | регулярное выражение. Возвращает первый найденный элемент. Аргумент должен быть TEXT                                                              | TEXT                  | re "(\d+)"                          |
| reAll    | "<expr>"                  | регулярное выражение. Возвращает все найденные элементы. Аргумент должен быть TEXT                                                                | ARRAY                 | reAll "(\d+)"                       |
| reSub    | "<expr>" "<repl>" <count> | Замена по регулярному выражение. Аргумент должен быть TEXT                                                                                        | TEXT                  | reSub "(\d+)" "digit(lol)"          |
| strip    | "<string>"                | Удаляет заданную строку СЛЕВА и СПРАВА. Аргумент должен быть TEXT                                                                                 | TEXT                  | strip "\n"                          |
| lstrip   | "<string>"                | Удаляет заданную строку СЛЕВА. Аргумент должен быть TEXT                                                                                          | TEXT                  | lstrip " "                          |
| rstrip   | "<string>"                | Удаляет заданную строку СПРАВА. Аргумент должен быть TEXT                                                                                         | TEXT                  | rstrip " "                          |
| format   | "<string>"                | Format string. Аргумент подстановки указывать с помощью `{{}}` оператора. Аргумент должен быть TEXT                                               | TEXT                  | format "spam {{}} egg"              |
| split    | "<value>" <count>         | Разделение строки. Если count = -1 - делить на максимально доступное. Аргумент должен быть TEXT                                                   | ARRAY                 | default "empty"                     |
| slice    | <start> <end>             | Срез массива. Аргумент должен быть ARRAY. поддерживает отрицательные индексы                                                                      | ARRAY                 | slice 1 5 / slice 1 # `[1..]` алиас |
| index    | <index>                   | Взять элемент по индекса. Аргумент должен быть ARRAY                                                                                              | TEXT                  | index 1                             |
| first    |                           | `index 1` alias                                                                                                                                   | TEXT                  | first                               |
| last     |                           | `index -1` alias                                                                                                                                  | TEXT                  | last                                |
| join     | "<string>"                | Собирает ARRAY в строку. Аргумент должен быть ARRAY                                                                                               | TEXT                  | join ", "                           |

### Токены валидации

Следующие команды нужны для предварительной валидации входного документа и они **не изменяют** конечные
и промежуточные значения.

В данном языке `boolean` тип отсутствует, поэтому при ложном (false) результате будет выбрасывать ошибку.

Операторы принимают `SELECTOR`:
- assertCss
- assertXpath


Все остальные операторы принимают `TEXT`:

| Оператор       | Описание                                              | Пример                          |
|----------------|-------------------------------------------------------|---------------------------------|
| assertEqual    | Сравнение по полной строке (`==`) (с учетом регистра) | assertEqual "lorem upsum dolor" |
| assertContains | Сравнение по наличию части строки в `TEXT`            | assertContains "sum"            |
| assertStarts   | Сравнение по наличию части строки в начале `TEXT`     | assertStarts "lorem"            |
| assertEnds     | Сравнение по наличию части строки в конце `TEXT`      | assertEnds "dolor"              |
| assertMatch    | Сравнение `TEXT` по регулярному выражению             | assertMatch "lorem \w+ dolor"   |
| assertCss      | Проверка валидности запроса в `SELECTOR`.             | assertCss "head > title"        |
| assertXpath    | Проверка валидности запроса в `SELECTOR`.             | assertXpath "//head/title"      |


### examples

```
// set default value if parse process is failing
xpath "//title"
text
format "Cool title: {{}}"
```

python generated equivalent code:

```python
from parsel import Selector


def dummy_parse(val: Selector):
    val = val.xpath('//title')
    val = val.xpath('/text()').get()
    val = "Cool title: {}".format(val)
    return val
```

add default value

```
// set default value if parse process is failing
default "0"
xpath "//title"
text
format "Cool title: {{}}"
```

```python
from parsel import Selector


def dummy_parse(val: Selector):
    try:  
      val = val.xpath('//title')
      val = val.xpath('/text()').get()
      val = "Cool title: {}".format(val)
      return val
    except Exception:
        return "0"
```

add validator

```
// set default value if parse process is failing
assertCss "head > title"
xpath "//title"
text
format "Cool title: {{}}"
```


```python
from parsel import Selector


def dummy_parse(val: Selector):
    assert val.css("head > title")
    val = val.xpath('//title')
    val = val.xpath('/text()').get()
    val = "Cool title: {}".format(val)
    return val
```

## yaml config
TODO

## dev 
TODO


## TODO
- more languages, libs support
- template generator refactoring
- generation code optimizations
- css/xpath check in analyzer
- slices syntax analyze
- retranslate regex expressions. Eg: `\d` to `[0-9]`
- string methods: `title`, `upper`, `lower`, `capitalize`
