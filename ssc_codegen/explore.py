"""HTML context distillation and structural reconnaissance engine for `ssc-gen scout`.

Provides pure functions and dataclasses that distill raw HTML documents into
token-compact, DOM-verified structural digests for LLM and human KDL schema
authoring. Includes three specialized reconnaissance engines:
1. Embedded JSON Engine (`raw_decode` scanning and deep collection projection).
2. Key-Value & Table Engine (`<table>`, `<dl>`, and two-column repeating rows).
3. Repeating Lists & Folded DOM Skeleton Engine (Union Archetype folding).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

__all__ = [
    "AttrFilter",
    "DiscoverResult",
    "FilterError",
    "ScoutFilters",
    "ScoutResult",
    "compile_filters",
    "run_discover",
    "run_scout",
]

BS4_PARSER = "lxml"

# Default compression budgets (when full=False)
MAX_REPEATING_LISTS = 7
MAX_FIELDS_PER_LIST = 25
MAX_SAMPLES_PER_FIELD = 3
MAX_SAMPLE_LEN = 80
MAX_KV_BLOCKS = 5
MAX_KV_KEYS = 25
MAX_JSON_SIGNALS = 5
MAX_JSON_COLLECTIONS = 5
MAX_JSON_KEYS = 20

MIN_REPEAT_COUNT = 3
JSON_MAX_DEPTH = 8
JSON_PARSE_MAX_BYTES = 512 * 1024

STRIP_TAGS: frozenset[str] = frozenset({"svg", "style", "noscript", "template"})

NOTABLE_ATTRS: tuple[str, ...] = (
    "href",
    "src",
    "data-src",
    "srcset",
    "content",
    "value",
    "datetime",
    "title",
    "alt",
    "itemprop",
    "name",
    "role",
    "type",
)

ANCHOR_ATTRS: tuple[str, ...] = (
    "data-testid",
    "data-test",
    "data-qa",
    "data-cy",
    "itemprop",
    "name",
    "role",
)

WRAPPER_TAGS: frozenset[str] = frozenset({"div", "span", "section"})

SEMANTIC_CONTAINER_TAGS: frozenset[str] = frozenset(
    {"main", "article", "section", "aside", "form", "table", "dl", "ul", "ol"}
)

NAV_CONTAINER_TAGS: frozenset[str] = frozenset({"nav", "header", "footer"})

LABEL_TAGS: frozenset[str] = frozenset({"strong", "b", "dt", "label", "th"})

JSON_MIME_TYPES: frozenset[str] = frozenset(
    {"application/ld+json", "application/json"}
)

JSON_SKIP_ATTRS: frozenset[str] = frozenset(
    {
        "class",
        "style",
        "href",
        "src",
        "action",
        "id",
        "name",
        "alt",
        "title",
        "srcset",
    }
)


# ─────────────────────────── CSS class classifier ────────────────────────────

_HASH_CLASS_RE = re.compile(
    r"^(?:"
    r"css-[a-z0-9]{4,}|"
    r"sc-[a-zA-Z0-9_-]{4,}|"
    r"svelte-[a-z0-9]{4,}|"
    r"jsx-\d+|"
    r"_[a-zA-Z0-9_-]+_[a-z0-9]{4,}|"
    r"[a-zA-Z0-9_-]+__[a-zA-Z0-9_-]+___[a-zA-Z0-9]{4,}|"
    r"styles_[a-zA-Z0-9_-]+__[a-zA-Z0-9]{4,}|"
    r"emotion-[a-z0-9]+"
    r")$"
)

_UTILITY_EXACT: frozenset[str] = frozenset(
    {
        # Transient UI states & modifiers
        "active",
        "selected",
        "disabled",
        "enabled",
        "open",
        "opened",
        "closed",
        "hidden",
        "visible",
        "invisible",
        "show",
        "hide",
        "collapse",
        "collapsed",
        "expanded",
        "first",
        "last",
        "odd",
        "even",
        "current",
        "focused",
        "checked",
        "featured",
        "highlighted",
        "pinned",
        "is-active",
        "is-open",
        "is-hidden",
        "is-selected",
        "is-disabled",
        "has-error",
        # Layout / Bootstrap / Tailwind exact tokens
        "clearfix",
        "container",
        "container-fluid",
        "row",
        "col",
        "flex",
        "inline-flex",
        "grid",
        "inline-grid",
        "block",
        "inline-block",
        "inline",
        "table",
        "table-row",
        "table-cell",
        "contents",
        "flow-root",
        "static",
        "fixed",
        "absolute",
        "relative",
        "sticky",
        "truncate",
        "uppercase",
        "lowercase",
        "capitalize",
        "normal-case",
        "italic",
        "not-italic",
        "underline",
        "overline",
        "line-through",
        "no-underline",
        "antialiased",
        "subpixel-antialiased",
        "border",
        "rounded",
        "shadow",
        "ring",
        "outline",
        "blur",
        "grayscale",
        "invert",
        "sepia",
        "filter",
        "backdrop-filter",
        "transition",
        "transform",
        "sr-only",
        "not-sr-only",
        "d-none",
        "d-inline",
        "d-inline-block",
        "d-block",
        "d-table",
        "d-flex",
        "d-inline-flex",
        "d-grid",
        "w-full",
        "h-full",
        "w-screen",
        "h-screen",
        "w-auto",
        "h-auto",
        "mx-auto",
        "my-auto",
        "m-auto",
        "ml-auto",
        "mr-auto",
        "mt-auto",
        "mb-auto",
        "btn",
    }
)

_UTILITY_PREFIX_RE = re.compile(
    r"^(?:"
    r"-?(?:m|p)[xytblrse]?-(?:\d+|auto|px|\[\S+\])|"
    r"space-[xy]-|"
    r"gap-(?:\d+|x-|y-|px|\[\S+\])|"
    r"(?:w|h|size)-(?:\d+|full|screen|min|max|fit|auto|px|\d+/\d+|\[\S+\])|"
    r"(?:min|max)-(?:w|h)-|"
    r"flex-(?:row|col|wrap|nowrap|1|auto|initial|none|grow|shrink)|"
    r"(?:grow|shrink)(?:-\d+)?$|"
    r"basis-|"
    r"grid-(?:cols|rows|flow)-|"
    r"(?:col|row)-(?:auto|span-|start-|end-|\d+|xs|sm|md|lg|xl|xxl)|"
    r"offset-(?:xs|sm|md|lg|xl|xxl|\d+)|"
    r"order-(?:\d+|first|last|none)|"
    r"(?:items|justify|content|self|place)-(?:start|end|center|between|around|evenly|stretch|baseline|auto|normal)|"
    r"text-(?:xs|sm|base|lg|xl|\d+xl|left|center|right|justify|start|end|wrap|nowrap|balance|pretty|ellipsis|clip|white|black|transparent|current|inherit|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|muted|primary|secondary|success|danger|warning|info|light|dark|body|reset|truncate|uppercase|lowercase|capitalize|decoration-none|\[\S+\])|"
    r"font-(?:thin|extralight|light|normal|medium|semibold|bold|extrabold|black|sans|serif|mono)|"
    r"(?:leading|tracking|line-clamp)-|"
    r"bg-(?:fixed|local|scroll|clip-|origin-|bottom|center|left|right|top|no-repeat|repeat|auto|cover|contain|none|gradient-|transparent|current|inherit|white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|primary|secondary|success|danger|warning|info|light|dark|body|opacity-|\[\S+\])|"
    r"(?:from|via|to)-(?:transparent|current|black|white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|\d+)|"
    r"border-(?:\d+|t|r|b|l|x|y|s|e|solid|dashed|dotted|double|hidden|none|collapse|separate|spacing-|transparent|current|inherit|white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|primary|secondary|success|danger|warning|info|light|dark|\[\S+\])|"
    r"divide-[xy]-|"
    r"rounded-(?:none|sm|md|lg|xl|2xl|3xl|full|t|r|b|l|tl|tr|br|bl|s|e|ss|se|ee|es|\d+|pill|circle)|"
    r"shadow-(?:sm|md|lg|xl|2xl|inner|none)|"
    r"ring-(?:\d+|inset|offset-|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)|"
    r"opacity-\d+|"
    r"z-(?:\d+|auto)|"
    r"-?(?:top|right|bottom|left|inset)-(?:\d+|auto|px|full|\d+/\d+|\[\S+\])|"
    r"overflow-(?:auto|hidden|clip|visible|scroll|x-|y-)|"
    r"overscroll-|"
    r"object-(?:contain|cover|fill|none|scale-down|bottom|center|left|right|top)|"
    r"aspect-(?:auto|square|video|\[\S+\])|"
    r"cursor-(?:auto|default|pointer|wait|text|move|help|not-allowed|none)|"
    r"select-(?:none|text|all|auto)|"
    r"pointer-events-(?:none|auto)|"
    r"transition-(?:none|all|colors|opacity|shadow|transform)|"
    r"(?:duration|delay)-\d+|"
    r"ease-(?:linear|in|out|in-out)|"
    r"animate-(?:none|spin|ping|pulse|bounce)|"
    r"-?(?:scale|rotate|translate|skew)-|"
    r"origin-|"
    r"align-(?:baseline|top|middle|bottom|text-top|text-bottom|sub|super)|"
    r"float-(?:start|end|right|left|none)|"
    r"clear-(?:start|end|left|right|both|none)|"
    r"list-(?:none|disc|decimal|inside|outside|unstyled|inline)|"
    r"appearance-none|"
    r"outline-(?:none|0|\d+)|"
    r"(?:fill|stroke)-(?:none|current|inherit|\w+-\d+)|"
    r"d-(?:sm|md|lg|xl|xxl)-|"
    r"g[xy]?-\d+|"
    r"fs-\d+|"
    r"fw-(?:light|lighter|normal|medium|semibold|bold|bolder)|"
    r"lh-(?:1|sm|base|lg)"
    r")"
)


def _looks_like_random_hash(token: str) -> bool:
    """Check whether a class token has high mixed-case/digit entropy typical of CSS modules."""
    if len(token) < 5:
        return False
    if ":" in token or "/" in token or "[" in token:
        return False
    # Tokens with both digits and mixed case letters like `a1B2c3D` or `x7f9q2`
    has_digit = any(ch.isdigit() for ch in token)
    has_upper = any(ch.isupper() for ch in token)
    has_lower = any(ch.islower() for ch in token)
    if has_digit and has_upper and has_lower and "-" not in token:
        return True
    # Short random-looking hex/alnum suffix after dash e.g. `box-3f8a9c`
    if "-" in token:
        _, _, suffix = token.rpartition("-")
        if (
            len(suffix) >= 5
            and any(c.isdigit() for c in suffix)
            and any(c.isalpha() for c in suffix)
            and all(c in "0123456789abcdefABCDEF" for c in suffix)
        ):
            return True
    # Pure random alphanumeric with >=2 digits mixed with letters and no semantic word structure
    digit_count = sum(1 for ch in token if ch.isdigit())
    if digit_count >= 2 and "-" not in token and "_" not in token:
        # e.g. css1a2b3c
        transitions = sum(
            1
            for i in range(1, len(token))
            if token[i].isdigit() != token[i - 1].isdigit()
        )
        if transitions >= 3:
            return True
    return False


def _classify_class_token(
    token: str,
) -> Literal["hash", "utility", "semantic"]:
    """Classify a single CSS class token into hash, utility, or semantic."""
    t = token.strip()
    if not t:
        return "utility"
    # Tailwind responsive/state modifiers or arbitrary values (`sm:`, `hover:`, `[...]`, `!`)
    if ":" in t or "[" in t or "]" in t or t.startswith("!") or "/" in t:
        return "utility"
    if _HASH_CLASS_RE.match(t) or _looks_like_random_hash(t):
        return "hash"
    low = t.lower()
    if low in _UTILITY_EXACT or _UTILITY_PREFIX_RE.match(low):
        return "utility"
    return "semantic"


def _get_raw_classes(tag: Tag) -> list[str]:
    """Extract raw CSS class list from a Tag."""
    raw = tag.get("class")
    if isinstance(raw, list):
        return [str(c).strip() for c in raw if str(c).strip()]
    if isinstance(raw, str) and raw.strip():
        return [c.strip() for c in raw.split() if c.strip()]
    return []


def _get_semantic_classes(tag: Tag) -> list[str]:
    """Return semantic CSS classes on a Tag (preserving order, deduplicated)."""
    seen: set[str] = set()
    out: list[str] = []
    for cls in _get_raw_classes(tag):
        if cls not in seen and _classify_class_token(cls) == "semantic":
            seen.add(cls)
            out.append(cls)
    return out


# ─────────────────────────── filter spec & compilation ───────────────────────


@dataclass
class AttrFilter:
    """Single attribute filter specification for Zoom-in mode.

    Attributes:
        name: Attribute name to inspect.
        kind: Matching mode (`"present"`, `"exact"`, or `"regex"`).
        value: Expected attribute string or raw regular expression.
        compiled: Compiled regular expression when `kind == "regex"`.
    """

    name: str
    kind: Literal["present", "exact", "regex"]
    value: str = ""
    compiled: re.Pattern[str] | None = None


@dataclass
class ScoutFilters:
    """Compiled filter criteria for Zoom-in mode.

    Attributes:
        text_regex: Compiled regex matched against normalized subtree text.
        attrs: List of attribute filter criteria.
        tag: Optional HTML tag name filter.
        css: Optional CSS selector filter.
    """

    text_regex: re.Pattern[str] | None = None
    attrs: list[AttrFilter] = field(default_factory=list)
    tag: str | None = None
    css: str | None = None

    def is_active(self) -> bool:
        """Check whether any Zoom-in filter criterion is active.

        Returns:
            bool: True if at least one filter criterion is set.
        """
        return bool(
            self.text_regex is not None
            or self.attrs
            or self.tag is not None
            or self.css is not None
        )


class FilterError(ValueError):
    """Raised when a user-supplied CSS selector or regex filter cannot be compiled."""


def _compile_regex(
    pattern: str, ignore_case: bool, fixed: bool
) -> re.Pattern[str]:
    """Compile a regex pattern with optional case-folding or literal escaping."""
    raw = re.escape(pattern) if fixed else pattern
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(raw, flags)
    except re.error as exc:
        raise FilterError(f"invalid regex {pattern!r}: {exc}") from exc


def _parse_attr_flag(raw: str, ignore_case: bool, fixed: bool) -> AttrFilter:
    """Parse `--attr NAME`, `--attr NAME=VAL`, or `--attr NAME=~REGEX`."""
    if not raw or not raw.strip():
        raise FilterError("invalid --attr '': missing attribute name")
    if "=" not in raw:
        return AttrFilter(name=raw.strip(), kind="present")
    name, _, value = raw.partition("=")
    name = name.strip()
    if not name:
        raise FilterError(f"invalid --attr {raw!r}: missing attribute name")
    if value.startswith("~"):
        regex = _compile_regex(value[1:], ignore_case, fixed)
        return AttrFilter(
            name=name, kind="regex", value=value[1:], compiled=regex
        )
    if ignore_case:
        regex = _compile_regex(re.escape(value), ignore_case=True, fixed=False)
        return AttrFilter(name=name, kind="regex", value=value, compiled=regex)
    return AttrFilter(name=name, kind="exact", value=value)


def compile_filters(
    *,
    text: str | None = None,
    attrs: Iterable[str] = (),
    tag: str | None = None,
    css: str | None = None,
    ignore_case: bool = False,
    fixed: bool = False,
) -> ScoutFilters:
    """Compile raw CLI or keyword filter arguments into a `ScoutFilters` object.

    Args:
        text (str | None): Regex or literal string matched against normalized subtree text.
        attrs (Iterable[str]): Attribute filter specifications (`NAME`, `NAME=VAL`, `NAME=~REGEX`).
        tag (str | None): Tag name filter (e.g. `'div'`, `'a'`).
        css (str | None): CSS selector scoping filter.
        ignore_case (bool): Whether regex and attribute matching is case-insensitive.
        fixed (bool): Whether to escape regex metacharacters and match literals.

    Returns:
        ScoutFilters: Validated and compiled filter set.

    Raises:
        FilterError: If any regex, attribute specification, or CSS selector is invalid.
    """
    text_re = (
        _compile_regex(text, ignore_case, fixed) if text is not None else None
    )
    compiled_attrs = [
        _parse_attr_flag(a, ignore_case=ignore_case, fixed=fixed) for a in attrs
    ]
    if css is not None:
        if not css.strip():
            raise FilterError("invalid CSS selector '': empty selector")
        # Validate CSS syntax eagerly against an empty fragment
        probe = BeautifulSoup("<div></div>", BS4_PARSER)
        try:
            probe.select(css)
        except Exception as exc:
            raise FilterError(f"invalid CSS selector {css!r}: {exc}") from exc
    return ScoutFilters(
        text_regex=text_re,
        attrs=compiled_attrs,
        tag=tag.lower().strip() if tag else None,
        css=css,
    )


# ─────────────────────────── ScoutResult ────────────────────────────


@dataclass
class ScoutResult:
    """Unified HTML context distillation and reconnaissance result.

    Attributes:
        mode: Analysis mode (`"overview"` or `"zoom"`).
        matched: Number of matched minimal DOM elements in zoom mode, or total discovered signals in overview mode.
        sample_normalized: True indicating sample text has normalized whitespace.
        page_summary: High-level document metadata and section counts.
        embedded_json: Discovered RFC 8259 JSON payloads from `<script>` tags and attributes.
        kv_blocks: Discovered key-value specification blocks and data tables.
        repeating_lists: Ranked repeating item lists with folded Union Archetype fields.
        navigation_lists: Collapsed navigation link lists.
        zoom_matches: Enclosing container skeletons for Zoom-in mode matches.
    """

    mode: Literal["overview", "zoom"] = "overview"
    matched: int = 0
    sample_normalized: bool = True
    page_summary: dict[str, object] = field(default_factory=dict)
    embedded_json: list[dict[str, object]] = field(default_factory=list)
    kv_blocks: list[dict[str, object]] = field(default_factory=list)
    repeating_lists: list[dict[str, object]] = field(default_factory=list)
    navigation_lists: list[dict[str, object]] = field(default_factory=list)
    zoom_matches: list[dict[str, object]] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize the reconnaissance result as formatted JSON.

        Returns:
            str: Indented JSON string representation of the result.
        """
        payload: dict[str, object] = {
            "mode": self.mode,
            "matched": self.matched,
            "sample_normalized": self.sample_normalized,
            "page_summary": self.page_summary,
            "embedded_json": self.embedded_json,
            "kv_blocks": self.kv_blocks,
            "repeating_lists": self.repeating_lists,
            "navigation_lists": self.navigation_lists,
        }
        if self.mode == "zoom" or self.zoom_matches:
            payload["zoom_matches"] = self.zoom_matches
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_text(self) -> str:
        """Render the reconnaissance result as a token-compact text digest.

        Returns:
            str: Human- and LLM-readable structural digest.
        """
        lines: list[str] = [
            "# sample_normalized: true (whitespace collapsed; not verbatim)"
        ]

        # 1. PAGE SUMMARY
        lines.append("")
        lines.append("=== PAGE SUMMARY ===")
        title = self.page_summary.get("title")
        h1 = self.page_summary.get("h1")
        lines.append(f"mode: {self.mode} (matched={self.matched})")
        if title:
            lines.append(f"title: {title!r}")
        if h1:
            lines.append(f"h1: {h1!r}")
        lines.append(
            f"signals: embedded_json={len(self.embedded_json)}, "
            f"kv_blocks={len(self.kv_blocks)}, "
            f"repeating_lists={len(self.repeating_lists)}, "
            f"navigation_lists={len(self.navigation_lists)}"
        )

        # 2. EMBEDDED JSON
        if self.embedded_json:
            lines.append("")
            lines.append("=== EMBEDDED JSON ===")
            for sig in self.embedded_json:
                kind = sig.get("kind", "script")
                subtype = sig.get("subtype", "")
                sel = sig.get("selector", "")
                size = sig.get("size", 0)
                extra = ""
                if sig.get("var_name"):
                    extra = f" var={sig['var_name']!r}"
                elif sig.get("attr"):
                    extra = f" attr={sig['attr']!r}"
                lines.append(
                    f"[{kind}:{subtype}]{extra} selector={sel!r} size={size}"
                )
                hint = sig.get("kdl_hint")
                if hint:
                    lines.append(f"  kdl: {hint}")
                collections = sig.get("collections", [])
                if isinstance(collections, list):
                    for col in collections:
                        if not isinstance(col, dict):
                            continue
                        cpath = col.get("path", "")
                        ckind = col.get("kind", "object")
                        ccount = col.get("count", 0)
                        path_label = (
                            f'path="{cpath}"' if cpath else "path=(root)"
                        )
                        lines.append(
                            f"  collection [{ckind} x{ccount}] {path_label}"
                        )
                        fields_list = col.get("fields", [])
                        if isinstance(fields_list, list):
                            for fld in fields_list:
                                if not isinstance(fld, dict):
                                    continue
                                fname = fld.get("name", "")
                                ftype = fld.get("type", "str")
                                fsamples = fld.get("samples", [])
                                lines.append(
                                    f"    - {fname}: {ftype} = {fsamples!r}"
                                )

        # 3. KEY-VALUE & TABLES
        if self.kv_blocks:
            lines.append("")
            lines.append("=== KEY-VALUE & TABLES ===")
            for kv in self.kv_blocks:
                kind = kv.get("kind", "kv_table")
                csel = kv.get("container_selector", "")
                rsel = kv.get("rows_selector", "")
                rcount = kv.get("row_count", 0)
                match_flag = " <-- MATCH" if kv.get("matched") else ""
                lines.append(
                    f"[{kind} rows={rcount}] container={csel!r} rows={rsel!r}{match_flag}"
                )
                if kind == "table_list":
                    headers = kv.get("headers", [])
                    if headers:
                        lines.append(f"  headers: {headers!r}")
                    cols = kv.get("columns", [])
                    if isinstance(cols, list):
                        for col in cols:
                            if not isinstance(col, dict):
                                continue
                            col_match = (
                                " <-- MATCH" if col.get("matched") else ""
                            )
                            lines.append(
                                f"    col {col.get('header', '')!r}: "
                                f"css={col.get('css', '')!r} samples={col.get('samples', [])!r}{col_match}"
                            )
                else:
                    ksel = kv.get("key_selector", "")
                    vsel = kv.get("value_selector", "")
                    lines.append(f"  key={ksel!r} value={vsel!r}")
                    entries = kv.get("entries", [])
                    if isinstance(entries, list):
                        for ent in entries:
                            if not isinstance(ent, dict):
                                continue
                            ent_match = (
                                " <-- MATCH" if ent.get("matched") else ""
                            )
                            lines.append(
                                f"    {ent.get('key', '')!r}: {ent.get('sample', '')!r}{ent_match}"
                            )

        # 4. REPEATING LISTS & DOM SKELETON
        if self.repeating_lists or self.navigation_lists:
            lines.append("")
            lines.append("=== REPEATING LISTS & DOM SKELETON ===")
            for lst in self.repeating_lists:
                sel = lst.get("selector", "")
                psel = lst.get("parent_selector", "")
                cnt = lst.get("count", 0)
                score = lst.get("score", 0.0)
                stab = lst.get("selector_stability", "stable")
                match_flag = " <-- MATCH" if lst.get("matched") else ""
                lines.append(
                    f'[repeat x{cnt}] selector="{sel}" parent="{psel}" '
                    f"[{stab}, score={score}]{match_flag}"
                )
                outliers = lst.get("outliers", [])
                if isinstance(outliers, list) and outliers:
                    out_parts: list[str] = []
                    for o in outliers:
                        if isinstance(o, dict):
                            otag = o.get("tag", "")
                            ocls = o.get("classes", [])
                            ocnt = o.get("count", 1)
                            cls_sfx = (
                                "." + ".".join(str(x) for x in ocls)
                                if isinstance(ocls, list) and ocls
                                else ""
                            )
                            out_parts.append(f"{otag}{cls_sfx} (x{ocnt})")
                    if out_parts:
                        lines.append(f"  outliers: {', '.join(out_parts)}")
                fields_list = lst.get("fields", [])
                if isinstance(fields_list, list):
                    for fld in fields_list:
                        if not isinstance(fld, dict):
                            continue
                        lines.append(_format_field_line(fld))
            for nav in self.navigation_lists:
                nsel = nav.get("selector", "")
                ncnt = nav.get("count", 0)
                nsamples = nav.get("samples", [])
                lines.append(f"<!-- nav-list x{ncnt}: {nsel} {nsamples!r} -->")

        # 5. ZOOM MATCHES
        if self.zoom_matches:
            lines.append("")
            lines.append("=== ZOOM MATCHES ===")
            for zm in self.zoom_matches:
                csel = zm.get("container_selector", "")
                ctag = zm.get("container_tag", "")
                msel = zm.get("match_selector", "")
                mtext = zm.get("match_text", "")
                lines.append(
                    f'[zoom-container <{ctag}>] container="{csel}" match="{msel}" text={mtext!r}'
                )
                zfields = zm.get("fields", [])
                if isinstance(zfields, list):
                    for zf in zfields:
                        if not isinstance(zf, dict):
                            continue
                        lines.append(_format_field_line(zf))

        return "\n".join(lines)


