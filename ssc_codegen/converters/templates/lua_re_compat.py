"""
PCRE (Python re) -> Lua 5.2+ experimental research pattern translator

Made to convert modules to PURE lua without C dependencies, performance is not guaranteed!
================================================

Supported subset:
- Only re.I (re.IGNORECASE) flag supports
- 0 or 1 capturing group total; non-capturing groups (?:...) allowed
- No lookarounds of any kind
- Pattern must compile with Python's `re`
- Translate to Lua patterns where possible; otherwise, fall back to `PM` class (PatternMatcher).

Mapping of common tokens:
-------------------------
Anchors:
- `^` -> `^`
- `$` -> `$`
- `\A` -> `^`
- `\Z`, `\z` -> `$`

Character classes:
- `.` -> `.` (matches any char)
- `\d` -> `%d`
- `\D` -> `[^%d]`
- `\w` -> `%w`
- `\W` -> `[^%w]`
- `\s` -> `%s`
- `\S` -> `[^%s]`
- `[abc]` -> `[abc]`
- `[^abc]` -> `[^abc]`
- Ranges like `[a-z]` preserved

Word boundaries:
- `\b(pat)\b` -> `%f[%w](pat)%f[^%w]`
- `\B` not supported

Quantifiers:
- `*` -> `*`
- `+` -> `+`
- `?` -> `*` or create new pattern for backport
- `|` -> create new pattern for backport
- `A{n}` -> A*{n}
- `A{n,m}` -> A*{n}A?*{m}
- Lazy quantifiers (`*?`, `+?`, `{n,m}?`, etc.) try unpack to list of alt patterns or treated as greedy

Alternation:
- `a|b` -> list of alternatives

Helpers (Lua namespace `MD`):
-----------------------------------------
- `MD.serach(s, pat, ...)`
- `MD.findall(s, pat, ...)`
- `MD.sub(s, repl, pat, ...)`

Multiple patterns input имитируют OR `|` и Lazy quantifiers `?`

Eg:
    a|b|c|d -> [abcd]
    foo|bar|baz -> foo, bar, baz
    foo(?:foo|bar|baz)? -> foofoo, foobar, foobaz, foo

Not supported:
--------------
- Lookahead/lookbehind assertions
- Named groups
- More than one capturing group
- `\B`
- single `\b`
- {n,}, {,n} correct translate not guaranteed
"""

import sre_parse
import sre_constants as srec
from dataclasses import dataclass, field
from typing import Literal
import logging

__all__ = ["py_regex_to_lua_pattern"]


LOGGER = logging.getLogger("ssc-gen")


@dataclass
class Piece:
    text: str
    # mark required use helper functions
    pure: bool = True
    # list of alternative patterns when needed
    alternatives: list[str] = field(default_factory=list)

    def __add__(self, other: "Piece") -> "Piece":
        if self.alternatives or other.alternatives:
            # Handle alternatives by combining them
            new_alts = []

            # If self has alternatives
            if self.alternatives:
                if other.alternatives:
                    # Both have alternatives - cartesian product
                    for alt1 in [self.text] + self.alternatives:
                        for alt2 in [other.text] + other.alternatives:
                            new_alts.append(alt1 + alt2)
                else:
                    # Only self has alternatives
                    for alt in [self.text] + self.alternatives:
                        new_alts.append(alt + other.text)
            else:
                # Only other has alternatives
                for alt in [other.text] + other.alternatives:
                    new_alts.append(self.text + alt)

            return Piece(
                self.text + other.text, self.pure and other.pure, new_alts
            )
        else:
            return Piece(self.text + other.text, self.pure and other.pure)

    def order(self) -> None:
        # drop alternativives patterns duplicates and reverse list
        if not self.alternatives:
            return

        self.alternatives = sorted(
            list(set([self.text] + [i for i in self.alternatives if i != ""])),
            reverse=True,
            key=len,
        )


def escape_lua_char(c: str) -> str:
    return "%" + c if c in "^$()%.[]*+-?" else c


def category_to_lua(cat: int) -> str:
    mapping = {
        srec.CATEGORY_DIGIT: "%d",
        srec.CATEGORY_NOT_DIGIT: "[^%d]",
        srec.CATEGORY_WORD: "%w",
        srec.CATEGORY_NOT_WORD: "[^%w]",
        srec.CATEGORY_SPACE: "%s",
        srec.CATEGORY_NOT_SPACE: "[^%s]",
    }
    return mapping.get(cat)


