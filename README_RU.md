# Selector schema codegen

[RU](README_RU.md) [EN](README.md)

ssc_codegen - генератор html парсеров на различные языки программирования.

# Зачем

- Для удобной разработки веб-скреперов, неофициальных API интерфейсов, CI/CD интеграции
- поддержка API интерфейсов для различных языков программирования (пока доступны dart, python)
- удобное чтение файлов конфигурации
- документирование использования с автоматической документации возвращаемой сигнатуры
- переносимость: сгенерированные парсеры не привязаны к конкретному проекту и их можно переиспользовать
- Простой синтаксис, схожий с jquery, ORM фреймворками и библиотеками для сериализации данных

# Особенности

- декларативный стиль: описывайте, ЧТО вы хотите сделать, а не КАК это запрограммировать
- стандартизация: сгенерированный код имеет минимальное количество зависимостей
- возможность пересобирать на другие языки программирования
- css, xpath, regex, минимальные операции форматирования строк
- валидация полей, css/xpath/regex выражений
- перенос документации в сгенерированный код
- конвертация css в xpath запросы

## Установка

### pipx

```shell
pipx install ssc_codegen
```

### pip

```shell
pip install ssc_codegen
```

## Usage

see [examples](examples)

## Поддерживаемые библиотеки и языки программирования

| language | lib                                                          | xpath support | css support | formatter   |
|----------|--------------------------------------------------------------|---------------|-------------|-------------|
| python   | bs4                                                          | NO            | YES         | black       |
| -        | parsel                                                       | YES           | YES         | -           |
| -        | selectolax (modest)                                          | NO            | YES         | -           |
| -        | scrapy (based on parsel, but class init argument - Response) | YES           | YES         | -           |
| dart     | universal_html                                               | NO            | YES         | dart format |

## Рекомендации

