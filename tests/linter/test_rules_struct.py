"""
Tests for ssc_codegen/linter/rules_struct.py

Covers: struct name/type validation, required reserved fields, reserved field
checks, regular field checks, define rules, and the wildcard unknown-op rule.

Behavioural notes (established empirically):
- Children blocks inside reserved/regular fields MUST use multiline KDL (ops on
  separate lines). Inline semicolons inside a `{ }` block are not walked by the
  linter's child-walk (tree-sitter CST limitation).
- `@init` sub-pipelines: the named sub-pipeline nodes (e.g. `root { css ".x" }`)
  are walked with _in_pipeline=False inside @init, so their names are reported
  as "unknown operation". The linter only checks that @init is non-empty.
- `define NAME { ops }` block defines: can be used as ops in a field pipeline.
  The field must have the define name on its own line inside the field block.
- `transform` is registered as a module-level keyword — it fires the wildcard
  "unknown operation" rule when used inside a pipeline (not yet implemented as
  a pipeline op in the walker).
"""
from __future__ import annotations

import pytest
from hypothesis import given, assume, settings, HealthCheck
from hypothesis import strategies as st

from ssc_codegen.linter.format_errors import lint_string


# ── helpers ────────────────────────────────────────────────────────────────────


def lint(src: str) -> list[str]:
    result = lint_string(src)
    return [e.message for e in result.errors]


def no_errors(src: str) -> bool:
    result = lint_string(src)
    return not result.has_errors()


def item_struct(*field_lines: str) -> str:
    """Wrap field lines inside a minimal `item` struct."""
    body = "\n".join(f"  {l}" for l in field_lines)
    return f"struct S {{\n{body}\n}}\n"


