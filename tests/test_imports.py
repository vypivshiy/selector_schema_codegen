"""Tests for the import statement in the KDL DSL parser."""

from pathlib import Path


from ssc_codegen.ast import (
    StructBase,
    TypeDef,
    Fmt,
    Nested,
)
from ssc_codegen.core import parse_module
from kdlquery import Severity

FIXTURES = Path(__file__).parent / "fixtures" / "imports"


# ── helpers ───────────────────────────────────────────────────────────────────


def _parse_file(path):
    """Parse a KDL file and return (Module, diagnostics)."""
    p = Path(path)
    src = p.read_text(encoding="utf-8-sig")
    return parse_module(src, source_path=p)


def _error_messages(diagnostics):
    return [d.message for d in diagnostics if d.severity == Severity.ERROR]


def _structs(module) -> list[StructBase]:
    return [n for n in module.body if isinstance(n, StructBase)]


def _struct(module, name: str) -> StructBase:
    return next(s for s in _structs(module) if s.name == name)


def _field(struct: StructBase, name: str):
    return next(n for n in struct.body if getattr(n, "name", None) == name)


def _field_ops(struct: StructBase, field_name: str) -> list:
    f = _field(struct, field_name)
    return f.body


# ── basic import ──────────────────────────────────────────────────────────────


def test_import_defines():
    """Imported scalar and block defines are resolved in the importing module."""
    m, _ = _parse_file(FIXTURES / "main_schema.kdl")
    page = _struct(m, "Page")

    # FMT-BASE was imported and used in fmt
    url_ops = _field_ops(page, "url")
    fmt_node = next(op for op in url_ops if isinstance(op, Fmt))
    assert "example.com" in fmt_node.template

    # RE-PRICE was imported and used in re
    price_ops = _field_ops(page, "price")
    from ssc_codegen.ast import Re

    re_node = next(op for op in price_ops if isinstance(op, Re))
    assert r"\d+" in re_node.pattern


def test_import_struct():
    """Imported struct is available for nested references and appears in module body."""
    m, _ = _parse_file(FIXTURES / "main_schema.kdl")
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
    m, _ = _parse_file(FIXTURES / "main_schema.kdl")
    typedefs = [n for n in m.body if isinstance(n, TypeDef)]
    typedef_names = [t.name for t in typedefs]
    assert "SharedItem" in typedef_names


# ── selective import (feature removed — tests deleted) ────────────────────────


def test_selective_import_includes_named():
    """Selective import is no longer implemented; all names are imported."""
    m, _ = _parse_file(FIXTURES / "selective_schema.kdl")
    page = _struct(m, "SelectivePage")

    url_ops = _field_ops(page, "url")
    fmt_node = next(op for op in url_ops if isinstance(op, Fmt))
    assert "example.com" in fmt_node.template


# ── transitive import ────────────────────────────────────────────────────────


def test_transitive_import():
    """A -> B -> C: A sees names from C."""
    m, _ = _parse_file(FIXTURES / "transitive_schema.kdl")
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
    """Circular imports are detected and reported as diagnostics."""
    _, diagnostics = _parse_file(FIXTURES / "circular_a.kdl")
    msgs = _error_messages(diagnostics)
    assert any("ircular" in m for m in msgs)


# ── error cases ───────────────────────────────────────────────────────────────


def test_import_file_not_found():
    """Importing a nonexistent file is reported as a diagnostic."""
    bad_kdl = FIXTURES / "import_missing.kdl"
    bad_kdl.write_text(
        'import "./does_not_exist.kdl"\nstruct X { x { css "x"; text } }\n',
        encoding="utf-8",
    )
    try:
        _, diagnostics = _parse_file(bad_kdl)
        msgs = _error_messages(diagnostics)
        assert any("file not found" in m.lower() for m in msgs)
    finally:
        bad_kdl.unlink(missing_ok=True)


def test_import_from_string_fails():
    """Using import when parsing from string (no file path) is reported as a diagnostic."""
    src = 'import "./something.kdl"\nstruct X { x { css "x"; text } }\n'
    _, diagnostics = parse_module(src)
    msgs = _error_messages(diagnostics)
    assert any("file path" in m.lower() for m in msgs)


# ── codegen with imports ──────────────────────────────────────────────────────


def test_codegen_with_imports():
    """Code generation works with imported structs and defines."""
    m, _ = _parse_file(FIXTURES / "main_schema.kdl")

    from ssc_codegen.converters.py_bs4 import PY_BASE_CONVERTER

    code = PY_BASE_CONVERTER.convert(m)

    # imported struct class is generated
    assert "class SharedItem" in code
    # local struct class is generated
    assert "class Page" in code
    # imported define resolved in generated code
    assert "example.com" in code
