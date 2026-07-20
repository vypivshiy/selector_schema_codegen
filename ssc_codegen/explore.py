"""HTML reconnaissance for selector discovery and ad-hoc extraction.

Pure functions backing the `ssc-gen scout` CLI command. Lets users / LLMs
probe raw HTML with regex on text/attribute values (which CSS alone
cannot express), optional CSS selector scoping, and relative navigation
(parent / child / sibling) — useful for picking selectors before writing
a `.kdl` schema or for one-off data extraction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from bs4 import BeautifulSoup, NavigableString, Tag

BS4_PARSER = "lxml"
DEFAULT_LIMIT = 50
DEFAULT_SNIPPET = 200
DEFAULT_FIELDS = ("path", "tag", "text")


# ─────────────────────────── filter spec ────────────────────────────


@dataclass
class AttrFilter:
    """A single --attr filter.

    kind:
      - "present" : attribute exists (NAME only)
      - "exact"   : attribute equals VAL
      - "regex"   : attribute matches REGEX
    """

    name: str
    kind: Literal["present", "exact", "regex"]
    value: str = ""
    compiled: re.Pattern[str] | None = None


@dataclass
class ScoutFilters:
    """Compiled filter set applied to candidate tags."""

    text_regex: re.Pattern[str] | None = None
    attrs: list[AttrFilter] = field(default_factory=list)
    tag: str | None = None
    css: str | None = None


@dataclass
class NavSpec:
    """Navigation instruction sequence.

    Applied in declaration order: up → down → next → prev (each N steps).
    """

    up: int = 0
    down: int = 0
    next: int = 0
    prev: int = 0

    def is_noop(self) -> bool:
        return not (self.up or self.down or self.next or self.prev)

    def steps(self) -> list[tuple[Literal["up", "down", "next", "prev"], int]]:
        return [
            ("up", self.up),
            ("down", self.down),
            ("next", self.next),
            ("prev", self.prev),
        ]


# ─────────────────────────── compilation ────────────────────────────


class FilterError(ValueError):
    """Raised when a user-supplied filter cannot be compiled."""


def _compile_regex(
    pattern: str, ignore_case: bool, fixed: bool
) -> re.Pattern[str]:
    """Compile a regex with optional case-folding or literal escaping."""
    if fixed:
        pattern = re.escape(pattern)
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        raise FilterError(f"invalid regex {pattern!r}: {exc}") from exc


def parse_attr_flag(raw: str, ignore_case: bool, fixed: bool) -> AttrFilter:
    """Parse `--attr NAME`, `--attr NAME=VAL`, `--attr NAME=~REGEX`."""
    if "=" not in raw:
        return AttrFilter(name=raw, kind="present")
    name, _, value = raw.partition("=")
    if not name:
        raise FilterError(f"invalid --attr {raw!r}: missing name")
    if value.startswith("~"):
        regex = _compile_regex(value[1:], ignore_case, fixed)
        return AttrFilter(
            name=name, kind="regex", value=value[1:], compiled=regex
        )
    return AttrFilter(name=name, kind="exact", value=value)


def compile_filters(
    *,
    text: str | None,
    attrs: Iterable[str],
    tag: str | None,
    css: str | None,
    ignore_case: bool,
    fixed: bool,
) -> ScoutFilters:
    """Build ScoutFilters from raw CLI arguments."""
    text_re = None
    if text is not None:
        text_re = _compile_regex(text, ignore_case, fixed)
    return ScoutFilters(
        text_regex=text_re,
        attrs=[
            parse_attr_flag(a, ignore_case=ignore_case, fixed=fixed)
            for a in attrs
        ],
        tag=tag,
        css=css,
    )


# ─────────────────────────── matching ──────────────────────────────


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML string into a BeautifulSoup tree."""
    return BeautifulSoup(html, BS4_PARSER)


def _candidate_set(soup: BeautifulSoup, css: str | None) -> list[Tag]:
    if css:
        try:
            return list(soup.select(css))
        except Exception as exc:  # soupsieve raises various exceptions
            raise FilterError(f"invalid CSS selector {css!r}: {exc}") from exc
    return [t for t in soup.find_all(True)]


def _matches_text_regex(tag: Tag, pattern: re.Pattern[str]) -> bool:
    """True if any direct NavigableString child of `tag` matches `pattern`.

    Direct children only (not descendants) — prevents every ancestor of
    a matching text node from being reported.
    """
    for child in tag.children:
        if isinstance(child, NavigableString) and pattern.search(str(child)):
            return True
    return False


def _matches_attr(tag: Tag, flt: AttrFilter) -> bool:
    if flt.kind == "present":
        return tag.has_attr(flt.name)
    if not tag.has_attr(flt.name):
        return False
    value = tag.get(flt.name)
    if isinstance(value, list):  # class/multivalued attr
        value = " ".join(value)
    if flt.kind == "exact":
        return value == flt.value
    if flt.kind == "regex":
        assert flt.compiled is not None
        return flt.compiled.search(str(value)) is not None
    return False


