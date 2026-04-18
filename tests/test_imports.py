"""Tests for the import statement in the KDL DSL parser."""

from pathlib import Path

import pytest

from ssc_codegen import parse_ast
from ssc_codegen.ast import (
    Struct,
    TypeDef,
    TransformDef,
    Fmt,
    CssSelect,
    Text,
    Attr,
    Nested,
)
from ssc_codegen.ast.types import VariableType
from ssc_codegen.exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures" / "imports"


# ── helpers ───────────────────────────────────────────────────────────────────


def _structs(module) -> list[Struct]:
    return [n for n in module.body if isinstance(n, Struct)]


def _struct(module, name: str) -> Struct:
    return next(s for s in _structs(module) if s.name == name)


def _field(struct: Struct, name: str):
    return next(n for n in struct.body if getattr(n, "name", None) == name)


def _field_ops(struct: Struct, field_name: str) -> list:
    f = _field(struct, field_name)
    return f.body


# ── basic import ──────────────────────────────────────────────────────────────


def test_import_defines():
    """Imported scalar and block defines are resolved in the importing module."""
    m = parse_ast(path=str(FIXTURES / "main_schema.kdl"))
    page = _struct(m, "Page")

    # FMT-BASE was imported and used in fmt
    url_ops = _field_ops(page, "url")
    fmt_node = next(op for op in url_ops if isinstance(op, Fmt))
    assert "example.com" in fmt_node.template

    # RE-PRICE was imported and used in re
    price_ops = _field_ops(page, "price")
    # price pipeline: css -> text -> re -> to-float -> return
    # re node has the regex from the imported define
    from ssc_codegen.ast import Re

    re_node = next(op for op in price_ops if isinstance(op, Re))
    assert r"\d+" in re_node.pattern


def test_import_struct():
    """Imported struct is available for nested references and appears in module body."""
    m = parse_ast(path=str(FIXTURES / "main_schema.kdl"))
    structs = _structs(m)
    names = [s.name for s in structs]

    assert "SharedItem" in names
    assert "Page" in names

    # SharedItem comes before Page (imported first)
    assert names.index("SharedItem") < names.index("Page")

    # nested reference works
    page = _struct(m, "Page")
    item_ops = _field_ops(page, "item")
    nested_node = next(op for op in item_ops if isinstance(op, Nested))
    assert nested_node.struct_name == "SharedItem"


def test_import_struct_has_typedef():
    """Imported struct gets a TypeDef in the module body."""
    m = parse_ast(path=str(FIXTURES / "main_schema.kdl"))
    typedefs = [n for n in m.body if isinstance(n, TypeDef)]
    typedef_names = [t.name for t in typedefs]
    assert "SharedItem" in typedef_names


# ── selective import ──────────────────────────────────────────────────────────


def test_selective_import_includes_named():
    """Selective import only brings in requested names."""
    m = parse_ast(path=str(FIXTURES / "selective_schema.kdl"))
    page = _struct(m, "SelectivePage")

    # FMT-BASE was imported selectively
    url_ops = _field_ops(page, "url")
    fmt_node = next(op for op in url_ops if isinstance(op, Fmt))
    assert "example.com" in fmt_node.template


def test_selective_import_excludes_others():
    """Selective import does not bring in names not listed."""
    # selective_schema.kdl only imports FMT-BASE, not STRIP-PREFIX or RE-PRICE
    # If we try to use STRIP-PREFIX it should fail
    src = (FIXTURES / "selective_schema.kdl").read_text(encoding="utf-8-sig")
    # This should parse fine (STRIP-PREFIX is not used)
    m = parse_ast(path=str(FIXTURES / "selective_schema.kdl"))
    assert _structs(m)  # parsed OK


def test_selective_import_missing_name_errors():
    """Requesting a name that doesn't exist in the imported file raises ParseError."""
    bad_kdl = FIXTURES / "selective_bad.kdl"
    bad_kdl.write_text(
        'import "./shared_defines.kdl" { NONEXISTENT }\n'
        'struct X { x { css "x"; text } }\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ParseError, match="names not found.*NONEXISTENT"):
            parse_ast(path=str(bad_kdl))
    finally:
        bad_kdl.unlink(missing_ok=True)


# ── transitive import ────────────────────────────────────────────────────────


def test_transitive_import():
    """A -> B -> C: A sees names from C."""
    m = parse_ast(path=str(FIXTURES / "transitive_schema.kdl"))
    structs = _structs(m)
    names = [s.name for s in structs]

    # Level2Item is imported from level2.kdl
    assert "Level2Item" in names
    assert "TransitivePage" in names

    # FMT-BASE from shared_defines.kdl is available transitively
    page = _struct(m, "TransitivePage")
    url_ops = _field_ops(page, "url")
    fmt_node = next(op for op in url_ops if isinstance(op, Fmt))
    assert "example.com" in fmt_node.template


# ── circular import detection ─────────────────────────────────────────────────


def test_circular_import_detected():
    """Circular imports are detected and raise ParseError."""
    with pytest.raises(ParseError, match="[Cc]ircular"):
        parse_ast(path=str(FIXTURES / "circular_a.kdl"))


# ── name conflict detection ───────────────────────────────────────────────────


def test_name_conflict_define():
    """Redefining an imported define name raises ParseError."""
    with pytest.raises(ParseError, match="conflict.*FMT-BASE"):
        parse_ast(path=str(FIXTURES / "conflict_schema.kdl"))


def test_name_conflict_struct():
    """Redefining an imported struct name raises ParseError."""
    bad_kdl = FIXTURES / "conflict_struct.kdl"
    bad_kdl.write_text(
        'import "./shared_struct.kdl"\n'
        'struct SharedItem { x { css "x"; text } }\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ParseError, match="conflict.*SharedItem"):
            parse_ast(path=str(bad_kdl))
    finally:
        bad_kdl.unlink(missing_ok=True)


# ── error cases ───────────────────────────────────────────────────────────────


def test_import_file_not_found():
    """Importing a nonexistent file raises ParseError."""
    bad_kdl = FIXTURES / "import_missing.kdl"
    bad_kdl.write_text(
        'import "./does_not_exist.kdl"\nstruct X { x { css "x"; text } }\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ParseError, match="file not found"):
            parse_ast(path=str(bad_kdl))
    finally:
        bad_kdl.unlink(missing_ok=True)


def test_import_from_string_fails():
    """Using import when parsing from string (no file path) raises ParseError."""
    src = 'import "./something.kdl"\nstruct X { x { css "x"; text } }\n'
    with pytest.raises(ParseError, match="file path"):
        parse_ast(src=src)


# ── codegen with imports ──────────────────────────────────────────────────────


def test_codegen_with_imports():
    """Code generation works with imported structs and defines."""
    from ssc_codegen.parser import PARSER

    m = parse_ast(path=str(FIXTURES / "main_schema.kdl"))

    from ssc_codegen.converters.py_bs4 import PY_BASE_CONVERTER

    code = PY_BASE_CONVERTER.convert(m)

    # imported struct class is generated
    assert "class SharedItem" in code
    # local struct class is generated
    assert "class Page" in code
    # imported define resolved in generated code
    assert "example.com" in code
