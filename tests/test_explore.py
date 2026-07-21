"""Tests for `ssc-gen scout` (exploration engine in ssc_codegen/explore.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ssc_codegen.explore import (
    DEFAULT_FIELDS,
    FilterError,
    NavSpec,
    apply_navigation,
    compile_filters,
    compute_css_path,
    parse_attr_flag,
    run_scout,
)

FIXTURE = (
    Path(__file__).parent / "integration" / "fixtures" / "dsl_coverage.html"
)


@pytest.fixture
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


# ─────────────────────────── filter compilation ────────────────────


def test_parse_attr_present() -> None:
    flt = parse_attr_flag("data-card", ignore_case=False, fixed=False)
    assert flt.name == "data-card"
    assert flt.kind == "present"


def test_parse_attr_exact() -> None:
    flt = parse_attr_flag("data-card=1", ignore_case=False, fixed=False)
    assert flt.kind == "exact"
    assert flt.value == "1"


def test_parse_attr_regex() -> None:
    flt = parse_attr_flag(
        "href=~/nested/\\w+\\.html", ignore_case=False, fixed=False
    )
    assert flt.kind == "regex"
    assert flt.value == r"/nested/\w+\.html"
    assert flt.compiled is not None


def test_parse_attr_empty_name_raises() -> None:
    with pytest.raises(FilterError):
        parse_attr_flag("=value", ignore_case=False, fixed=False)


def test_compile_filters_text() -> None:
    flt = compile_filters(
        text="foo", attrs=[], tag=None, css=None, ignore_case=False, fixed=False
    )
    assert flt.text_regex is not None
    assert flt.text_regex.search("foo") is not None


def test_compile_filters_fixed_escapes() -> None:
    flt = compile_filters(
        text="$5.99",
        attrs=[],
        tag=None,
        css=None,
        ignore_case=False,
        fixed=True,
    )
    assert flt.text_regex is not None
    # Literal $ should not anchor-match
    assert flt.text_regex.search("price is $5.99") is not None
    assert flt.text_regex.search("5.99") is None


def test_compile_filters_ignore_case() -> None:
    flt = compile_filters(
        text="FOO", attrs=[], tag=None, css=None, ignore_case=True, fixed=False
    )
    assert flt.text_regex is not None
    assert flt.text_regex.search("foo bar") is not None


def test_compile_filters_invalid_regex_raises() -> None:
    with pytest.raises(FilterError):
        compile_filters(
            text="[",
            attrs=[],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=False,
        )


# ─────────────────────────── text/attr/tag filters ─────────────────


def test_text_regex_finds_titles(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text="foo Title",
            attrs=[],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        list(DEFAULT_FIELDS),
    )
    assert result.matched == 2
    for r in result.results:
        assert r["tag"] == "h2"
        assert "foo Title" in r["text"]


def test_attr_regex_finds_nested_links(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=["href=~/nested/\\w+\\.html"],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["attr.href"],
    )
    assert result.matched == 2
    for r in result.results:
        assert "/nested/" in r["attr.href"]


def test_attr_presence_finds_data_cards(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=["data-card"],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag", "attr.data-card"],
    )
    assert result.matched == 2
    assert {r["attr.data-card"] for r in result.results} == {"1", "2"}


def test_attr_exact_value(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=["data-card=1"],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["attr.data-card"],
    )
    assert result.matched == 1
    assert result.results[0]["attr.data-card"] == "1"


def test_tag_filter_finds_articles(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag"],
    )
    assert result.matched == 2


def test_css_initial_candidate_set(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text="foo",
            attrs=[],
            tag=None,
            css=".title",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag", "text"],
    )
    assert result.matched == 2


def test_css_text_intersect(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text="foo",
            attrs=[],
            tag=None,
            css=".title",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["text"],
    )
    assert result.matched == 2
    for r in result.results:
        assert "foo" in r["text"]


def test_invert_filter(html: str) -> None:
    # All divs without data-flag attr — should match many
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=["data-flag"],
            tag="div",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag"],
        invert=True,
    )
    # data-flag divs: 5 (3 in card 1, 2 in card 2). divs total > 5
    assert result.matched > 5


def test_ignore_case_text(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text="FOO",
            attrs=[],
            tag=None,
            css=None,
            ignore_case=True,
            fixed=False,
        ),
        NavSpec(),
        ["text"],
    )
    assert result.matched >= 2


def test_fixed_string_literal_dollar(html: str) -> None:
    # In dsl_coverage: "Score: 41" / "Score: 18" — search literal "Score:"
    result = run_scout(
        html,
        compile_filters(
            text="Score:",
            attrs=[],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=True,
        ),
        NavSpec(),
        ["text"],
    )
    assert result.matched == 2


# ─────────────────────────── navigation ────────────────────────────


def test_nav_is_noop() -> None:
    assert NavSpec().is_noop() is True
    assert NavSpec(up=1).is_noop() is False
    assert NavSpec(down=2).is_noop() is False


def test_nav_up_climbs_to_parent(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css=".title",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(up=1),
        ["tag", "attr.data-card"],
    )
    # Both .title h2s should climb to <article data-card="1"/"2">
    assert result.matched == 2
    assert {r["attr.data-card"] for r in result.results} == {"1", "2"}


def test_nav_down_descends(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css="section.cards",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(down=1),
        ["tag"],
    )
    assert result.matched == 1
    assert result.results[0]["tag"] == "article"


def test_nav_next_sibling(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css="section.single > h1",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(next=1),
        ["tag"],
    )
    # h1 in section.single -> next sibling is span.is-active
    assert result.matched == 1
    assert result.results[0]["tag"] == "span"


def test_nav_prev_sibling(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css="section.single > .is-active",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(prev=1),
        ["tag"],
    )
    assert result.matched == 1
    assert result.results[0]["tag"] == "h1"


def test_nav_chain_order(html: str) -> None:
    # .title -> up 1 (article) -> next 1 (next article if exists)
    # In fixture: card 1's title climbs to article 1, next is article 2
    result = run_scout(
        html,
        compile_filters(
            text="foo Title One",
            attrs=[],
            tag=None,
            css=".title",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(up=1, next=1),
        ["attr.data-card"],
    )
    assert result.matched == 1
    assert result.results[0]["attr.data-card"] == "2"


def test_nav_dedup_by_identity(html: str) -> None:
    # Two prices inside same article — climb to article, should dedupe.
    result = run_scout(
        html,
        compile_filters(
            text="Score:",
            attrs=[],
            tag="div",
            css=None,
            ignore_case=False,
            fixed=True,
        ),
        NavSpec(up=1),
        ["tag"],
    )
    # Both "Score:" divs in card 1 and card 2 — each climbs to its own article.
    # 2 matches, 2 different articles, no dedup needed.
    assert result.matched == 2


def test_nav_dropped_returns_empty(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css=".title",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(up=100),
        ["tag"],
    )
    assert result.matched == 0
    assert result.results == []


def test_apply_navigation_noop_dedupes() -> None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<div><a>x</a><a>y</a></div>", "lxml")
    tags = soup.find_all("a")
    # Pass duplicate references
    doubled = tags + tags
    out = apply_navigation(doubled, NavSpec())
    assert len(out) == 2


# ─────────────────────────── output fields ─────────────────────────


def test_default_fields_returned(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        list(DEFAULT_FIELDS),
    )
    for r in result.results:
        assert set(r.keys()) == {"path", "tag", "text"}


def test_custom_fields(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["attr.data-card", "classes"],
    )
    for r in result.results:
        assert set(r.keys()) == {"attr.data-card", "classes"}


def test_attr_dot_extraction(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["attr.data-card"],
    )
    assert {r["attr.data-card"] for r in result.results} == {"1", "2"}


def test_attr_dot_missing_returns_none(html: str) -> None:
    # articles have no 'alt' attr
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["attr.alt"],
    )
    for r in result.results:
        assert r["attr.alt"] is None


def test_index_field(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["index"],
    )
    assert [r["index"] for r in result.results] == [0, 1]


def test_html_field(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css=".title",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["html"],
    )
    for r in result.results:
        assert "<h2" in r["html"]


def test_attrs_field_returns_dict(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["attrs"],
    )
    for r in result.results:
        assert isinstance(r["attrs"], dict)
        assert "data-card" in r["attrs"]
        assert "class" in r["attrs"]


def test_classes_field(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["classes"],
    )
    for r in result.results:
        assert r["classes"] == ["card"]


def test_unknown_field_raises(html: str) -> None:
    with pytest.raises(FilterError):
        run_scout(
            html,
            compile_filters(
                text=None,
                attrs=[],
                tag="article",
                css=None,
                ignore_case=False,
                fixed=False,
            ),
            NavSpec(),
            ["bogus"],
        )


def test_line_field_via_lxml(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["line"],
    )
    # articles are on lines 31 and 58 of dsl_coverage.html
    lines = sorted(r["line"] for r in result.results)
    assert lines == [31, 58]


def test_snippet_truncates_text(html: str) -> None:
    # Long text node — script contains JSON. Use the script tag.
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag=None,
            css="script",
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["text"],
        snippet=10,
    )
    for r in result.results:
        # truncated text ends with ellipsis
        assert isinstance(r["text"], str)
        assert len(r["text"]) <= 11  # 10 chars + ellipsis


# ─────────────────────────── pagination ────────────────────────────


def test_limit_and_offset(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="div",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag"],
        limit=3,
        offset=2,
    )
    assert result.returned <= 3
    assert result.offset == 2


def test_truncated_flag(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="div",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag"],
        limit=1,
        offset=0,
    )
    assert result.matched > 1
    assert result.truncated is True


# ─────────────────────────── css path ──────────────────────────────


def test_css_path_format(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["path"],
    )
    paths = [r["path"] for r in result.results]
    # All paths start with html and contain article
    for p in paths:
        assert p.startswith("html")
        assert "article.card" in p
    # First article should have nth-of-type(1)
    assert "nth-of-type(1)" in paths[0]
    assert "nth-of-type(2)" in paths[1]


def test_compute_css_path_simple() -> None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        "<html><body><div class='x'>hi</div></body></html>", "lxml"
    )
    div = soup.find("div")
    assert div is not None
    path = compute_css_path(div)
    assert "div" in path
    assert "html" in path


# ─────────────────────────── result formats ────────────────────────


def test_result_to_json(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["tag"],
    )
    import json

    parsed = json.loads(result.to_json())
    assert parsed["matched"] == 2
    assert "results" in parsed
    assert parsed["returned"] == 2


def test_result_to_text_empty() -> None:
    from ssc_codegen.explore import ScoutResult

    r = ScoutResult(
        matched=0, returned=0, limit=50, offset=0, truncated=False, results=[]
    )
    assert r.to_text() == "0 matches"


def test_result_to_text_with_matches(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        ["path", "tag", "text"],
    )
    text = result.to_text()
    assert "article" in text


# ─────────────────────────── exit-code semantics ───────────────────


def test_exit_zero_on_match(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text=None,
            attrs=[],
            tag="article",
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        list(DEFAULT_FIELDS),
    )
    assert result.matched > 0


def test_exit_nonzero_on_no_match(html: str) -> None:
    result = run_scout(
        html,
        compile_filters(
            text="zzz-not-present-zzz",
            attrs=[],
            tag=None,
            css=None,
            ignore_case=False,
            fixed=False,
        ),
        NavSpec(),
        list(DEFAULT_FIELDS),
    )
    assert result.matched == 0


# ─────────────────────────── discover mode ─────────────────────────


from ssc_codegen.explore import (  # noqa: E402
    DISCOVER_MIN_REPEAT,
    DISCOVER_TOP_CLASSES,
    DISCOVER_TOP_CONTAINERS,
    DISCOVER_TOP_TAGS,
    DiscoverResult,
    run_discover,
)

DISCOVER_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Shop</title>
  <meta data-id="x" data-track="abc">
</head>
<body>
  <ul class="pagination">
    <li class="page-item"><a class="page-link" href="/p1">1</a></li>
    <li class="page-item"><a class="page-link" href="/p2">2</a></li>
    <li class="page-item"><a class="page-link" href="/p3">3</a></li>
  </ul>
  <div class="grid">
    <div class="card">
      <h3 class="title">A</h3>
      <span class="price" data-currency="USD">$1</span>
      <a class="url" href="/a">link</a>
    </div>
    <div class="card">
      <h3 class="title">B</h3>
      <span class="price" data-currency="USD">$2</span>
      <a class="url" href="/b">link</a>
    </div>
    <div class="card">
      <h3 class="title">C</h3>
      <span class="price" data-currency="USD">$3</span>
      <a class="url" href="/c">link</a>
    </div>
  </div>
  <p>lone paragraph</p>
</body>
</html>
"""


