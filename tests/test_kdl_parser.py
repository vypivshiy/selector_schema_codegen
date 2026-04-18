from pathlib import Path

import pytest

from ssc_codegen.kdl.parser import (
    CSTArgEntry,
    CSTPropEntry,
    KDLParseError,
    KDL2CSTParser,
)


_ROOT = Path(__file__).parent.parent
_ALL_KDL_FILES = list((_ROOT / "examples").glob("*.kdl")) + list(
    (_ROOT / "tests/kdl_test_cases/input").glob("*.kdl")
)
_VALID_KDL_FILES = [
    f for f in _ALL_KDL_FILES if not f.name.endswith("_fail.kdl")
]
_INVALID_KDL_FILES = [f for f in _ALL_KDL_FILES if f.name.endswith("_fail.kdl")]


@pytest.mark.parametrize("file", _VALID_KDL_FILES, ids=lambda p: p.name)
def test_orig_kdl2_valid_cases(file: Path):
    parser = KDL2CSTParser()
    doc = parser.parse(file.read_text(encoding="utf-8-sig"))
    assert doc.span.end.offset >= doc.span.start.offset


@pytest.mark.parametrize("file", _INVALID_KDL_FILES, ids=lambda p: p.name)
def test_orig_kdl2_invalid_cases(file: Path):
    with pytest.raises(KDLParseError):
        KDL2CSTParser().parse(file.read_text(encoding="utf-8-sig"))


def test_kdl_parser_keeps_spans_and_entries():
    src = """
struct Main {
    item type=list {
        css \"a[href]\";
        attr href
        fallback #null
    }
}
"""
    doc = KDL2CSTParser().parse(src)

    assert len(doc.nodes) == 1
    root = doc.nodes[0]
    assert root.name.value == "struct"
    assert isinstance(root.entries[0], CSTArgEntry)
    assert root.entries[0].value.value == "Main"

    item = root.children[0]
    assert item.name.value == "item"

    prop_entries = [e for e in item.entries if isinstance(e, CSTPropEntry)]
    assert len(prop_entries) == 1
    assert prop_entries[0].key.value == "type"
    assert prop_entries[0].value.value == "list"

    arg_entries = [
        e for e in item.children[0].entries if isinstance(e, CSTArgEntry)
    ]
    assert arg_entries[0].value.value == "a[href]"

    assert item.span.start.line > 0
    assert item.span.end.offset > item.span.start.offset


def test_kdl_parser_multiline_and_raw_strings():
    src = '''
@doc """
line1
line2
"""
define PAT=#"""
(?xs)
abc
"""#
'''
    doc = KDL2CSTParser().parse(src)

    assert len(doc.nodes) == 2
    doc_node = doc.nodes[0]
    define_node = doc.nodes[1]

    assert doc_node.name.value == "@doc"
    assert isinstance(doc_node.entries[0], CSTArgEntry)
    assert "line1" in doc_node.entries[0].value.value

    assert define_node.name.value == "define"
    assert isinstance(define_node.entries[0], CSTPropEntry)
    assert "(?xs)" in define_node.entries[0].value.value


def test_kdl_parser_accepts_dotted_bare_identifier_values():
    src = """
struct X {
    f { css-all .col-auto }
}
"""
    doc = KDL2CSTParser().parse(src)
    field = doc.nodes[0].children[0]
    css_all = field.children[0]
    assert css_all.name.value == "css-all"
    assert isinstance(css_all.entries[0], CSTArgEntry)
    assert css_all.entries[0].value.value == ".col-auto"


def test_kdl_parser_allows_string_identifier_node_name():
    src = """
repl {
    "from" "to"
}
"""
    doc = KDL2CSTParser().parse(src)
    repl_node = doc.nodes[0]
    child = repl_node.children[0]
    assert child.name.value == "from"
    assert isinstance(child.entries[0], CSTArgEntry)
    assert child.entries[0].value.value == "to"