DiscoverResult = ScoutResult


def _format_field_line(fld: dict[str, object]) -> str:
    """Format a single field entry inside a repeating list or zoom container."""
    path = fld.get("path", "")
    css = fld.get("css", "")
    kind = fld.get("kind", "scalar")
    present = fld.get("present", 1)
    total = fld.get("total", 1)
    optional = fld.get("optional", False)
    cov = (
        f"[{present}/{total}, optional]" if optional else f"[{present}/{total}]"
    )

    if kind == "array":
        arr_range = fld.get("array_range", [1, 1])
        if isinstance(arr_range, list) and len(arr_range) == 2:
            r_str = f"[array {arr_range[0]}..{arr_range[1]} items]"
        else:
            r_str = "[array]"
        sel_str = f'css-all="{css}" {r_str}'
    else:
        sel_str = f'css="{css}"'

    parts = [f"  - {path} {cov} {sel_str}"]
    samples = fld.get("samples", [])
    if isinstance(samples, list) and samples:
        parts.append(f"text={samples!r}")
    attr_samples = fld.get("attr_samples", {})
    if isinstance(attr_samples, dict) and attr_samples:
        for k, v in attr_samples.items():
            parts.append(f"{k}={v!r}")
    if fld.get("matched"):
        parts.append("<-- MATCH")
    return " ".join(parts)