@pytest.fixture
def discover_html() -> str:
    return DISCOVER_HTML


def test_discover_returns_dataclass(discover_html: str) -> None:
    result = run_discover(discover_html)
    assert isinstance(result, DiscoverResult)


def test_discover_tag_stats_sorted_desc(discover_html: str) -> None:
    result = run_discover(discover_html)
    counts = [row["count"] for row in result.tag_stats]
    assert counts == sorted(counts, reverse=True)
    # All entries have tag + count
    for row in result.tag_stats:
        assert "tag" in row
        assert "count" in row
        assert isinstance(row["count"], int)


def test_discover_class_stats_capped(discover_html: str) -> None:
    result = run_discover(discover_html)
    assert len(result.class_stats) <= DISCOVER_TOP_CLASSES
    # Each row well-formed
    for row in result.class_stats:
        assert isinstance(row["class"], str)
        assert isinstance(row["count"], int)


def test_discover_tag_stats_capped(discover_html: str) -> None:
    result = run_discover(discover_html)
    assert len(result.tag_stats) <= DISCOVER_TOP_TAGS


def test_discover_data_attrs_deduped_and_sorted(discover_html: str) -> None:
    result = run_discover(discover_html)
    # data-id, data-track, data-currency all present, no duplicates, sorted
    assert "data-currency" in result.data_attrs
    assert "data-id" in result.data_attrs
    assert "data-track" in result.data_attrs
    assert len(result.data_attrs) == len(set(result.data_attrs))
    assert result.data_attrs == sorted(result.data_attrs)
    # Non-data attributes excluded
    assert "href" not in result.data_attrs
    assert "class" not in result.data_attrs


