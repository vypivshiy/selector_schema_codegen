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
]


def to_snake_case(s: str) -> str:
    # camelCase
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    # PascalCase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def to_upper_camel_case(s: str) -> str:
    return (
        "".join(word[0].upper() + word[1:] for word in s.split("_")) if s else s
    )


def to_lower_camel_case(s: str) -> str:
    if not s:
        return s

    up_case = to_upper_camel_case(s)
    return up_case[0].lower() + up_case[1:]


def wrap_double_quotes(s: str, escape_ch: str = "\\") -> str:
    """used if string marks only in this chars"""
    return '"' + s.replace('"', f'{escape_ch}"') + '"'


def wrap_backtick(s: str, escape_ch: str = "\\") -> str:
    return "`" + s.replace("`", f"{escape_ch}`") + "`"


def escape_str(
    s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters.
    Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)


def remove_empty_lines(code: list[str], sep: str = "\n") -> str:
    """remove empty lines from sequence of strings"""
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