# ─────────────────────────── DOM utilities & selectors ───────────────────────


def _normalize_ws(text: str, max_len: int = MAX_SAMPLE_LEN) -> str:
    """Collapse internal whitespace and truncate to `max_len`."""
    collapsed = " ".join(text.split())
    if max_len > 0 and len(collapsed) > max_len:
        return collapsed[:max_len] + "…"
    return collapsed


def _safe_select(root: BeautifulSoup | Tag, selector: str) -> list[Tag]:
    """Run `.select(selector)` safely, returning an empty list on any error."""
    if not selector or not selector.strip():
        return []
    try:
        return list(root.select(selector))
    except Exception:  # noqa: BLE001
        return []


_CSS_SIMPLE_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


def _is_valid_css_ident(ident: str) -> bool:
    """Return True if `ident` can be used directly in `.class` or `#id` selector."""
    return bool(ident and _CSS_SIMPLE_IDENT_RE.match(ident))


def _attr_selector_val(val: str) -> str:
    """Escape a value for `[attr="val"]` CSS selector."""
    escaped = val.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _same_node_list(a: list[Tag], b: list[Tag]) -> bool:
    """Check whether two lists of `Tag` contain the exact same DOM elements in order."""
    return len(a) == len(b) and all(
        id(x) == id(y) for x, y in zip(a, b, strict=True)
    )


def _same_node_set(a: list[Tag], b: list[Tag]) -> bool:
    """Check whether two lists of `Tag` contain the exact same set of DOM elements."""
    if len(a) != len(b):
        return False
    return {id(x) for x in a} == {id(y) for y in b}


def compute_css_path(tag: Tag) -> str:
    """Compute an exact, root-anchored CSS path from `<html>` down to `tag`.

    Args:
        tag (Tag): Target BeautifulSoup DOM element.

    Returns:
        str: Root-anchored CSS selector path with `:nth-of-type(...)` disambiguation.
    """
    parts: list[str] = []
    current: Tag | None = tag
    while current is not None and current.name not in ("[document]", None):
        name = current.name
        sem_classes = [
            c for c in _get_semantic_classes(current) if _is_valid_css_ident(c)
        ]
        same_tag_index = 1
        sib: Tag | None = current.find_previous_sibling(name)
        while sib is not None:
            same_tag_index += 1
            sib = sib.find_previous_sibling(name)
        has_sib = (
            current.find_previous_sibling(name) is not None
            or current.find_next_sibling(name) is not None
        )
        cls_part = f".{'.'.join(sem_classes[:2])}" if sem_classes else ""
        nth_part = (
            f":nth-of-type({same_tag_index})"
            if (same_tag_index > 1 or has_sib)
            else ""
        )
        parts.append(f"{name}{cls_part}{nth_part}")
        current = current.parent if isinstance(current.parent, Tag) else None
    parts.reverse()
    return " > ".join(parts)


def _is_safe_selector_attr(attr_name: str) -> bool:
    """Return True if `attr_name` is a stable semantic/testing attribute (`data-*`, `aria-*`, etc.)."""
    return attr_name in ANCHOR_ATTRS or attr_name.startswith(("data-", "aria-"))


def _rank_semantic_classes(
    classes: list[str],
    root: BeautifulSoup | Tag | None,
    target_count: int = 1,
) -> list[str]:
    """Order semantic classes by proximity of their document frequency to `target_count`."""
    if len(classes) <= 1 or root is None:
        return classes

    def _freq_key(cls: str) -> tuple[int, int]:
        freq = len(_safe_select(root, f".{cls}"))
        return (abs(freq - target_count), freq)

    return sorted(classes, key=_freq_key)


def _element_self_candidates(
    tag: Tag,
    *,
    root: BeautifulSoup | Tag | None = None,
    target_count: int = 1,
) -> list[str]:
    """Generate short candidate selector segments for a single `tag`."""
    cands: list[str] = []
    name = tag.name
    raw_id = tag.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        rid = raw_id.strip()
        if _is_valid_css_ident(rid):
            cands.append(f"#{rid}")
            cands.append(f"{name}#{rid}")
        else:
            cands.append(f"{name}[id={_attr_selector_val(rid)}]")

    for attr_name in ANCHOR_ATTRS:
        val = tag.get(attr_name)
        if isinstance(val, str) and val.strip():
            cands.append(
                f"{name}[{attr_name}={_attr_selector_val(val.strip())}]"
            )

    sem = _rank_semantic_classes(
        [c for c in _get_semantic_classes(tag) if _is_valid_css_ident(c)],
        root,
        target_count=target_count,
    )
    if sem:
        for sc in sem:
            cands.append(f"{name}.{sc}")
        if len(sem) > 1:
            cands.append(f"{name}.{'.'.join(sem[:2])}")
        for sc in sem:
            cands.append(f".{sc}")

    for k, v in tag.attrs.items():
        if not k.startswith(("data-", "aria-")):
            continue
        if isinstance(v, str) and v.strip() and len(v.strip()) <= 40:
            cands.append(f"{name}[{k}={_attr_selector_val(v.strip())}]")
        elif _is_valid_css_ident(k):
            cands.append(f"{name}[{k}]")

    cands.append(name)
    return cands


def _synthesize_unique_selector(
    soup: BeautifulSoup, target: Tag
) -> tuple[str, Literal["stable", "fragile"]]:
    """Synthesize a DOM-verified CSS selector that uniquely selects `[target]` in `soup`."""
    # 1. Try direct candidates on target itself
    self_cands = _element_self_candidates(target, root=soup, target_count=1)
    for cand in self_cands:
        if _same_node_list(_safe_select(soup, cand), [target]):
            return cand, "stable"

    # 2. Try combining with an ancestor anchor within <= 3 hops
    ancestors: list[Tag] = []
    curr = target.parent
    while (
        isinstance(curr, Tag)
        and curr.name not in ("[document]", None)
        and len(ancestors) < 4
    ):
        ancestors.append(curr)
        curr = curr.parent

    # Positional step on target within its direct parent
    same_tag_index = 1
    sib: Tag | None = target.find_previous_sibling(target.name)
    while sib is not None:
        same_tag_index += 1
        sib = sib.find_previous_sibling(target.name)
    nth_self = f"{target.name}:nth-of-type({same_tag_index})"

    for depth_idx, anc in enumerate(ancestors):
        anc_cands = _element_self_candidates(anc, root=soup, target_count=1)
        # Filter ancestor candidates that are reasonably selective
        for ac in anc_cands:
            for tc in self_cands:
                sep = " > " if depth_idx == 0 else " "
                comb = f"{ac}{sep}{tc}"
                if _same_node_list(_safe_select(soup, comb), [target]):
                    return comb, "stable"
            if depth_idx == 0:
                comb_nth = f"{ac} > {nth_self}"
                if _same_node_list(_safe_select(soup, comb_nth), [target]):
                    return comb_nth, "stable"

    # 3. Fallback to full verified path
    full_path = compute_css_path(target)
    if _same_node_list(_safe_select(soup, full_path), [target]):
        return full_path, "fragile"

    return target.name, "fragile"


def _synthesize_group_selector(
    soup: BeautifulSoup, parent: Tag, items: list[Tag]
) -> tuple[str, str, Literal["stable", "fragile"]]:
    """Synthesize DOM-verified `(item_selector, parent_selector, stability)` for repeating `items`."""
    parent_sel, parent_stab = _synthesize_unique_selector(soup, parent)
    if not items:
        return parent_sel, parent_sel, "fragile"

    item_tag = items[0].name
    # Shared semantic classes present on ALL items in the group, ranked by correlation with item count
    first_sem = [
        c for c in _get_semantic_classes(items[0]) if _is_valid_css_ident(c)
    ]
    shared_sem = _rank_semantic_classes(
        [
            c
            for c in first_sem
            if all(c in _get_semantic_classes(it) for it in items[1:])
        ],
        soup,
        target_count=len(items),
    )

    # Shared data-*, aria-*, and anchor attributes across all items
    shared_attr_specs: list[str] = []
    for k in items[0].attrs:
        if (
            _is_safe_selector_attr(k)
            and _is_valid_css_ident(k)
            and all(it.has_attr(k) for it in items[1:])
        ):
            v0 = items[0].get(k)
            if (
                isinstance(v0, str)
                and v0.strip()
                and len(v0.strip()) <= 40
                and all(it.get(k) == v0 for it in items[1:])
            ):
                shared_attr_specs.append(
                    f"{item_tag}[{k}={_attr_selector_val(v0.strip())}]"
                )
            if k.startswith(("data-", "aria-")):
                shared_attr_specs.append(f"{item_tag}[{k}]")

    item_specs: list[str] = []
    if shared_sem:
        for sc in shared_sem:
            item_specs.append(f".{sc}")
            item_specs.append(f"{item_tag}.{sc}")
        if len(shared_sem) > 1:
            item_specs.append(f"{item_tag}.{'.'.join(shared_sem[:2])}")
    item_specs.extend(shared_attr_specs)
    item_specs.append(item_tag)

    # Check if there are same-tag outliers in parent that need exclusion
    all_parent_children = [
        c for c in parent.children if isinstance(c, Tag) and c.name == item_tag
    ]
    item_ids = {id(it) for it in items}
    outlier_children = [c for c in all_parent_children if id(c) not in item_ids]
    not_clauses: list[str] = []
    if outlier_children:
        outlier_sem: list[str] = []
        for oc in outlier_children:
            for c in _get_semantic_classes(oc):
                if (
                    _is_valid_css_ident(c)
                    and c not in shared_sem
                    and c not in outlier_sem
                ):
                    outlier_sem.append(c)
        if outlier_sem and len(outlier_sem) <= 3:
            not_sfx = "".join(f":not(.{c})" for c in outlier_sem)
            not_clauses.append(f"{item_tag}{not_sfx}")

    # 1. Try standalone item specs if shared_sem or shared_attr_specs is globally exact
    for spec in item_specs:
        if spec == item_tag:
            continue  # Bare tag globally is rarely a good standalone selector unless verified with parent
        if _same_node_set(_safe_select(soup, spec), items):
            return spec, parent_sel, "stable"

    # 2. Try parent_sel > spec and ancestor anchor > spec
    ancestors: list[Tag] = []
    curr: Tag | None = parent
    while (
        isinstance(curr, Tag)
        and curr.name not in ("[document]", None)
        and len(ancestors) < 3
    ):
        ancestors.append(curr)
        curr = curr.parent if isinstance(curr.parent, Tag) else None

    for depth_idx, anc in enumerate(ancestors):
        anc_cands = _element_self_candidates(anc, root=soup, target_count=1)
        for ac in anc_cands:
            for spec in item_specs + not_clauses:
                if depth_idx == 0:
                    cand_direct = f"{ac} > {spec}"
                    if _same_node_set(_safe_select(soup, cand_direct), items):
                        return cand_direct, parent_sel, "stable"
                cand_desc = f"{ac} {spec}"
                if _same_node_set(_safe_select(soup, cand_desc), items):
                    return cand_desc, parent_sel, "stable"

    # 3. Try parent_sel > spec
    for spec in item_specs + not_clauses:
        cand = f"{parent_sel} > {spec}"
        if _same_node_set(_safe_select(soup, cand), items):
            stab: Literal["stable", "fragile"] = (
                "stable" if parent_stab == "stable" else "fragile"
            )
            return cand, parent_sel, stab

    fallback = f"{parent_sel} > {item_tag}"
    return fallback, parent_sel, "fragile"


# ─────────────────────────── DOM Preprocessing ───────────────────────────────


def _preprocess_dom(soup: BeautifulSoup) -> None:
    """Strip non-content tags (`<svg>`, `<style>`, `<noscript>`, `<template>`) and HTML comments."""
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for tag in soup.find_all(list(STRIP_TAGS)):
        tag.decompose()


def _strip_scripts(soup: BeautifulSoup) -> None:
    """Remove `<script>` tags after Embedded JSON extraction is complete."""
    for script in soup.find_all("script"):
        script.decompose()


# ─────────────────────────── 1. Embedded JSON Engine ─────────────────────────

_JS_ASSIGN_RE = re.compile(
    r"(?:"
    r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)"
    r"|"
    r"\b(?:window|globalThis|self)\.([A-Za-z_$][\w$]*)"
    r"|"
    r"\b(?:window|globalThis|self)\[\s*['\"]([^'\"]+)['\"]\s*\]"
    r"|"
    r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)"
    r")\s*=\s*"
)

_JS_PUSH_RE = re.compile(r"\b([A-Za-z_$][\w$.]*)\.push\(\s*")

_JSON_PARSE_CALL_RE = re.compile(r"""JSON\.parse\(\s*(['"])""")