def test_discover_finds_card_container(discover_html: str) -> None:
    result = run_discover(discover_html)
    card_containers = [
        c
        for c in result.repeat_containers
        if c["item_tag"] == "div" and "card" in c["item_classes"]
    ]
    assert len(card_containers) == 1
    card = card_containers[0]
    assert card["count"] == 3
    # parent is .grid
    assert ".grid" in card["parent_selector"]
    # common_descendants includes the three child patterns
    descs = {
        (d["tag"], tuple(d["classes"])) for d in card["common_descendants"]
    }
    assert ("h3", ("title",)) in descs
    assert ("span", ("price",)) in descs
    assert ("a", ("url",)) in descs


def test_discover_common_descendants_attrs_union(discover_html: str) -> None:
    result = run_discover(discover_html)
    card = next(
        c
        for c in result.repeat_containers
        if c["item_tag"] == "div" and "card" in c["item_classes"]
    )
    price_desc = next(
        d for d in card["common_descendants"] if d["tag"] == "span"
    )
    assert "data-currency" in price_desc["attrs"]
    url_desc = next(d for d in card["common_descendants"] if d["tag"] == "a")
    assert "href" in url_desc["attrs"]


def test_discover_common_descendants_attrs_omitted_when_empty() -> None:
    # Descendants with no extractable attrs (only `class`) should omit the
    # `attrs` key entirely — saves JSON output bytes.
    html = """<div>
      <p class='card'>a</p>
      <p class='card'>b</p>
      <p class='card'>c</p>
    </div>"""
    result = run_discover(html)
    # No containers expected since <p class=card> has no descendants with attrs
    for c in result.repeat_containers:
        for d in c["common_descendants"]:
            if not d.get("attrs"):
                assert "attrs" not in d, (
                    f"Empty attrs key should be omitted, got {d}"
                )


