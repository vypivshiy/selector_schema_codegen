# Selector schema codegen
[RUSSIAN](README_RU.md) [ENGLISH](README.md)

ssc_codegen - генератор парсеров на различные языки программирования (преимущественно под html) с помощью 
yaml-DSL конфигурации со встроенным декларативным языком. 

Разработан для портирования парсеров на различные языки программирования

## Минимальные требования к целевому портируемому ЯП:
- есть регулярные выражения
- есть css/xpath библиотека с большинством поддерживаемых конструкций
- базовые методы работы со строками (format string, trim/left trim/right trim/split/replace)

## Рекомендации
- использовать css селекторы: их можно **гарантированно** конвертировать в xpath.
- есть конвертер xpath в css простых запросов **без гарантий работоспособности**. 
Например, в css нет аналога `contains` из xpath и тд
## Схематичное представление работы генератора

![img.png](docs/img.png)

## Спецификация синтаксиса

### Особенности языка

- DSL (Domain-Specific Language), декларативный (отсутствуют операции присвоения, арифметики, приоритетов)
- Минималистичный синтаксис, для работы с селекторами, регулярными выражениями и простыми операциями со строками
- Принимает на вход **один** аргумент и он всегда selector-like типа
- 4 типа данных
- Синтаксис регулярных выражений как в python. Для максимальной совместимости используйте, например, `[0-9]` вместо `\d`
- Пустые строки и комментарии (`//`) игнорируются анализатором.

### Описание типов
Для данного скриптового языка существуют 4 типа данных

| Тип            | Описание                                                                                               |
|----------------|--------------------------------------------------------------------------------------------------------|
| SELECTOR       | инстанс класса (Document, Element), из которого вызываются css/xpath селекторы. Всегда первый аргумент |
| SELECTOR_ARRAY | репрезентация списка узлов (Element nodes) всех найденных элементов из инстанса SELECTOR               |
| TEXT           | строка                                                                                                 |
| ARRAY          | список строк.                                                                                          |


### Описание директив
- операторы разделяются отступом строки `\n`
- Все строковые аргументы указываются **двойными** `"` кавычками.
- Игнорируются пробелы

| Оператор | Аргументы                 | Описание                                                                                                                                          | Возвращаемое значение | Пример                     |
|----------|---------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------|----------------------------|
| default  | "<value>"                 | Значение по умолчанию, если произошла ошибка во время парсинга. **Указывается первым**                                                            | -                     | default "empty"            |
| xpath    | "<expr>"                  | xpath селектор, возвращает первое найденное значение                                                                                              | SELECTOR              | xpath "//title"            |
| xpathAll | "<expr>"                  | xpath селектор, возвращает все значения                                                                                                           | SELECTOR              | xpathAll "//div"           |
| css      | "<expr>"                  | css селектор, возвращает первое найденное значение                                                                                                | SELECTOR              | css "title"                |
| cssAll   | "<expr>"                  | css селектор, возвращает все значения                                                                                                             | SELECTOR              | cssAll "div > a"           |
| attr     | "<tag attr>"              | получить тег(и). Вызывается после xpath/xpathAll/css/cssAll                                                                                       | TEXT/ARRAY            | attr "href"                |
| text     |                           | получить текст внутри тега. Вызывается после xpath/xpathAll/css/cssAll. Может быть вызван первым для полного перевода объекта `SELECTOR` в `TEXT` | TEXT/ARRAY            | text                       |
| raw      |                           | получить сырой тег в виде текста. Вызывается после xpath/xpathAll/css/cssAll                                                                      | TEXT/ARRAY            | raw                        |
| re       | "<exrp>"                  | регулярное выражение. Возвращает первый найденный элемент. Аргумент должен быть TEXT                                                              | TEXT                  | re "(\d+)"                 |
| reAll    | "<expr>"                  | регулярное выражение. Возвращает все найденные элементы. Аргумент должен быть TEXT                                                                | ARRAY                 | reAll "(\d+)"              |
| reSub    | "<expr>" "<repl>" <count> | Замена по регулярному выражение. Аргумент должен быть TEXT                                                                                        | TEXT                  | reSub "(\d+)" "digit(lol)" |
| strip    | "<string>"                | Удаляет заданную строку СЛЕВА и СПРАВА. Аргумент должен быть TEXT                                                                                 | TEXT                  | strip "\n"                 |
| lstrip   | "<string>"                | Удаляет заданную строку СЛЕВА. Аргумент должен быть TEXT                                                                                          | TEXT                  | lstrip " "                 |
| rstrip   | "<string>"                | Удаляет заданную строку СПРАВА. Аргумент должен быть TEXT                                                                                         | TEXT                  | rstrip " "                 |
| format   | "<string>"                | Format string. Аргумент подстановки указывать с помощью `{{}}` оператора. Аргумент должен быть TEXT                                               | TEXT                  | format "spam {{}} egg"     |
| split    | "<value>" <count>         | Разделение строки. Если count = -1 или не передан - делить на максимально доступное. Аргумент должен быть TEXT                                    | ARRAY                 | split ", "                 |
| replace  | "<old>" "<old>" <count>   | Замена строки. Если count = -1 или не передан - заменять на максимально доступное. Аргумент должен быть TEXT                                      | ARRAY                 | split ", "                 |
| limit    | <count>                   | Максимальное число элементов                                                                                                                      | ARRAY                 | limit 50                   |
| index    | <index>                   | Взять элемент по индекса. Аргумент должен быть ARRAY                                                                                              | TEXT                  | index 1                    |
| first    |                           | `index 1` alias                                                                                                                                   | TEXT                  | first                      |
| last     |                           | `index -1` alias                                                                                                                                  | TEXT                  | last                       |
| join     | "<string>"                | Собирает ARRAY в строку. Аргумент должен быть ARRAY                                                                                               | TEXT                  | join ", "                  |
| ret      |                           | Указать транслятору вернуть значение. Автоматически добавляется если не указан в скрипте                                                          |                       | ret                        |
| noRet    | "<string>"                | Указать транслятору ничего не возвращать. Добавлено для предварительной валидации документа                                                       |                       | noRet                      |
| //       | ...                       | Однострочный комментарий. Игнорируется конечным кодогенератором                                                                                   |                       | // this is comment line    |