_GENERIC_JSON_SLICE_RE = re.compile(
    r"(?:['\"]?([A-Za-z_$][\w$.-]*)['\"]?\s*)?(?:(?<![=!<>])=(?!=)|:)\s*(?=[\[{])"
)


def _extract_js_string_literal(
    text: str, quote_pos: int
) -> tuple[str | None, int]:
    """Extract and unescape a JS string literal starting at `quote_pos` (`'` or `"`)."""
    quote = text[quote_pos]
    i = quote_pos + 1
    n = len(text)
    chars: list[str] = []
    while i < n:
        ch = text[i]
        if ch == "\\":
            if i + 1 >= n:
                return None, n
            nxt = text[i + 1]
            if nxt in ('"', "'", "\\", "/"):
                chars.append(nxt)
                i += 2
            elif nxt == "n":
                chars.append("\n")
                i += 2
            elif nxt == "r":
                chars.append("\r")
                i += 2
            elif nxt == "t":
                chars.append("\t")
                i += 2
            elif nxt == "b":
                chars.append("\b")
                i += 2
            elif nxt == "f":
                chars.append("\f")
                i += 2
            elif nxt == "u" and i + 5 < n:
                hex_part = text[i + 2 : i + 6]
                try:
                    chars.append(chr(int(hex_part, 16)))
                    i += 6
                except ValueError:
                    chars.append(nxt)
                    i += 2
            elif nxt == "x" and i + 3 < n:
                hex_part = text[i + 2 : i + 4]
                try:
                    chars.append(chr(int(hex_part, 16)))
                    i += 4
                except ValueError:
                    chars.append(nxt)
                    i += 2
            else:
                chars.append(nxt)
                i += 2
        elif ch == quote:
            return "".join(chars), i + 1
        else:
            chars.append(ch)
            i += 1
    return None, n


def _is_trivial_json(val: object) -> bool:
    """Return True if a parsed JSON value is a trivial object (<2 keys and no nested collections)."""
    if isinstance(val, dict):
        has_nested = any(
            isinstance(v, (dict, list)) and bool(v) for v in val.values()
        )
        return bool(len(val) < 2 and not has_nested)
    if isinstance(val, list):
        if not val:
            return True
        return bool(
            all(not isinstance(x, (dict, list)) for x in val) and len(val) < 2
        )
    return True


def _infer_json_type(values: list[object], total_count: int) -> str:
    """Infer KDL JSON field type (`str`, `int`, `float`, `bool`, `array`, `object`, plus `?`)."""
    non_null = [v for v in values if v is not None]
    is_optional = len(non_null) < total_count
    if not non_null:
        return "str?"
    types_seen: set[str] = set()
    for v in non_null:
        if isinstance(v, bool):
            types_seen.add("bool")
        elif isinstance(v, int):
            types_seen.add("int")
        elif isinstance(v, float):
            types_seen.add("float")
        elif isinstance(v, str):
            types_seen.add("str")
        elif isinstance(v, list):
            types_seen.add("array")
        elif isinstance(v, dict):
            types_seen.add("object")
        else:
            types_seen.add("str")

    if types_seen == {"int", "float"}:
        base = "float"
    elif len(types_seen) == 1:
        base = next(iter(types_seen))
    else:
        base = "str"
    return f"{base}?" if is_optional else base


def _sample_json_val(val: object) -> object:
    """Produce a compact preview sample for a JSON field value."""
    if isinstance(val, str):
        return _normalize_ws(val, MAX_SAMPLE_LEN)
    if isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, list):
        return f"[{len(val)} items]"
    if isinstance(val, dict):
        return f"{{{len(val)} keys}}"
    return None


def _escape_gjson_seg(key: str) -> str:
    """Escape a single key segment for a GJSON path expression."""
    escaped = (
        key.replace("\\", "\\\\")
        .replace(".", "\\.")
        .replace("*", "\\*")
        .replace("?", "\\?")
    )
    return escaped


def _join_gjson_path(prefix: str, key: str) -> str:
    seg = _escape_gjson_seg(key)
    return f"{prefix}.{seg}" if prefix else seg


def _discover_json_collections(
    root_val: object, *, max_keys: int, max_collections: int | None = None
) -> list[dict[str, object]]:
    """Recursively walk a parsed JSON payload up to depth 8 to discover object arrays and data dicts."""
    collections: list[dict[str, object]] = []

    def _walk(node: object, path: str, depth: int) -> None:
        if depth > JSON_MAX_DEPTH:
            return
        if isinstance(node, list):
            dict_items = [x for x in node if isinstance(x, dict)]
            if len(dict_items) >= 2 and len(dict_items) >= len(node) * 0.5:
                # Homogeneous array of objects!
                all_keys: list[str] = []
                seen_k: set[str] = set()
                for d in dict_items:
                    for k in d:
                        ks = str(k)
                        if ks not in seen_k:
                            seen_k.add(ks)
                            all_keys.append(ks)
                fields_out: list[dict[str, object]] = []
                for k in all_keys[:max_keys]:
                    vals = [d.get(k) for d in dict_items if k in d]
                    ftype = _infer_json_type(vals, len(dict_items))
                    samples: list[object] = []
                    for v in vals:
                        if v is None:
                            continue
                        sv = _sample_json_val(v)
                        if sv is not None and sv not in samples:
                            samples.append(sv)
                        if len(samples) >= 2:
                            break
                    fields_out.append(
                        {"name": k, "type": ftype, "samples": samples}
                    )
                collections.append(
                    {
                        "path": path,
                        "kind": "array",
                        "count": len(dict_items),
                        "fields": fields_out,
                    }
                )
            # Also walk inside first few elements if they contain deeper collections
            for idx, item in enumerate(node[:3]):
                if isinstance(item, (dict, list)):
                    sub_path = f"{path}.{idx}" if path else str(idx)
                    _walk(item, sub_path, depth + 1)

        elif isinstance(node, dict):
            # Check if this dict itself is a meaningful data object
            scalar_or_struct_keys = [str(k) for k in node]
            # Record dict if it has >= 3 keys or is root with >= 2 keys
            if len(scalar_or_struct_keys) >= 3 or (
                path == "" and len(scalar_or_struct_keys) >= 2
            ):
                fields_out = []
                for k in scalar_or_struct_keys[:max_keys]:
                    v = node[k]
                    ftype = _infer_json_type([v], 1)
                    sv = _sample_json_val(v)
                    samples = [sv] if sv is not None else []
                    fields_out.append(
                        {"name": k, "type": ftype, "samples": samples}
                    )
                collections.append(
                    {
                        "path": path,
                        "kind": "object",
                        "count": len(scalar_or_struct_keys),
                        "fields": fields_out,
                    }
                )
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    _walk(v, _join_gjson_path(path, str(k)), depth + 1)

    _walk(root_val, "", 0)

    def _col_key(c: dict[str, object]) -> tuple[int, int]:
        cnt = c.get("count")
        return (
            0 if c.get("kind") == "array" else 1,
            -(cnt if isinstance(cnt, int) else 0),
        )

    collections.sort(key=_col_key)
    if max_collections is not None:
        return collections[:max_collections]
    return collections


def _try_decode_json_parse(
    body: str, match: re.Match[str], decoder: json.JSONDecoder
) -> tuple[object, int, int] | None:
    """Extract and `raw_decode` the string literal argument of a `JSON.parse(` match.

    Returns `(parsed_value, raw_byte_size, end_pos)` or `None`.
    """
    quote_pos = match.end() - 1
    unescaped, end_pos = _extract_js_string_literal(body, quote_pos)
    if not unescaped:
        return None
    ustr = unescaped.strip()
    if not ustr or ustr[0] not in "{[":
        return None
    try:
        parsed, _ = decoder.raw_decode(ustr)
    except (ValueError, json.JSONDecodeError):
        return None
    return parsed, len(ustr), end_pos


def _prepare_json_signal_collections(
    parsed: object, *, full: bool
) -> tuple[list[dict[str, object]], str] | None:
    """Validate non-triviality and extract collections + GJSON `path_sfx` for a parsed JSON value."""
    if _is_trivial_json(parsed):
        return None
    max_keys = 1000 if full else MAX_JSON_KEYS
    max_cols = None if full else MAX_JSON_COLLECTIONS
    cols = _discover_json_collections(
        parsed, max_keys=max_keys, max_collections=max_cols
    )
    if not cols:
        return None
    top_col = cols[0]
    path_sfx = f' path="{top_col["path"]}"' if top_col.get("path") else ""
    return cols, path_sfx


def _scan_script_json_payloads(
    body: str, decoder: json.JSONDecoder
) -> list[tuple[str, str | None, object, int]]:
    """Scan a `<script>` body using `raw_decode` for all embedded JSON payloads.

    Returns list of `(subtype, var_name, parsed_value, raw_byte_size)`.
    """
    results: list[tuple[str, str | None, object, int]] = []
    consumed_spans: list[tuple[int, int]] = []

    def _is_consumed(pos: int) -> bool:
        return any(start <= pos < end for start, end in consumed_spans)

    # 1. Scan var/let/const/window and dotted property assignments first
    for m in _JS_ASSIGN_RE.finditer(body):
        rhs_start = m.end()
        if _is_consumed(m.start()) or _is_consumed(rhs_start):
            continue
        var_name = next((g for g in m.groups() if g is not None), None)
        # Check if RHS is JSON.parse(...)
        jp_match = _JSON_PARSE_CALL_RE.match(body, rhs_start)
        if jp_match is not None:
            decoded = _try_decode_json_parse(body, jp_match, decoder)
            if decoded is not None:
                parsed, str_len, end_pos = decoded
                consumed_spans.append((m.start(), end_pos))
                results.append(("json-parse", var_name, parsed, str_len))
                continue
        # Otherwise check if RHS starts with `{` or `[`
        if rhs_start < len(body) and body[rhs_start] in "{[":
            try:
                parsed, end_offset = decoder.raw_decode(body, rhs_start)
                consumed_spans.append((m.start(), end_offset))
                results.append(
                    ("js-var", var_name, parsed, end_offset - rhs_start)
                )
            except (ValueError, json.JSONDecodeError):
                pass

    # 2. Scan standalone JSON.parse("...") calls outside already-consumed assignments
    for m in _JSON_PARSE_CALL_RE.finditer(body):
        if _is_consumed(m.start()):
            continue
        decoded = _try_decode_json_parse(body, m, decoder)
        if decoded is not None:
            parsed, str_len, end_pos = decoded
            consumed_spans.append((m.start(), end_pos))
            results.append(("json-parse", None, parsed, str_len))

    # 3. Scan .push({...}) or .push([...]) calls
    for m in _JS_PUSH_RE.finditer(body):
        arg_start = m.end()
        if _is_consumed(m.start()) or _is_consumed(arg_start):
            continue
        var_name = m.group(1)
        if arg_start < len(body) and body[arg_start] in "{[":
            try:
                parsed, end_offset = decoder.raw_decode(body, arg_start)
                consumed_spans.append((m.start(), end_offset))
                results.append(
                    ("js-push", var_name, parsed, end_offset - arg_start)
                )
            except (ValueError, json.JSONDecodeError):
                pass

    # 4. If bare JSON script (starts with `{` or `[`), try raw_decode at start
    stripped = body.lstrip()
    lead_ws = len(body) - len(stripped)
    if stripped and stripped[0] in "{[" and not _is_consumed(lead_ws):
        try:
            parsed, end_offset = decoder.raw_decode(body, lead_ws)
            consumed_spans.append((lead_ws, end_offset))
            results.append(("bare-json", None, parsed, end_offset - lead_ws))
        except (ValueError, json.JSONDecodeError):
            pass

    # 5. Scan any remaining `{` or `[` following `=` or `:` outside consumed spans
    for m in _GENERIC_JSON_SLICE_RE.finditer(body):
        slice_start = m.end()
        if _is_consumed(m.start()) or _is_consumed(slice_start):
            continue
        if slice_start < len(body) and body[slice_start] in "{[":
            try:
                parsed, end_offset = decoder.raw_decode(body, slice_start)
                consumed_spans.append((m.start(), end_offset))
                key_name = m.group(1)
                results.append(
                    ("js-var", key_name, parsed, end_offset - slice_start)
                )
            except (ValueError, json.JSONDecodeError):
                pass

    return results


