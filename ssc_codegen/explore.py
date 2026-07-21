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


# ─────────────────────────── discover mode ──────────────────────────


# Limits for `run_discover` output. Tuned to give LLMs enough signal
# for selector design without flooding context with noise.
DISCOVER_TOP_TAGS = 15
DISCOVER_TOP_CLASSES = 20
DISCOVER_TOP_IDS = 10
DISCOVER_TOP_CONTAINERS = 5
DISCOVER_TOP_DESCENDANTS = 15
# Minimum number of identical siblings required for a group to be
# reported as a `repeat_container`. count==2 is usually noise (header/footer
# pairs, etc.) — real repeating lists have ≥3 siblings.
DISCOVER_MIN_REPEAT = 3

# Sample text/attr truncated to this many characters when surfacing
# per-descendant "what does this element actually contain?" signal.
DISCOVER_SAMPLE_LEN = 80

# Leaf tags prioritised in `common_descendants` sort — these typically carry
# extractable data (text/attrs), so surfacing them first helps the LLM
# design field pipelines without extra probes.
LEAF_TAGS: frozenset[str] = frozenset(
    {
        "a",
        "img",
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "span",
        "li",
        "td",
        "th",
        "time",
        "code",
        "em",
        "strong",
        "b",
        "i",
    }
)
# Descendants present in at least this fraction of items (per container)
# are surfaced as `common_descendants`.
DISCOVER_DESCENDANT_THRESHOLD = 0.8

