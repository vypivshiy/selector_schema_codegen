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