- Для быстрого получения эффективных css селекторов рекомендуется использовать **любой** браузер на базе chromium 
и расширение [selectorGadget](https://chromewebstore.google.com/detail/selectorgadget/mhjhnkcfbdhnjickkkdbjoemdmbfginb)
- Используйте css селекторы: их можно **гарантированно** конвертировать в xpath
- Для максимальной поддержки большинства ЯП, используйте простые запросы по следующим причинам:
    - Некоторые библиотеки не поддерживают полную спецификацию css. 
Например, селектор `#product_description+ p` в `python.parsel`, `javascript` работают, а в `dart.universal_html`, 
`selectolax` библиотеках - нет.
- Присутствует конвертер xpath в css, но работоспособность не гарантируется. Например, в css нет аналога `contains`
  из xpath

### Как читать код схемы

Перед прочтением убедитесь, что вы знаете что такое:

- css селекторы
- xpath селекторы
- регулярные выражениях

### Shortcuts

Обозначения переменных в коде:

- D() - маркер `Document`/`Element` объекта
- N() - маркер операции для вложенных структур
- R() - шорткат для `D().raw()`. Полезно, если не нужны операции с селекторами, а только нужны операции 
с регулярными выражениями и строками

### Build-in schemas

#### ItemSchema
Парсит структуру по правилам `{<key1> = <value1>, <key2> = <value2>, ...}`, возвращает хеш таблицу

#### DictSchema 

Парсит структуру по правилу `{<key1> = <value1>, <key2> = <value2>, ...}`. Возвращает хеш таблицу 

#### ListSchema 

Парсит структуру по правилу `[{<key11> = <value12, <key2> = <value2>, ...}, {<key1> = <value1, <key2> = <value2>, ...}]`.  
Возвращает список хеш таблиц.


#### FlattenListSchema 

Парсит структуру по правилу `[<item1>, <item2>, ...]`. Возвращает список объектов.


## Спецификация ssc-gen синтаксиса

### Типы

На данный момент присутствует 5 видов

| TYPE          | DESCRIPTION                                               |
|---------------|-----------------------------------------------------------|
| DOCUMENT      | 1 элемент/объект документа. Всегда первый аргумент в поле |
| LIST_DOCUMENT | Коллекция элементов                                       |
| STRING        | Строка/Атрибут тега/текст тега                            |
| LIST_STRING   | Коллекция Строк/Атрибутов/текста                          |
| NESTED        | Коллекция Строк/Атрибутов/текста                          |

### Магические методы

- `__SPLIT_DOC__` - разделение документа на элементы для более удобного разбора.
- `__PRE_VALIDATE__` - предварительная валидация документа. Использует конструкцию `assert`. Если проверка провалилась
- выкидывает ошибка
- `__KEY__`, `__VALUE__` - магические методы для инициализации `DictSchema` структуры
- `__ITEM__` - магический мето для инициализации `FlattenListSchema` структуры

### Операторы

| Метод             | Принимает     | Возвращает         | Пример                                                   |   | Описание                                                                                   |
|-------------------|---------------|--------------------|----------------------------------------------------------|:--|--------------------------------------------------------------------------------------------|
| default(None/str) | None/str      | DOCUMENT           | `D().default(None)`                                      |   | Значение по умолчанию если произошла ошибка. Должен быть первым                            |
| sub_parser        | Schema        | -                  | `N().sub_parser(Books)`                                  |   | Передает документ/элемент другому объекту парсера. Возвращает полученный результат         |
| css               | CSS query     | DOCUMENT           | `D().css('a')`                                           |   | возвращает первый найденный элемент результата селектора                                   |
| xpath             | XPATH query   | DOCUMENT           | `D().xpath('//a')`                                       |   | возвращает первый найденный элемент результата селектора                                   |
| css_all           | CSS query     | LIST_DOCUMENT      | `D().css_all('a')`                                       |   | возвращает все элементы результата селектора                                               |
| xpath_all         | XPATH query   | LIST_DOCUMENT      | `D().xpath_all('//a')`                                   |   | возвращает все элементы результата селектора                                               |
| raw               |               | STRING/LIST_STRING | `D().raw()`                                              |   | возвращает сырой html документа/элемента. работает с DOCUMENT, LIST_DOCUMENT               |
| text              |               | STRING/LIST_STRING | `D().css('title').text()`                                |   | возвращает текст из html документа/элемента. работает с DOCUMENT, LIST_DOCUMENT            |
| attr              | ATTR-NAME     | STRING/LIST_STRING | `D().css('a').attr('href')`                              |   | возвращает атрибут из html тега. работает с DOCUMENT, LIST_DOCUMENT                        |
| trim              | str           | STRING/LIST_STRING | `R().trim('<body>')`                                     |   | отрезает строку СЛЕВА и СПРАВА. работает со STRING, LIST_STRING                            |
| ltrim             | str           | STRING/LIST_STRING | `D().css('a').attr('href').ltrim('//')`                  |   | отрезает строку СЛЕВА. работает со STRING, LIST_STRING                                     |
| rtrim             | str           | STRING/LIST_STRING | `D().css('title').rtrim(' ')`                            |   | отрезает строку СПРАВА. работает со STRING, LIST_STRING                                    |
| replace/repl      | old, new      | STRING/LIST_STRING | `D().css('a').attr('href').repl('//', 'https://')`       |   | замена строки. работает со STRING, LIST_STRING                                             |
| format/fmt        | template      | STRING/LIST_STRING | `D().css('title').fmt("title: {{}}")`                    |   | форматирование строки по шаблону. Должна быть метка `{{}}` работает со STRING, LIST_STRING |
| re                | pattern       | STRING/LIST_STRING | `D().css('title').re('(\w+)')`                           |   | поиск первого найденного результата регулярного выражения работает со STRING, LIST_STRING  |
| re_all            | pattern       | LIST_STRING        | `D().css('title').re('(\w+)')`                           |   | поиск всех результатов регулярного выражения работает со STRING                            |
| re_sub            | pattern, repl | STRING/LIST_STRING | `D().css('title').re_sub('(\w+)', 'wow')`                |   | замена строки по регулярному выражению. работает со STRING, LIST_STRING                    |
| index             | int           | STRING/DOCUMENT    | `D().css_all('a').index(0)`                              |   | взять элемент по индексу.  работает с LIST_STRING, LIST_STRING                             |
| first             |               | -                  | `D().css_all('a').first`                                 |   | алиас index(0)                                                                             |
| last              |               | -                  | `D().css_all('a').last`                                  |   | алиас index(-1). Или имплементация отрицательного индекса                                  |
| join              | sep           | STRING             | `D().css_all('a').text().join(', ')`                     |   | собирает коллекцию в строку. работает с LIST_STRING                                        |
| assert_in         | str           | NONE               | `D().css_all('a').attr('href').assert_in('example.com')` |   | проверка нахождения строки в коллекции. проверяемый аргумент должен быть LIST_STRING       |
| assert_re         | pattern       | NONE               | `D().css('a').attr('href').assert_re('example.com')`     |   | проверка нахождения регулярного выражения. проверяемый аргумент должен быть STRING         |
| assert_css        | CSS query     | NONE               | `D().assert_css('title')`                                |   | проверка элемента по css. проверяемый аргумент должен быть DOCUMENT                        |
| assert_xpath      | XPATH query   | NONE               | `D().assert_xpath('//title')`                            |   | проверка элемента по xpath. проверяемый аргумент должен быть DOCUMENT                      |