def test_discover_filters_head_boilerplate() -> None:
    # <head> children (link, meta, script) often have high counts but are
    # never list-struct candidates. They must be filtered out.
    html = """<html>
      <head>
        <meta name='a' content='1'>
        <meta name='b' content='2'>
        <meta name='c' content='3'>
        <link rel='stylesheet' href='/a'>
        <link rel='stylesheet' href='/b'>
        <link rel='stylesheet' href='/c'>
      </head>
      <body>
        <div class='card'>x1</div>
        <div class='card'>x2</div>
        <div class='card'>x3</div>
      </body>
    </html>"""
    result = run_discover(html)
    # Only the .card container should remain, not head>meta or head>link
    parent_paths = [c["parent_selector"] for c in result.repeat_containers]
    for p in parent_paths:
        assert " head" not in p, f"Head boilerplate not filtered: {p}"
    card_containers = [
        c for c in result.repeat_containers if "card" in c["item_classes"]
    ]
    assert len(card_containers) == 1


def test_discover_common_descendants_sample_text() -> None:
    # Each common_descendant should include a `sample` showing what the
    # element actually contains — saves the LLM a probe round-trip.
    html = """<div>
      <div class='card'>
        <h3 class='title'>First</h3>
        <a href='/1'>link1</a>
      </div>
      <div class='card'>
        <h3 class='title'>Second</h3>
        <a href='/2'>link2</a>
      </div>
      <div class='card'>
        <h3 class='title'>Third</h3>
        <a href='/3'>link3</a>
      </div>
    </div>"""
    result = run_discover(html)
    card = next(
        c for c in result.repeat_containers if "card" in c["item_classes"]
    )
    by_tag = {
        (d["tag"], tuple(d["classes"])): d for d in card["common_descendants"]
    }
    title_d = by_tag[("h3", ("title",))]
    assert title_d["sample"] == ["First", "Second", "Third"]
    link_d = by_tag[("a", ())]
    assert link_d["sample"] == ["link1", "link2", "link3"]


def test_discover_common_descendants_sample_attrs_only() -> None:
    # Elements without text (img, empty <a>) should fall back to first attr
    # value as sample.
    html = """<div>
      <div class='card'><img src='/img1.png' alt='first'></div>
      <div class='card'><img src='/img2.png' alt='second'></div>
      <div class='card'><img src='/img3.png' alt='third'></div>
    </div>"""
    result = run_discover(html)
    card = next(
        c for c in result.repeat_containers if "card" in c["item_classes"]
    )
    img_d = next(d for d in card["common_descendants"] if d["tag"] == "img")
    # No text → fall back to src (priority over alt)
    assert img_d["sample"] == ["/img1.png", "/img2.png", "/img3.png"]


def test_discover_common_descendants_max_per_item() -> None:
    # When a signature appears multiple times within a single item (e.g.
    # multiple <p class="card-text"> for year/country/mileage), surface
    # `max_per_item` so the LLM knows to use :nth-of-type or expect LIST.
    html = """<div>
      <div class='card'>
        <p class='field'>Year: 1955</p>
        <p class='field'>Country: UK</p>
        <p class='field'>Mileage: 100</p>
      </div>
      <div class='card'>
        <p class='field'>Year: 1954</p>
        <p class='field'>Country: DE</p>
        <p class='field'>Mileage: 200</p>
      </div>
      <div class='card'>
        <p class='field'>Year: 1983</p>
        <p class='field'>Country: DE</p>
        <p class='field'>Mileage: 300</p>
      </div>
    </div>"""
    result = run_discover(html)
    card = next(
        c for c in result.repeat_containers if "card" in c["item_classes"]
    )
    field_d = next(
        d
        for d in card["common_descendants"]
        if d["tag"] == "p" and "field" in d["classes"]
    )
    assert field_d["max_per_item"] == 3
    assert field_d["sample"] == ["Year: 1955", "Year: 1954", "Year: 1983"]


def test_discover_common_descendants_leaf_sort_priority() -> None:
    # Leaf tags (a/img/p/h*/span) must sort before container <div>s even when
    # the div has higher coverage or alphabetical priority — leaves carry
    # extractable data and shouldn't be cut off by max_n.
    html = """<div>
      <div class='card'>
        <div class='wrapper'><h3 class='title'>A</h3></div>
        <a href='/1'>x</a>
      </div>
      <div class='card'>
        <div class='wrapper'><h3 class='title'>B</h3></div>
        <a href='/2'>y</a>
      </div>
      <div class='card'>
        <div class='wrapper'><h3 class='title'>C</h3></div>
        <a href='/3'>z</a>
      </div>
    </div>"""
    result = run_discover(html)
    card = next(
        c for c in result.repeat_containers if "card" in c["item_classes"]
    )
    # First two descendants should be leaf tags (a, h3), not div.wrapper
    first_two_tags = [d["tag"] for d in card["common_descendants"][:2]]
    assert "a" in first_two_tags
    assert "h3" in first_two_tags


