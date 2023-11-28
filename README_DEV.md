# DEV
## install
TODO

## Minimum requirements for the target portable language:
- include regular expressions
- include css/xpath libs  (better - supports queries like nth-child, etc)
- basic methods for works with strings (format string, trim/left trim/right trim/split/replace)


## Translator customization
The translator works on the principle of hook token values and based on this information, 
generates code according to the jinja2 template.

### Translator methods

### Constants

- AUTO_CONVERT_TO_CSS bool - auto convert XPATH to CSS (not stable), default `false`

- AUTO_CONVERT_TO_XPATH bool - auto convert CSS to XPATH, default `false`

- XPATH_START_PREFIX - XPATH prefix (for XPATH converter)

- DELIM_DEFAULT_WRAPPER - try/catch, try/except statements

- DELIM_LINES - line delimiter (for example in python `\n`, C#, Dart - `;\n` )

- ELEMENT_TYPE - Node (Element) type in selector

- FIRST_ASSIGMENT - first assigment operator

- LIST_OF_ELEMENTS_TYPE - list of node (elements)

- LIST_OF_STRING_TYPE - list of strings

- METHOD_ARG_NAME - first argument name, default `part`

- REGEX_IMPORT - regex lib import

- SELECTOR_IMPORT - html parser lib import

- SELECTOR_TYPE - selector (Document) type

- STRING_TYPE - string type

- VAR_NAME - var name prefix, default `val`

### methods

#### Private (utils)

- _gen_var_name - generate var name 

- _VAR - shortcut of _gen_var_name(node)

- _VAR_P - shortcut _gen_var_name(node.prev)

#### hooks translations

- op_assert_contains - translate `assertContains`

- op_assert_css - translate `assertCss`

- op_assert_ends_with - translate `assertEnds`

- op_assert_equal - translate `assertEqual`

- op_assert_re_match - translate `assertRe`

- op_assert_starts_with - translate `assertStarts`

- op_assert_xpath - translate `assertXpath`

- op_attr - - translate `attr`

- op_css - - translate `css`

- op_css_all - - translate `cssAll`

- op_first_index - - translate `first`

- op_index - - translate `index`

- op_last_index - - translate `last`

- op_limit - - translate `limit`

- op_no_ret - - translate `noRet`

- op_raw - - translate `raw`

- op_regex - - translate `re`

- op_regex_all - - translate `reAll`

- op_regex_sub - - translate `reSub`

- op_ret - - translate `ret` (return)

- op_ret_array - translate `ARRAY` (List<String>, list[str\]) type

- op_ret_nothing - translate return nothing

- op_ret_selector - translate return `SELECTOR` type

- op_ret_selector_array - translate `SELECTOR_ARRAY` type 

- op_ret_text - translate `TEXT` (str, String) type

- op_ret_type - return statement entrypoint

- op_skip_part_document - translate skip `split` from configuration

- op_skip_pre_validate - translate skip `validate` from configuration

- op_string_format  - - translate `TEXT` (string) `format`

- op_string_join - - translate `join` ARRAY by delimiter. EG: `array=["1", "2", "3"], join=", " -> "1, 2, 3"` 

- op_string_ltrim - - translate `lStrip` (left trim) operation

- op_string_replace - - translate `replace` operation (regex matching exclude)

- op_string_rtrim - - translate `rStrip` (right trim) operation

- op_string_split - - translate `split` (split string by delimiter and convert list of string type)

- op_string_trim - - translate `strip` (trim) string (LEFT and RIGHT)

- op_text - - translate `text`: `SELECTOR` to `TEXT` or `SELECTOR_ARRAY` to `ARRAY`

- op_wrap_code - translate add delimiter to line of code

- op_wrap_code_with_default_value - translate add delimiters to try/catch/try/except statements

- op_xpath - - translate `xpath`

- op_xpath_all - - translate `xpathAll`

- tokens_map - codegen entrypoint: get translate methods from this method


## Jinja2

### Macros
Include in `*.j2` templates

- snake_case convert to snake_case

- camelcase convert to camelCase

- repr_str - wrap string to quotes: `"`, `'`

- generate_meta_info - generate meta information from configuration

- generate_attr_signature - generate attrs signature from schema

- ret_type - generate return type (for static typing or typehints)


### Write template
TODO