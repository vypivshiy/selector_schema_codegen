"""AST nodes for regular expression matching, extraction, and substitution.

This module defines pattern-matching nodes using a portable PCRE-compatible regex subset:
- `Re`: Extracts the first match or first capturing group from input string(s).
- `ReAll`: Extracts all matching substrings as a list of strings (`LIST_STRING`).
- `ReSub`: Replaces all regex matches with a substitution string.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType

# Re and ReSub support map semantics:
# STRING → STRING, LIST_STRING → LIST_STRING.
# accept/ret are set by the builder from cursor type.
#
# ReAll is scalar-only: STRING → LIST_STRING.
#
# ignore_case / dotall are extracted from re.Pattern defines at parse time
# and stored as explicit flags so codegen can emit them without inline (?i)(?s).


@dataclass
class Re(Node):
    r"""Extracts the first regular expression match or capture group from string(s).

    Uses a portable, restricted PCRE-compatible regular expression subset.
    Flags `(?i)` (ignore-case) and `(?s)` (dotall) are normalized and supported across all backends.
    If capturing groups `(...)` are present, extracts the first capture group (group 1); otherwise
    extracts the entire matched substring (group 0). If no match is found, an error is raised
    (intercepted by `Fallback` if present).
    Supports map semantics: `STRING -> STRING`, `LIST_STRING -> LIST_STRING`.

    Attributes:
        pattern: Portable PCRE regular expression pattern string.

    Examples:
        - KDL: `re #"ID:\s*(\d+)"#`
        - Python: `v1 = std_re_search(r"ID:\s*(\d+)", v)`
        - JavaScript: `const v1 = sscReSearch(/ID:\s*(\d+)/, v);`
        - Go: `v1 := stdReSearch("ID:\\s*(\\d+)", v)`
    """

    pattern: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class ReAll(Node):
    r"""Extracts all regular expression matches across the input string as a list of strings.

    Scalar input only (`STRING -> LIST_STRING`). Returns every match found in the input string.
    Supports portable PCRE syntax with `(?i)` and `(?s)` flags.

    Attributes:
        pattern: Portable PCRE regular expression pattern string.

    Examples:
        - KDL: `re-all #"\d+"#`
        - Python: `v1 = re.findall(r"\d+", v)`
        - JavaScript: `const v1 = Array.from(v.matchAll(/\d+/g), m => m[0]);`
        - Go: `v1 := regexp.MustCompile("\\d+").FindAllString(v, -1)`
    """

    pattern: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.STRING, is_array=True
        )
    )
    is_array: bool = True


@dataclass
class ReSub(Node):
    r"""Replaces regular expression matches with a substitution string.

    Performs global substitution across the input string.
    Supports map semantics: `STRING -> STRING`, `LIST_STRING -> LIST_STRING`.

    Attributes:
        pattern: Portable PCRE regular expression search pattern.
        repl: Replacement string or group reference.

    Examples:
        - KDL: `re-sub #"\s+"# "-"`
        - Python: `v1 = re.sub(r"\s+", "-", v)`
        - JavaScript: `const v1 = v.replace(/\s+/g, "-");`
        - Go: `v1 := regexp.MustCompile("\\s+").ReplaceAllString(v, "-")`
    """

    pattern: str = ""
    repl: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