def test_discover_pagination_container(discover_html: str) -> None:
    result = run_discover(discover_html)
    page_items = [
        c
        for c in result.repeat_containers
        if c["item_tag"] == "li" and "page-item" in c["item_classes"]
    ]
    assert len(page_items) == 1
    assert page_items[0]["count"] == 3
    descs = page_items[0]["common_descendants"]
    a_desc = next(d for d in descs if d["tag"] == "a")
    assert "href" in a_desc["attrs"]


def test_discover_containers_capped(discover_html: str) -> None:
    result = run_discover(discover_html)
    assert len(result.repeat_containers) <= DISCOVER_TOP_CONTAINERS


def test_discover_min_repeat_filter() -> None:
    # Two cards = filtered (min_repeat=3); single <p> also filtered.
    html = """<div>
      <p class='x'>a</p>
      <p class='x'>b</p>
    </div>"""
    result = run_discover(html)
    for c in result.repeat_containers:
        assert c["count"] >= DISCOVER_MIN_REPEAT


def test_discover_containers_sorted_by_count_desc(discover_html: str) -> None:
    result = run_discover(discover_html)
    counts = [c["count"] for c in result.repeat_containers]
    assert counts == sorted(counts, reverse=True)


def test_discover_empty_html_safe() -> None:
    # Even on near-empty input we shouldn't crash; containers list is empty.
    result = run_discover("<html></html>")
    assert result.repeat_containers == []
    assert result.tag_stats == [{"tag": "html", "count": 1}]


def test_discover_to_json_roundtrip(discover_html: str) -> None:
    import json

    result = run_discover(discover_html)
    data = json.loads(result.to_json())
    # Non-empty sections always present
    assert "tag_stats" in data
    assert "class_stats" in data
    assert "data_attrs" in data
    assert "repeat_containers" in data
    # Empty sections omitted (no ids, no json signals in fixture)
    assert "id_stats" not in data
    assert "json_signals" not in data


def test_discover_to_text_has_section_headers(discover_html: str) -> None:
    result = run_discover(discover_html)
    text = result.to_text()
    assert "== tag_stats ==" in text
    assert "== class_stats ==" in text
    assert "== repeat_containers ==" in text


def test_discover_to_text_omits_empty_id_section() -> None:
    # HTML without ids should not emit the id_stats section.
    html = (
        "<html><body><div class='x'>a</div><div class='x'>b</div></body></html>"
    )
    result = run_discover(html)
    assert result.id_stats == []
    text = result.to_text()
    assert "== id_stats ==" not in text
    assert "== data_attrs ==" not in text


def test_discover_id_stats_collected() -> None:
    html = """
    <html><body>
      <div id="header">h</div>
      <div id="header">h</div>
      <div id="footer">f</div>
    </body></html>
    """
    result = run_discover(html)
    id_map = {row["id"]: row["count"] for row in result.id_stats}
    assert id_map.get("header") == 2
    assert id_map.get("footer") == 1


def test_discover_signature_groups_by_class_set_not_list() -> None:
    # Same classes in different order should group together.
    html = """
    <html><body>
      <div class="b a">x</div>
      <div class="a b">y</div>
      <div class="a b">z</div>
    </body></html>
    """
    result = run_discover(html)
    matched = [
        c
        for c in result.repeat_containers
        if c["item_tag"] == "div" and set(c["item_classes"]) == {"a", "b"}
    ]
    assert len(matched) == 1
    assert matched[0]["count"] == 3


# ─────────────────────────── json_signals ──────────────────────────


JSON_SIGNALS_HTML = """
<!DOCTYPE html>
<html>
<head>
  <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Product", "name": "X"}
  </script>
  <script type="application/json" id="__NEXT_DATA__">
    {"props": {"pageProps": {"items": [1, 2, 3]}}}
  </script>
  <script>
    var data = [
      {"text": "first", "tags": ["a", "b"]},
      {"text": "second", "tags": ["c"]}
    ];
  </script>
</head>
<body>
  <div class="card" data-config='{"id": 1, "name": "A"}'>A</div>
  <div class="card" data-config='{"id": 2, "name": "B"}'>B</div>
  <a href="/path?x={not_json}">link</a>
  <span class="x-data" x-data="{ open: false }">Vue/Alpine-ish</span>
</body>
</html>
"""


@pytest.fixture
def json_signals_html() -> str:
    return JSON_SIGNALS_HTML


def test_json_signals_jsonld_script(json_signals_html: str) -> None:
    result = run_discover(json_signals_html)
    jsonld = [s for s in result.json_signals if s.get("subtype") == "json-ld"]
    assert len(jsonld) == 1
    sig = jsonld[0]
    assert sig["kind"] == "script"
    assert sig["script_type"] == "application/ld+json"
    assert sig["container_kind"] == "object"
    assert "@context" in sig["snippet"]


