## Translator customization
Транслятор работает по принципу перехвата значений токена и на основе этой информации генерирует код по шаблона
### Description

#### Constants

- AUTO_CONVERT_TO_CSS bool - автоматическая конвертация XPATH в CSS

- AUTO_CONVERT_TO_XPATH bool - автоматическая конвертация CSS в XPATH

- XPATH_START_PREFIX - префикс xpath для автоматической конвертации CSS в XPATH

- DELIM_DEFAULT_WRAPPER - разделитель для конструкции try/catch, try/except

- DELIM_LINES - разделитель

- ELEMENT_TYPE - тип node элемента из селектора

- FIRST_ASSIGMENT - оператор первого присвоения

- LIST_OF_ELEMENTS_TYPE - список node элементлв из селектора

- LIST_OF_STRING_TYPE - тип списка со строками

- METHOD_ARG_NAME - имя первого аргумента

- REGEX_IMPORT - импорт библиотеки regex

- SELECTOR_IMPORT - импорт библиотеки для разбора html

- SELECTOR_TYPE - тип селектора

- STRING_TYPE - тип строки

- VAR_NAME - префикс промежуточной переменной

#### методы
- _gen_var_name создать имя переменной 

- _VAR алиас _gen_var_name(node)

- _VAR_P алиас _gen_var_name(node.prev)

- op_assert_contains трансляция команды `assertContains`

- op_assert_css трансляция команды `assertCss`

- op_assert_ends_with трансляция команды `assertEnds`

- op_assert_equal трансляция команды `assertEqual`

- op_assert_re_match трансляция команды `assertRe`

- op_assert_starts_with трансляция команды `assertStarts`

- op_assert_xpath трансляция команды `assertXpath`

- op_attr - трансляция команды `attr`

- op_css - трансляция команды `css`

- op_css_all - трансляция команды `cssAll`

- op_first_index - трансляция команды `first`

- op_index - трансляция команды `index`

- op_last_index - трансляция команды `last`

- op_limit - трансляция команды `limit`

- op_no_ret - трансляция команды `noRet`

- op_raw - трансляция команды `raw`

- op_regex - трансляция команды `re`

- op_regex_all - трансляция команды `reAll`

- op_regex_sub - трансляция команды `reSub`

- op_ret - трансляция команды `ret` (return)

- op_ret_array - трансляция возвращение типа List<String>

- op_ret_nothing - трансляция отсутствия возвращения значения

- op_ret_selector - трансляция возвращение типа SELECTOR

- op_ret_selector_array - трансляция возвращение типа List<Selector> 

- op_ret_text - трансляция возвращение типа String

- op_ret_type - входная точка для трансляции возвращаемого типа

- op_skip_part_document - трансляция пропуска конфигурации `split`

- op_skip_pre_validate - трансляция пропуска конфигурации `validate`

- op_string_format  - трансляция команды `format`

- op_string_join - трансляция команды `join`

- op_string_ltrim - трансляция команды `lStrip`

- op_string_replace - трансляция команды `replace`

- op_string_rtrim - трансляция команды `rStrip`

- op_string_split - трансляция команды `split`

- op_string_trim - трансляция команды `strip`

- op_text - трансляция команды `text`

- op_wrap_code - трансляция добавления отступов в сгенерированный блок кода

- op_wrap_code_with_default_value - трансляция добавления отступов в сгенерированный блок кода в try/catch, try/except

- op_xpath - трансляция команды `xpath`

- op_xpath_all - трансляция команды `xpathAll`

- tokens_map - входная точка получения метода трансляции токена для кодогенератора


## Jinja2

### Macros
Вызываются в шаблоне `*.j2`

- snake_case перевод строки в snake_case

- camelcase перевод строки в camelCase

- repr_str - оборачивает строку в кавычки

- generate_meta_info - генерирует мета информацию на основе файла конфигурации

- generate_attr_signature - генерация сигнатуры атрибутов для документации

- ret_type - генерация типа возвращаемого значения


### Write template
TODO