# Embedded-JSON discovery (json_signals). Lax detection: this is a
# reconnaissance tool, LLM is expected to inspect `snippet` and decide.
DISCOVER_TOP_JSON_SCRIPT = 10
DISCOVER_TOP_JSON_ATTR = 10
DISCOVER_SNIPPET_LEN = 200
JSON_MIME_TYPES: frozenset[str] = frozenset(
    {"application/ld+json", "application/json"}
)
JSON_SKIP_ATTRS: frozenset[str] = frozenset(
    {"class", "style", "href", "src", "action"}
)
JS_VAR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:var|let|const)\s+(\w+)\s*=\s*[\[{]"),
    re.compile(r"\b(?:window|globalThis|self)\.(\w+)\s*=\s*[\[{]"),
]

# Discovery v2 — short `item_selector`, head+tail samples, table candidates.
# A class occurring at most RARE_CLASS_MAX times in the document is treated
# as a "rare anchor" when building short selectors (id anchor still wins).
RARE_CLASS_MAX = 5
# Maximum hops below an anchor when building `item_selector`. If the real
# depth is greater we still emit the path (truncated to MAX_DEPTH) and mark
# the selector as `fragile`.
SELECTOR_MAX_DEPTH = 3
DISCOVER_TOP_TABLES = 5
SAMPLE_HEAD_N = 3
SAMPLE_TAIL_N = 3
# Skip JSON.parse on pathological scripts — reconnaissance, not validation.
JSON_PARSE_MAX_BYTES = 256 * 1024
# Tags that carry a label-like role inside list items (definition lists,
# "label: value" patterns). Used by `_detect_single_label_child`.
LABEL_TAGS: frozenset[str] = frozenset({"strong", "b", "dt", "label"})


@dataclass
class DiscoverResult:
    """Aggregated overview of an HTML document.

    Returned by `run_discover`. Designed as a single-call replacement for
    brute-force selector guessing: gives LLMs the page's structure
    (tag/class/id frequency, repeating containers with pre-computed
    common descendants, embedded JSON signals, table candidates, page
    summary) so selector design can start from data, not from guesses.
    """

    tag_stats: list[dict[str, object]]
    class_stats: list[dict[str, object]]
    id_stats: list[dict[str, object]]
    data_attrs: list[str]
    repeat_containers: list[dict[str, object]]
    json_signals: list[dict[str, object]]
    table_candidates: list[dict[str, object]] = field(default_factory=list)
    page_summary: dict[str, object] = field(
        default_factory=lambda: {
            "has_table": False,
            "has_embedded_json": False,
            "container_count_estimate": 0,
        }
    )
    # All samples in this result are whitespace-collapsed via
    # `Tag.get_text(strip=True)` — NOT verbatim HTML. Surfaced once
    # globally so the LLM does not write regex against raw whitespace.
    sample_normalized: bool = True

    def to_json(self) -> str:
        # Omit empty sections — saves tokens, signals absence by key
        # missing rather than `key: []`. LLM treats missing = not present.
        payload: dict[str, object] = {
            "sample_normalized": self.sample_normalized
        }
        for name in (
            "tag_stats",
            "class_stats",
            "id_stats",
            "data_attrs",
            "repeat_containers",
            "json_signals",
            "table_candidates",
            "page_summary",
        ):
            value = getattr(self, name)
            if value:
                payload[name] = value
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_text(self) -> str:
        lines: list[str] = []

        if self.sample_normalized:
            lines.append(
                "# sample_normalized: true (whitespace collapsed; not verbatim)"
            )
            lines.append("")

        lines.append("== tag_stats ==")
        for row in self.tag_stats:
            lines.append(f"{row['tag']}\t{row['count']}")
        lines.append("")

        lines.append("== class_stats ==")
        for row in self.class_stats:
            lines.append(f".{row['class']}\t{row['count']}")
        lines.append("")

        if self.id_stats:
            lines.append("== id_stats ==")
            for row in self.id_stats:
                lines.append(f"#{row['id']}\t{row['count']}")
            lines.append("")

        if self.data_attrs:
            lines.append("== data_attrs ==")
            lines.append(", ".join(self.data_attrs))
            lines.append("")

        lines.append("== repeat_containers ==")
        for c in self.repeat_containers:
            item_classes = c["item_classes"]
            assert isinstance(item_classes, list)
            cls = ".".join(str(x) for x in item_classes)
            count = c["count"]
            depth = c["depth"]
            lines.append(f"{c['item_tag']}.{cls}\tcount={count}\tdepth={depth}")
            lines.append(f"  parent: {c['parent_selector']}")
            item_sel = c.get("item_selector", "")
            if isinstance(item_sel, str) and item_sel:
                stability = c.get("selector_stability", "stable")
                lines.append(f"  item_selector: {item_sel}  [{stability}]")
            # Cheap boolean flags (only print when true).
            flag_bits: list[str] = []
            for f in ("single_link_item", "has_th_row", "single_label_child"):
                if c.get(f) is True:
                    flag_bits.append(f)
            if flag_bits:
                lines.append(f"  flags: {', '.join(flag_bits)}")
            descendants = c["common_descendants"]
            assert isinstance(descendants, list)
            for d in descendants:
                assert isinstance(d, dict)
                d_classes = d["classes"]
                assert isinstance(d_classes, list)
                dcls = ".".join(str(x) for x in d_classes) if d_classes else "_"
                d_attrs = d.get("attrs", [])
                assert isinstance(d_attrs, list)
                attrs_str = f"  attrs=[{','.join(d_attrs)}]" if d_attrs else ""
                mpi = d.get("max_per_item")
                mpi_str = (
                    f"  max_per_item={mpi}"
                    if isinstance(mpi, int) and mpi > 1
                    else ""
                )
                sample = d.get("sample")
                sample_str = ""
                if isinstance(sample, list) and sample:
                    sample_str = f"  sample={sample!r}"
                    tail = d.get("sample_tail")
                    if isinstance(tail, list) and tail:
                        sample_str += f"  sample_tail={tail!r}"
                lines.append(
                    f"  - {d['tag']}.{dcls}\tin={d['in_items']}/{count}{attrs_str}{mpi_str}{sample_str}"
                )
        lines.append("")

        if self.json_signals:
            lines.append("== json_signals ==")
            for sig in self.json_signals:
                assert isinstance(sig, dict)
                head = f"{sig['kind']}\t{sig['subtype']}"
                if sig.get("subtype") == "js-var":
                    head += f"\tvar={sig.get('var_name', '')}"
                elif sig.get("kind") == "script":
                    stype = sig.get("script_type", "")
                    if isinstance(stype, str) and stype:
                        head += f"\ttype={stype}"
                    sid = sig.get("script_id", "")
                    if isinstance(sid, str) and sid:
                        head += f"\tid={sid}"
                elif sig.get("kind") == "attr":
                    head += f"\tattr={sig.get('attr', '')}"
                head += f"\tkind={sig.get('container_kind', 'unknown')}"
                head += f"\tsize={sig.get('size', 0)}"
                lines.append(head)
                lines.append(f"  selector: {sig['selector']}")
                top_keys = sig.get("top_level_keys")
                if isinstance(top_keys, list) and top_keys:
                    lines.append(
                        f"  top_level_keys: {','.join(str(k) for k in top_keys)}"
                    )
                snippet = str(sig.get("snippet", ""))
                snippet = snippet.replace("\n", " ").replace("\r", "")
                lines.append(f"  snippet: {snippet[:DISCOVER_SNIPPET_LEN]}")
            lines.append("")

        if self.table_candidates:
            lines.append("== table_candidates ==")
            for t in self.table_candidates:
                assert isinstance(t, dict)
                keys = t.get("keys", [])
                assert isinstance(keys, list)
                keys_str = ", ".join(str(k) for k in keys) if keys else "(none)"
                lines.append(
                    f"rows={t.get('row_count', 0)}\tselector: {t.get('selector', '')}"
                )
                lines.append(f"  keys: {keys_str}")
            lines.append("")

        if self.page_summary:
            lines.append("== page_summary ==")
            for k, v in self.page_summary.items():
                lines.append(f"{k}\t{v}")
            lines.append("")

        return "\n".join(lines).rstrip()


def _collect_tag_stats(
    soup: BeautifulSoup,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[str],
    dict[str, int],
]:
    """Walk all tags; return (tag_stats, class_stats, id_stats, data_attrs,
    class_count_full).

    `class_count_full` is the **uncapped** class→occurrence-count lookup —
    used downstream by `_build_short_selector` to detect rare anchor
    classes. The capped `class_stats` list stays for output.
    """
    tag_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    id_counts: dict[str, int] = {}
    data_attrs: set[str] = set()

    for tag in soup.find_all(True):
        name = tag.name
        tag_counts[name] = tag_counts.get(name, 0) + 1

        for cls in tag.get("class") or []:
            class_counts[cls] = class_counts.get(cls, 0) + 1

        id_val = tag.get("id")
        if isinstance(id_val, str) and id_val:
            id_counts[id_val] = id_counts.get(id_val, 0) + 1

        for attr_name in tag.attrs:
            if attr_name.startswith("data-"):
                data_attrs.add(attr_name)

    tag_stats = [
        {"tag": t, "count": c}
        for t, c in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:DISCOVER_TOP_TAGS]
    class_stats = [
        {"class": c, "count": n}
        for c, n in sorted(class_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:DISCOVER_TOP_CLASSES]
    id_stats = [
        {"id": i, "count": n}
        for i, n in sorted(id_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:DISCOVER_TOP_IDS]
    return (
        tag_stats,
        class_stats,
        id_stats,
        sorted(data_attrs),
        class_counts,
    )


def _depth_of(tag: Tag) -> int:
    """Depth from the document root (root = 1)."""
    depth = 0
    current: object = tag
    while isinstance(current, Tag) and current.name not in ("[document]",):
        depth += 1
        parent = current.parent
        current = parent
    return depth


def _signature(tag: Tag) -> tuple[str, frozenset[str]]:
    """Stable identity for grouping siblings: (tag_name, class set)."""
    raw_classes = tag.get("class")
    if isinstance(raw_classes, list):
        classes = frozenset(str(c) for c in raw_classes)
    elif raw_classes is not None:
        classes = frozenset([str(raw_classes)])
    else:
        classes = frozenset()
    return (tag.name, classes)


def _compute_common_descendants(
    items: list[Tag],
    *,
    threshold: float = DISCOVER_DESCENDANT_THRESHOLD,
    max_n: int = DISCOVER_TOP_DESCENDANTS,
) -> list[dict[str, object]]:
    """Find descendants that appear in >= `threshold` fraction of `items`.

    Returns one entry per distinct (tag_name, class_set) signature, with:
    - `attrs`: union of non-class attributes seen across matching descendants
    - `sample`: first matching descendant's text (or first attr value when no
      text) — truncated to DISCOVER_SAMPLE_LEN. Omitted when nothing useful.
    - `max_per_item`: max occurrences of this signature within a single item.
      When >1, the LLM knows to use `:nth-of-type(N)` or expect LIST output.

    Sort: leaf-tag first (a/img/p/h/span/etc.), then coverage desc, then
    alphabetical. Leaf tags carry extractable data and are typically the
    fields the LLM needs to design — surfacing them ahead of intermediate
    container <div>s prevents them being cut off by `max_n`.
    """
    n = len(items)
    if n == 0:
        return []
    min_items = max(1, int(n * threshold))

    # Per-item: track signatures seen, attribute unions, occurrence counts,
    # and one sample element per signature (first encountered).
    per_item_signatures: list[set[tuple[str, frozenset[str]]]] = []
    per_item_attrs: list[dict[tuple[str, frozenset[str]], set[str]]] = []
    per_item_counts: list[dict[tuple[str, frozenset[str]], int]] = []
    per_item_samples: list[dict[tuple[str, frozenset[str]], Tag]] = []
    for item in items:
        seen: set[tuple[str, frozenset[str]]] = set()
        attr_map: dict[tuple[str, frozenset[str]], set[str]] = {}
        count_map: dict[tuple[str, frozenset[str]], int] = {}
        sample_map: dict[tuple[str, frozenset[str]], Tag] = {}
        for desc in item.find_all(True):
            sig = _signature(desc)
            seen.add(sig)
            attrs = attr_map.setdefault(sig, set())
            for k in desc.attrs:
                if k != "class":
                    attrs.add(k)
            count_map[sig] = count_map.get(sig, 0) + 1
            if sig not in sample_map:
                sample_map[sig] = desc
        per_item_signatures.append(seen)
        per_item_attrs.append(attr_map)
        per_item_counts.append(count_map)
        per_item_samples.append(sample_map)

    counts: dict[tuple[str, frozenset[str]], int] = {}
    for seen in per_item_signatures:
        for sig in seen:
            counts[sig] = counts.get(sig, 0) + 1

    common = [(sig, c) for sig, c in counts.items() if c >= min_items]

    # Sort: leaf-tag first (leaves carry data, surface ahead of containers),
    # then coverage desc, then alphabetical for determinism.
    def _sort_key(
        kv: tuple[tuple[str, frozenset[str]], int],
    ) -> tuple[int, int, str, list[str]]:
        sig, count = kv
        tag_name, classes = sig
        is_leaf = 0 if tag_name in LEAF_TAGS else 1
        return (is_leaf, -count, tag_name, sorted(classes))

    common.sort(key=_sort_key)

    result: list[dict[str, object]] = []
    for sig, count in common[:max_n]:
        tag_name, classes = sig
        # Union of attrs across all items for this signature.
        attr_union: set[str] = set()
        for attr_map in per_item_attrs:
            attr_union.update(attr_map.get(sig, set()))
        # Max occurrences within any single item — flags "appears N times
        # per row" patterns (e.g. <p class="card-text"> year/country/mileage).
        max_per_item = 1
        for count_map in per_item_counts:
            occ = count_map.get(sig, 0)
            if occ > max_per_item:
                max_per_item = occ
        # Sample values: head + tail (deduped) for variety coverage.
        samples = _extract_samples(per_item_samples, sig, attr_union)
        entry: dict[str, object] = {
            "tag": tag_name,
            "classes": sorted(classes),
            "in_items": count,
        }
        if attr_union:
            entry["attrs"] = sorted(attr_union)
        if max_per_item > 1:
            entry["max_per_item"] = max_per_item
        if samples["sample"]:
            entry["sample"] = samples["sample"]
            if "sample_tail" in samples:
                entry["sample_tail"] = samples["sample_tail"]
        result.append(entry)
    return result


def _extract_samples(
    per_item_samples: list[dict[tuple[str, frozenset[str]], Tag]],
    sig: tuple[str, frozenset[str]],
    attr_union: set[str],
    *,
    head_n: int = SAMPLE_HEAD_N,
    tail_n: int = SAMPLE_TAIL_N,
) -> dict[str, list[str]]:
    """Collect head+tail distinct sample values for a signature.

    Walks `per_item_samples` in order, extracts a value (text or first attr)
    from each item's stored sample Tag, deduplicates, and returns::

        {"sample": [first head_n distinct], "sample_tail": [last tail_n
         distinct not already in head]}

    `sample_tail` is omitted (key absent) when the list is too short to
    produce non-overlapping tail values. Values are whitespace-collapsed
    via `Tag.get_text(strip=True)` — the caller surfaces a global
    `sample_normalized: true` marker to flag this.
    """
    limit = DISCOVER_SAMPLE_LEN
    priority = ["href", "src", "title", "alt", "content", "value"]

    def _value_from(tag: Tag) -> str | None:
        text = tag.get_text(strip=True)
        if text:
            return text[:limit]
        for name in priority:
            if name in attr_union:
                val = tag.get(name)
                if isinstance(val, str) and val:
                    return val[:limit]
        for name in sorted(attr_union):
            val = tag.get(name)
            if isinstance(val, str) and val:
                return val[:limit]
        return None

    head: list[str] = []
    seen: set[str] = set()
    for sample_map in per_item_samples:
        tag = sample_map.get(sig)
        if tag is None:
            continue
        val = _value_from(tag)
        if val is None or val in seen:
            continue
        seen.add(val)
        head.append(val)
        if len(head) >= head_n:
            break

    tail: list[str] = []
    for sample_map in reversed(per_item_samples):
        tag = sample_map.get(sig)
        if tag is None:
            continue
        val = _value_from(tag)
        if val is None or val in seen:
            continue
        seen.add(val)
        tail.append(val)
        if len(tail) >= tail_n:
            break

    result: dict[str, list[str]] = {"sample": head}
    if tail:
        result["sample_tail"] = tail
    return result


# ─────────────────── discover v2: flags + short selector ─────────────


def _detect_single_link_item(items: list[Tag]) -> bool:
    """True when every item is itself a bare `<a>` OR has exactly one direct
    child Tag and it is `<a>`.

    Signals a navigation list: each row is just a link (e.g. `<li><a>...
    </a></li>` or a sequence of sibling `<a>` tags). The LLM can then prefer
    `(list)struct` of single-field structs or skip the container entirely.
    """
    if not items:
        return False
    for item in items:
        # Item itself is a bare link.
        if item.name == "a":
            continue
        # Item wraps exactly one <a> child.
        child_tags = [c for c in item.children if isinstance(c, Tag)]
        if len(child_tags) != 1 or child_tags[0].name != "a":
            return False
    return True


def _detect_has_th_row(parent: Tag, item_tag: str) -> bool:
    """True when `item_tag == 'tr'` and the enclosing `<table>` contains
    at least one `<th>` anywhere (typically in `<thead>`).

    Marks the group as a table body — keys are available from `<th>`
    cells (surfaced separately via `table_candidates`).
    """
    if item_tag != "tr":
        return False
    # Walk up from the items' parent to the nearest <table> ancestor —
    # <th> may live in a sibling <thead>, not in the same parent as items.
    table: Tag | None = parent
    while table is not None and table.name != "table":
        p = table.parent
        table = p if isinstance(p, Tag) else None
    if table is None:
        return False
    return table.find("th") is not None


def _detect_single_label_child(items: list[Tag]) -> bool:
    """True when at least one item has exactly one direct child Tag with
    a label-like name (strong/b/dt/label) AND non-empty residual text
    (i.e. item text ≠ label child text).

    Signals "label: value" patterns typical of definition lists.
    """
    for item in items:
        child_tags = [c for c in item.children if isinstance(c, Tag)]
        if len(child_tags) != 1 or child_tags[0].name not in LABEL_TAGS:
            continue
        child = child_tags[0]
        item_text = item.get_text(strip=True)
        child_text = child.get_text(strip=True)
        if item_text and item_text != child_text:
            return True
    return False


def _build_short_selector(
    item: Tag,
    class_count: dict[str, int],
) -> tuple[str, str]:
    """Build a short, stable CSS selector for `item`.

    Walks upward from `item.parent` looking for the nearest "anchor"
    (item itself is never used as anchor — `item_selector` targets ALL
    siblings, the item's own id/class would match only one):
      1. ancestor with non-empty `id` → `#id`
      2. ancestor with at least one class whose document frequency ≤
         RARE_CLASS_MAX → `tag.rare-class`
      3. no anchor found → fall back to `compute_css_path(item)`,
         `selector_stability = "fragile"`

    Below the anchor, builds a path of `tag` / `tag.class` segments down
    to `item`, capped at SELECTOR_MAX_DEPTH. When the real depth exceeds
    SELECTOR_MAX_DEPTH, the path is still truncated to MAX_DEPTH and
    stability is forced to "fragile".

    Returns `(selector, stability)`. Stability is `"stable"` only when
    a real anchor was found and the path below fits within MAX_DEPTH.
    """
    # Step 1: walk up from item.parent looking for anchor.
    anchor: Tag | None = None
    anchor_segment: str = ""
    current: Tag | None = item.parent if isinstance(item.parent, Tag) else None
    while current is not None and current.name not in ("[document]", None):
        # id anchor wins
        raw_id = current.get("id")
        if isinstance(raw_id, str) and raw_id:
            anchor = current
            anchor_segment = f"#{raw_id}"
            break
        # rare class anchor
        raw_classes = current.get("class")
        if isinstance(raw_classes, list):
            cls_list = [str(c) for c in raw_classes]
        elif raw_classes is not None:
            cls_list = [str(raw_classes)]
        else:
            cls_list = []
        rare = [c for c in cls_list if class_count.get(c, 0) <= RARE_CLASS_MAX]
        if rare:
            anchor = current
            anchor_segment = f"{current.name}.{'.'.join(rare)}"
            break
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None

    # No anchor — fragile fallback to full path.
    if anchor is None or not anchor_segment:
        return compute_css_path(item), "fragile"

    # Step 2: build path from anchor down to item.
    chain: list[Tag] = []
    walker: Tag | None = item
    while walker is not None and walker is not anchor:
        chain.append(walker)
        p = walker.parent
        walker = p if isinstance(p, Tag) else None
    chain.reverse()  # anchor-first → item-last

    below_segments: list[str] = []
    for tag in chain:
        raw_classes = tag.get("class")
        if isinstance(raw_classes, list):
            cls_list = [str(c) for c in raw_classes]
        elif raw_classes is not None:
            cls_list = [str(raw_classes)]
        else:
            cls_list = []
        # Keep only rare classes below anchor (avoid noise from common ones).
        rare = [c for c in cls_list if class_count.get(c, 0) <= RARE_CLASS_MAX]
        seg = f"{tag.name}.{'.'.join(rare)}" if rare else tag.name
        below_segments.append(seg)

    # Depth check: truncate path if too deep, force fragile.
    over_depth = len(below_segments) > SELECTOR_MAX_DEPTH
    if over_depth:
        below_segments = below_segments[:SELECTOR_MAX_DEPTH]

    parts = [anchor_segment, *below_segments]
    selector = " > ".join(parts)
    stability = "fragile" if over_depth else "stable"
    return selector, stability


def _try_top_level_keys(body: str) -> list[str] | None:
    """Return up to 10 top-level keys when `body` parses as JSON object,
    or as array whose first element is an object. None on any other case
    (non-JSON, scalar JSON, oversized body, arrays of scalars).

    Used to enrich `json_signals` so the LLM can match against schema
    field names without re-parsing the snippet.
    """
    if len(body) > JSON_PARSE_MAX_BYTES:
        return None
    try:
        parsed: object = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        return keys[:10] if keys else None
    if isinstance(parsed, list) and parsed:
        first = parsed[0]
        if isinstance(first, dict):
            keys = list(first.keys())
            return keys[:10] if keys else None
    return None


def _find_table_candidates(
    soup: BeautifulSoup,
    class_count: dict[str, int],
    *,
    max_tables: int = DISCOVER_TOP_TABLES,
) -> list[dict[str, object]]:
    """Collect `<table>` candidates with pre-computed row keys.

    For each table:
      - `keys`: text content of `<th>` cells from the first row containing
        them; if no row has `<th>`, falls back to first `<td>` of each row.
      - `row_count`: number of `<tr>` rows (excluding thead-only rows when
        keys come from `<th>`).
      - `selector`: short selector via `_build_short_selector` on the
        first `<tr>`.
    Tables with zero rows are skipped.
    """
    candidates: list[dict[str, object]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        keys: list[str] = []
        for row in rows:
            th_cells = row.find_all("th")
            if th_cells:
                keys = [
                    (c.get_text(strip=True) or "")[:DISCOVER_SAMPLE_LEN]
                    for c in th_cells
                ]
                # Filter out empty strings — they carry no signal.
                keys = [k for k in keys if k]
                if keys:
                    break
        if not keys:
            # No <th>: take first cell of each row.
            for row in rows:
                first_td = row.find("td")
                if first_td is None:
                    continue
                text = first_td.get_text(strip=True)
                if text:
                    keys.append(text[:DISCOVER_SAMPLE_LEN])
            keys = keys[:DISCOVER_TOP_DESCENDANTS]
        selector, _ = _build_short_selector(rows[0], class_count)
        candidates.append(
            {
                "selector": selector,
                "row_count": len(rows),
                "keys": keys,
            }
        )
        if len(candidates) >= max_tables:
            break

    def _sort_key(c: dict[str, object]) -> int:
        rc = c["row_count"]
        assert isinstance(rc, int)
        return -rc

    candidates.sort(key=_sort_key)
    return candidates


def _build_page_summary(
    soup: BeautifulSoup,
    repeat_containers: list[dict[str, object]],
    json_signals: list[dict[str, object]],
) -> dict[str, object]:
    """Cheap aggregate flags: table presence, embedded JSON presence,
    repeat-container count estimate. Derived purely from existing data —
    no extra tree walk beyond a single `find('table')` lookup.
    """
    return {
        "has_table": soup.find("table") is not None,
        "has_embedded_json": bool(json_signals),
        "container_count_estimate": len(repeat_containers),
    }


def _find_repeat_containers(
    soup: BeautifulSoup,
    class_count: dict[str, int],
    *,
    max_containers: int = DISCOVER_TOP_CONTAINERS,
) -> list[dict[str, object]]:
    """Find groups of ≥2 siblings sharing the same (tag, classes) signature.

    For each group, computes `common_descendants` — descendants that
    appear in ≥80% of items — so the caller gets a ready-made field list
    for list-struct schemas. Also emits a short `item_selector` (anchored
    on a rare id/class when possible), optional `selector_stability:
    "fragile"` marker when the path is unreliable, and three cheap
    boolean flags (`single_link_item`, `has_th_row`, `single_label_child`)
    that help the LLM pick the right struct shape.
    """
    # Group by (parent_css_path, signature). Using parent_css_path as
    # the key keeps grouping stable across re-parses of the same HTML.
    groups: dict[
        tuple[str, tuple[str, frozenset[str]]], tuple[Tag, list[Tag]]
    ] = {}
    for tag in soup.find_all(True):
        parent = tag.parent
        if not isinstance(parent, Tag):
            continue
        sig = _signature(tag)
        parent_path = compute_css_path(parent)
        key = (parent_path, sig)
        entry = groups.get(key)
        if entry is None:
            groups[key] = (parent, [tag])
        else:
            entry[1].append(tag)

    containers: list[dict[str, object]] = []
    for (parent_path, (tag_name, classes)), (parent, tags) in groups.items():
        if len(tags) < DISCOVER_MIN_REPEAT:
            continue
        # Skip page boilerplate — head metadata (link/meta/script/style in <head>)
        # is never a list-struct candidate, but frequently dominates by count.
        if " > head" in parent_path or parent_path.endswith(" head"):
            continue
        descendants = _compute_common_descendants(tags)
        item_selector, stability = _build_short_selector(tags[0], class_count)
        entry_dict: dict[str, object] = {
            "parent_selector": parent_path,
            "item_selector": item_selector,
            "item_tag": tag_name,
            "item_classes": sorted(classes),
            "count": len(tags),
            "depth": _depth_of(tags[0]),
            "common_descendants": descendants,
            "single_link_item": _detect_single_link_item(tags),
            "has_th_row": _detect_has_th_row(parent, tag_name),
            "single_label_child": _detect_single_label_child(tags),
        }
        # Emit stability marker only when fragile — saves tokens, signals
        # the LLM to prefer `table_candidates` / more precise selectors.
        if stability == "fragile":
            entry_dict["selector_stability"] = "fragile"
        containers.append(entry_dict)

    # Sort by count desc, then depth asc (closer to leaves first on ties).
    def _sort_key(c: dict[str, object]) -> tuple[int, int]:
        count = c["count"]
        depth = c["depth"]
        assert isinstance(count, int)
        assert isinstance(depth, int)
        return (-count, depth)

    containers.sort(key=_sort_key)
    return containers[:max_containers]


def run_discover(html: str) -> DiscoverResult:
    """Build a `DiscoverResult` overview for the given HTML.

    Single-call replacement for blind selector probing: returns tag/class
    frequency, custom data-* attributes, groups of repeating siblings
    (list-struct candidates) with their common descendants (field hints),
    embedded JSON signals (typed <script>, JS-var assignments, bare JSON
    bodies, JSON-shaped attributes), table candidates with row keys, and
    a page-level summary.
    """
    soup = parse_html(html)
    tag_stats, class_stats, id_stats, data_attrs, class_count = (
        _collect_tag_stats(soup)
    )
    # `class_count` is uncapped — used by `_build_short_selector` to detect
    # rare anchor classes (count ≤ RARE_CLASS_MAX) anywhere in the document.
    repeat_containers = _find_repeat_containers(soup, class_count)
    json_signals = _find_json_signals(soup)
    table_candidates = _find_table_candidates(soup, class_count)
    page_summary = _build_page_summary(soup, repeat_containers, json_signals)
    return DiscoverResult(
        tag_stats=tag_stats,
        class_stats=class_stats,
        id_stats=id_stats,
        data_attrs=data_attrs,
        repeat_containers=repeat_containers,
        json_signals=json_signals,
        table_candidates=table_candidates,
        page_summary=page_summary,
    )


def _detect_container_kind(snippet: str) -> str:
    """Return 'object' | 'array' | 'unknown' based on first non-ws char."""
    s = snippet.lstrip()
    if not s:
        return "unknown"
    if s[0] == "{":
        return "object"
    if s[0] == "[":
        return "array"
    return "unknown"


def _find_json_signals(
    soup: BeautifulSoup,
    *,
    max_scripts: int = DISCOVER_TOP_JSON_SCRIPT,
    max_attrs: int = DISCOVER_TOP_JSON_ATTR,
    snippet_len: int = DISCOVER_SNIPPET_LEN,
) -> list[dict[str, object]]:
    """Detect embedded JSON containers in the document.

    Returns signals in **document order** (no priority sort). Detection
    is intentionally lax: this is a reconnaissance tool, the LLM is
    expected to inspect `snippet` and decide what to extract.

    Covers four `<script>` cases:
      - `type` ∈ {application/ld+json, application/json} → typed JSON
      - `var/let/const X = ...` or `window.X = ...` → js-var (first match only)
      - body starting with `{` or `[` → bare-json candidate
      - empty body → skipped

    Plus attributes whose value starts with `{` or `[` (excluding
    `class`, `style`, `href`, `src`, `action`).
    """
    script_signals: list[dict[str, object]] = []

    for script in soup.find_all("script"):
        body = (script.get_text() or "").strip()
        if not body:
            continue

        raw_type = script.get("type", "")
        if isinstance(raw_type, list):
            script_type = raw_type[0] if raw_type else ""
        else:
            script_type = str(raw_type)

        signal: dict[str, object] | None = None
        # Substring of `body` that holds the actual JSON payload (for
        # `_try_top_level_keys`). Same as `body` for typed/bare-json;
        # narrows to the bracket-onwards for js-var signals.
        json_source: str = body

        if script_type in JSON_MIME_TYPES:
            signal = {
                "kind": "script",
                "subtype": (
                    "json-ld"
                    if script_type == "application/ld+json"
                    else "json-mime"
                ),
                "script_type": script_type,
                "snippet": body[:snippet_len],
            }
        else:
            for pat in JS_VAR_PATTERNS:
                m = pat.search(body)
                if m is None:
                    continue
                # m.end() points just past the opening bracket (regex
                # consumes one char of `[{`). Snippet starts there.
                snippet_from = m.end() - 1
                json_source = body[snippet_from:]
                signal = {
                    "kind": "script",
                    "subtype": "js-var",
                    "var_name": m.group(1),
                    "snippet": body[snippet_from : snippet_from + snippet_len],
                }
                break
            if signal is None and body[0] in "{[":
                signal = {
                    "kind": "script",
                    "subtype": "bare-json",
                    "snippet": body[:snippet_len],
                }

        if signal is None:
            continue

        signal["selector"] = compute_css_path(script)
        sid = script.get("id")
        if isinstance(sid, str) and sid:
            signal["script_id"] = sid
        snippet_val = str(signal.get("snippet", ""))
        signal["container_kind"] = _detect_container_kind(snippet_val)
        signal["size"] = len(body)
        top_keys = _try_top_level_keys(json_source)
        if top_keys:
            signal["top_level_keys"] = top_keys
        script_signals.append(signal)

        if len(script_signals) >= max_scripts:
            break

    attr_signals: list[dict[str, object]] = []
    for tag in soup.find_all(True):
        for attr_name, raw_val in list(tag.attrs.items()):
            if attr_name in JSON_SKIP_ATTRS:
                continue
            if not isinstance(raw_val, str):
                continue
            v = raw_val.strip()
            if len(v) < 2 or v[0] not in "{[":
                continue
            attr_signal: dict[str, object] = {
                "kind": "attr",
                "subtype": "attr-json",
                "selector": compute_css_path(tag),
                "attr": attr_name,
                "container_kind": _detect_container_kind(v),
                "snippet": v[:snippet_len],
                "size": len(v),
            }
            top_keys = _try_top_level_keys(v)
            if top_keys:
                attr_signal["top_level_keys"] = top_keys
            attr_signals.append(attr_signal)
            if len(attr_signals) >= max_attrs:
                break
        if len(attr_signals) >= max_attrs:
            break

    return script_signals + attr_signals
