import re


def escape_str(
    s: str, pattern: str = r"[\-.^$*+?{}\[\]\\|()]", escape_ch: str = "\\"
) -> str:
    """Sanitize matching characters. Used, for trim, l_trim, r_trim realizations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(pattern, _repl, s)


def to_camelcase(s: str) -> str:
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()