def test_json_signals_json_mime_script(json_signals_html: str) -> None:
    result = run_discover(json_signals_html)
    jm = [s for s in result.json_signals if s.get("subtype") == "json-mime"]
    assert len(jm) == 1
    sig = jm[0]
    assert sig["script_type"] == "application/json"
    assert sig["script_id"] == "__NEXT_DATA__"
    assert sig["container_kind"] == "object"


def test_json_signals_var_assignment(json_signals_html: str) -> None:
    result = run_discover(json_signals_html)
    jsvars = [s for s in result.json_signals if s.get("subtype") == "js-var"]
    assert len(jsvars) == 1
    sig = jsvars[0]
    assert sig["var_name"] == "data"
    # snippet starts at the opening bracket
    assert sig["snippet"][0] == "["
    assert sig["container_kind"] == "array"


def test_json_signals_var_assignment_window_pattern() -> None:
    html = """
    <html><body>
      <script>
        window.__INITIAL_STATE__ = {"user": {"id": 1}};
      </script>
    </body></html>
    """
    result = run_discover(html)
    jsvars = [s for s in result.json_signals if s.get("subtype") == "js-var"]
    assert len(jsvars) == 1
    assert jsvars[0]["var_name"] == "__INITIAL_STATE__"
    assert jsvars[0]["container_kind"] == "object"


def test_json_signals_bare_json_array_script() -> None:
    html = """
    <html><body>
      <script>[{"a": 1}, {"b": 2}]</script>
    </body></html>
    """
    result = run_discover(html)
    bare = [s for s in result.json_signals if s.get("subtype") == "bare-json"]
    assert len(bare) == 1
    assert bare[0]["container_kind"] == "array"


def test_json_signals_attr_first_char(json_signals_html: str) -> None:
    result = run_discover(json_signals_html)
    attr_sigs = [
        s for s in result.json_signals if s.get("subtype") == "attr-json"
    ]
    # 2x data-config + 1x x-data (Alpine — JS object literal not strict JSON,
    # but lax detection is intentional; LLM inspects snippet to discard).
    assert len(attr_sigs) == 3
    cfg_sigs = [s for s in attr_sigs if s["attr"] == "data-config"]
    assert len(cfg_sigs) == 2
    for sig in cfg_sigs:
        assert sig["snippet"][0] == "{"
        assert sig["container_kind"] == "object"
    xdata_sig = next(s for s in attr_sigs if s["attr"] == "x-data")
    assert xdata_sig["snippet"].startswith("{")


def test_json_signals_skips_known_attrs(json_signals_html: str) -> None:
    # href="?x={not_json}" should NOT produce an attr-json signal.
    result = run_discover(json_signals_html)
    href_sigs = [s for s in result.json_signals if s.get("attr") == "href"]
    assert href_sigs == []
    # class/style/src/action never appear either.
    for name in ("class", "style", "src", "action"):
        assert not [s for s in result.json_signals if s.get("attr") == name]


def test_json_signals_skips_empty_script() -> None:
    html = """
    <html><head>
      <script></script>
      <script>   </script>
    </head></html>
    """
    result = run_discover(html)
    assert result.json_signals == []


def test_json_signals_caps_at_max_scripts_and_attrs() -> None:
    # 12 scripts + 12 attrs, both above the default cap of 10.
    scripts_html = "".join(
        f"<script type='application/json'>{{\"i\": {i}}}</script>"
        for i in range(12)
    )
    attrs_html = "".join(
        f"<div data-cfg='{{\"i\": {i}}}'>x</div>" for i in range(12)
    )
    html = f"<html><body>{scripts_html}{attrs_html}</body></html>"

    result = run_discover(html)
    scripts = [s for s in result.json_signals if s.get("kind") == "script"]
    attrs = [s for s in result.json_signals if s.get("kind") == "attr"]
    assert len(scripts) == 10
    assert len(attrs) == 10


def test_json_signals_script_id_field(json_signals_html: str) -> None:
    # Next.js pattern: <script id="__NEXT_DATA__" type="application/json">
    result = run_discover(json_signals_html)
    next_data = next(
        s for s in result.json_signals if s.get("subtype") == "json-mime"
    )
    assert next_data["script_id"] == "__NEXT_DATA__"


def test_json_signals_first_var_only_per_script() -> None:
    # Two var assignments in one script — we capture only the first.
    html = """
    <html><body>
      <script>
        var first = {"a": 1};
        var second = {"b": 2};
      </script>
    </body></html>
    """
    result = run_discover(html)
    jsvars = [s for s in result.json_signals if s.get("subtype") == "js-var"]
    assert len(jsvars) == 1
    assert jsvars[0]["var_name"] == "first"


def test_json_signals_to_text_omitted_when_empty() -> None:
    # Page with no embedded JSON shouldn't emit the section.
    html = "<html><body><p>nothing here</p></body></html>"
    result = run_discover(html)
    assert result.json_signals == []
    text = result.to_text()
    assert "== json_signals ==" not in text


def test_json_signals_document_order_preserved() -> None:
    # Insert signals in a known order; expect same order out.
    html = """
    <html>
      <head>
        <script type="application/ld+json">{"first": true}</script>
        <script>var second = [1, 2];</script>
      </head>
      <body>
        <div data-third='{"order": 3}'></div>
      </body>
    </html>
    """
    result = run_discover(html)
    # json-ld → js-var → attr-json, in document order (not priority-sorted).
    subtypes = [s["subtype"] for s in result.json_signals]
    assert subtypes == ["json-ld", "js-var", "attr-json"]


