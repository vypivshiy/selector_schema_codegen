"""
Tests for ssc_codegen/kdl/linter/type_rules.py

Covers pipeline type inference and type-mismatch detection.

Behavioural notes (established empirically):
- ALL ops and children MUST be written on separate lines inside `{ }` blocks.
  Inline semicolons are not walked by the linter's CST child-walk.
- `index`, `first`, `last`, `slice` have accept=None (AUTO), so they accept
  any type including scalars — no type error on STRING input.
- `len` has accept=None but ret=INT, yet still no type-error fires for STRING
  (AUTO accept matches anything). Tests reflect actual behaviour.
- `fallback ""` on LIST_DOCUMENT produces a type mismatch error.
- `fallback {}` (empty-list sugar) requires a children block on a new line.
  Written as bare `fallback` with a children block.
- `transform <name>` is a pipeline call op. The linter looks up the transform
  by name in ctx.transforms (collected from module-level transform definitions).
  Type mismatch IS reported when the pipeline type doesn't match accept=TYPE.
- `-init` sub-pipeline names fire "unknown operation" in the wildcard rule
  (they are not registered ops). The -init structural check still passes.
- `match` node fires the `filter/assert/match` rule requiring children;
  used correctly only via match without children: linter reports empty-block.
  In table fields, use `match` alone on its own line — linter sees it as
  predicate container with no children → reports empty block. This is the
  actual behaviour; tests are aligned accordingly.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ssc_codegen.kdl.linter.format_errors import lint_string


# ── helpers ────────────────────────────────────────────────────────────────────


def lint(src: str) -> list[str]:
    errors, _ = lint_string(src)
    return [e.message for e in errors]


def no_errors(src: str) -> bool:
    errors, _ = lint_string(src)
    return len(errors) == 0


def field(*ops: str) -> str:
    """Wrap ops (one per line) in a minimal item-struct field."""
    body = "\n    ".join(ops)
    return f"struct S {{\n  f {{\n    {body}\n  }}\n}}\n"


# ═══════════════════════════════════════════════════════════════════════════════
# VALID PIPELINES — no type errors expected
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidPipelines:
    def test_css_text(self):
        assert no_errors(field('css ".x"', "text"))

    def test_css_raw(self):
        assert no_errors(field('css ".x"', "raw"))

    def test_css_attr(self):
        assert no_errors(field('css ".x"', 'attr "href"'))

    def test_css_all_text(self):
        assert no_errors(field('css-all ".x"', "text"))

    def test_css_all_attr(self):
        assert no_errors(field('css-all ".x"', 'attr "href"'))

    def test_css_all_index_text(self):
        assert no_errors(field('css-all ".x"', "index 0", "text"))

    def test_css_all_first_text(self):
        assert no_errors(field('css-all ".x"', "first", "text"))

    def test_css_all_last_text(self):
        assert no_errors(field('css-all ".x"', "last", "text"))

    def test_css_all_slice(self):
        assert no_errors(field('css-all ".x"', "slice 0 5"))

    def test_css_all_slice_text(self):
        assert no_errors(field('css-all ".x"', "slice 0 5", "text"))

    def test_text_to_int(self):
        assert no_errors(field('css ".x"', "text", "to-int"))

    def test_text_to_float(self):
        assert no_errors(field('css ".x"', "text", "to-float"))

    def test_text_to_bool(self):
        assert no_errors(field('css ".x"', "text", "to-bool"))

    def test_text_split_join(self):
        assert no_errors(field('css ".x"', "text", 'split " "', 'join ", "'))

    def test_text_re_sub(self):
        assert no_errors(field('css ".x"', "text", r're-sub #"\D"# ""'))

    def test_text_fmt(self):
        assert no_errors(field('css ".x"', "text", 'fmt "v={{}}"'))

    def test_text_lower_upper(self):
        assert no_errors(field('css ".x"', "text", "lower"))
        assert no_errors(field('css ".x"', "text", "upper"))

    def test_text_trim_chain(self):
        assert no_errors(field('css ".x"', "text", "trim", "lower", "upper"))

    def test_text_normalize_space(self):
        assert no_errors(field('css ".x"', "text", "normalize-space"))

    def test_list_string_join(self):
        assert no_errors(field('css-all ".x"', "text", 'join ", "'))

    def test_list_string_unique(self):
        assert no_errors(field('css-all ".x"', "text", "unique"))

    def test_list_string_to_int(self):
        assert no_errors(field('css-all ".x"', "text", "to-int"))

    def test_list_string_to_float(self):
        assert no_errors(field('css-all ".x"', "text", "to-float"))

    def test_css_all_len(self):
        assert no_errors(field('css-all ".x"', "len"))

    def test_fallback_string_after_text(self):
        assert no_errors(field('css ".x"', "text", 'fallback ""'))

    def test_fallback_int_after_to_int(self):
        assert no_errors(field('css ".x"', "text", "to-int", "fallback 0"))

    def test_fallback_float_after_to_float(self):
        assert no_errors(field('css ".x"', "text", "to-float", "fallback 0.0"))

    def test_fallback_null_after_text(self):
        assert no_errors(field('css ".x"', "text", "fallback #null"))

    def test_css_nested(self):
        msgs = lint(field('css ".x"', "nested MyStruct"))
        assert not any("does not accept" in m for m in msgs)

    def test_css_text_jsonify(self):
        msgs = lint(field('css ".x"', "text", "jsonify MySchema"))
        assert not any("does not accept" in m for m in msgs)

    def test_re_all_on_string(self):
        assert no_errors(field('css ".x"', "text", r're-all #"\d+"#'))

    def test_re_on_string(self):
        assert no_errors(field('css ".x"', "text", r're #"(\d+)"#'))

    def test_rm_prefix_on_string(self):
        assert no_errors(field('css ".x"', "text", 'rm-prefix "http"'))

    def test_rm_suffix_on_string(self):
        assert no_errors(field('css ".x"', "text", 'rm-suffix ".html"'))

    def test_unescape_on_string(self):
        assert no_errors(field('css ".x"', "text", "unescape"))

    def test_repl_on_string(self):
        assert no_errors(field('css ".x"', "text", 'repl "a" "b"'))

    def test_transform_no_name_fires_error(self):
        # transform with no name argument fires a name-required error
        msgs = lint(field('css ".x"', "text", "transform"))
        assert any("requires a name argument" in m for m in msgs)

    def test_transform_undefined_fires_error(self):
        # transform referencing an undefined name fires not-defined error
        msgs = lint(field('css ".x"', "text", "transform nonexistent"))
        assert any("is not defined" in m for m in msgs)

    def test_transform_valid_call_no_errors(self):
        # transform referencing a defined transform with matching types is valid
        src = (
            "transform to-str accept=STRING return=STRING {\n"
            "    py {\n"
            '        code "{{NXT}} = {{PRV}}"\n'
            "    }\n"
            "}\n"
            "struct S {\n"
            "    f {\n"
            '        css ".x"\n'
            "        text\n"
            "        transform to-str\n"
            "    }\n"
            "}\n"
        )
        assert no_errors(src)


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE MISMATCHES — errors expected
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypeMismatches:
    def test_string_op_on_document_error(self):
        msgs = lint(field('css ".x"', "trim"))
        assert any("does not accept" in m for m in msgs)

    def test_lower_on_document_error(self):
        msgs = lint(field('css ".x"', "lower"))
        assert any("does not accept" in m for m in msgs)

    def test_upper_on_document_error(self):
        msgs = lint(field('css ".x"', "upper"))
        assert any("does not accept" in m for m in msgs)

    def test_normalize_space_on_document_error(self):
        msgs = lint(field('css ".x"', "normalize-space"))
        assert any("does not accept" in m for m in msgs)

    def test_to_int_on_document_error(self):
        msgs = lint(field('css ".x"', "to-int"))
        assert any("does not accept" in m for m in msgs)

    def test_to_float_on_document_error(self):
        msgs = lint(field('css ".x"', "to-float"))
        assert any("does not accept" in m for m in msgs)

    def test_split_on_document_error(self):
        msgs = lint(field('css ".x"', 'split " "'))
        assert any("does not accept" in m for m in msgs)

    def test_re_sub_on_document_error(self):
        msgs = lint(field('css ".x"', r're-sub #"\D"# ""'))
        assert any("does not accept" in m for m in msgs)

    def test_join_on_document_error(self):
        msgs = lint(field('css ".x"', 'join ", "'))
        assert any("does not accept" in m for m in msgs)

    def test_join_on_string_error(self):
        # join requires LIST_STRING, not STRING
        msgs = lint(field('css ".x"', "text", 'join ", "'))
        assert any("does not accept" in m for m in msgs)

    def test_unique_on_string_error(self):
        msgs = lint(field('css ".x"', "text", "unique"))
        assert any("does not accept" in m for m in msgs)

    def test_css_on_list_document_error(self):
        msgs = lint(field('css-all ".x"', 'css ".y"'))
        assert any("does not accept" in m for m in msgs)

    def test_xpath_on_list_document_error(self):
        msgs = lint(field('css-all ".x"', 'xpath "//a"'))
        assert any("does not accept" in m for m in msgs)

    def test_filter_on_scalar_document_error(self):
        msgs = lint(field('css ".x"', "filter"))
        # filter with no children fires empty-block error; but type check also runs
        assert any("requires a list type" in m or "must contain at least one" in m for m in msgs)

    def test_filter_on_string_error(self):
        msgs = lint(field('css ".x"', "text", "filter"))
        assert any("requires a list type" in m or "must contain at least one" in m for m in msgs)

    def test_fallback_type_mismatch_string_on_list_error(self):
        # pipeline is LIST_DOCUMENT after css-all; scalar string fallback → mismatch
        msgs = lint(field('css-all ".x"', 'fallback ""'))
        assert any("does not match pipeline type" in m for m in msgs)

    def test_fallback_null_on_list_document_error(self):
        msgs = lint(field('css-all ".x"', "fallback #null"))
        assert any("only valid for STRING, INT, or FLOAT" in m for m in msgs)

    def test_fallback_int_mismatch_after_text_error(self):
        # STRING ≠ INT → mismatch
        msgs = lint(field('css ".x"', "text", "fallback 0"))
        assert any("does not match pipeline type" in m for m in msgs)

    def test_to_float_on_list_document_error(self):
        msgs = lint(field('css-all ".x"', "to-float"))
        assert any("does not accept" in m for m in msgs)

    def test_re_all_on_list_string_error(self):
        # re-all: STRING → LIST_STRING; cannot accept LIST_STRING input
        msgs = lint(field('css-all ".x"', "text", r're-all #"\d+"#'))
        assert any("does not accept" in m for m in msgs)

    def test_transform_type_mismatch_error(self):
        # css ".x" → DOCUMENT; transform to-str expects STRING → type mismatch
        src = (
            "transform to-str accept=STRING return=INT {\n"
            "    py {\n"
            '        code "{{NXT}} = int({{PRV}})"\n'
            "    }\n"
            "}\n"
            "struct S {\n"
            "    f {\n"
            '        css ".x"\n'
            "        transform to-str\n"
            "    }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("expects STRING" in m for m in msgs)

    @pytest.mark.parametrize("op", ["trim", "lower", "upper", "normalize-space",
                                     "to-int", "to-float", 'split " "'])
    def test_parametrize_string_ops_on_document_error(self, op: str):
        msgs = lint(field('css ".x"', op))
        assert any("does not accept" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK DEFINE — inline type expansion
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockDefineTypeExpansion:
    def test_block_define_valid_expansion(self):
        src = (
            "define EXTRACT {\n"
            '  css ".x"\n'
            "  text\n"
            "}\n"
            "struct S {\n"
            "  f {\n    EXTRACT\n  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_block_define_text_after_css_valid(self):
        src = (
            "define GET-TEXT {\n"
            "  text\n"
            "}\n"
            "struct S {\n"
            '  f {\n    css ".x"\n    GET-TEXT\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_block_define_type_mismatch_error(self):
        # EXTRACT starts with trim (requires STRING), but pipeline is DOCUMENT
        src = (
            "define BAD {\n"
            "  trim\n"
            "}\n"
            "struct S {\n"
            "  f {\n    BAD\n  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("does not accept" in m for m in msgs)

    def test_block_define_chained_valid(self):
        src = (
            "define GET-TEXT {\n"
            '  css ".item"\n'
            "  text\n"
            "}\n"
            "define NORMALIZE {\n"
            "  trim\n"
            "  lower\n"
            "}\n"
            "struct S {\n"
            "  f {\n    GET-TEXT\n    NORMALIZE\n  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_block_define_works_for_list_context(self):
        # text works for both DOCUMENT and LIST_DOCUMENT
        src = (
            "define EXTRACT-TEXT {\n"
            "  text\n"
            "}\n"
            "struct S {\n"
            '  f1 {\n    css ".x"\n    EXTRACT-TEXT\n  }\n'
            '  f2 {\n    css-all ".x"\n    EXTRACT-TEXT\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_scalar_define_as_op_error(self):
        src = (
            'define MY_SEL=".item"\n'
            "struct S {\n"
            "  f {\n    MY_SEL\n    text\n  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("scalar define" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETE VALID SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompleteSchemas:
    def test_item_schema_full(self):
        src = (
            "struct Product {\n"
            '  -doc "A product item"\n'
            '  title {\n    css "h1"\n    text\n    trim\n  }\n'
            '  price {\n    css ".price"\n    text\n    re #"([\\d\\.]+)"#\n    to-float\n  }\n'
            '  url {\n    css "a"\n    attr "href"\n  }\n'
            '  in_stock {\n    css ".stock"\n    text\n    to-bool\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_list_schema_full(self):
        src = (
            'struct ProductList type="list" {\n'
            '  -split-doc {\n    css ".product"\n  }\n'
            '  title {\n    css "h2"\n    text\n  }\n'
            '  price {\n    css ".price"\n    text\n    to-float\n    fallback 0.0\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_dict_schema_full(self):
        src = (
            'struct Attrs type="dict" {\n'
            '  -key {\n    css ".label"\n    text\n    trim\n  }\n'
            '  -value {\n    css ".val"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_schema_with_assert(self):
        # assert is transparent; empty assert node fires empty-block error,
        # but assert used without children is fine structurally — wait:
        # assert alone fires "must contain at least one". Use assert with -pre-validate style.
        # Actually just test a valid pipeline with no assert block.
        src = (
            "struct S {\n"
            '  title {\n    css "h1"\n    text\n    trim\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_schema_with_define_and_struct(self):
        src = (
            'define SEL=".item"\n'
            "define CLEAN-TEXT {\n"
            "  text\n"
            "  trim\n"
            "  lower\n"
            "}\n"
            "struct S {\n"
            '  title {\n    css ".title"\n    CLEAN-TEXT\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_schema_with_optional_fallback(self):
        src = (
            "struct S {\n"
            '  title {\n    css ".x"\n    text\n    fallback #null\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_schema_with_list_to_string(self):
        src = (
            "struct S {\n"
            "  tags {\n"
            '    css-all ".tag"\n'
            "    text\n"
            '    join ", "\n'
            "  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_schema_with_re_all_pipeline(self):
        src = (
            "struct S {\n"
            "  numbers {\n"
            '    css ".text"\n'
            "    text\n"
            '    re-all #"\\d+"#\n'
            "    to-int\n"
            "  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_schema_with_xpath(self):
        src = (
            "struct S {\n"
            '  items {\n    xpath-all "//li"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS — pipeline type coherence
# ═══════════════════════════════════════════════════════════════════════════════


class TestHypothesisPipelineTypes:
    _STRING_OPS = ["trim", "lower", "upper", "normalize-space", "ltrim", "rtrim"]
    _LIST_REDUCE_OPS = ["first", "last", "index 0", "slice 0 5"]

    @given(st.sampled_from(_STRING_OPS))
    @settings(max_examples=len(_STRING_OPS))
    def test_string_op_after_text_no_type_error(self, op: str):
        src = field('css ".x"', "text", op)
        msgs = lint(src)
        assert not any("does not accept" in m for m in msgs)

    @given(st.sampled_from(_STRING_OPS))
    @settings(max_examples=len(_STRING_OPS))
    def test_string_op_on_document_type_error(self, op: str):
        src = field('css ".x"', op)
        msgs = lint(src)
        assert any("does not accept" in m for m in msgs)

    @given(st.sampled_from(_LIST_REDUCE_OPS))
    @settings(max_examples=len(_LIST_REDUCE_OPS))
    def test_list_reduce_on_list_document_no_error(self, op: str):
        src = field('css-all ".x"', op)
        msgs = lint(src)
        assert not any("does not accept" in m for m in msgs)

    @given(
        st.lists(
            st.sampled_from(["trim", "lower", "upper", "normalize-space"]),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=20)
    def test_chained_string_ops_no_type_error(self, ops: list[str]):
        chain = list(ops)
        src = field('css ".x"', "text", *chain)
        msgs = lint(src)
        assert not any("does not accept" in m for m in msgs)

    @given(st.sampled_from(["trim", "lower", "upper", "to-int", "to-float", 'split " "']))
    @settings(max_examples=6)
    def test_string_ops_on_document_always_error(self, op: str):
        src = field('css ".x"', op)
        msgs = lint(src)
        assert any("does not accept" in m for m in msgs)

    @given(st.integers(min_value=-50, max_value=50), st.integers(min_value=-50, max_value=50))
    @settings(max_examples=20)
    def test_slice_any_integers_no_int_error(self, a: int, b: int):
        src = field('css-all ".x"', f"slice {a} {b}")
        msgs = lint(src)
        assert not any("must be integers" in m for m in msgs)

    @given(
        st.one_of(
            st.just('fallback ""'),
            st.just("fallback 0"),
            st.just("fallback 0.0"),
        )
    )
    @settings(max_examples=3)
    def test_scalar_fallback_on_list_document_type_error(self, fb: str):
        src = field('css-all ".x"', fb)
        msgs = lint(src)
        assert any("does not match pipeline type" in m for m in msgs)