def _extract_embedded_json(
    soup: BeautifulSoup, *, full: bool
) -> list[dict[str, object]]:
    """Run the Embedded JSON reconnaissance engine across all scripts and attributes."""
    decoder = json.JSONDecoder()
    signals: list[dict[str, object]] = []

    for script in soup.find_all("script"):
        body = script.string or script.get_text() or ""
        if not body or not body.strip() or len(body) > JSON_PARSE_MAX_BYTES:
            continue
        sel, _ = _synthesize_unique_selector(soup, script)
        raw_type = script.get("type")
        stype = raw_type.strip().lower() if isinstance(raw_type, str) else ""

        if stype in JSON_MIME_TYPES:
            s_trimmed = body.lstrip()
            lead = len(body) - len(s_trimmed)
            if not s_trimmed:
                continue
            try:
                parsed, end_off = decoder.raw_decode(body, lead)
            except (ValueError, json.JSONDecodeError):
                continue
            prep = _prepare_json_signal_collections(parsed, full=full)
            if prep is None:
                continue
            cols, path_sfx = prep
            subtype = (
                "json-ld" if stype == "application/ld+json" else "json-mime"
            )
            hint = f'css "{sel}"; raw inner; jsonify Schema{path_sfx}'
            signals.append(
                {
                    "kind": "script",
                    "subtype": subtype,
                    "selector": sel,
                    "kdl_hint": hint,
                    "size": end_off - lead,
                    "collections": cols,
                }
            )
            continue

        # Standard JS script block: scan for multiple payloads
        payloads = _scan_script_json_payloads(body, decoder)
        for subtype, var_name, parsed, byte_size in payloads:
            prep = _prepare_json_signal_collections(parsed, full=full)
            if prep is None:
                continue
            cols, path_sfx = prep
            if subtype == "bare-json":
                hint = f'css "{sel}"; raw inner; jsonify Schema{path_sfx}'
            elif subtype == "json-parse":
                hint = (
                    f'css "{sel}"; raw inner; '
                    f're "JSON\\\\.parse\\\\([\'\\"](.+?)[\'\\"]\\\\)"; '
                    f"unescape; jsonify Schema{path_sfx}"
                )
            elif var_name:
                escaped_var = re.escape(var_name)
                hint = (
                    f'css "{sel}"; raw inner; '
                    f're "{escaped_var}\\\\s*[:=]\\\\s*(\\\\{{.+\\\\}}|\\\\[.+\\\\])"; '
                    f"jsonify Schema{path_sfx}"
                )
            else:
                hint = f'css "{sel}"; raw inner; jsonify Schema{path_sfx}'

            entry: dict[str, object] = {
                "kind": "script",
                "subtype": subtype,
                "selector": sel,
                "kdl_hint": hint,
                "size": byte_size,
                "collections": cols,
            }
            if var_name:
                entry["var_name"] = var_name
            signals.append(entry)

    # Scan HTML attributes for JSON objects/arrays
    for tag in soup.find_all(True):
        if tag.name == "script":
            continue
        for attr_name, raw_val in tag.attrs.items():
            if attr_name in JSON_SKIP_ATTRS or not isinstance(raw_val, str):
                continue
            val = raw_val.strip()
            if len(val) < 2 or val[0] not in "{[":
                continue
            try:
                parsed, end_off = decoder.raw_decode(val)
            except (ValueError, json.JSONDecodeError):
                continue
            prep = _prepare_json_signal_collections(parsed, full=full)
            if prep is None:
                continue
            cols, path_sfx = prep
            sel, _ = _synthesize_unique_selector(soup, tag)
            hint = (
                f'css "{sel}"; attr "{attr_name}"; '
                f"unescape; jsonify Schema{path_sfx}"
            )
            signals.append(
                {
                    "kind": "attr",
                    "subtype": "attr-json",
                    "selector": sel,
                    "attr": attr_name,
                    "kdl_hint": hint,
                    "size": end_off,
                    "collections": cols,
                }
            )

    if not full:
        return signals[:MAX_JSON_SIGNALS]
    return signals


# ─────────────────────────── 2. Key-Value & Table Engine ─────────────────────

_NUMERIC_ONLY_RE = re.compile(r"^[\d\s.,+$€£¥₽%-]+$")


@dataclass
class _DomNodeMap:
    """Side-table mapping output dictionary `id(...)` keys to live BS4 `Tag` nodes for Zoom-in mode."""

    list_items: dict[int, list[Tag]] = field(default_factory=dict)
    field_nodes: dict[int, list[Tag]] = field(default_factory=dict)
    kv_nodes: dict[int, Tag] = field(default_factory=dict)
    kv_entry_nodes: dict[int, list[Tag]] = field(default_factory=dict)
    kv_col_nodes: dict[int, list[Tag]] = field(default_factory=dict)


def _looks_like_kv_key(text: str) -> bool:
    """Check whether a string looks like a specification label/key."""
    t = text.strip().rstrip(":").strip()
    if not t or len(t) > 50:
        return False
    return not _NUMERIC_ONLY_RE.match(t)


def _extract_direct_residual_text(row: Tag) -> str:
    """Extract normalized direct text children of `row` (excluding child `Tag` subtrees)."""
    parts = [
        str(node).strip()
        for node in row.children
        if isinstance(node, NavigableString)
        and not isinstance(node, Comment)
        and str(node).strip()
    ]
    return _normalize_ws(" ".join(parts).lstrip(":").strip())


def _extract_kv_and_tables(
    soup: BeautifulSoup,
    *,
    full: bool,
    node_map: _DomNodeMap | None = None,
) -> tuple[list[dict[str, object]], set[int]]:
    """Detect `<table>`, `<dl>`, and two-column repeating KV rows.

    Returns `(kv_blocks, claimed_parent_ids)` so repeating KV containers are
    not redundantly duplicated if already surfaced, or can be cross-referenced.
    """
    max_keys = 1000 if full else MAX_KV_KEYS
    blocks: list[dict[str, object]] = []
    claimed_parents: set[int] = set()

    # 1. Inspect <table> elements
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        container_sel, _ = _synthesize_unique_selector(soup, table)
        # Check for horizontal headers in <thead> or first row of <th>
        header_row: Tag | None = None
        headers: list[str] = []
        thead = table.find("thead")
        if isinstance(thead, Tag):
            hr = thead.find("tr")
            if isinstance(hr, Tag):
                ths = hr.find_all(["th", "td"], recursive=False)
                if len(ths) >= 2:
                    header_row = hr
                    headers = [
                        _normalize_ws(c.get_text(" ", strip=True), 50)
                        for c in ths
                    ]
        if not headers:
            first_ths = rows[0].find_all("th", recursive=False)
            if len(first_ths) >= 2:
                header_row = rows[0]
                headers = [
                    _normalize_ws(c.get_text(" ", strip=True), 50)
                    for c in first_ths
                ]

        data_rows = [
            r
            for r in rows
            if r is not header_row
            and len(r.find_all("td", recursive=False)) >= 2
        ]

        # Decide rows selector (verified against soup)
        tbody = table.find("tbody")
        if (
            isinstance(tbody, Tag)
            and header_row is not None
            and header_row.parent is not tbody
        ):
            cand_rows_sel = f"{container_sel} tbody tr"
            if not _safe_select(soup, cand_rows_sel):
                cand_rows_sel = f"{container_sel} tr"
        else:
            cand_rows_sel = f"{container_sel} tr"

        # A. Horizontal-header table (`table_list`)
        if len(headers) >= 2 and len(data_rows) >= 1:
            columns: list[dict[str, object]] = []
            for idx, h_text in enumerate(headers[:max_keys], start=1):
                col_css = f"td:nth-of-type({idx})"
                col_samples: list[str] = []
                col_cells: list[Tag] = []
                for dr in data_rows:
                    cells = _safe_select(dr, col_css)
                    if cells:
                        col_cells.extend(cells)
                        val = _normalize_ws(cells[0].get_text(" ", strip=True))
                        if (
                            val
                            and val not in col_samples
                            and len(col_samples) < MAX_SAMPLES_PER_FIELD
                        ):
                            col_samples.append(val)
                col_entry: dict[str, object] = {
                    "header": h_text or f"col_{idx}",
                    "css": col_css,
                    "samples": col_samples,
                }
                if node_map is not None:
                    node_map.kv_col_nodes[id(col_entry)] = col_cells
                columns.append(col_entry)
            tbl_block: dict[str, object] = {
                "kind": "table_list",
                "container_selector": container_sel,
                "rows_selector": cand_rows_sel,
                "row_count": len(data_rows),
                "headers": headers[:max_keys],
                "columns": columns,
            }
            if node_map is not None:
                node_map.kv_nodes[id(tbl_block)] = table
            blocks.append(tbl_block)
            if tbody is not None:
                claimed_parents.add(id(tbody))
            claimed_parents.add(id(table))

        # B. 2-column Key-Value table (`kv_table`)
        kv_rows_cands = [
            r
            for r in rows
            if r is not header_row
            and len(r.find_all(["th", "td"], recursive=False)) == 2
        ]
        if len(kv_rows_cands) >= 2:
            pairs: list[tuple[str, str, Tag]] = []
            key_tags: set[str] = set()
            val_tags: set[str] = set()
            for r in kv_rows_cands:
                cells = r.find_all(["th", "td"], recursive=False)
                k_txt = (
                    _normalize_ws(cells[0].get_text(" ", strip=True), 50)
                    .rstrip(":")
                    .strip()
                )
                v_txt = _normalize_ws(cells[1].get_text(" ", strip=True))
                if _looks_like_kv_key(k_txt):
                    pairs.append((k_txt, v_txt, r))
                    key_tags.add(cells[0].name)
                    val_tags.add(cells[1].name)

            unique_keys = {p[0] for p in pairs}
            if len(pairs) >= 2 and len(unique_keys) >= len(pairs) * 0.8:
                if key_tags == {"th"} and val_tags == {"td"}:
                    key_sel = "th"
                    val_sel = "td"
                else:
                    key_sel = "td:nth-of-type(1)"
                    val_sel = "td:nth-of-type(2)"
                if _safe_select(table, key_sel) and _safe_select(
                    table, val_sel
                ):
                    entries: list[dict[str, object]] = []
                    for k, v, r_node in pairs[:max_keys]:
                        ent_dict: dict[str, object] = {"key": k, "sample": v}
                        if node_map is not None:
                            node_map.kv_entry_nodes[id(ent_dict)] = [r_node]
                        entries.append(ent_dict)
                    kv_tbl_block: dict[str, object] = {
                        "kind": "kv_table",
                        "container_selector": container_sel,
                        "rows_selector": cand_rows_sel,
                        "key_selector": key_sel,
                        "value_selector": val_sel,
                        "row_count": len(pairs),
                        "entries": entries,
                    }
                    if node_map is not None:
                        node_map.kv_nodes[id(kv_tbl_block)] = table
                    blocks.append(kv_tbl_block)
                    if tbody is not None:
                        claimed_parents.add(id(tbody))
                    claimed_parents.add(id(table))

    # 2. Inspect <dl> definition lists
    for dl in soup.find_all("dl"):
        container_sel, _ = _synthesize_unique_selector(soup, dl)
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        if len(dts) < 2 or len(dds) < 2:
            continue
        # Check if wrapped in row divs (e.g. <dl><div class="row"><dt/><dd/></div></dl>)
        direct_children = [c for c in dl.children if isinstance(c, Tag)]
        wrapper_rows = [
            c
            for c in direct_children
            if c.name not in ("dt", "dd") and c.find("dt") and c.find("dd")
        ]
        dl_entries: list[dict[str, object]] = []
        if len(wrapper_rows) >= 2:
            rows_sel, _, _ = _synthesize_group_selector(soup, dl, wrapper_rows)
            for r in wrapper_rows[:max_keys]:
                dt = r.find("dt")
                dd = r.find("dd")
                if dt and dd:
                    k = (
                        _normalize_ws(dt.get_text(" ", strip=True), 50)
                        .rstrip(":")
                        .strip()
                    )
                    v = _normalize_ws(dd.get_text(" ", strip=True))
                    if k:
                        ent_dict = {"key": k, "sample": v}
                        if node_map is not None:
                            node_map.kv_entry_nodes[id(ent_dict)] = [r]
                        dl_entries.append(ent_dict)
        else:
            rows_sel = f"{container_sel} > dt"
            if not _safe_select(soup, rows_sel):
                rows_sel = f"{container_sel} dt"
            for dt in dts[:max_keys]:
                dd = dt.find_next_sibling("dd")
                if dd is not None:
                    k = (
                        _normalize_ws(dt.get_text(" ", strip=True), 50)
                        .rstrip(":")
                        .strip()
                    )
                    v = _normalize_ws(dd.get_text(" ", strip=True))
                    if k:
                        ent_dict = {"key": k, "sample": v}
                        if node_map is not None:
                            node_map.kv_entry_nodes[id(ent_dict)] = [dt, dd]
                        dl_entries.append(ent_dict)

        key_sel = "dt"
        val_sel = "dd" if _safe_select(dl, "dd") else "dt + dd"
        if (
            len(dl_entries) >= 2
            and _safe_select(dl, key_sel)
            and _safe_select(dl, val_sel)
        ):
            dl_block: dict[str, object] = {
                "kind": "dl",
                "container_selector": container_sel,
                "rows_selector": rows_sel,
                "key_selector": key_sel,
                "value_selector": val_sel,
                "row_count": len(dl_entries),
                "entries": dl_entries,
            }
            if node_map is not None:
                node_map.kv_nodes[id(dl_block)] = dl
            blocks.append(dl_block)
            claimed_parents.add(id(dl))

    # 3. Inspect repeating 2-column div/li label-value rows (or single label tag + residual text)
    for parent in soup.find_all(True):
        if id(parent) in claimed_parents or parent.name in (
            "head",
            "table",
            "tbody",
            "thead",
            "tr",
            "dl",
            "nav",
        ):
            continue
        children = [
            c
            for c in parent.children
            if isinstance(c, Tag) and c.name in ("div", "li", "p")
        ]
        if len(children) < MIN_REPEAT_COUNT:
            continue

        # Check if children have consistent 2-child key/value or label-tag + residual text structure
        kv_rows: list[tuple[Tag, Tag, Tag | None, str, str]] = []
        for ch in children:
            sub_tags = [s for s in ch.children if isinstance(s, Tag)]
            if len(sub_tags) == 2:
                left, right = sub_tags[0], sub_tags[1]
                # Neither should be a complex multi-field card, heading, or link list
                if (
                    left.find_all(True)
                    or len(right.find_all(True)) > 2
                    or left.name
                    in ("h1", "h2", "h3", "h4", "h5", "h6", "img", "figure")
                    or (left.name == "a" and right.name == "a")
                ):
                    continue
                k_full = " ".join(left.get_text(" ", strip=True).split())
                k_clean = k_full.rstrip(":").strip()
                v_raw = _normalize_ws(right.get_text(" ", strip=True))
                if _looks_like_kv_key(k_clean) and v_raw:
                    kv_rows.append((ch, left, right, k_clean, v_raw))
            elif len(sub_tags) == 1 and sub_tags[0].name in LABEL_TAGS:
                label_tag = sub_tags[0]
                if label_tag.find_all(True):
                    continue
                k_full = " ".join(label_tag.get_text(" ", strip=True).split())
                k_clean = k_full.rstrip(":").strip()
                v_raw = _extract_direct_residual_text(ch)
                if _looks_like_kv_key(k_clean) and v_raw:
                    kv_rows.append((ch, label_tag, None, k_clean, v_raw))

        if len(kv_rows) >= MIN_REPEAT_COUNT:
            unique_k = {r[3] for r in kv_rows}
            # Require >=80% unique keys and ensure keys are not all numbered item titles (e.g. "Item 0-0")
            has_non_numbered_key = not all(
                any(ch.isdigit() for ch in k) for k in unique_k
            )
            if len(unique_k) >= len(kv_rows) * 0.8 and has_non_numbered_key:
                row_tags = [r[0] for r in kv_rows]
                rows_sel, container_sel, _ = _synthesize_group_selector(
                    soup, parent, row_tags
                )
                first_left = kv_rows[0][1]
                first_right = kv_rows[0][2]
                l_sem = [
                    c
                    for c in _get_semantic_classes(first_left)
                    if _is_valid_css_ident(c)
                ]
                if l_sem and all(
                    l_sem[0] in _get_semantic_classes(r[1]) for r in kv_rows
                ):
                    key_sel = f"{first_left.name}.{l_sem[0]}"
                elif first_right is None or first_left.name != first_right.name:
                    key_sel = first_left.name
                else:
                    key_sel = f"{first_left.name}:nth-of-type(1)"

                if first_right is None or any(r[2] is None for r in kv_rows):
                    val_sel = ":scope"
                else:
                    r_sem = [
                        c
                        for c in _get_semantic_classes(first_right)
                        if _is_valid_css_ident(c)
                    ]
                    if r_sem and all(
                        r[2] is not None
                        and r_sem[0] in _get_semantic_classes(r[2])
                        for r in kv_rows
                    ):
                        val_sel = f"{first_right.name}.{r_sem[0]}"
                    elif first_left.name != first_right.name:
                        val_sel = first_right.name
                    else:
                        val_sel = f"{first_right.name}:nth-of-type(2)"

                if _safe_select(parent, key_sel) and (
                    val_sel == ":scope" or _safe_select(parent, val_sel)
                ):
                    entries = []
                    for r_tag, _, _, k, v in kv_rows[:max_keys]:
                        ent_dict = {"key": k, "sample": v}
                        if node_map is not None:
                            node_map.kv_entry_nodes[id(ent_dict)] = [r_tag]
                        entries.append(ent_dict)
                    kv_row_block: dict[str, object] = {
                        "kind": "kv_rows",
                        "container_selector": container_sel,
                        "rows_selector": rows_sel,
                        "key_selector": key_sel,
                        "value_selector": val_sel,
                        "row_count": len(kv_rows),
                        "entries": entries,
                    }
                    if node_map is not None:
                        node_map.kv_nodes[id(kv_row_block)] = parent
                    blocks.append(kv_row_block)
                    claimed_parents.add(id(parent))

    if not full:
        return blocks[:MAX_KV_BLOCKS], claimed_parents
    return blocks, claimed_parents


