# TODO: regex parse
import re
from re import Pattern

# https://stackoverflow.com/a/14919203
CM1_RX = r"(?m)(?<!\\)((\\{2})*)#.*$"
CM2_RX = r"(\\)?((\\{2})*)(#)"
WS_RX = r"(\\)?((\\{2})*)(\s)\s*"

RE_CAPTURED_GROUPS = re.compile(r"(?<!\()\((?!\?:)[^)]+\)")


def is_ignore_case_regex(pattern: str | Pattern) -> bool:
    if isinstance(pattern, str):
        return False
    return bool(pattern.flags & re.IGNORECASE)


def is_dotall_case_regex(pattern: str | Pattern) -> bool:
    if isinstance(pattern, str):
        return False
    return bool(pattern.flags & re.DOTALL)


def add_inline_regex_flags(
    pattern: str, ignore_case: bool = False, dotall: bool = False
) -> str:
    flags = ""
    if ignore_case:
        flags += "i"
    if dotall:
        flags += "s"
    if flags:
        flags = f"(?{flags})"
    return flags + pattern


def unverbosify_regex(pattern: str | Pattern) -> str:
    if isinstance(pattern, str):
        return pattern

    def strip_escapes(match):  # type: ignore
        ## if even slashes: delete space and retain slashes
        if match.group(1) is None:
            return match.group(2)
        ## if number of slashes is odd: delete slash and keep space (or 'comment')
        elif match.group(1) == "\\":
            return match.group(2) + match.group(4)
        ## error
        else:
            raise Exception

    if pattern.flags & re.X:
        not_verbose_regex = re.sub(
            WS_RX,
            strip_escapes,
            re.sub(
                CM2_RX, strip_escapes, re.sub(CM1_RX, "\\1", pattern.pattern)
            ),
        )

        return not_verbose_regex
    return pattern.pattern