### Токены валидации

Следующие команды нужны для предварительной валидации входного документа при помощи `assert` и они **не изменяют** 
конечные и промежуточные значения.

В данном DSL языке `boolean`, `null` типы отсутствуют, поэтому при ложном (false) результате будет выбрасывать ошибку
вида `AssertionError`.

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


### Примеры генерации

```
// set default value if parse process is failing
xpath "//title"
text
format "Cool title: {{}}"
```

generated python equivalent code:

```python
from parsel import Selector


def dummy_parse(part: Selector):
    val_0 = part.xpath('//title')
    val_1 = val_0.xpath('/text()').get()
    val_2 = "Cool title: {}".format(val_1)
    return val_2
```

generated dart equivalent code:

```dart
import 'package:html/parser.dart' as html;

dummy_parse(part){
    var val_0 = part.querySelector('title');
    String val_1 = val_0?.text ?? "";
    var val_2 = "Cool title: $val_1";
    return val_2;
}
```
add default value:

```
// set default value if parse process is failing
default "spam egg"
xpath "//title"
text
format "Cool title: {{}}"
```

```python
from parsel import Selector


def dummy_parse(part: Selector):
    try:  
      val_1 = part.xpath('//title')
      val_2 = val_1.xpath('/text()').get()
      val_3 = "Cool title: {}".format(val_2)
      return val_3
    except Exception:
        return "spam egg"
```

```dart
import 'package:html/parser.dart' as html;

dummy_parse(html.Document part){
  try{
    var val_0 = part.querySelector('title');
    String val_1 = val_0?.text ?? "";
    var val_2 = "Cool title: $val_1";
    return val_2;
  } catch (e){
    return "spam egg";
  }
    
}
```
add assert validator

```
// not null check operation
assertCss "head > title"
xpath "//title"
text
format "Cool title: {{}}"
```


```python
from parsel import Selector


def dummy_parse(part: Selector):
    assert part.css("head > title")
    val_1 = part.xpath('//title')
    val_2 = val_1.xpath('/text()').get()
    val_3 = "Cool title: {}".format(val_2)
    return val_3
```

```dart
import 'package:html/parser.dart' as html;

dummy_parse(html.Document part){
    assert(part.querySelector('title') != null);
    var val_0 = part.querySelector('title');
    String val_1 = val_0?.text ?? "";
    var val_2 = "Cool title: $val_1";
    return val_2;
}
```

## yaml config
Пример структуры сгенерированного класса-парсера:
![img_2.png](docs/img_2.png)

- selector - Selector/Document инстанс, инициализируется с помощью document
- _aliases - ключи переназначения для метода view()
- _viewKeys - ключи вывода для метода view()
- _cachedResult - кеш полученных значений из метода parse()
- parse() - запуск парсера
- view() - получение полученных значений
- _preValidate() - опциональный метод предварительной валидации входного документа по правилам из конфигурации. Если результат false/null - выбрасывает `AssertError`
- _partDocument() - опциональный метод разделения документа на части по заданному селектору. Полезен, например, для получения однотипных элементов (карточек товара и тд)
- _parseA, _parseB, _parseC, ... - автоматически генерируемые методы парсера для каждого ключа (A,B,C) по правилам из конфигурации

### Usage pseudocode example:
```
document = ... // extracted html document
instance = Klass(document)
instance.parse()
print(instance.view())
```

Пример файла конфигурации, конечное значение смотрите в [examples](examples)

## dev 
TODO


## TODO
- generated schemas checksum
- filter operations (?)
- constants support
- more languages, libs support
- codegen optimizations (usage SELECTOR fluent interfaces, one-line code generation)
- css/xpath analyzer in pre-generate step
- css/xpath patches (for example, if css selectors in target language not support `:nth-child` operation?)
- translate regex expressions. Eg: `\d` to `[0-9]`
- string methods: `title`, `upper`, `lower`, `capitalize` or any useful
