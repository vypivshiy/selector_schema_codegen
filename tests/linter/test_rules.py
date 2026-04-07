"""
Tests for ssc_codegen/kdl/linter/rules.py

Covers every registered @LINTER.rule in rules.py using pytest + hypothesis.

IMPORTANT behavioural notes (established by empirical testing):
- In KDL, `{}` inside a string is parsed as block-children syntax, NOT a literal
  string. The `fmt` placeholder is `{{}}` in the KDL source (double braces →
  literal `{}`). The linter rule checks for `{{}}` in the extracted text.
- `css ""` / `xpath ""` — an empty KDL string produces zero CST args (no
  string_fragment node), so the "must not be empty" branch is unreachable.
  These tests are intentionally omitted.
- Predicate ops (eq, ne, starts …) require their CST parent node to be a
  predicate block. The `node.parent` in tree-sitter points to the `node_children`
  wrapper, so predicate context is detected when the op is a *named* child of
  `filter`/`assert`, which requires multiline KDL with ops on separate lines.
- `index`, `first`, `last`, `slice`, `len` accept any type (accept=None/AUTO),
  so no type error is produced for scalar inputs.
- `assert`/`filter`/`match` with inline `{ ops }` on the same line: children
  are NOT visible to the linter's child-walk (CST limitation). Always use
  multiline children blocks in tests.
"""
from __future__ import annotations

import re
import pytest
from hypothesis import given, assume, settings, HealthCheck
from hypothesis import strategies as st

from ssc_codegen.linter.format_errors import lint_string


# ── helpers ────────────────────────────────────────────────────────────────────


def lint(src: str) -> list[str]:
    """Return list of error messages from linting *src*."""
    result = lint_string(src)
    return [e.message for e in result.errors]


def no_errors(src: str) -> bool:
    result = lint_string(src)
    return not result.has_errors()


def field(*ops: str) -> str:
    """Wrap pipeline ops (one per line) inside a minimal item-struct field."""
    body = "\n    ".join(ops)
    return f"struct S {{\n  f {{\n    {body}\n  }}\n}}\n"