def multiline_field(name: str, *ops: str) -> str:
    """Build a regular field with ops on separate lines."""
    inner = "\n    ".join(ops)
    return f"{name} {{\n    {inner}\n  }}"


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCT — name and type validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructRule:
    def test_valid_item_struct(self):
        src = (
            "struct MyStruct {\n"
            '  title {\n    css ".title"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_struct_no_name_error(self):
        src = 'struct {\n  title {\n    css ".x"\n    text\n  }\n}\n'
        msgs = lint(src)
        assert any("requires a name" in m for m in msgs)

    @pytest.mark.parametrize("bad_type", ["unknown", "foobar", "Item", "LIST"])
    def test_struct_invalid_type_error(self, bad_type: str):
        src = f'struct S type="{bad_type}" {{\n  f {{\n    css ".x"\n    text\n  }}\n}}\n'
        msgs = lint(src)
        assert any("unknown struct type" in m for m in msgs)

    @pytest.mark.parametrize("stype", ["item", "flat"])
    def test_valid_types_no_required_fields(self, stype: str):
        src = (
            f'struct S type="{stype}" {{\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_list_struct_missing_split_doc_error(self):
        src = (
            'struct S type="list" {\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("@split-doc" in m for m in msgs)

    def test_list_struct_with_split_doc_valid(self):
        src = (
            'struct S type="list" {\n'
            '  @split-doc {\n    css ".x"\n  }\n'
            '  title {\n    css ".y"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_dict_struct_missing_value_error(self):
        src = (
            'struct S type="dict" {\n'
            '  @key {\n    css ".k"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("@value" in m and "missing required" in m for m in msgs)

    def test_dict_struct_valid(self):
        src = (
            'struct S type="dict" {\n'
            '  @split-doc {\n    css-all ".items"\n  }\n'
            '  @key {\n    css ".k"\n    text\n  }\n'
            '  @value {\n    css ".v"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_table_struct_missing_reserved_fields_error(self):
        # Only -table present; -row, -match, -value are missing
        src = (
            'struct S type="table" {\n'
            '  @table {\n    css ".t"\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("missing required field" in m for m in msgs)

    def test_table_struct_valid(self):
        src = (
            'struct S type="table" {\n'
            '  @table {\n    css ".t"\n  }\n'
            '  @rows {\n    css ".r"\n  }\n'
            '  @match {\n    css ".m"\n    text\n  }\n'
            '  @value {\n    css ".v"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    @given(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="_-",
            ),
        ).filter(lambda s: s[0].isalpha())
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_hypothesis_valid_struct_name_no_name_error(self, name: str):
        src = (
            f"struct {name} {{\n"
            '  f {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert not any("requires a name" in m for m in msgs)
        assert not any("unknown struct type" in m for m in msgs)

    @given(
        st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz_-")
        .filter(lambda s: s not in {"item", "list", "dict", "table", "flat"} and s[0].isalpha())
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
    def test_hypothesis_invalid_struct_type_error(self, bad_type: str):
        src = (
            f'struct S type="{bad_type}" {{\n'
            '  f {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("unknown struct type" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# RESERVED FIELDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestReservedFields:
    def test_doc_valid(self):
        src = (
            "struct S {\n"
            '  @doc "my description"\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_doc_no_arg_error(self):
        src = (
            "struct S {\n"
            "  @doc\n"
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("requires a description string" in m for m in msgs)

    def test_pre_validate_valid(self):
        src = (
            "struct S {\n"
            '  @pre-validate {\n    css ".x"\n  }\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_pre_validate_empty_error(self):
        src = (
            "struct S {\n"
            "  @pre-validate\n"
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("must contain at least one operation" in m for m in msgs)

    def test_init_non_empty_valid(self):
        # @init just needs at least one named sub-pipeline
        src = (
            "struct S {\n"
            "  @init {\n"
            "    root {\n"
            '      css ".root"\n'
            "    }\n"
            "  }\n"
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        # @init block is non-empty; 'root' fires wildcard "unknown operation"
        # but @init structural check passes
        msgs = lint(src)
        assert not any("must contain at least one named pipeline" in m for m in msgs)

    def test_init_empty_error(self):
        src = (
            "struct S {\n"
            "  @init\n"
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("must contain at least one named pipeline" in m for m in msgs)

    def test_split_doc_invalid_in_item_error(self):
        src = (
            'struct S type="item" {\n'
            '  @split-doc {\n    css ".x"\n  }\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("not allowed in struct type" in m for m in msgs)

    def test_key_invalid_in_item_error(self):
        src = (
            'struct S type="item" {\n'
            '  @key {\n    css ".k"\n    text\n  }\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("not allowed in struct type" in m for m in msgs)

    def test_table_field_invalid_in_item_error(self):
        src = (
            'struct S type="item" {\n'
            '  @table {\n    css ".t"\n  }\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("not allowed in struct type" in m for m in msgs)

    def test_row_invalid_in_item_error(self):
        src = (
            'struct S type="item" {\n'
            '  @rows {\n    css ".r"\n  }\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("not allowed in struct type" in m for m in msgs)

    def test_match_field_invalid_in_item_error(self):
        src = (
            'struct S type="item" {\n'
            '  @match {\n    css ".m"\n    text\n  }\n'
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("not allowed in struct type" in m for m in msgs)

    def test_value_valid_in_dict(self):
        src = (
            'struct S type="dict" {\n'
            '  @split-doc {\n    css-all ".items"\n  }\n'
            '  @key {\n    css ".k"\n    text\n  }\n'
            '  @value {\n    css ".v"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_reserved_field_empty_ops_error(self):
        # -pre-validate with empty block
        src = (
            "struct S {\n"
            "  @pre-validate\n"
            '  f {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("must contain at least one operation" in m for m in msgs)


# ═══════════════════════════════════════════════════════════════════════════════
# REGULAR FIELDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegularFields:
    def test_field_with_ops_valid(self):
        src = (
            "struct S {\n"
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_field_no_ops_error(self):
        src = "struct S {\n  title\n}\n"
        msgs = lint(src)
        assert any("has no operations" in m for m in msgs)

    def test_multiple_fields_valid(self):
        src = (
            "struct S {\n"
            '  title {\n    css ".title"\n    text\n  }\n'
            '  url {\n    css "a"\n    attr "href"\n  }\n'
            '  count {\n    css-all ".item"\n    len\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_field_with_fallback_valid(self):
        src = (
            "struct S {\n"
            '  title {\n    css ".x"\n    text\n    fallback ""\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_field_chain_string_ops_valid(self):
        src = (
            "struct S {\n"
            '  title {\n    css ".x"\n    text\n    trim\n    lower\n  }\n'
            "}\n"
        )
        assert no_errors(src)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFINE RULES
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefineRule:
    def test_scalar_define_valid(self):
        src = (
            'define MY_URL="https://example.com"\n'
            "struct S {\n"
            '  url {\n    css ".x"\n    attr "href"\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_block_define_valid(self):
        src = (
            "define EXTRACT-HREF {\n"
            '  css "a"\n'
            '  attr "href"\n'
            "}\n"
            "struct S {\n"
            "  url {\n    EXTRACT-HREF\n  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_block_define_used_as_pipeline_op_valid(self):
        src = (
            "define GET-TEXT {\n"
            '  css ".x"\n'
            "  text\n"
            "}\n"
            "struct S {\n"
            "  title {\n    GET-TEXT\n  }\n"
            "}\n"
        )
        assert no_errors(src)

    def test_define_no_name_no_prop_error(self):
        # bare `define` with neither a prop nor a block
        src = "define\nstruct S {\n  f {\n    css \".x\"\n    text\n  }\n}\n"
        msgs = lint(src)
        assert any("must be scalar" in m or "requires a name" in m for m in msgs)

    def test_block_define_no_name_error(self):
        src = (
            "define {\n"
            '  css ".x"\n'
            "}\n"
            "struct S {\n"
            '  f {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert any("requires a name" in m for m in msgs)

    def test_scalar_define_used_as_op_error(self):
        src = (
            'define MY_SEL=".item"\n'
            "struct S {\n"
            "  title {\n    MY_SEL\n    text\n  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("scalar define" in m for m in msgs)

    def test_multiple_scalar_defines_valid(self):
        src = (
            'define URL="https://example.com"\n'
            'define SEL=".item"\n'
            "struct S {\n"
            '  f {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        assert no_errors(src)

    def test_chained_block_defines_valid(self):
        src = (
            "define EXTRACT {\n"
            '  css ".x"\n'
            "  text\n"
            "}\n"
            "define NORMALIZE {\n"
            "  trim\n"
            "  lower\n"
            "}\n"
            "struct S {\n"
            "  f {\n    EXTRACT\n    NORMALIZE\n  }\n"
            "}\n"
        )
        assert no_errors(src)


# ═══════════════════════════════════════════════════════════════════════════════
# WILDCARD — unknown operations inside field pipelines
# ═══════════════════════════════════════════════════════════════════════════════


class TestWildcardUnknownOp:
    def test_unknown_op_inside_field_error(self):
        src = (
            "struct S {\n"
            "  title {\n"
            '    css ".x"\n'
            "    totally-fake-op\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("unknown operation" in m for m in msgs)

    def test_known_op_no_wildcard_error(self):
        src = (
            "struct S {\n"
            '  title {\n    css ".x"\n    text\n  }\n'
            "}\n"
        )
        msgs = lint(src)
        assert not any("unknown operation" in m for m in msgs)

    def test_multiple_unknown_ops_errors(self):
        src = (
            "struct S {\n"
            "  f {\n"
            '    css ".x"\n'
            "    fake-op-one\n"
            "    fake-op-two\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert sum(1 for m in msgs if "unknown operation" in m) >= 2

    @given(
        st.text(
            min_size=3,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="-"),
        ).filter(
            lambda s: (
                s[0].isalpha()
                and s[-1].isalpha()
                and "--" not in s
                and s
                not in {
                    "css", "css-all", "css-remove", "xpath", "xpath-all",
                    "xpath-remove", "text", "raw", "attr", "trim", "ltrim",
                    "rtrim", "normalize-space", "fmt", "repl", "lower", "upper",
                    "rm-prefix", "rm-suffix", "rm-prefix-suffix", "unescape",
                    "split", "join", "re", "re-all", "re-sub", "index", "first",
                    "last", "slice", "len", "unique", "to-int", "to-float",
                    "to-bool", "jsonify", "nested", "self", "fallback", "filter",
                    "assert", "match", "not", "and", "or", "eq", "ne", "starts",
                    "ends", "contains", "in", "len-eq", "len-ne", "len-gt",
                    "len-lt", "len-ge", "len-le", "len-range", "has-attr",
                    "attr-eq", "attr-ne", "attr-starts", "attr-ends", "attr-re",
                    "text-re", "text-starts", "text-ends", "text-contains",
                    "re-any", "gt", "lt", "ge", "le", "transform",
                    # module-level keywords — not reported as unknown ops inside pipelines
                    "struct", "json", "define", "dsl", "expr",
                }
            )
        )
    )
    @settings(max_examples=25, suppress_health_check=[HealthCheck.filter_too_much])
    def test_hypothesis_unknown_op_produces_error(self, op_name: str):
        src = (
            "struct S {\n"
            "  title {\n"
            '    css ".x"\n'
            f"    {op_name}\n"
            "  }\n"
            "}\n"
        )
        msgs = lint(src)
        assert any("unknown operation" in m or "scalar define" in m for m in msgs)