def test_json_signals_to_json_roundtrip(json_signals_html: str) -> None:
    import json

    result = run_discover(json_signals_html)
    data = json.loads(result.to_json())
    assert "json_signals" in data
    assert isinstance(data["json_signals"], list)
    assert len(data["json_signals"]) >= 4  # 3 scripts + 2 attrs - capped


# ─────────────────────────── discover v2 ────────────────────────────


def test_discover_item_selector_stable_via_id() -> None:
    # Container with `id` ancestor → short item_selector anchored on `#id`.
    # `selector_stability` field omitted (stable by default — saves tokens).
    html = """<div id='main-list'>
      <div class='item'>A</div>
      <div class='item'>B</div>
      <div class='item'>C</div>
    </div>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    sel = container["item_selector"]
    assert isinstance(sel, str)
    assert sel.startswith("#main-list")
    # `selector_stability` field absent when stable.
    assert "selector_stability" not in container


def test_discover_item_selector_stable_via_rare_class() -> None:
    # No id, but parent has a class appearing ≤ RARE_CLASS_MAX times.
    html = """<div>
      <div class='unique-cluster'>
        <div class='item'>A</div>
        <div class='item'>B</div>
        <div class='item'>C</div>
      </div>
    </div>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    sel = container["item_selector"]
    assert isinstance(sel, str)
    assert "unique-cluster" in sel
    assert "selector_stability" not in container


def test_discover_item_selector_fragile_without_anchor() -> None:
    # Deep nesting with only high-frequency classes → fragile full path.
    html = """<html><body><div><div><div>
      <div class='row'>A</div>
      <div class='row'>B</div>
      <div class='row'>C</div>
      <div class='row'>D</div>
      <div class='row'>E</div>
      <div class='row'>F</div>
    </div></div></div></body></html>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    # `row` appears 6 times (> RARE_CLASS_MAX=5) — not a rare anchor.
    assert container.get("selector_stability") == "fragile"


def test_discover_single_link_item_flag() -> None:
    # Every item has exactly one <a> child → navigation pattern.
    html = """<nav>
      <a class='nav-link'>Home</a>
      <a class='nav-link'>About</a>
      <a class='nav-link'>Contact</a>
    </nav>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    assert container["single_link_item"] is True


def test_discover_single_link_item_flag_false_when_mixed_children() -> None:
    # Items with more than one child tag → not single-link.
    html = """<ul>
      <li><a>A</a><span>meta</span></li>
      <li><a>B</a><span>meta</span></li>
      <li><a>C</a><span>meta</span></li>
    </ul>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    assert container["single_link_item"] is False


def test_discover_has_th_row_flag() -> None:
    html = """<table>
      <thead><tr><th>Name</th><th>Age</th></tr></thead>
      <tbody>
        <tr><td>Alice</td><td>30</td></tr>
        <tr><td>Bob</td><td>25</td></tr>
        <tr><td>Carol</td><td>40</td></tr>
      </tbody>
    </table>"""
    result = run_discover(html)
    # Find the <tr> group inside tbody.
    tr_container = next(
        c for c in result.repeat_containers if c["item_tag"] == "tr"
    )
    assert tr_container["has_th_row"] is True


def test_discover_has_th_row_false_outside_table() -> None:
    html = """<div>
      <div class='row'>r1</div>
      <div class='row'>r2</div>
      <div class='row'>r3</div>
    </div>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    assert container["has_th_row"] is False


def test_discover_single_label_child_flag() -> None:
    # One item has a single <strong>/<b>/<dt>/<label> child + residual text.
    html = """<dl>
      <dt><strong>Name:</strong> Alice</dt>
      <dt><strong>Name:</strong> Bob</dt>
      <dt><strong>Name:</strong> Carol</dt>
    </dl>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    assert container["single_label_child"] is True


def test_discover_single_label_child_false_when_only_label_text() -> None:
    # Label child but no residual text → not a "label: value" pattern.
    html = """<ul>
      <li><strong>Alice</strong></li>
      <li><strong>Bob</strong></li>
      <li><strong>Carol</strong></li>
    </ul>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    assert container["single_label_child"] is False


