import re


def sanitize_regex(s: str, escape_ch: str = '\\') -> str:
    """sanitize matching characters. Used, for trim, l_trim, r_trim realisations by regex"""
    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(r'[\-.^$*+?{}\[\]\\|()]', _repl, s)