def _tag_matches(tag: Tag, flt: ScoutFilters) -> bool:
    if flt.tag is not None and tag.name != flt.tag:
        return False
    if flt.text_regex is not None and not _matches_text_regex(
        tag, flt.text_regex
    ):
        return False
    for attr_flt in flt.attrs:
        if not _matches_attr(tag, attr_flt):
            return False
    return True


def find_matches(
    soup: BeautifulSoup, flt: ScoutFilters, invert: bool
) -> list[Tag]:
    """Return tags passing filters (or non-passing if `invert`)."""
    candidates = _candidate_set(soup, flt.css)
    if invert:
        return [t for t in candidates if not _tag_matches(t, flt)]
    return [t for t in candidates if _tag_matches(t, flt)]


# ─────────────────────────── navigation ────────────────────────────


def _first_child_tag(tag: Tag) -> Tag | None:
    for child in tag.children:
        if isinstance(child, Tag):
            return child
    return None


def _nth_sibling(tag: Tag | None, count: int, forward: bool) -> Tag | None:
    current = tag
    remaining = count
    while current is not None and remaining > 0:
        if forward:
            current = current.find_next_sibling()
        else:
            current = current.find_previous_sibling()
        if current is None:
            return None
        remaining -= 1
    return current


def apply_navigation(tags: list[Tag], nav: NavSpec) -> list[Tag]:
    """Walk each tag through nav steps, drop None, dedupe by identity."""
    if nav.is_noop():
        # Still dedupe in case duplicates slipped through filters.
        seen: set[int] = set()
        out: list[Tag] = []
        for t in tags:
            if id(t) not in seen:
                seen.add(id(t))
                out.append(t)
        return out

    result: list[Tag] = []
    seen_ids: set[int] = set()
    for tag in tags:
        current: Tag | None = tag
        for direction, count in nav.steps():
            if count <= 0 or current is None:
                continue
            if direction == "up":
                for _ in range(count):
                    current = current.parent if current is not None else None
                    if current is None:
                        break
            elif direction == "down":
                for _ in range(count):
                    current = (
                        _first_child_tag(current)
                        if current is not None
                        else None
                    )
                    if current is None:
                        break
            elif direction == "next":
                current = _nth_sibling(current, count, forward=True)
            elif direction == "prev":
                current = _nth_sibling(current, count, forward=False)
            if current is None:
                break
        if current is not None and id(current) not in seen_ids:
            seen_ids.add(id(current))
            result.append(current)
    return result


# ─────────────────────────── field extraction ──────────────────────


def compute_css_path(tag: Tag) -> str:
    """Return a copy-pasteable CSS path from <html> down to `tag`."""
    parts: list[str] = []
    current: Tag | None = tag
    while current is not None and current.name not in ("[document]", None):
        name = current.name
        raw_classes = current.get("class")
        if isinstance(raw_classes, list):
            classes: list[str] = [str(c) for c in raw_classes]
        elif raw_classes is not None:
            classes = [str(raw_classes)]
        else:
            classes = []
        classes_str = ".".join(classes)
        # Compute position among same-tag siblings.
        same_tag_index = 1
        sibling: Tag | None = current.find_previous_sibling(name)
        while sibling is not None:
            same_tag_index += 1
            sibling = sibling.find_previous_sibling(name)
        if same_tag_index > 1 or _has_same_tag_sibling(current, name):
            segment = f"{name}:nth-of-type({same_tag_index})"
        else:
            segment = name
        if classes_str:
            segment_full = f"{name}.{'.'.join(classes)}"
            if ":nth-of-type" in segment:
                segment_full += f":nth-of-type({same_tag_index})"
            segment = segment_full
        parts.append(segment)
        current = current.parent if isinstance(current.parent, Tag) else None
    parts.reverse()
    return " > ".join(parts) if parts else ""


def _has_same_tag_sibling(tag: Tag, name: str) -> bool:
    return tag.find_previous_sibling(name) is not None or (
        tag.find_next_sibling(name) is not None
    )


