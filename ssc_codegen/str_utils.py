"""post-processing functions for fix code output and utils operations with strings"""

import re

RE_GO_IMPORTS_BLOCK = re.compile(r"import\s*\(\s*([\s\S]*?)\s*\)")

__all__ = [
    "to_snake_case",
    "to_upper_camel_case",
    "to_lower_camel_case",
    "wrap_backtick",
    "wrap_double_quotes",
    "escape_str",
    "remove_empty_lines",
    "go_unimport_naive",
    "py_str_format_to_fstring",
    "py_optimize_return_naive",
    "js_pure_optimize_return",
    "py_remove_unused_none_type_import",
]


def to_snake_case(s: str) -> str:
    """convert string to snake_case"""
    # camelCase
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    # PascalCase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def to_upper_camel_case(s: str) -> str:
    """convert string to UpperCamelCase (PascalCase)"""
    return (
        "".join(word[0].upper() + word[1:] for word in s.split("_")) if s else s
    )


def to_lower_camel_case(s: str) -> str:
    """convert string to lowerCamelCase"""
    if not s:
        return s

    up_case = to_upper_camel_case(s)
    return up_case[0].lower() + up_case[1:]


def wrap_double_quotes(s: str, escape_ch: str = "\\") -> str:
    """wrap string to `"` chars"""
    if not s:
        return '""'
    return '"' + s.replace('"', f'{escape_ch}"') + '"'


def wrap_backtick(s: str, escape_ch: str = "\\") -> str:
    """wrap string to '`' chars"""
    if not s:
        return "``"
    return "`" + s.replace("`", f"{escape_ch}`") + "`"


def escape_str(
    s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters.
    Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)


def escape_regex_pattern(pattern: str) -> str:
    return re.escape(pattern)


def remove_empty_lines(code: list[str], sep: str = "\n") -> str:
    """remove empty lines from sequence of strings and concatenate"""
    return sep.join([i for i in code if i])


def go_unimport_naive(go_code: str) -> str:
    """remove unused imports in golang code"""
    imports_block = RE_GO_IMPORTS_BLOCK.search(go_code)
    if not imports_block:
        return go_code
    imports_code = imports_block.group(1)
    import_libs = re.findall(r'"([^"]+)"', imports_code)
    for absolute_lib in import_libs:
        lib = (
            absolute_lib.split("/")[-1]
            if absolute_lib.find("/") != -1
            else absolute_lib
        )
        if not re.search(lib + "\\.", go_code):
            sub_pattern = f'\\s*"{absolute_lib}"'
            go_code = re.sub(sub_pattern, "", go_code)
    return go_code


RE_PY_METHOD_BLOCK = re.compile(
    r"""
def\s_(?:parse|split)\w+\(.*\:\s*   # SPLIT_DOC STRUCT_PARSE HEAD
(?:\n|.)*?                          # BLOCK OF CODE
return\s(?P<ret_var>\w+)    # RET STMT 
""",
    re.X,
)


def py_optimize_return_naive(py_code: str) -> str:
    """optimize _parse_[a-zA-Z_0-9] and _split_doc return statements

    insert last expr instruction to return stmt instead create new variable

    example:

    IN:

    class Foo:
        # ...
        def _split_doc(self, v):
            v1 = v.expr1
            v2 = v1.expr2
            return v2
        def _parse_a(self, v):
            v1 = v.expr1
            return v1
        # ...

    OUT:

    class Foo:
        # ...
        def _split_doc(self, v):
            v1 = v.expr1
            return v1.expr2
        def _parse_a(self, v):
            return v.expr1
        # ...

    """
    tmp_code = py_code
    for method_block in RE_PY_METHOD_BLOCK.finditer(tmp_code):
        ret_var = method_block["ret_var"]
        # v6\s*=\s*(?P<expr>.*)$
        re_expr = f"{ret_var}\\s*=\\s*(?P<expr>.*)"
        if match := re.search(re_expr, method_block[0]):
            expr = match["expr"]  # noqa

            # optimization function convert double backslash to single (\\ -> \) in regex patterns
            # add `r` prefix for avoid SyntaxWarning then compile generated code to cpython bytecode
            def add_r_prefix(m: re.Match) -> str:
                func, string = m.groups()
                if not string.startswith(('r"', "r'")):
                    return f"{func}r{string}"
                return match.group(0)

            # in patterns codegen used single quotas literals
            expr = re.sub(
                r'(\bre\.\w+\()\s*(".*?"|\'.*?\')', add_r_prefix, expr
            )
            new_method_block = re.sub(f"\\s*{re_expr}", "", method_block[0])
            new_method_block = re.sub(
                rf"return {ret_var}", f"return {expr}", new_method_block
            )
            tmp_code = tmp_code.replace(method_block[0], new_method_block, 1)
    return tmp_code


RE_STR_FMT = re.compile(
    r"(?P<template_str>['\"].*['\"])\.format\((?P<var>.*)\)"
)


def py_str_format_to_fstring(py_code: str) -> str:
    """replace str.format() to fstring"""
    tmp_code = py_code
    for expr in RE_STR_FMT.finditer(tmp_code):
        old_expr = expr[0]
        var = expr["var"]
        template_str = expr["template_str"]
        new_expr = "f" + template_str.replace("{}", "{" + var + "}")
        tmp_code = tmp_code.replace(old_expr, new_expr)
    return tmp_code


RE_JS_METHOD_BLOCK = re.compile(
    r"\s_(?:parse|split)\w+\(.*\{(?:\n|.)*?return\s(?P<ret_var>\w+);"
)


RE_PY_REMOVE_NONE_TYPE_IMPORT = re.compile(
    r"if sys\.version_info >= \(3, 10\):[^)]*\(None\)", flags=re.MULTILINE
)


def py_remove_unused_none_type_import(py_code: str) -> str:
    if len(re.findall(r"\bNoneType\b", py_code)) == 2:
        return RE_PY_REMOVE_NONE_TYPE_IMPORT.sub("", py_code)
    return py_code


def js_pure_optimize_return(js_code: str) -> str:
    tmp_code = js_code
    for method_code in RE_JS_METHOD_BLOCK.finditer(tmp_code):
        ret_var = method_code["ret_var"]
        method_code_raw = method_code[0]
        if match_expr := re.search(
            f"let {ret_var} = (?P<expr>.*);", method_code_raw
        ):
            expr = match_expr["expr"]  # noqa
            new_method_code = re.sub(
                f"\\s*let {ret_var} = (?P<expr>.*);", "", method_code_raw
            )
            new_method_code = new_method_code.replace(
                f"return {ret_var}", f"return {expr}", 1
            )
            tmp_code = tmp_code.replace(method_code_raw, new_method_code, 1)
    return tmp_code