def test_discover_sample_head_tail_dedup() -> None:
    # 6 distinct values → sample has 3 from head, sample_tail has 3 from
    # tail (reverse order), no overlap. Items need descendants for samples
    # to surface — wrap values in <span>.
    html = """<div>
      <div class='item'><span class='val'>V1</span></div>
      <div class='item'><span class='val'>V2</span></div>
      <div class='item'><span class='val'>V3</span></div>
      <div class='item'><span class='val'>V4</span></div>
      <div class='item'><span class='val'>V5</span></div>
      <div class='item'><span class='val'>V6</span></div>
    </div>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    text_d = next(
        d for d in container["common_descendants"] if d["tag"] == "span"
    )
    assert text_d["sample"] == ["V1", "V2", "V3"]
    assert text_d["sample_tail"] == ["V6", "V5", "V4"]


def test_discover_sample_tail_omitted_when_short() -> None:
    # 3 items but only 2 distinct values → all fit in `sample`; tail omitted.
    html = """<div>
      <div class='item'><span class='val'>V1</span></div>
      <div class='item'><span class='val'>V2</span></div>
      <div class='item'><span class='val'>V1</span></div>
    </div>"""
    result = run_discover(html)
    container = result.repeat_containers[0]
    text_d = next(
        d for d in container["common_descendants"] if d["tag"] == "span"
    )
    assert text_d["sample"] == ["V1", "V2"]
    assert "sample_tail" not in text_d


def test_discover_sample_normalized_global_flag() -> None:
    # Whitespace collapsed in samples — global flag must be surfaced.
    html = "<div><p>a</p><p>b</p><p>c</p></div>"
    result = run_discover(html)
    assert result.sample_normalized is True
    # Reflected in JSON output.
    import json

    payload = json.loads(result.to_json())
    assert payload["sample_normalized"] is True


def test_discover_table_candidates_with_th_keys() -> None:
    html = """<div>
      <table>
        <tr><th>Name</th><th>Age</th></tr>
        <tr><td>Alice</td><td>30</td></tr>
        <tr><td>Bob</td><td>25</td></tr>
      </table>
    </div>"""
    result = run_discover(html)
    assert len(result.table_candidates) == 1
    t = result.table_candidates[0]
    assert t["keys"] == ["Name", "Age"]
    assert t["row_count"] == 3


def test_discover_table_candidates_without_th_uses_first_cell() -> None:
    html = """<div>
      <table>
        <tr><td>Alice</td><td>30</td></tr>
        <tr><td>Bob</td><td>25</td></tr>
        <tr><td>Carol</td><td>40</td></tr>
      </table>
    </div>"""
    result = run_discover(html)
    assert len(result.table_candidates) == 1
    t = result.table_candidates[0]
    # Keys fall back to first <td> of each row.
    assert t["keys"] == ["Alice", "Bob", "Carol"]


def test_discover_table_candidates_empty_when_no_rows() -> None:
    html = "<table></table>"
    result = run_discover(html)
    assert result.table_candidates == []


def test_discover_page_summary_fields() -> None:
    html = """<html><body>
      <table><tr><td>x</td></tr></table>
      <script type='application/ld+json'>{"a": 1}</script>
      <div><p>a</p><p>b</p><p>c</p></div>
    </body></html>"""
    result = run_discover(html)
    summary = result.page_summary
    assert summary["has_table"] is True
    assert summary["has_embedded_json"] is True
    assert summary["container_count_estimate"] >= 1


def test_discover_page_summary_negative_fields() -> None:
    html = "<html><body><p>nothing here</p></body></html>"
    result = run_discover(html)
    assert result.page_summary["has_table"] is False
    assert result.page_summary["has_embedded_json"] is False
    assert result.page_summary["container_count_estimate"] == 0


def test_discover_json_signals_top_level_keys_object() -> None:
    html = """<script type='application/json'>
      {"name": "Alice", "age": 30, "city": "Berlin"}
    </script>"""
    result = run_discover(html)
    assert len(result.json_signals) == 1
    sig = result.json_signals[0]
    assert sig["top_level_keys"] == ["name", "age", "city"]


def test_discover_json_signals_top_level_keys_array_first_elem() -> None:
    html = """<script type='application/json'>
      [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
    </script>"""
    result = run_discover(html)
    sig = result.json_signals[0]
    assert sig["top_level_keys"] == ["id", "title"]


def test_discover_json_signals_no_top_level_keys_on_invalid_json() -> None:
    html = "<script type='application/json'>{not valid json}</script>"
    result = run_discover(html)
    sig = result.json_signals[0]
    assert "top_level_keys" not in sig


def test_discover_json_signals_no_top_level_keys_on_scalar_json() -> None:
    # Valid JSON but a scalar — no keys to extract.
    html = "<script type='application/json'>42</script>"
    result = run_discover(html)
    # Bare scalar starting with a digit is not detected as json_signal
    # (needs `{` or `[` prefix or a JSON-mime type body matching shape).
    # If signal exists, it must not carry top_level_keys.
    for sig in result.json_signals:
        assert "top_level_keys" not in sig


def test_discover_to_json_includes_new_sections() -> None:
    import json

    html = """<div>
      <table><tr><th>K</th></tr><tr><td>v</td></tr></table>
      <script type='application/ld+json'>{"x": 1}</script>
      <div class='item'>a</div>
      <div class='item'>b</div>
      <div class='item'>c</div>
    </div>"""
    payload = json.loads(run_discover(html).to_json())
    assert "table_candidates" in payload
    assert "page_summary" in payload
    assert payload["sample_normalized"] is True


def test_discover_to_text_includes_new_sections() -> None:
    html = """<div>
      <table><tr><th>K</th></tr><tr><td>v</td></tr></table>
      <script type='application/ld+json'>{"x": 1}</script>
      <div class='item'>a</div>
      <div class='item'>b</div>
      <div class='item'>c</div>
    </div>"""
    text = run_discover(html).to_text()
    assert "== table_candidates ==" in text
    assert "== page_summary ==" in text
    assert "sample_normalized: true" in text
    # item_selector line is present on every container.
    assert "item_selector:" in text