# ─────────────────── 3. Repeating Lists & Folded DOM Skeleton ────────────────


def _descendant_tag_set(tag: Tag) -> set[str]:
    """Return the set of descendant HTML tag names inside `tag`."""
    return {d.name for d in tag.find_all(True) if isinstance(d, Tag)}


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _are_siblings_compatible(a: Tag, b: Tag) -> bool:
    """Return True if sibling tags `a` and `b` belong to the same repeating cluster."""
    if a.name != b.name:
        return False
    sem_a = set(_get_semantic_classes(a))
    sem_b = set(_get_semantic_classes(b))
    if sem_a and sem_b:
        return bool(sem_a & sem_b)
    # Classless page sections with distinct IDs (e.g. <section id="sec-1">, <section id="sec-2">)
    # are distinct containers, not repeating items.
    if (
        not sem_a
        and not sem_b
        and a.name in ("section", "div", "main", "aside", "ul", "ol")
        and a.get("id")
        and b.get("id")
        and a.get("id") != b.get("id")
    ):
        return False
    # When at least one lacks semantic classes, compare descendant structure
    desc_a = _descendant_tag_set(a)
    desc_b = _descendant_tag_set(b)
    if not desc_a and not desc_b:
        # Both are leaf tags of the same name (only cluster if neither has distinct semantic classes)
        return not sem_a and not sem_b
    return _jaccard_similarity(desc_a, desc_b) >= 0.5


def _cluster_parent_children(
    soup: BeautifulSoup, parent: Tag
) -> list[tuple[list[Tag], list[dict[str, object]]]]:
    """Cluster direct child tags of `parent` into repeating groups (>= 3 items) and outliers."""
    children = [c for c in parent.children if isinstance(c, Tag)]
    if len(children) < MIN_REPEAT_COUNT:
        return []

    clusters: list[list[Tag]] = []
    cluster_indices: list[list[int]] = []

    for idx, child in enumerate(children):
        placed = False
        for c_idx, cluster in enumerate(clusters):
            # Check compatibility with the cluster's first or majority elements
            if _are_siblings_compatible(cluster[0], child) or (
                len(cluster) > 1
                and _are_siblings_compatible(cluster[-1], child)
            ):
                cluster.append(child)
                cluster_indices[c_idx].append(idx)
                placed = True
                break
        if not placed:
            clusters.append([child])
            cluster_indices.append([idx])

    valid_results: list[tuple[list[Tag], list[dict[str, object]]]] = []
    for c_idx, cluster in enumerate(clusters):
        if len(cluster) < MIN_REPEAT_COUNT:
            continue
        indices = cluster_indices[c_idx]
        first_pos, last_pos = indices[0], indices[-1]
        in_cluster = set(indices)

        # Find outliers (< 3 items) that sit inside the span of this cluster or in the same parent
        outlier_groups: dict[tuple[str, tuple[str, ...]], list[Tag]] = {}
        for o_idx, other_cluster in enumerate(clusters):
            if o_idx == c_idx or len(other_cluster) >= MIN_REPEAT_COUNT:
                continue
            o_positions = cluster_indices[o_idx]
            # Check if any element of other_cluster sits between cluster items or is a sibling
            if (
                any(first_pos < p < last_pos for p in o_positions)
                or len(clusters) == 2
            ):
                for o_tag in other_cluster:
                    if id(o_tag) not in in_cluster:
                        key = (o_tag.name, tuple(_get_semantic_classes(o_tag)))
                        outlier_groups.setdefault(key, []).append(o_tag)

        outliers_out: list[dict[str, object]] = []
        for (otag, oclasses), otags in outlier_groups.items():
            osel, _ = _synthesize_unique_selector(soup, otags[0])
            outliers_out.append(
                {
                    "tag": otag,
                    "classes": list(oclasses),
                    "count": len(otags),
                    "selector": osel,
                }
            )
        valid_results.append((cluster, outliers_out))

    return valid_results


def _is_navigation_cluster(parent: Tag, items: list[Tag]) -> bool:
    """Detect whether a repeating cluster is a navigation or boilerplate link list."""
    # Check if inside <nav>, <header>, or <footer>
    curr: Tag | None = parent
    while isinstance(curr, Tag) and curr.name not in ("[document]", None):
        if curr.name in NAV_CONTAINER_TAGS:
            return True
        sem_str = " ".join(_get_semantic_classes(curr)).lower()
        if any(
            nav_word in sem_str
            for nav_word in (
                "nav",
                "navbar",
                "menu",
                "breadcrumb",
                "pagination",
                "footer",
                "header",
            )
        ):
            return True
        curr = curr.parent if isinstance(curr.parent, Tag) else None

    # Check if every item is a bare <a> or wraps a single <a> with no secondary data fields
    for item in items:
        if item.name == "a":
            if len(item.find_all(True)) == 0:
                continue
            return False
        desc_tags = item.find_all(True)
        if len(desc_tags) == 1 and desc_tags[0].name == "a":
            # Ensure item has no extra text outside the <a>
            item_txt = _normalize_ws(item.get_text(" ", strip=True))
            a_txt = _normalize_ws(desc_tags[0].get_text(" ", strip=True))
            if item_txt == a_txt:
                continue
        return False
    return True


def _has_direct_text(tag: Tag) -> bool:
    """Check whether `tag` has non-whitespace direct `NavigableString` children."""
    for ch in tag.children:
        if (
            isinstance(ch, NavigableString)
            and not isinstance(ch, Comment)
            and str(ch).strip()
        ):
            return True
    return False


def _has_notable_attrs(tag: Tag) -> bool:
    """Check whether `tag` carries extractable data attributes (`href`, `src`, `data-*`, etc.)."""
    for attr in NOTABLE_ATTRS:
        if tag.has_attr(attr):
            return True
    return any(k.startswith(("data-", "aria-")) for k in tag.attrs)


def _is_elidable_wrapper(
    tag: Tag, multi_child_sigs: set[tuple[str, tuple[str, ...]]]
) -> bool:
    """Return True if `tag` is a pure single-child layout wrapper across all items."""
    if tag.name not in WRAPPER_TAGS:
        return False
    if _has_direct_text(tag) or _has_notable_attrs(tag):
        return False
    sig = (tag.name, tuple(_get_semantic_classes(tag)))
    if sig in multi_child_sigs:
        return False
    child_tags = [c for c in tag.children if isinstance(c, Tag)]
    return len(child_tags) == 1


def _node_step_label(tag: Tag) -> str:
    """Format a single tag step (`tag.sem_class`) for relative path construction."""
    sem = [c for c in _get_semantic_classes(tag) if _is_valid_css_ident(c)]
    if sem:
        return f"{tag.name}.{sem[0]}"
    for attr_name in (*ANCHOR_ATTRS, "aria-label"):
        val = tag.get(attr_name)
        if isinstance(val, str) and val.strip() and len(val.strip()) <= 40:
            return f"{tag.name}[{attr_name}={_attr_selector_val(val.strip())}]"
    return tag.name


def _collect_item_field_nodes(
    item: Tag,
    multi_child_sigs: set[tuple[str, tuple[str, ...]]] | None = None,
) -> list[tuple[tuple[str, ...], Tag]]:
    """Walk `item` and return `(collapsed_steps_tuple, target_tag)` for extractable descendant nodes."""
    results: list[tuple[tuple[str, ...], Tag]] = []
    mc_sigs = multi_child_sigs or set()

    def _walk(curr: Tag, steps: tuple[str, ...]) -> None:
        child_tags = [c for c in curr.children if isinstance(c, Tag)]
        # Elide pure layout wrappers
        if _is_elidable_wrapper(curr, mc_sigs):
            _walk(child_tags[0], steps)
            return

        step = _node_step_label(curr)
        new_steps = (*steps, step)

        # If single child and curr has no direct text of its own (e.g., h3 > a)
        sig = (curr.name, tuple(_get_semantic_classes(curr)))
        if (
            len(child_tags) == 1
            and sig not in mc_sigs
            and not _has_direct_text(curr)
            and not _has_notable_attrs(curr)
        ):
            _walk(child_tags[0], new_steps)
            return

        # Record curr if it is a leaf with text/attrs, or has direct text/notable attrs
        is_leaf = len(child_tags) == 0
        has_text = bool(_normalize_ws(curr.get_text(" ", strip=True)))
        has_attrs = _has_notable_attrs(curr)

        if (
            (is_leaf and (has_text or has_attrs))
            or _has_direct_text(curr)
            or has_attrs
        ):
            results.append((new_steps, curr))

        for ch in child_tags:
            _walk(ch, new_steps)

    top_children = [c for c in item.children if isinstance(c, Tag)]
    if not top_children:
        # Item itself is a leaf tag (e.g. <li class="item">text</li>)
        if _normalize_ws(item.get_text(" ", strip=True)) or _has_notable_attrs(
            item
        ):
            results.append(((_node_step_label(item),), item))
        return results

    for ch in top_children:
        _walk(ch, ())
    return results


