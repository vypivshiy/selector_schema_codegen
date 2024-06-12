import re


def escape_str(
    s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters. Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)


def wrap_str_q(s: str, char: str = '"', escape_ch: str = "\\") -> str:
    """alt variant representation string"""
    return f"{char}{s.replace(char, escape_ch + char)}{char}"


def to_camelcase(s: str) -> str:
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def dart_re(pattern: str) -> str:
    """convert a python regex pattern to dart RexExp"""
    return repr(pattern).replace("$", "\$")
