import re


def to_snake_case(s: str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def to_upper_camel_case(s: str):
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def to_lower_camel_case(s: str):
    return "".join(word[0].lower() + word[1:] for word in s.split("_"))


def wrap_double_quotes(s: str, escape_ch: str = "\\") -> str:
    """used if string marks only in this chars"""
    return '"' + s.replace('"', escape_ch + '"') + '"'
