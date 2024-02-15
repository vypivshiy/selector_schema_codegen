import re


def sanitize_regex(s: str, escape_ch: str = "\\") -> str:
    """sanitize matching characters. Used, for trim, l_trim, r_trim realisations by regex"""

    def _repl(ch: re.Match[str]) -> str:
        return escape_ch + ch[0]

    return re.sub(r"[\-.^$*+?{}\[\]\\|()]", _repl, s)


def wrap_regex_pattern(s: str, prefix: str = "r", escape_ch: str = "\\") -> str:
    if escape_ch + '"' in s:
        s = s.replace(escape_ch + '"', '"')

    if '"' in s:
        s = s.replace('"', escape_ch + '"')
    return prefix + '"' + s + '"'


if __name__ == '__main__':
    # r"content=\"(https://.*\.m3u8)\""
    print(wrap_regex_pattern(r"content=\"(https://.*\.m3u8)\""))