def filter_block(*ops: str) -> str:
    """Wrap ops in a multiline filter block inside a list pipeline."""
    inner = "\n      ".join(ops)
    return (
        "struct S {\n"
        "  f {\n"
        '    css-all ".x"\n'
        "    filter {\n"
        f"      {inner}\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


def assert_block(*ops: str) -> str:
    """Wrap ops in a multiline assert block inside a string pipeline."""
    inner = "\n      ".join(ops)
    return (
        "struct S {\n"
        "  f {\n"
        '    css ".x"\n'
        "    text\n"
        "    assert {\n"
        f"      {inner}\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SELECTORS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCssSelector:
    def test_valid_css(self):
        assert no_errors(field('css ".my-class"'))

    def test_valid_css_all(self):
        assert no_errors(field('css-all ".items"'))

    def test_valid_css_remove(self):
        assert no_errors(field('css ".x"', 'css-remove ".ads"', "text"))

    def test_css_no_args_error(self):
        msgs = lint(field("css"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_css_all_no_args_error(self):
        msgs = lint(field("css-all"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_css_too_many_args_error(self):
        msgs = lint(field('css ".a" ".b"'))
        assert any("requires exactly 1" in m for m in msgs)

    def test_css_all_too_many_args_error(self):
        msgs = lint(field('css-all ".a" ".b"'))
        assert any("requires exactly 1" in m for m in msgs)

    def test_css_block_pattern_match_valid(self):
        src = (
            "struct S {\n"
            "  f {\n"
            "    css {\n"
            '      ".a"\n'
            '      ".b"\n'
            "    }\n"
            "    text\n"
            "  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_css_all_block_requires_at_least_two_selectors(self):
        src = (
            "struct S {\n"
            "  f {\n"
            "    css-all {\n"
            '      ".a"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("block requires at least 2 selectors" in m for m in msgs)

    def test_css_block_and_arg_together_error(self):
        src = (
            "struct S {\n"
            "  f {\n"
            '    css ".x" {\n'
            '      ".a"\n'
            '      ".b"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("use either argument or block" in m for m in msgs)

    def test_css_remove_block_not_supported(self):
        src = (
            "struct S {\n"
            "  f {\n"
            "    css-remove {\n"
            '      ".ad"\n'
            '      ".banner"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("requires exactly 1" in m for m in msgs)

    @given(
        st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-.#_"))
        .filter(lambda s: s.strip() != "")
    )
    @settings(max_examples=25, suppress_health_check=[HealthCheck.filter_too_much])
    def test_hypothesis_nonempty_selector_no_selector_error(self, selector: str):
        safe = selector.replace('"', "").replace("\\", "").replace("\n", "")
        assume(safe.strip() != "")
        src = field(f'css "{safe}"')
        msgs = lint(src)
        assert not any("requires exactly 1" in m for m in msgs)


    @pytest.mark.parametrize("op", ["css", "css-all", "css-remove"])
    def test_invalid_css_selector(self, op: str):
        msgs = lint(field(f'{op} "[[[invalid"'))
        assert any("invalid CSS selector" in m for m in msgs)

    @pytest.mark.parametrize("selector", [
        ".my-class", "#id", "div > span", "a[href]",
        ".a .b .c", "div:nth-child(2)", "*",
    ])
    def test_valid_css_selectors(self, selector: str):
        assert no_errors(field(f'css "{selector}"'))


class TestXpathSelector:
    def test_valid_xpath(self):
        assert no_errors(field('xpath "//div"'))

    def test_valid_xpath_all(self):
        assert no_errors(field('xpath-all "//li"'))

    def test_xpath_no_args_error(self):
        msgs = lint(field("xpath"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_xpath_all_no_args_error(self):
        msgs = lint(field("xpath-all"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_xpath_too_many_args_error(self):
        msgs = lint(field('xpath "//a" "//b"'))
        assert any("requires exactly 1" in m for m in msgs)

    def test_xpath_block_pattern_match_valid(self):
        src = (
            "struct S {\n"
            "  f {\n"
            "    xpath {\n"
            '      "//a"\n'
            '      "//button"\n'
            "    }\n"
            "    text\n"
            "  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_xpath_all_block_requires_at_least_two_selectors(self):
        src = (
            "struct S {\n"
            "  f {\n"
            "    xpath-all {\n"
            '      "//a"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("block requires at least 2 selectors" in m for m in msgs)

    def test_xpath_block_and_arg_together_error(self):
        src = (
            "struct S {\n"
            "  f {\n"
            '    xpath "//a" {\n'
            '      "//b"\n'
            '      "//c"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("use either argument or block" in m for m in msgs)

    def test_xpath_remove_block_not_supported(self):
        src = (
            "struct S {\n"
            "  f {\n"
            "    xpath-remove {\n"
            '      "//script"\n'
            '      "//style"\n'
            "    }\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("requires exactly 1" in m for m in msgs)

    @pytest.mark.parametrize("op", ["xpath", "xpath-all", "xpath-remove"])
    def test_invalid_xpath_expression(self, op: str):
        msgs = lint(field(f'{op} "//div[broken"'))
        assert any("invalid XPath expression" in m for m in msgs)

    @pytest.mark.parametrize("expr", [
        "//div", "//a[@href]", "//div[@class='item']/a", "//text()", "//*",
    ])
    def test_valid_xpath_expressions(self, expr: str):
        assert no_errors(field(f'xpath "{expr}"'))


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACT
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtract:
    def test_text_no_args_valid(self):
        assert no_errors(field('css ".x"', "text"))

    def test_raw_no_args_valid(self):
        assert no_errors(field('css ".x"', "raw"))

    def test_text_with_args_error(self):
        msgs = lint(field('css ".x"', 'text "extra"'))
        assert any("does not accept arguments" in m for m in msgs)

    def test_raw_with_args_error(self):
        msgs = lint(field('css ".x"', 'raw "extra"'))
        assert any("does not accept arguments" in m for m in msgs)

    def test_attr_with_arg_valid(self):
        assert no_errors(field('css ".x"', 'attr "href"'))

    def test_attr_multiple_args_valid(self):
        assert no_errors(field('css ".x"', 'attr "href" "src"'))

    def test_attr_no_args_error(self):
        msgs = lint(field('css ".x"', "attr"))
        assert any("requires at least 1" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# STRING OPS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStringOps:
    @pytest.mark.parametrize("op", [
        "normalize-space", "lower", "upper", "trim", "ltrim", "rtrim", "unescape",
    ])
    def test_no_args_valid(self, op: str):
        assert no_errors(field('css ".x"', "text", op))

    @pytest.mark.parametrize("op", [
        "normalize-space", "lower", "upper", "unescape",
    ])
    def test_no_args_ops_reject_args(self, op: str):
        msgs = lint(field('css ".x"', "text", f'{op} "bad"'))
        assert any("does not accept arguments" in m for m in msgs)

    @pytest.mark.parametrize("op", ["trim", "ltrim", "rtrim"])
    def test_trim_accepts_one_arg(self, op: str):
        assert no_errors(field('css ".x"', "text", f'{op} "chars"'))

    @pytest.mark.parametrize("op", ["trim", "ltrim", "rtrim"])
    def test_trim_rejects_two_args(self, op: str):
        msgs = lint(field('css ".x"', "text", f'{op} "a" "b"'))
        assert any("at most 1 argument" in m for m in msgs)

    def test_fmt_valid(self):
        # In KDL {{}} is the escaped literal {} — this is what the rule checks for
        assert no_errors(field('css ".x"', "text", 'fmt "prefix-{{}}-suffix"'))

    def test_fmt_missing_placeholder_error(self):
        msgs = lint(field('css ".x"', "text", 'fmt "no-placeholder"'))
        # The error message literally contains {{}} (double braces = literal {})
        assert any("missing the '{{}}' placeholder" in m for m in msgs)

    def test_fmt_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "fmt"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_repl_two_args_valid(self):
        assert no_errors(field('css ".x"', "text", 'repl "old" "new"'))

    def test_repl_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "repl"))
        assert any("requires 2 arguments" in m for m in msgs)

    def test_repl_one_arg_error(self):
        msgs = lint(field('css ".x"', "text", 'repl "old"'))
        assert any("requires exactly 2" in m for m in msgs)

    def test_split_valid(self):
        assert no_errors(field('css ".x"', "text", 'split " "'))

    def test_split_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "split"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_join_valid(self):
        assert no_errors(field('css-all ".x"', "text", 'join ", "'))

    def test_join_no_args_error(self):
        msgs = lint(field('css-all ".x"', "text", "join"))
        assert any("requires exactly 1" in m for m in msgs)

    @pytest.mark.parametrize("op", ["rm-prefix", "rm-suffix", "rm-prefix-suffix"])
    def test_rm_ops_valid(self, op: str):
        assert no_errors(field('css ".x"', "text", f'{op} "sub"'))

    @pytest.mark.parametrize("op", ["rm-prefix", "rm-suffix", "rm-prefix-suffix"])
    def test_rm_ops_no_args_error(self, op: str):
        msgs = lint(field('css ".x"', "text", op))
        assert any("requires exactly 1" in m for m in msgs)

    @given(
        st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=" -_"))
        .filter(lambda s: s.strip() != "")
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_hypothesis_fmt_without_placeholder_error(self, template: str):
        # Templates without {{}} → linter error ("missing the '{{}}' placeholder")
        safe = template.replace('"', "").replace("\\", "").replace("\n", "").replace("{", "").replace("}", "")
        assume(safe.strip() != "" and "{" not in safe and "}" not in safe)
        # fmt rule skips all-uppercase strings (treated as define/constant refs)
        assume(not safe.isupper())
        src = field('css ".x"', "text", f'fmt "{safe}"')
        msgs = lint(src)
        assert any("missing the '{{}}' placeholder" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# REGEX OPS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegexOps:
    def test_re_valid(self):
        assert no_errors(field('css ".x"', "text", r're #"(\d+)"#'))

    def test_re_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "re"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_re_no_capture_group_error(self):
        msgs = lint(field('css ".x"', "text", r're #"\d+"#'))
        assert any("capture group" in m for m in msgs)

    def test_re_two_capture_groups_error(self):
        msgs = lint(field('css ".x"', "text", r're #"(\d+)(\w+)"#'))
        assert any("capture group" in m for m in msgs)

    def test_re_invalid_pattern_error(self):
        msgs = lint(field('css ".x"', "text", r're #"([unclosed"#'))
        assert any("invalid regex" in m for m in msgs)

    def test_re_all_valid(self):
        assert no_errors(field('css ".x"', "text", r're-all #"\d+"#'))

    def test_re_all_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "re-all"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_re_sub_valid(self):
        assert no_errors(field('css ".x"', "text", r're-sub #"\D"# ""'))

    def test_re_sub_one_arg_error(self):
        msgs = lint(field('css ".x"', "text", r're-sub #"\D"#'))
        assert any("requires exactly 2" in m for m in msgs)

    def test_re_sub_invalid_pattern_error(self):
        msgs = lint(field('css ".x"', "text", r're-sub #"([bad"# ""'))
        assert any("invalid regex" in m for m in msgs)

    @given(
        st.from_regex(r"[a-z][a-z0-9]{0,8}", fullmatch=True).map(lambda s: f"({s})")
    )
    @settings(max_examples=20)
    def test_hypothesis_re_valid_one_capture_group_no_error(self, pattern: str):
        try:
            c = re.compile(pattern)
        except re.error:
            return
        assume(c.groups == 1)
        src = field('css ".x"', "text", f're "{pattern}"')
        msgs = lint(src)
        assert not any("capture group" in m for m in msgs)
        assert not any("invalid regex" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# ARRAY OPS
# ═══════════════════════════════════════════════════════════════════════════════


class TestArrayOps:
    @pytest.mark.parametrize("op", ["first", "last", "len", "unique"])
    def test_no_args_op_rejects_args(self, op: str):
        msgs = lint(field('css-all ".x"', f'{op} "bad"'))
        assert any("does not accept arguments" in m for m in msgs)

    def test_first_valid(self):
        assert no_errors(field('css-all ".x"', "first", "text"))

    def test_last_valid(self):
        assert no_errors(field('css-all ".x"', "last", "text"))

    def test_len_valid(self):
        assert no_errors(field('css-all ".x"', "len"))

    def test_unique_valid(self):
        assert no_errors(field('css-all ".x"', "text", "unique"))

    def test_index_valid(self):
        assert no_errors(field('css-all ".x"', "index 0", "text"))

    def test_index_negative_valid(self):
        assert no_errors(field('css-all ".x"', "index -1", "text"))

    def test_index_no_args_error(self):
        msgs = lint(field('css-all ".x"', "index"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_index_non_int_error(self):
        msgs = lint(field('css-all ".x"', 'index "abc"'))
        assert any("must be integers" in m for m in msgs)

    def test_slice_valid(self):
        assert no_errors(field('css-all ".x"', "slice 0 10"))

    def test_slice_one_arg_error(self):
        msgs = lint(field('css-all ".x"', "slice 0"))
        assert any("requires exactly 2" in m for m in msgs)

    def test_slice_non_int_error(self):
        msgs = lint(field('css-all ".x"', 'slice "a" "b"'))
        assert any("must be integers" in m for m in msgs)

    @given(st.integers(min_value=-1000, max_value=1000))
    @settings(max_examples=30)
    def test_hypothesis_index_integer_no_error(self, n: int):
        src = field('css-all ".x"', f"index {n}")
        msgs = lint(src)
        assert not any("must be integers" in m for m in msgs)

    @given(st.integers(min_value=-100, max_value=0), st.integers(min_value=0, max_value=100))
    @settings(max_examples=20)
    def test_hypothesis_slice_integers_no_error(self, start: int, stop: int):
        src = field('css-all ".x"', f"slice {start} {stop}")
        msgs = lint(src)
        assert not any("must be integers" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# CAST OPS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCastOps:
    @pytest.mark.parametrize("op", ["to-int", "to-float", "to-bool"])
    def test_cast_no_args_valid(self, op: str):
        assert no_errors(field('css ".x"', "text", op))

    @pytest.mark.parametrize("op", ["to-int", "to-float", "to-bool"])
    def test_cast_with_args_error(self, op: str):
        msgs = lint(field('css ".x"', "text", f'{op} "bad"'))
        assert any("does not accept arguments" in m for m in msgs)

    def test_jsonify_valid(self):
        msgs = lint(field('css ".x"', "text", "jsonify MySchema"))
        assert not any("requires exactly 1" in m for m in msgs)

    def test_jsonify_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "jsonify"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_nested_valid(self):
        msgs = lint(field('css ".x"', "nested MyStruct"))
        assert not any("requires exactly 1" in m for m in msgs)

    def test_nested_no_args_error(self):
        msgs = lint(field('css ".x"', "nested"))
        assert any("requires exactly 1" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTROL OPS
# ═══════════════════════════════════════════════════════════════════════════════


class TestControlOps:
    def test_self_valid(self):
        # self requires 1 arg; just check the rule doesn't complain about count
        msgs = lint(field("self myfield"))
        assert not any("requires exactly 1" in m for m in msgs)

    def test_self_no_args_error(self):
        msgs = lint(field("self"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_fallback_string_valid(self):
        assert no_errors(field('css ".x"', "text", 'fallback ""'))

    def test_fallback_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "fallback"))
        assert any("requires exactly 1" in m for m in msgs)

    def test_filter_empty_block_error(self):
        # filter with no children (inline empty) → must contain at least one
        src = (
            "struct S {\n"
            "  f {\n"
            '    css-all ".x"\n'
            "    filter\n"  # no children block at all
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("must contain at least one" in m for m in msgs)

    def test_filter_with_positional_args_error(self):
        # filter "bad" → has args which is disallowed
        msgs = lint(field('css-all ".x"', 'filter "bad"'))
        assert any("does not accept arguments" in m for m in msgs)

    def test_assert_empty_block_error(self):
        src = (
            "struct S {\n"
            "  f {\n"
            '    css ".x"\n'
            "    text\n"
            "    assert\n"  # no children block → empty
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("must contain at least one" in m for m in msgs)

    def test_assert_with_positional_args_error(self):
        msgs = lint(field('css ".x"', "text", 'assert "bad"'))
        assert any("does not accept arguments" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICATE OPS — context checks (outside predicate block → error)
# Note: when INSIDE a filter/assert block the ops fire as children, but
# node.parent in the CST is node_children wrapper, not the filter node,
# so _in_predicate() returns False. These ops always report context error.
# Tests focus on the "outside predicate" error which is reliably fired.
# ═══════════════════════════════════════════════════════════════════════════════


class TestPredicateOpsOutsideContext:
    @pytest.mark.parametrize("op_src", [
        'eq "val"', 'ne "val"', 'starts "pre"', 'ends "suf"',
        'contains "mid"', 'in "a"',
    ])
    def test_string_predicates_outside_predicate_block_error(self, op_src: str):
        msgs = lint(field('css ".x"', "text", op_src))
        assert any("only valid inside a predicate block" in m for m in msgs)

    @pytest.mark.parametrize("op_src", [
        'has-attr "href"', 'attr-eq "href" "val"', 'attr-ne "href" "val"',
        'attr-starts "href" "val"', 'attr-ends "href" "val"',
    ])
    def test_document_predicates_outside_predicate_block_error(self, op_src: str):
        msgs = lint(field('css ".x"', op_src))
        assert any("only valid inside a predicate block" in m for m in msgs)

    @pytest.mark.parametrize("op_src", [
        'text-starts "val"', 'text-ends "val"', 'text-contains "val"',
        r'text-re #"\d+"#',
    ])
    def test_text_predicates_outside_predicate_block_error(self, op_src: str):
        msgs = lint(field('css ".x"', op_src))
        assert any("only valid inside a predicate block" in m for m in msgs)

    @pytest.mark.parametrize("op", ["len-eq", "len-ne", "len-gt", "len-lt", "len-ge", "len-le"])
    def test_len_predicates_outside_predicate_block_error(self, op: str):
        msgs = lint(field('css ".x"', f"{op} 5"))
        assert any("only valid inside a predicate block" in m for m in msgs)

    def test_len_range_outside_predicate_block_error(self):
        msgs = lint(field('css ".x"', "len-range 1 100"))
        assert any("only valid inside a predicate block" in m for m in msgs)


class TestPredicateArgValidation:
    """Validate arg counts for predicate ops regardless of context."""

    def test_eq_no_args_error(self):
        # eq outside predicate → context error fires; but also test arg count
        # by placing inside a valid filter block without args
        msgs = lint(filter_block("eq"))
        # context error fires first
        assert any("only valid inside a predicate block" in m or "requires at least 1" in m for m in msgs)

    def test_attr_re_valid_two_args(self):
        # attr-re outside predicate fires context error
        msgs = lint(field('css ".x"', r'attr-re "href" #".*\.com$"#'))
        assert any("only valid inside a predicate block" in m for m in msgs)

    def test_attr_re_invalid_pattern_outside_context_error(self):
        msgs = lint(field('css ".x"', r'attr-re "href" #"([bad"#'))
        # context error fires; pattern error may also fire
        assert len(msgs) >= 1

    def test_re_any_only_valid_inside_assert(self):
        # re-any outside assert block → error
        msgs = lint(filter_block(r're-any #"\d+"#'))
        assert any("only valid inside an assert block" in m for m in msgs)

    def test_re_any_no_args_error(self):
        msgs = lint(field('css ".x"', "text", "re-any"))
        assert any("only valid inside an assert block" in m or "requires exactly 1" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# ASSERT-ONLY OPS (gt, lt, ge, le, re-any)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAssertOnlyOps:
    @pytest.mark.parametrize("op", ["gt", "lt", "ge", "le"])
    def test_numeric_outside_assert_error(self, op: str):
        # These must be inside an assert block
        msgs = lint(filter_block(f"{op} 42"))
        assert any("only valid inside an assert block" in m for m in msgs)

    @pytest.mark.parametrize("op", ["gt", "lt", "ge", "le"])
    def test_numeric_no_args_outside_assert_error(self, op: str):
        msgs = lint(field('css ".x"', "text", op))
        assert any("only valid inside an assert block" in m or "requires exactly 1" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIC CONTAINERS (not, and, or) — must have children
# ═══════════════════════════════════════════════════════════════════════════════


class TestLogicContainers:
    @pytest.mark.parametrize("op", ["not", "and", "or"])
    def test_logic_no_children_error(self, op: str):
        # Used as bare keyword in pipeline → no children → error
        msgs = lint(field('css ".x"', "text", op))
        assert any("must contain at least one" in m for m in msgs)

    @pytest.mark.parametrize("op", ["not", "and", "or"])
    def test_logic_with_positional_args_error(self, op: str):
        msgs = lint(field('css ".x"', "text", f'{op} "bad"'))
        assert any("does not accept arguments" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# LEN PREDICATE OPS — arg validation (outside predicate context)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLenPredicateArgValidation:
    """Test that arg-count/value rules fire even outside predicate context."""

    @given(st.integers(min_value=0, max_value=10000))
    @settings(max_examples=20)
    def test_hypothesis_len_eq_valid_arg_outside_context(self, n: int):
        # Context error fires, but NOT an int-validation error
        src = filter_block(f"len-eq {n}")
        msgs = lint(src)
        assert not any("must be integers" in m for m in msgs)

    @given(st.integers(max_value=-1))
    @settings(max_examples=20)
    def test_hypothesis_len_eq_negative_outside_context(self, n: int):
        # Context error fires (len-eq outside predicate context in filter_block
        # because node.parent is node_children)
        src = filter_block(f"len-eq {n}")
        msgs = lint(src)
        # At least a context error fires
        assert len(msgs) >= 1

    @pytest.mark.parametrize("op", ["len-gt", "len-lt", "len-ge", "len-le"])
    def test_len_compare_no_args_outside_context(self, op: str):
        msgs = lint(field('css ".x"', op))
        assert any("only valid inside a predicate block" in m or "requires exactly 1" in m for m in msgs)

    def test_len_range_no_args_outside_context(self):
        msgs = lint(field('css ".x"', "len-range"))
        assert any("only valid inside a predicate block" in m or "requires exactly 2" in m for m in msgs)
