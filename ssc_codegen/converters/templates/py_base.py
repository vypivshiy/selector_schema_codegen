# used old style typing for support old python versions (3.8)


IMPORTS_MIN = """
import re
import sys
import json
from html import unescape as _html_unescape
from typing import List, Dict, TypedDict, Union, Optional, ClassVar
from contextlib import suppress
from functools import reduce

if sys.version_info >= (3, 10):
    from types import NoneType
else:
    NoneType = type(None)
"""


# NOTE: used hacks remove prefix and suffix by slices for py < 3.9 support reasons
HELPER_FUNCTIONS = r"""

_RE_HEX_ENTITY = re.compile(r'&#x([0-9a-fA-F]+);')
_RE_UNICODE_ENTITY = re.compile(r'\\\\u([0-9a-fA-F]{4})')
_RE_BYTES_ENTITY = re.compile(r'\\\\x([0-9a-fA-F]{2})')
_RE_CHARS_MAP = {'\\b': '\b', '\\f': '\f', '\\n': '\n', '\\r': '\r', '\\t': '\t'}


def ssc_unescape(s: str) -> str:
    s = _html_unescape(s)
    s = _RE_HEX_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = _RE_UNICODE_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = _RE_BYTES_ENTITY.sub(lambda m: chr(int(m.group(1), 16)), s)
    for ch, r in _RE_CHARS_MAP.items():
        s = s.replace(ch, r)
    return s

    
def ssc_map_replace(s: str, replacements: Dict[str, str]) -> str:
    return reduce(lambda acc, kv: acc.replace(kv[0], kv[1]), replacements.items(), s)

    
def ssc_rm_prefix(v: str, p: str) -> str:
    return v[len(p):] if v.startswith(p) else v


def ssc_rm_suffix(v: str, s: str) -> str:
    return v[:-(len(s))] if v.endswith(s) else v

    
def ssc_rm_prefix_and_suffix(v: str, p: str, s: str) -> str:
    return ssc_rm_suffix(ssc_rm_prefix(v, p), s)
"""