def _synthesize_relative_selector(
    items: list[Tag],
    steps: tuple[str, ...],
    sample_nodes: list[Tag],
    *,
    positional_idx: int | None = None,
) -> str:
    """Synthesize and verify a relative CSS selector within `items` for `sample_nodes`."""
    if not sample_nodes:
        return " > ".join(steps)
    target0 = sample_nodes[0]
    if target0 in items:
        return ":scope"

    last_step = steps[-1] if steps else _node_step_label(target0)
    if positional_idx is not None:
        base_tag = target0.name
        sem = [
            c for c in _get_semantic_classes(target0) if _is_valid_css_ident(c)
        ]
        last_with_nth = (
            f"{base_tag}.{sem[0]}:nth-of-type({positional_idx})"
            if sem
            else f"{base_tag}:nth-of-type({positional_idx})"
        )
        cands: list[str] = []
        if len(steps) > 1:
            prefix = " > ".join(steps[:-1])
            cands.append(f"{prefix} > {last_with_nth}")
            cands.append(f"{steps[-2]} > {last_with_nth}")
        cands.append(last_with_nth)
        cands.append(f"{base_tag}:nth-of-type({positional_idx})")
    else:
        cands = []
        # 1. Try shortest unique leaf step (e.g. `.price`, `h3.title`, `a.url`)
        sem = [
            c for c in _get_semantic_classes(target0) if _is_valid_css_ident(c)
        ]
        if sem:
            for sc in sem:
                cands.append(f".{sc}")
                cands.append(f"{target0.name}.{sc}")
        for attr_name, val in target0.attrs.items():
            if not _is_safe_selector_attr(attr_name):
                continue
            if isinstance(val, str) and val.strip() and len(val.strip()) <= 40:
                cands.append(
                    f"{target0.name}[{attr_name}={_attr_selector_val(val.strip())}]"
                )
        if len(steps) > 1:
            cands.append(" > ".join(steps[-2:]))
        cands.append(" > ".join(steps))
        cands.append(last_step)

    target_ids = {id(n) for n in sample_nodes}
    items_with_target = {
        id(it)
        for it in items
        if any(id(d) in target_ids for d in it.find_all(True))
        or id(it) in target_ids
    }
    for cand in cands:
        matched_ok = True
        found_any = False
        for it in items:
            sel_nodes = _safe_select(it, cand)
            expect_match = id(it) in items_with_target
            if expect_match:
                if not sel_nodes or any(
                    id(n) not in target_ids for n in sel_nodes
                ):
                    matched_ok = False
                    break
                found_any = True
            else:
                if sel_nodes:
                    matched_ok = False
                    break
        if matched_ok and found_any:
            return cand

    return cands[-1] if cands else target0.name


def _extract_node_samples(
    nodes: list[Tag],
) -> tuple[list[str], list[str], dict[str, list[str]]]:
    """Extract `(text_samples, attr_names, attr_samples)` across `nodes`."""
    text_samples: list[str] = []
    seen_texts: set[str] = set()
    attr_names_set: set[str] = set()
    attr_samples: dict[str, list[str]] = {}

    for node in nodes:
        txt = _normalize_ws(node.get_text(" ", strip=True), MAX_SAMPLE_LEN)
        if (
            txt
            and txt not in seen_texts
            and len(text_samples) < MAX_SAMPLES_PER_FIELD
        ):
            seen_texts.add(txt)
            text_samples.append(txt)

        for k, v in node.attrs.items():
            if k in ("class", "style", "id"):
                continue
            attr_names_set.add(k)
            if k in NOTABLE_ATTRS or k.startswith(("data-", "aria-")):
                val_str = " ".join(v) if isinstance(v, list) else str(v)
                val_norm = _normalize_ws(val_str, MAX_SAMPLE_LEN)
                if val_norm:
                    bucket = attr_samples.setdefault(k, [])
                    if (
                        val_norm not in bucket
                        and len(bucket) < MAX_SAMPLES_PER_FIELD
                    ):
                        bucket.append(val_norm)

    return text_samples, sorted(attr_names_set), attr_samples


def _build_union_archetype_fields(
    items: list[Tag],
    *,
    full: bool,
    node_map: _DomNodeMap | None = None,
) -> list[dict[str, object]]:
    """Fold `items` into a Union Archetype of field definitions."""
    total_items = len(items)
    if total_items == 0:
        return []

    # Identify tags that ever have >1 child tag across items so they are never elided as single-child wrappers
    multi_child_sigs: set[tuple[str, tuple[str, ...]]] = set()
    for item in items:
        for d in item.find_all(True):
            ch_tags = [c for c in d.children if isinstance(c, Tag)]
            if len(ch_tags) > 1:
                multi_child_sigs.add((d.name, tuple(_get_semantic_classes(d))))

    # Per item, group nodes by their collapsed step signature `steps: tuple[str, ...]`
    sig_order: list[tuple[str, ...]] = []
    sig_seen: set[tuple[str, ...]] = set()
    per_item_by_sig: list[dict[tuple[str, ...], list[Tag]]] = []

    for item in items:
        item_map: dict[tuple[str, ...], list[Tag]] = {}
        for steps, node in _collect_item_field_nodes(item, multi_child_sigs):
            if steps not in sig_seen:
                sig_seen.add(steps)
                sig_order.append(steps)
            item_map.setdefault(steps, []).append(node)
        per_item_by_sig.append(item_map)

    fields_out: list[dict[str, object]] = []

    for steps in sig_order:
        counts_per_item = [
            len(imap.get(steps, []))
            for imap in per_item_by_sig
            if steps in imap
        ]
        if not counts_per_item:
            continue
        present_items = len(counts_per_item)
        max_per_item = max(counts_per_item)
        min_per_item = min(counts_per_item)

        if max_per_item == 1:
            # Scalar field
            all_nodes = [
                imap[steps][0] for imap in per_item_by_sig if steps in imap
            ]
            rel_css = _synthesize_relative_selector(items, steps, all_nodes)
            samples, attrs, attr_samples = _extract_node_samples(all_nodes)
            if not samples and not attr_samples:
                continue
            fld_dict: dict[str, object] = {
                "path": " > ".join(steps),
                "css": rel_css,
                "kind": "scalar",
                "present": present_items,
                "total": total_items,
                "optional": present_items < total_items,
                "attrs": attrs,
                "samples": samples,
                "attr_samples": attr_samples,
            }
            if node_map is not None:
                node_map.field_nodes[id(fld_dict)] = all_nodes
            fields_out.append(fld_dict)
        else:
            # Multiple occurrences per item: decide Positional Slots vs Array
            # Consistent count across >= 80% of items containing this signature AND max_per_item <= 6
            mode_count = max(set(counts_per_item), key=counts_per_item.count)
            consistent_ratio = sum(
                1 for c in counts_per_item if c == mode_count
            ) / len(counts_per_item)
            if consistent_ratio >= 0.8 and max_per_item <= 6 and mode_count > 1:
                for slot_idx in range(1, max_per_item + 1):
                    slot_nodes = [
                        imap[steps][slot_idx - 1]
                        for imap in per_item_by_sig
                        if steps in imap and len(imap[steps]) >= slot_idx
                    ]
                    if not slot_nodes:
                        continue
                    slot_present = len(slot_nodes)
                    slot_steps = (
                        *steps[:-1],
                        f"{steps[-1]}:nth-of-type({slot_idx})",
                    )
                    rel_css = _synthesize_relative_selector(
                        items,
                        steps,
                        slot_nodes,
                        positional_idx=slot_idx,
                    )
                    samples, attrs, attr_samples = _extract_node_samples(
                        slot_nodes
                    )
                    if not samples and not attr_samples:
                        continue
                    pos_dict: dict[str, object] = {
                        "path": " > ".join(slot_steps),
                        "css": rel_css,
                        "kind": "positional",
                        "present": slot_present,
                        "total": total_items,
                        "optional": slot_present < total_items,
                        "attrs": attrs,
                        "samples": samples,
                        "attr_samples": attr_samples,
                    }
                    if node_map is not None:
                        node_map.field_nodes[id(pos_dict)] = slot_nodes
                    fields_out.append(pos_dict)
            else:
                # Nested array (`css-all`)
                all_nodes = [
                    n
                    for imap in per_item_by_sig
                    if steps in imap
                    for n in imap[steps]
                ]
                rel_css = _synthesize_relative_selector(items, steps, all_nodes)
                samples, attrs, attr_samples = _extract_node_samples(all_nodes)
                if not samples and not attr_samples:
                    continue
                arr_dict: dict[str, object] = {
                    "path": " > ".join(steps),
                    "css": rel_css,
                    "kind": "array",
                    "is_array": True,
                    "present": present_items,
                    "total": total_items,
                    "optional": present_items < total_items,
                    "array_range": [min_per_item, max_per_item],
                    "attrs": attrs,
                    "samples": samples,
                    "attr_samples": attr_samples,
                }
                if node_map is not None:
                    node_map.field_nodes[id(arr_dict)] = all_nodes
                fields_out.append(arr_dict)

    max_f = 1000 if full else MAX_FIELDS_PER_LIST
    return fields_out[:max_f]


def _score_repeating_list(
    items: list[Tag], fields: list[dict[str, object]]
) -> float:
    """Compute information density score for a repeating list candidate."""
    count = len(items)
    unique_leaf_fields = len(fields)
    distinct_samples: set[str] = set()
    for f in fields:
        samples = f.get("samples")
        if isinstance(samples, list):
            for s in samples:
                if isinstance(s, str):
                    distinct_samples.add(s)
    text_diversity_bonus = min(10.0, len(distinct_samples) * 0.5)
    score = count * (1.0 + 2.0 * unique_leaf_fields + text_diversity_bonus)
    return round(score, 1)


