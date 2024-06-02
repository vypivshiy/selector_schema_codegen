import re


def sanitize_regex(s: str, escape_ch: str = "\\") -> str:
    """sanitize matching characters. Used, for trim, l_trim, r_trim realisations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(r"[\-.^$*+?{}\[\]\\|()]", _repl, s)


def to_camelcase(s: str) -> str:
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()