def in_class_to_lua(items: list[tuple[int, object]]) -> str:
    """
    Convert a character class from sre_parse into a Lua pattern.
    Special handling: if the class is exactly one CATEGORY (like \d, \w, \s),
    return the pure shorthand (%d, %w, %s or their negated forms).
    """
    negate = False
    parts: list[str] = []
    single_category: str | None = None

    for op, av in items:
        if op == srec.NEGATE:
            negate = True
        elif op == srec.LITERAL:
            ch = chr(av)
            parts.append(
                "%" + ch if ch in "^%-]" else ("%%" if ch == "%" else ch)
            )
        elif op == srec.RANGE:
            a, b = av
            parts.append(f"{chr(a)}-{chr(b)}")
        elif op == srec.CATEGORY:
            cls = category_to_lua(av)
            # record single category
            single_category = cls
            if cls == "%d":
                parts.append("0-9")
            elif cls == "%w":
                parts.append("0-9A-Za-z_")
            elif cls == "%s":
                parts.append("\\t\\n\\v\\f\\r ")
            elif cls.startswith("[^"):
                # already a negated shorthand
                return cls
            else:
                raise NotImplementedError(f"Unsupported category {av}")
        else:
            raise NotImplementedError(op)

    # if the class was exactly one category, return shorthand
    if single_category and len(parts) == 1 and not negate:
        return single_category

    inside = "".join(parts)
    return "[^" + inside + "]" if negate else "[" + inside + "]"


def piece(text: str, pure=True, alternatives=None):
    return Piece(text, pure, alternatives or [])


def repeat_atom(atom: Piece, minrep: int, maxrep: int) -> Piece:
    UNLIM = srec.MAXREPEAT

    def trivial(a: Piece):
        t = a.text
        return (
            len(t) == 1
            or (t.startswith("%") and len(t) == 2)  # classes %d, %w, %s
            or (t.startswith("[") and t.endswith("]"))
        )

    # Special case: optional quantifier (?) on complex structures that need alternatives
    if minrep == 0 and maxrep == 1:
        if atom.alternatives and len(atom.alternatives) > 0:
            # Create alternatives: with the atom and without it (empty string)
            all_alts = [atom.text] + atom.alternatives
            # Add empty string as alternative
            all_alts.append("")
            return piece(atom.text, False, all_alts)
        elif not trivial(atom) and not atom.alternatives:
            # For non-trivial atoms without alternatives, create simple alternatives
            return piece(atom.text, False, [""])

    # Handle existing alternatives
    if atom.alternatives:
        all_alts = [atom.text] + atom.alternatives

        if maxrep == UNLIM:
            # For unlimited repetition with alternatives, not supported
            raise NotImplementedError(
                "{n,} quantifier with alternatives not supported"
            )
        elif minrep == maxrep:
            # Fixed repetition
            combined_alts = []
            for alt in all_alts:
                combined_alts.append(alt * minrep)
            main_text = atom.text * minrep
            return piece(
                main_text,
                False,
                combined_alts[1:] if len(combined_alts) > 1 else [],
            )
        else:
            # Variable repetition with alternatives
            combined_alts = []
            for k in range(minrep, maxrep + 1):
                for alt in all_alts:
                    combined_alts.append(alt * k)
            main_text = atom.text * minrep + (atom.text + "?") * (
                maxrep - minrep
            )
            return piece(main_text, False, combined_alts)

    if maxrep == UNLIM:
        if trivial(atom):
            return piece(atom.text + "+")
        else:
            # Not supported for non-trivial atoms
            raise NotImplementedError("{n,} quantifier not supported")
    if minrep == maxrep:
        return piece(atom.text * minrep)
    if trivial(atom):
        return piece(atom.text * minrep + (atom.text + "?") * (maxrep - minrep))
    alts = [atom.text * k for k in range(minrep, maxrep + 1)]
    return piece(atom.text, False, alts)


def wrap_group(piece_str: str, capturing: bool = True) -> str:
    """
    Wrap a translated piece into a Lua capturing group ( ... )
    or a non-capturing group using a PatternHelpers helper if needed.
    """
    if capturing:
        return f"({piece_str})"
    else:
        return piece_str  # for now, just inline for non-capturing