def lookup_line(tag: Tag, lxml_tree: object) -> int | None:
    """Look up source line via lxml `.sourceline`.

    Builds a path of (name, index_among_siblings) for `tag` and walks
    the lxml tree to the same position. Handles the case where lxml's
    root element already matches the outermost path entry.
    """
    try:
        from lxml import etree  # type: ignore[import-not-found]
    except ImportError:
        return None
    if not isinstance(lxml_tree, etree._Element):
        return None

    # Build path bottom-up.
    path_parts: list[tuple[str, int]] = []
    current: Tag | None = tag
    while current is not None and current.name not in ("[document]", None):
        name = current.name
        index = 1
        sib: Tag | None = current.find_previous_sibling(name)
        while sib is not None:
            index += 1
            sib = sib.find_previous_sibling(name)
        path_parts.append((name, index))
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    path_parts.reverse()

    node: object = lxml_tree
    # If the lxml root element matches the outermost path entry, treat it
    # as already-located and skip descent into that level.
    if (
        path_parts
        and isinstance(node, etree._Element)
        and node.tag == path_parts[0][0]
    ):
        path_parts = path_parts[1:]

    for name, idx in path_parts:
        if not isinstance(node, etree._Element):
            return None
        matching = [c for c in node if c.tag == name]
        if idx - 1 >= len(matching):
            return None
        node = matching[idx - 1]

    sourceline = getattr(node, "sourceline", None)
    return int(sourceline) if sourceline else None


def _truncate(value: str, limit: int) -> str:
    if limit <= 0 or len(value) <= limit:
        return value
    return value[:limit] + "…"


def extract_fields(
    tag: Tag,
    fields: list[str],
    index: int,
    snippet: int,
    lxml_tree: object | None,
) -> dict[str, object]:
    """Extract requested fields from a tag."""
    out: dict[str, object] = {}
    for raw in fields:
        key = raw.strip()
        if key == "index":
            out["index"] = index
        elif key == "tag":
            out["tag"] = tag.name
        elif key == "text":
            out["text"] = _truncate(tag.get_text(), snippet)
        elif key == "html":
            out["html"] = _truncate(str(tag), snippet)
        elif key == "attrs":
            attrs_d = {
                k: (" ".join(v) if isinstance(v, list) else v)
                for k, v in tag.attrs.items()
            }
            out["attrs"] = attrs_d
        elif key == "classes":
            raw_cls = tag.get("class")
            if isinstance(raw_cls, list):
                out["classes"] = raw_cls
            elif raw_cls is not None:
                out["classes"] = [raw_cls]
            else:
                out["classes"] = []
        elif key == "path":
            out["path"] = compute_css_path(tag)
        elif key == "line":
            out["line"] = (
                lookup_line(tag, lxml_tree) if lxml_tree is not None else None
            )
        elif key.startswith("attr."):
            attr_name = key[len("attr.") :]
            if tag.has_attr(attr_name):
                v = tag.get(attr_name)
                out[f"attr.{attr_name}"] = (
                    " ".join(v) if isinstance(v, list) else v
                )
            else:
                out[f"attr.{attr_name}"] = None
        else:
            raise FilterError(f"unknown field {raw!r}")
    return out


# ─────────────────────────── result types ──────────────────────────


@dataclass
class ScoutResult:
    """Aggregated scout output."""

    matched: int
    returned: int
    limit: int
    offset: int
    truncated: bool
    results: list[dict[str, object]]

    def to_json(self) -> str:
        return json.dumps(
            {
                "matched": self.matched,
                "returned": self.returned,
                "limit": self.limit,
                "offset": self.offset,
                "truncated": self.truncated,
                "results": self.results,
            },
            ensure_ascii=False,
            indent=2,
        )

    def to_text(self) -> str:
        if not self.results:
            return "0 matches"
        lines: list[str] = []
        for r in self.results:
            path = r.get("path", "")
            tag = r.get("tag", "")
            text = r.get("text", "")
            text_str = str(text).replace("\n", " ")
            lines.append(f"{path}\t{tag}\t{text_str}")
        return "\n".join(lines)


# ─────────────────────────── orchestrator ──────────────────────────


def run_scout(
    html: str,
    filters: ScoutFilters,
    nav: NavSpec,
    fields: list[str],
    *,
    invert: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    snippet: int = DEFAULT_SNIPPET,
) -> ScoutResult:
    """Run scout end-to-end on raw HTML.

    Raises FilterError on invalid regex / CSS / unknown field.
    """
    soup = parse_html(html)
    matched_tags = find_matches(soup, filters, invert=invert)
    matched_tags = apply_navigation(matched_tags, nav)

    total = len(matched_tags)
    truncated = offset + limit < total
    page = (
        matched_tags[offset : offset + limit]
        if limit > 0
        else matched_tags[offset:]
    )

    needs_line = "line" in fields
    lxml_tree: object | None = None
    if needs_line:
        try:
            from lxml import etree  # type: ignore[import-not-found]

            lxml_tree = etree.HTML(html)
        except ImportError:
            lxml_tree = None

    results = [
        extract_fields(
            tag, fields, index=i, snippet=snippet, lxml_tree=lxml_tree
        )
        for i, tag in enumerate(page)
    ]

    return ScoutResult(
        matched=total,
        returned=len(results),
        limit=limit,
        offset=offset,
        truncated=truncated,
        results=results,
    )
