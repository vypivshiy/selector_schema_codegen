"""AST nodes for string manipulation, trimming, case conversion, and replacements.

This module defines operations transforming string data within field pipelines:
- Trimming: `Trim`, `Ltrim`, `Rtrim`, `NormalizeSpace`, `RmPrefix`, `RmSuffix`, `RmPrefixSuffix`.
- Case conversion: `Lower`, `Upper`.
- Formatting & Replacement: `Fmt`, `Repl`, `ReplMap`, `Unescape`.
- Array conversions: `Split` (`STRING -> LIST_STRING`), `Join` (`LIST_STRING -> STRING`).
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import TypeInfo, VariableType

# All string nodes (except Split and Join) support map semantics:
# STRING → STRING, LIST_STRING → LIST_STRING.
# accept/ret are set by the builder from cursor type.


@dataclass
class Trim(Node):
    """Strips leading and trailing whitespace or matching characters.

    Attributes:
        substr: Characters to strip from edges (defaults to whitespace).

    Examples:
        - KDL: `trim`
        - Python: `v1 = v.strip()`
        - JavaScript: `const v1 = v.trim();`
        - Go: `v1 := strings.TrimSpace(v)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    substr: str = ""


@dataclass
class Ltrim(Node):
    """Strips leading whitespace or matching characters from the left side.

    Attributes:
        substr: Characters to strip from the left side (defaults to whitespace).

    Examples:
        - KDL: `ltrim`
        - Python: `v1 = v.lstrip()`
        - JavaScript: `const v1 = v.trimStart();`
        - Go: `v1 := strings.TrimLeft(v, " ")`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    substr: str = ""


@dataclass
class Rtrim(Node):
    """Strips trailing whitespace or matching characters from the right side.

    Attributes:
        substr: Characters to strip from the right side (defaults to whitespace).

    Examples:
        - KDL: `rtrim`
        - Python: `v1 = v.rstrip()`
        - JavaScript: `const v1 = v.trimEnd();`
        - Go: `v1 := strings.TrimRight(v, " ")`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    substr: str = ""


@dataclass
class NormalizeSpace(Node):
    """Collapses consecutive whitespace sequences into a single space and trims edges.

    Examples:
        - KDL: `normalize-space`
        - Python: `v1 = " ".join(v.split())`
        - JavaScript: `const v1 = v.replace(/\\s+/g, ' ').trim();`
        - Go: `v1 := strings.Join(strings.Fields(v), " ")`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class RmPrefix(Node):
    """Removes a prefix substring from the string if present.

    Attributes:
        substr: Prefix string to remove.

    Examples:
        - KDL: `rm-prefix "id_"`
        - Python: `v1 = v.removeprefix("id_")`
        - JavaScript: `const v1 = v.startsWith("id_") ? v.slice(3) : v;`
        - Go: `v1 := strings.TrimPrefix(v, "id_")`
    """

    substr: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class RmSuffix(Node):
    """Removes a suffix substring from the string if present.

    Attributes:
        substr: Suffix string to remove.

    Examples:
        - KDL: `rm-suffix ".html"`
        - Python: `v1 = v.removesuffix(".html")`
        - JavaScript: `const v1 = v.endsWith(".html") ? v.slice(0, -5) : v;`
        - Go: `v1 := strings.TrimSuffix(v, ".html")`
    """

    substr: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class RmPrefixSuffix(Node):
    """Removes matching substring from both the prefix and suffix if present.

    Attributes:
        substr: String to remove from both ends.

    Examples:
        - KDL: `rm-prefix-suffix "_"`
        - Python: `v1 = v.removeprefix("_").removesuffix("_")`
    """

    substr: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Fmt(Node):
    r"""Formats string using a template string containing `{}` placeholder.

    Attributes:
        template: Format string template containing `{}` for the input value.

    Examples:
        - KDL: `fmt "https://example.com/{}"`
        - Python: `v1 = f"https://example.com/{v}"`
        - JavaScript: `const v1 = \`https://example.com/${v}\`;`
        - Go: `v1 := fmt.Sprintf("https://example.com/%s", v)`
    """

    template: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Repl(Node):
    """Replaces occurrences of a target substring with a replacement string.

    Attributes:
        old: Substring to replace.
        new: Replacement string.

    Examples:
        - KDL: `repl "old" "new"`
        - Python: `v1 = v.replace("old", "new")`
        - JavaScript: `const v1 = v.replaceAll("old", "new");`
        - Go: `v1 := strings.ReplaceAll(v, "old", "new")`
    """

    old: str = ""
    new: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class ReplMap(Node):
    """Replaces multiple search substrings using a dictionary mapping.

    Attributes:
        replacements: Mapping of search keys to replacement values.

    Examples:
        - KDL: `repl { "a" "1"; "b" "2" }`
        - Python: `v1 = std_repl_map(v, {"a": "1", "b": "2"})`
        - JavaScript: `const v1 = sscReplMap(v, {"a": "1", "b": "2"});`
        - Go: `v1 := stdReplMap(v, map[string]string{"a": "1", "b": "2"})`
    """

    replacements: dict[str, str] = field(default_factory=dict)
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Lower(Node):
    """Converts the input string(s) to lower case.

    Examples:
        - KDL: `lower`
        - Python: `v1 = v.lower()`
        - JavaScript: `const v1 = v.toLowerCase();`
        - Go: `v1 := strings.ToLower(v)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Upper(Node):
    """Converts the input string(s) to upper case.

    Examples:
        - KDL: `upper`
        - Python: `v1 = v.upper()`
        - JavaScript: `const v1 = v.toUpperCase();`
        - Go: `v1 := strings.ToUpper(v)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Split(Node):
    """Splits a string into a list of strings by a delimiter.

    Attributes:
        sep: Delimiter substring used to split the input string.

    Examples:
        - KDL: `split ","`
        - Python: `v1 = v.split(",")`
        - JavaScript: `const v1 = v.split(",");`
        - Go: `v1 := strings.Split(v, ",")`
    """

    sep: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(
            base=VariableType.STRING, is_array=True
        )
    )


@dataclass
class Join(Node):
    """Joins a list of strings into a single string by a separator delimiter.

    Attributes:
        sep: Separator string placed between joined elements.

    Examples:
        - KDL: `join ", "`
        - Python: `v1 = ", ".join(v)`
        - JavaScript: `const v1 = v.join(", ");`
        - Go: `v1 := strings.Join(v, ", ")`
    """

    sep: str = ""
    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )


@dataclass
class Unescape(Node):
    """Decodes HTML entities and unescapes special characters in the string.

    Examples:
        - KDL: `unescape`
        - Python: `v1 = html.unescape(v)`
        - JavaScript: `const v1 = sscUnescapeText(v);`
        - Go: `v1 := html.UnescapeString(v)`
    """

    accept_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
    ret_type_info: TypeInfo = field(
        default_factory=lambda: TypeInfo(base=VariableType.STRING)
    )