def literal_to_lua(ch: str, ignorecase: bool = False) -> str:
    """
    Convert a literal character to its Lua pattern representation.
    If ignorecase is True and the character is an ASCII letter,
    expand it to a character class covering both cases.
    """
    if ignorecase and ch.isalpha():
        lower = ch.lower()
        upper = ch.upper()
        if lower != upper:
            return f"[{lower}{upper}]"
    if ch in "^$()%.[]*+-?":
        return "%" + ch  # escape special lua pattern chars
    return ch


def translate(pattern: str, ignore_case: bool = False) -> Piece:
    parsed = sre_parse.parse(pattern)
    at_boundary_state = False

    def walk(sub) -> Piece:
        nonlocal at_boundary_state
        out = piece("")
        i = 0

        while i < len(sub.data):
            op, av = sub.data[i]

            # Special handling for word boundary followed by group followed by word boundary
            if (
                op == srec.AT
                and av == srec.AT_BOUNDARY
                and i + 2 < len(sub.data)
                and sub.data[i + 1][0] == srec.SUBPATTERN
                and sub.data[i + 2][0] == srec.AT
                and sub.data[i + 2][1] == srec.AT_BOUNDARY
            ):
                # Found \b(group)\b pattern
                _, group_av = sub.data[i + 1]
                (gid, add_flags, del_flags, p) = group_av
                inner = walk(p)
                if gid > 0:  # capturing group
                    wrapped = wrap_group(inner.text, capturing=True)
                    out += piece(f"%f[%w]{wrapped}%f[^%w]")
                else:
                    wrapped = wrap_group(inner.text, capturing=False)
                    out += piece(f"%f[%w]{wrapped}%f[^%w]")

                # Skip the next two tokens (group and second boundary)
                i += 3
                continue

            # Regular token processing
            if op == srec.LITERAL:
                out += piece(literal_to_lua(chr(av), ignore_case))
            elif op == srec.SUBPATTERN:
                (gid, add_flags, del_flags, p) = av
                inner = walk(p)
                if gid > 0:  # capturing group
                    # For capturing groups with alternatives, generate the full alternatives
                    if inner.alternatives:
                        all_alts = [inner.text] + inner.alternatives
                        wrapped_alts = [
                            wrap_group(alt, capturing=True) for alt in all_alts
                        ]
                        out += piece(
                            wrap_group(inner.text, capturing=True),
                            False,
                            wrapped_alts,
                        )
                    else:
                        out += piece(
                            wrap_group(inner.text, capturing=True), inner.pure
                        )
                else:
                    # Non-capturing group
                    out += piece(
                        wrap_group(inner.text, capturing=False),
                        inner.pure,
                        inner.alternatives,
                    )
            elif op == srec.IN:
                out += piece(in_class_to_lua(av))
            elif op == srec.BRANCH:
                _, branches = av
                branch_results = [walk(b) for b in branches]

                # Collect all alternatives from all branches
                all_alternatives = []

                for branch_result in branch_results:
                    all_alternatives.append(branch_result.text)
                    all_alternatives.extend(branch_result.alternatives)

                # Remove duplicates while preserving order
                seen = set()
                unique_alternatives = []
                for alt in all_alternatives:
                    if alt not in seen:
                        seen.add(alt)
                        unique_alternatives.append(alt)

                main_text = (
                    unique_alternatives[0] if unique_alternatives else ""
                )
                alternatives = (
                    unique_alternatives[1:]
                    if len(unique_alternatives) > 1
                    else []
                )

                out += piece(main_text, False, alternatives)
            elif op == srec.MAX_REPEAT:
                minr, maxr, p = av
                atom = walk(p)
                out += repeat_atom(atom, minr, maxr)
            elif op == srec.MIN_REPEAT:
                LOGGER.warning(
                    "lua pattern matching not support non-greedy modifier suffix `?`. Replaced to eager `*`"
                )
                minr, maxr, p = av
                atom = walk(p)
                out += repeat_atom(atom, minr, maxr)
            elif op == srec.ANY:
                out += piece(".")
            elif op == srec.CATEGORY:
                cls = category_to_lua(av)
                out += piece(cls)
            elif op == srec.AT:
                if av in (srec.AT_BEGINNING, srec.AT_BEGINNING_STRING):
                    out += piece("^")
                elif av in (srec.AT_END, srec.AT_END_STRING):
                    out += piece("$")
                elif av == srec.AT_BOUNDARY:
                    # Standalone word boundary (should be closed)
                    # \bfoo\b -> %f[%w]foo%f[^%w]
                    if at_boundary_state:
                        out += piece("%f[^%w]")
                    else:
                        out += piece("%f[%w]")
                    at_boundary_state = not at_boundary_state
                elif av == srec.AT_NON_BOUNDARY:
                    raise NotImplementedError("\\B not supported")
                else:
                    raise NotImplementedError(av)
            elif op == srec.NOT_LITERAL:
                out += piece("[^" + escape_lua_char(chr(av)) + "]")
            else:
                raise NotImplementedError(op)

            i += 1

        return out

    assert not at_boundary_state, "not supported single AT_BOUNDRARY `\b`"
    return walk(parsed)


