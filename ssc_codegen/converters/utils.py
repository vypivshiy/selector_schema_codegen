import re


# def to_snake_case(s: str) -> str:
#     return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()

def to_snake_case(s: str) -> str:
    # camelCase
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    # PascalCase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def to_upper_camel_case(s: str) -> str:
    if not s:
        return s
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_lower_camel_case(s: str) -> str:
    if not s:
        return s

    up_case = to_upper_camel_case(s)
    return up_case[0].lower() + up_case[1:]


def wrap_double_quotes(s: str, escape_ch: str = "\\") -> str:
    """used if string marks only in this chars"""
    return '"' + s.replace('"', escape_ch + '"') + '"'


def wrap_backtick(s: str, escape_ch: str = "\\") -> str:
    return "`" + s.replace("`", escape_ch + "`") + "`"


def escape_str(
    s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters.
    Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)