def test_kdl_parser_parses_radix_and_keyword_numbers():
    src = """
node 0x10 0o10 0b10 #inf #-inf #nan
"""
    doc = KDL2CSTParser().parse(src)
    vals = [
        entry.value.value
        for entry in doc.nodes[0].entries
        if isinstance(entry, CSTArgEntry)
    ]
    assert vals[0] == 16
    assert vals[1] == 8
    assert vals[2] == 2
    assert vals[3] > 0
    assert vals[4] < 0
    assert vals[5] != vals[5]


def test_kdl_parser_supports_slashdash_omission():
    src = """
/- dropped 1
kept 2
"""
    doc = KDL2CSTParser().parse(src)
    assert len(doc.nodes) == 1
    assert doc.nodes[0].name.value == "kept"
    assert doc.nodes[0].entries[0].value.value == 2


def test_kdl_parser_supports_nested_block_comments():
    src = """
/* outer
   /* inner */
*/
node 1
"""
    doc = KDL2CSTParser().parse(src)
    assert len(doc.nodes) == 1
    assert doc.nodes[0].name.value == "node"


def test_kdl_parser_raises_on_unterminated_block_comment():
    with pytest.raises(KDLParseError, match="Unterminated block comment"):
        KDL2CSTParser().parse("/* x")


def test_kdl_parser_raises_on_newline_in_quoted_string():
    bad = 'node "a\nb"'
    with pytest.raises(KDLParseError, match="Newline in quoted string"):
        KDL2CSTParser().parse(bad)


def test_kdl_parser_supports_escline_line_continuation():
    src = 'node "a" \\\n "b"'
    doc = KDL2CSTParser().parse(src)
    vals = [
        entry.value.value
        for entry in doc.nodes[0].entries
        if isinstance(entry, CSTArgEntry)
    ]
    assert vals == ["a", "b"]


def test_kdl_parser_handles_spec_like_package_example():
    src = '''
package {
  name my-pkg
  version "1.2.3"

  dependencies {
    lodash "^3.2.1" optional=#true alias=underscore
  }

  scripts {
    message """
      hello
      world
      """
    build #"""
      echo "foo"
      node -c "console.log('hello, world!');"
      echo "foo" > some-file.txt
      """#
  }

  the-matrix 1 2 3 \\
             4 5 6 \\
             7 8 9

  /-this-is-commented {
    this entire node {
      is gone
    }
  }
}
'''
    doc = KDL2CSTParser().parse(src)

    assert len(doc.nodes) == 1
    pkg = doc.nodes[0]
    assert pkg.name.value == "package"

    children = {n.name.value: n for n in pkg.children}
    assert "name" in children
    assert "version" in children
    assert "dependencies" in children
    assert "scripts" in children
    assert "the-matrix" in children
    assert "this-is-commented" not in children

    deps = children["dependencies"].children[0]
    assert deps.name.value == "lodash"
    dep_args = [
        e.value.value for e in deps.entries if isinstance(e, CSTArgEntry)
    ]
    dep_props = {
        e.key.value: e.value.value
        for e in deps.entries
        if isinstance(e, CSTPropEntry)
    }
    assert dep_args == ["^3.2.1"]
    assert dep_props["optional"] is True
    assert dep_props["alias"] == "underscore"

    scripts = children["scripts"].children
    message = next(n for n in scripts if n.name.value == "message")
    build = next(n for n in scripts if n.name.value == "build")
    assert "hello" in message.entries[0].value.value
    assert "world" in message.entries[0].value.value
    assert "console.log('hello, world!');" in build.entries[0].value.value

    matrix = children["the-matrix"]
    matrix_vals = [
        e.value.value for e in matrix.entries if isinstance(e, CSTArgEntry)
    ]
    assert matrix_vals == [1, 2, 3, 4, 5, 6, 7, 8, 9]