def py_regex_to_lua_pattern(
    pattern: str,
    prv: str,
    mode: Literal[
        "re", "re_all", "re_sub", "re_sub_map", "mre_any", "mre_all", "re_f"
    ],
    repl: str = "",
    ignore_case: bool = False,
) -> str:
    """convert PCRE regex to lua equalent string pattern matching code

    helper functions API

    -- PM.search(s, pat, ...)  # re()
    -- PM.findall(s, pat, ...)  # re_all()
    -- PM.sub(s, repl, pat, ...)  # re_sub()
    -- PM.re_any(s, pat, ...)  # any pattern matched
    -- PM.re_all(s, pat, ...)  # all patterns matched
    -- F.pm(e, pat, ...)  # regex filter equalent

    """
    result = translate(pattern, ignore_case=ignore_case)
    result.order()

    pm_function = {
        "re": "PM.search",
        "re_all": "PM.findall",
        "re_sub": "PM.sub",
        "re_sub_map": "_",  # stub, manually format
        "mre_any": "PM.re_any",
        "mre_all": "PM.re_all",
        "re_f": "F.pm",
    }.get(mode)

    if pm_function is None:
        raise NotImplementedError(f"Unsupported mode: {mode}")

    if result.alternatives:
        patterns = ", ".join(repr(alt) for alt in result.alternatives)
    else:
        patterns = repr(result.text)

    if mode == "re_sub":
        return f"{pm_function}({prv}, {repl!r}, {patterns})"
    elif mode == "re_sub_map":
        # function Buildins.map(tbl, fn)
        return f"Buildins.map({prv}, function(e) PM.sub(e, {patterns}) end)"
    else:
        return f"{pm_function}({prv}, {patterns})"


if __name__ == "__main__":
    tests = [
        r"Page\s(\d+)",  # Page%s(%d+)
        r"\d{2}",  # %d%d
        r"\d{2,4}",  # %d%d%d?%d?
        r"\d{,4}",  # %d?%d?%d?%d?
        r"\bhello world\b",  # %f[%w]hello world%f[^%w]
        r"\b(hello\s+world)\b",  # %f[%w]hello%s+world%f[^%w]
        r"\b(hello\s+w[^auo]orld)\b",  # %f[%w]hello%s+w[^auo]orld%f[^%w]
        r"(azz?a)",  # azz?a
        r"(az\w?a)",  # az%w?a
        r"(az(?:z)?a)",  # (azz?a)
        r"(az(?:z)a)",  # (azza)
        r"(az(?:z|a|b)a)",  # (az[zab]a)
        r"(az(?:z|a|b)?a)",  # (az[zab]?a)
        r"foobar (az(?:z|a|b)?a)",  # foobar  (az[zab]?a)
        r"(foo(?:bar|baz|zaz))",  # [('foobar'), '(foobaz)', '(foozaz)']
        r"(\d+(?:\.\d+)?)",  # ['%d+%.%d+', '%d+']
        r"(https?://(?:www\.|wap\.)[a-z]+\.[a-z]+)",  # multiple alternatives
        r"(https?://(?:www\.|wap\.)?[a-z]+\.[a-z]+)",  # multiple alternatives with optional group
    ]
    for pat in tests:
        print(pat)
        p = translate(pat)
        p.order()
        if p.alternatives:
            print(f"{pat} -> {p.alternatives}")
        else:
            print(f"{pat} -> {p.text}")
        print(f"  Pure: {p.pure}")
        print()