def _extract_repeating_and_nav_lists(
    soup: BeautifulSoup,
    claimed_kv_parents: set[int],
    *,
    full: bool,
    node_map: _DomNodeMap | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Discover repeating item lists and navigation lists across `soup`."""
    repeating_lists: list[dict[str, object]] = []
    navigation_lists: list[dict[str, object]] = []
    claimed_subtrees: set[int] = set(claimed_kv_parents)

    for parent in soup.find_all(True):
        if parent.name in (
            "head",
            "table",
            "thead",
            "tbody",
            "tr",
            "dl",
            "select",
        ):
            continue
        if id(parent) in claimed_subtrees:
            continue

        clusters = _cluster_parent_children(soup, parent)
        for items, outliers in clusters:
            item_sel, parent_sel, stability = _synthesize_group_selector(
                soup, parent, items
            )
            if _is_navigation_cluster(parent, items) and not full:
                for it in items:
                    claimed_subtrees.add(id(it))
                    for d in it.find_all(True):
                        claimed_subtrees.add(id(d))
                nav_samples: list[str] = []
                for it in items:
                    txt = _normalize_ws(
                        it.get_text(" ", strip=True), MAX_SAMPLE_LEN
                    )
                    if txt and txt not in nav_samples:
                        nav_samples.append(txt)
                    if len(nav_samples) >= MAX_SAMPLES_PER_FIELD:
                        break
                navigation_lists.append(
                    {
                        "selector": item_sel,
                        "count": len(items),
                        "samples": nav_samples,
                    }
                )
                continue

            fields = _build_union_archetype_fields(
                items, full=full, node_map=node_map
            )
            if not fields:
                continue
            for it in items:
                claimed_subtrees.add(id(it))
                for d in it.find_all(True):
                    claimed_subtrees.add(id(d))
            score = _score_repeating_list(items, fields)
            first_sem = _get_semantic_classes(items[0])
            shared_sem = _rank_semantic_classes(
                [
                    c
                    for c in first_sem
                    if all(c in _get_semantic_classes(it) for it in items[1:])
                ],
                soup,
                target_count=len(items),
            )
            lst_dict: dict[str, object] = {
                "selector": item_sel,
                "parent_selector": parent_sel,
                "item_tag": items[0].name,
                "item_classes": shared_sem if shared_sem else first_sem,
                "count": len(items),
                "score": score,
                "selector_stability": stability,
                "outliers": outliers,
                "fields": fields,
            }
            if node_map is not None:
                node_map.list_items[id(lst_dict)] = items
            repeating_lists.append(lst_dict)

    def _list_key(r: dict[str, object]) -> float:
        sc = r.get("score")
        return -(float(sc) if isinstance(sc, (int, float)) else 0.0)

    repeating_lists.sort(key=_list_key)

    if not full and len(repeating_lists) > MAX_REPEATING_LISTS:
        overflow = repeating_lists[MAX_REPEATING_LISTS:]
        repeating_lists = repeating_lists[:MAX_REPEATING_LISTS]
        for ov in overflow:
            ov_samples: list[str] = []
            ov_fields = ov.get("fields", [])
            if isinstance(ov_fields, list) and ov_fields:
                first_f = ov_fields[0]
                if isinstance(first_f, dict):
                    s_list = first_f.get("samples", [])
                    if isinstance(s_list, list):
                        ov_samples = [str(x) for x in s_list[:3]]
            ov_cnt = ov.get("count", 0)
            navigation_lists.append(
                {
                    "selector": str(ov.get("selector", "")),
                    "count": ov_cnt if isinstance(ov_cnt, int) else 0,
                    "samples": ov_samples,
                }
            )

    return repeating_lists, navigation_lists


# ─────────────────────────── 4. Zoom-in Mode Engine ──────────────────────────


def _matches_attr_filter(tag: Tag, flt: AttrFilter) -> bool:
    """Check whether `tag` satisfies a single `AttrFilter`."""
    if flt.kind == "present":
        return tag.has_attr(flt.name)
    if not tag.has_attr(flt.name):
        return False
    raw_val = tag.get(flt.name)
    val = (
        " ".join(str(x) for x in raw_val)
        if isinstance(raw_val, list)
        else str(raw_val or "")
    )
    if flt.kind == "exact":
        return val == flt.value
    if flt.kind == "regex" and flt.compiled is not None:
        return flt.compiled.search(val) is not None
    return False


def _find_minimal_matching_tags(
    soup: BeautifulSoup, filters: ScoutFilters
) -> list[Tag]:
    """Find the deepest minimal DOM tags matching `filters` (including normalized subtree text)."""
    has_secondary_filter = bool(
        filters.text_regex is not None
        or filters.attrs
        or filters.tag is not None
    )
    if filters.css is not None:
        try:
            css_roots = [
                t
                for t in soup.select(filters.css)
                if isinstance(t, Tag) and t.name not in ("html", "body", "head")
            ]
        except Exception as exc:
            raise FilterError(
                f"invalid CSS selector {filters.css!r}: {exc}"
            ) from exc
        if has_secondary_filter:
            seen_ids: set[int] = set()
            candidates: list[Tag] = []
            for root in css_roots:
                if id(root) not in seen_ids:
                    seen_ids.add(id(root))
                    candidates.append(root)
                for desc in root.find_all(True):
                    if isinstance(desc, Tag) and id(desc) not in seen_ids:
                        seen_ids.add(id(desc))
                        candidates.append(desc)
        else:
            candidates = css_roots
    else:
        candidates = [
            t
            for t in soup.find_all(True)
            if t.name not in ("html", "body", "head")
        ]

    matched: list[Tag] = []
    for tag in candidates:
        if filters.tag is not None and tag.name != filters.tag:
            continue
        if filters.text_regex is not None:
            norm_text = _normalize_ws(tag.get_text(" ", strip=True), max_len=0)
            if not norm_text or filters.text_regex.search(norm_text) is None:
                continue
        if any(not _matches_attr_filter(tag, af) for af in filters.attrs):
            continue
        matched.append(tag)

    # When text_regex is active (and css/tag didn't specifically ask for an outer container),
    # retain only the deepest minimal matching tags (no descendant also in `matched`).
    if filters.text_regex is not None and len(matched) > 1:
        matched_ids = {id(t) for t in matched}
        minimal: list[Tag] = []
        for t in matched:
            has_matching_descendant = any(
                id(d) in matched_ids for d in t.find_all(True)
            )
            if not has_matching_descendant:
                minimal.append(t)
        return minimal

    return matched


def _climb_to_semantic_container(tag: Tag) -> Tag:
    """Climb up to 3 parent levels to find an enclosing semantic container for `tag`."""
    curr = tag
    for _ in range(3):
        parent = curr.parent
        if not isinstance(parent, Tag) or parent.name in (
            "body",
            "html",
            "[document]",
        ):
            break
        curr = parent
        if (
            curr.name in SEMANTIC_CONTAINER_TAGS
            or curr.get("id")
            or _get_semantic_classes(curr)
        ):
            break
    return curr


def _apply_zoom_mode(
    soup: BeautifulSoup,
    minimal_matches: list[Tag],
    repeating_lists: list[dict[str, object]],
    kv_blocks: list[dict[str, object]],
    node_map: _DomNodeMap,
    *,
    full: bool,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Highlight matched nodes in `repeating_lists` / `kv_blocks` and build `zoom_matches`."""
    if not minimal_matches:
        return [], [], []

    match_ids = {id(m) for m in minimal_matches}

    def _overlaps_match(node: Tag) -> bool:
        if id(node) in match_ids:
            return True
        for d in node.find_all(True):
            if id(d) in match_ids:
                return True
        for m in minimal_matches:
            if node in m.parents or m in node.parents:
                return True
        return False

    # 1. Check repeating_lists for matches
    kept_lists: list[dict[str, object]] = []
    covered_match_ids: set[int] = set()

    for lst in repeating_lists:
        items = node_map.list_items.get(id(lst), [])
        list_matched = False
        for m in minimal_matches:
            if any(id(m) == id(it) or it in m.parents for it in items):
                list_matched = True
                covered_match_ids.add(id(m))

        if list_matched:
            lst["matched"] = True
            fields_list = lst.get("fields", [])
            if isinstance(fields_list, list):
                for fld in fields_list:
                    if not isinstance(fld, dict):
                        continue
                    fnodes = node_map.field_nodes.get(id(fld), [])
                    if any(
                        id(n) in match_ids
                        or any(id(d) in match_ids for d in n.find_all(True))
                        for n in fnodes
                    ):
                        fld["matched"] = True
            kept_lists.append(lst)

    # 2. Check kv_blocks for matches
    kept_kvs: list[dict[str, object]] = []
    for kv in kv_blocks:
        kv_node = node_map.kv_nodes.get(id(kv))
        if not isinstance(kv_node, Tag):
            continue
        kv_matched = False
        for m in minimal_matches:
            if id(m) == id(kv_node) or kv_node in m.parents:
                kv_matched = True
                covered_match_ids.add(id(m))
        if kv_matched:
            kv["matched"] = True
            entries = kv.get("entries", [])
            if isinstance(entries, list):
                for ent in entries:
                    if not isinstance(ent, dict):
                        continue
                    r_nodes = node_map.kv_entry_nodes.get(id(ent), [])
                    if any(_overlaps_match(rn) for rn in r_nodes):
                        ent["matched"] = True
            cols = kv.get("columns", [])
            if isinstance(cols, list):
                for col in cols:
                    if not isinstance(col, dict):
                        continue
                    c_nodes = node_map.kv_col_nodes.get(id(col), [])
                    if any(_overlaps_match(cn) for cn in c_nodes):
                        col["matched"] = True
            kept_kvs.append(kv)

    # 3. Build standalone zoom_matches for matches outside repeating_lists and kv_blocks
    zoom_matches: list[dict[str, object]] = []
    seen_containers: set[int] = set()

    for m in minimal_matches:
        if id(m) in covered_match_ids:
            continue
        container = _climb_to_semantic_container(m)
        if id(container) in seen_containers:
            continue
        seen_containers.add(id(container))

        m_sel, _ = _synthesize_unique_selector(soup, m)
        c_sel, _ = _synthesize_unique_selector(soup, container)
        c_fields = _build_union_archetype_fields(
            [container], full=full, node_map=node_map
        )
        any_field_marked = False
        for cf in c_fields:
            fnodes = node_map.field_nodes.get(id(cf), [])
            if any(
                id(n) in match_ids
                or any(id(d) in match_ids for d in n.find_all(True))
                for n in fnodes
            ):
                cf["matched"] = True
                any_field_marked = True

        if not any_field_marked:
            # Ensure the matched element itself is present in fields with matched=True
            samples, attrs, attr_samples = _extract_node_samples([m])
            rel_css = _synthesize_relative_selector(
                [container], (_node_step_label(m),), [m]
            )
            c_fields.append(
                {
                    "path": _node_step_label(m),
                    "css": rel_css,
                    "kind": "scalar",
                    "present": 1,
                    "total": 1,
                    "optional": False,
                    "attrs": attrs,
                    "samples": samples,
                    "attr_samples": attr_samples,
                    "matched": True,
                }
            )

        zoom_matches.append(
            {
                "match_selector": m_sel,
                "match_tag": m.name,
                "match_text": _normalize_ws(m.get_text(" ", strip=True)),
                "container_selector": c_sel,
                "container_tag": container.name,
                "fields": c_fields,
            }
        )

    return kept_lists, kept_kvs, zoom_matches


# ─────────────────────────── Public Entrypoints ──────────────────────────────


def run_scout(
    html: str,
    filters: ScoutFilters | None = None,
    *,
    text: str | None = None,
    attrs: Iterable[str] = (),
    tag: str | None = None,
    css: str | None = None,
    ignore_case: bool = False,
    fixed: bool = False,
    full: bool = False,
) -> ScoutResult:
    """Run HTML context distillation and structural reconnaissance on an HTML document.

    When called without filter arguments, performs full-page overview distillation
    across embedded JSON, key-value/table blocks, and repeating item archetypes.
    When called with filter criteria (`filters`, `text`, `attrs`, `tag`, or `css`),
    operates in Zoom-in mode: locates the deepest minimal matching DOM elements,
    climbs to their enclosing repeating list, table, or semantic container, and
    highlights matched fields with `matched=True` (`<-- MATCH`).

    Args:
        html (str): Raw HTML document string to analyze.
        filters (ScoutFilters | None): Pre-compiled filter set for Zoom-in mode.
        text (str | None): Regex or literal string matched against normalized subtree text.
        attrs (Iterable[str]): Attribute filter specifications (`NAME`, `NAME=VAL`, `NAME=~REGEX`).
        tag (str | None): HTML tag name filter.
        css (str | None): CSS selector scoping filter.
        ignore_case (bool): Case-insensitive regex matching.
        fixed (bool): Escape regex metacharacters for literal matching.
        full (bool): Disable default compression budgets and emit all discovered items.

    Returns:
        ScoutResult: Structured reconnaissance digest with `.to_text()` and `.to_json()`.

    Raises:
        FilterError: If any CSS selector, regex pattern, or attribute filter is invalid.
    """
    attrs_list = list(attrs)
    if filters is None and (
        text is not None or attrs_list or tag is not None or css is not None
    ):
        filters = compile_filters(
            text=text,
            attrs=attrs_list,
            tag=tag,
            css=css,
            ignore_case=ignore_case,
            fixed=fixed,
        )
    elif filters is None:
        filters = ScoutFilters()

    soup = BeautifulSoup(html, BS4_PARSER)
    _preprocess_dom(soup)

    # Extract title and h1 before stripping scripts
    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    title_str = (
        _normalize_ws(title_tag.get_text(" ", strip=True))
        if isinstance(title_tag, Tag)
        else None
    )
    h1_str = (
        _normalize_ws(h1_tag.get_text(" ", strip=True))
        if isinstance(h1_tag, Tag)
        else None
    )

    # 1. Embedded JSON Engine (runs while <script> tags are present)
    embedded_json = _extract_embedded_json(soup, full=full)

    # Remove <script> tags so they do not pollute DOM skeleton or text search
    _strip_scripts(soup)

    node_map: _DomNodeMap | None = (
        _DomNodeMap() if filters.is_active() else None
    )

    # 2. Key-Value & Table Engine
    kv_blocks, claimed_kv_parents = _extract_kv_and_tables(
        soup, full=full, node_map=node_map
    )

    # 3. Repeating Lists & Folded DOM Skeleton Engine
    repeating_lists, navigation_lists = _extract_repeating_and_nav_lists(
        soup, claimed_kv_parents, full=full, node_map=node_map
    )

    # 4. Check Zoom-in Mode vs Overview Mode
    if filters.is_active() and node_map is not None:
        minimal_matches = _find_minimal_matching_tags(soup, filters)
        kept_lists, kept_kvs, zoom_matches = _apply_zoom_mode(
            soup,
            minimal_matches,
            repeating_lists,
            kv_blocks,
            node_map,
            full=full,
        )
        page_summary: dict[str, object] = {
            "title": title_str or None,
            "h1": h1_str or None,
            "has_embedded_json": bool(embedded_json),
            "has_kv_blocks": bool(kept_kvs),
            "repeating_list_count": len(kept_lists),
            "navigation_list_count": 0,
        }
        return ScoutResult(
            mode="zoom",
            matched=len(minimal_matches),
            sample_normalized=True,
            page_summary=page_summary,
            embedded_json=[],
            kv_blocks=kept_kvs,
            repeating_lists=kept_lists,
            navigation_lists=[],
            zoom_matches=zoom_matches,
        )

    page_summary = {
        "title": title_str or None,
        "h1": h1_str or None,
        "has_embedded_json": bool(embedded_json),
        "has_kv_blocks": bool(kv_blocks),
        "repeating_list_count": len(repeating_lists),
        "navigation_list_count": len(navigation_lists),
    }
    total_signals = (
        len(embedded_json)
        + len(kv_blocks)
        + len(repeating_lists)
        + len(navigation_lists)
    )
    if total_signals == 0 and (
        title_str or h1_str or soup.find(True) is not None
    ):
        total_signals = 1

    return ScoutResult(
        mode="overview",
        matched=total_signals,
        sample_normalized=True,
        page_summary=page_summary,
        embedded_json=embedded_json,
        kv_blocks=kv_blocks,
        repeating_lists=repeating_lists,
        navigation_lists=navigation_lists,
        zoom_matches=[],
    )


def run_discover(
    html: str,
    *,
    full: bool = False,
) -> ScoutResult:
    """Compatibility alias forwarding to `run_scout(html, full=full)`.

    Args:
        html (str): Raw HTML document string to analyze.
        full (bool): Disable default compression budgets and emit all discovered items.

    Returns:
        ScoutResult: Full-page reconnaissance result.
    """
    return run_scout(html, full=full)
