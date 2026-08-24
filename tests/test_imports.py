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


# ── explicit imports ──────────────────────────────────────────────────────────


def test_selective_import_includes_named():
    """Every import names its symbols and their declaration kinds."""
    m, _ = _parse_file(FIXTURES / "selective_schema.kdl")
    page = _struct(m, "SelectivePage")

    url_ops = _field_ops(page, "url")
    fmt_node = next(op for op in url_ops if isinstance(op, Fmt))
    assert "example.com" in fmt_node.template


# ── transitive import ────────────────────────────────────────────────────────


def test_transitive_import():
    """Private dependencies remain available to imported declarations."""
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


def test_diamond_import_is_loaded_once(tmp_path):
    common = tmp_path / "common.kdl"
    common.write_text(
        'struct Common { title { css "h1"; text } }\n', encoding="utf-8"
    )
    for name in ("left", "right"):
        (tmp_path / f"{name}.kdl").write_text(
            'import "./common.kdl" { (struct)Common }\n'
            f"struct {name.title()} {{ child {{ nested Common }} }}\n",
            encoding="utf-8",
        )
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./left.kdl" { (struct)Left }\n'
        'import "./right.kdl" { (struct)Right }\n'
        "struct Root { left { nested Left } right { nested Right } }\n",
        encoding="utf-8",
    )

    module, diagnostics = _parse_file(root)

    assert not _error_messages(diagnostics)
    assert [s.name for s in _structs(module)].count("Common") == 1


def test_imported_document_is_structurally_linted(tmp_path):
    imported = tmp_path / "invalid.kdl"
    imported.write_text("unknown-node\n", encoding="utf-8")
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./invalid.kdl" { (struct)Missing }\n', encoding="utf-8"
    )

    _, diagnostics = _parse_file(root)

    error = next(d for d in diagnostics if "Unknown node" in d.message)
    assert error.path == str(imported.resolve())


def test_imported_document_syntax_error_reports_imported_path(tmp_path):
    imported = tmp_path / "invalid.kdl"
    imported.write_text("struct Broken {", encoding="utf-8")
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./invalid.kdl" { (struct)Broken }\n', encoding="utf-8"
    )

    _, diagnostics = _parse_file(root)

    error = next(d for d in diagnostics if "parse error" in d.message)
    assert error.path == str(imported.resolve())


# ── error cases ───────────────────────────────────────────────────────────────


def test_import_file_not_found():
    """Importing a nonexistent file is reported as a diagnostic."""
    bad_kdl = FIXTURES / "import_missing.kdl"
    bad_kdl.write_text(
        'import "./does_not_exist.kdl" { (struct)Missing }\n'
        'struct X { x { css "x"; text } }\n',
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
    src = (
        'import "./something.kdl" { (struct)Missing }\n'
        'struct X { x { css "x"; text } }\n'
    )
    _, diagnostics = parse_module(src)
    msgs = _error_messages(diagnostics)
    assert any("file path" in m.lower() for m in msgs)


def test_import_requires_explicit_typed_symbols(tmp_path):
    shared = tmp_path / "shared.kdl"
    shared.write_text('struct Shared { x { css "x"; text } }\n')
    root = tmp_path / "root.kdl"
    root.write_text('import "./shared.kdl"\n')

    _, diagnostics = _parse_file(root)

    assert any(
        "explicit non-empty symbol block" in m
        for m in _error_messages(diagnostics)
    )


def test_import_wrong_kind_suggests_declared_kind(tmp_path):
    shared = tmp_path / "shared.kdl"
    shared.write_text("json Shared { value str }\n")
    root = tmp_path / "root.kdl"
    root.write_text('import "./shared.kdl" { (struct)Shared }\n')

    _, diagnostics = _parse_file(root)

    error = next(d for d in diagnostics if "is not declared" in d.message)
    assert error.hint == "use (json)Shared"


def test_import_adds_local_dependency_closure(tmp_path):
    shared = tmp_path / "shared.kdl"
    shared.write_text(
        'struct Helper { x { css "x"; text } }\n'
        "struct Public { helper { nested Helper } }\n"
    )
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./shared.kdl" { (struct)Public }\n'
        "struct Root { value { nested Public } }\n"
    )

    module, diagnostics = _parse_file(root)

    assert not _error_messages(diagnostics)
    assert [struct.name for struct in _structs(module)] == [
        "Helper",
        "Public",
        "Root",
    ]


def test_private_dependency_is_not_reexported(tmp_path):
    common = tmp_path / "common.kdl"
    common.write_text('struct Common { x { css "x"; text } }\n')
    shared = tmp_path / "shared.kdl"
    shared.write_text(
        'import "./common.kdl" { (struct)Common }\n'
        "struct Public { common { nested Common } }\n"
    )
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./shared.kdl" { (struct)Public }\n'
        "struct Root { hidden { nested Common } value { nested Public } }\n"
    )

    _, diagnostics = _parse_file(root)

    assert any(
        "not visible" in message for message in _error_messages(diagnostics)
    )


def test_unselected_scalar_define_is_not_added_to_scope(tmp_path):
    shared = tmp_path / "shared.kdl"
    shared.write_text('define A="selected" B="private"\n', encoding="utf-8")
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./shared.kdl" { (define)A }\n'
        'struct Root { value { css "a"; text; fmt B } }\n',
        encoding="utf-8",
    )

    module, diagnostics = _parse_file(root)

    assert not _error_messages(diagnostics)
    operation = next(
        node
        for node in _field_ops(_struct(module, "Root"), "value")
        if isinstance(node, Fmt)
    )
    assert operation.template == "B"


def test_private_block_define_is_not_reexported(tmp_path):
    shared = tmp_path / "shared.kdl"
    shared.write_text(
        'define PIPE { css ".x"; text }\nstruct Public { value { PIPE } }\n',
        encoding="utf-8",
    )
    root = tmp_path / "root.kdl"
    root.write_text(
        'import "./shared.kdl" { (struct)Public }\n'
        "struct Root { hidden { PIPE } value { nested Public } }\n",
        encoding="utf-8",
    )

    _, diagnostics = _parse_file(root)

    assert any(
        "define 'PIPE' which is not visible" in message
        for message in _error_messages(diagnostics)
    )


# ── codegen with imports ──────────────────────────────────────────────────────


def test_codegen_with_imports():
    """Code generation works with imported structs and defines."""
    m, _ = _parse_file(FIXTURES / "main_schema.kdl")

    from ssc_codegen.targets.python import PY_BS4_CONVERTER as PY_BASE_CONVERTER

    code = PY_BASE_CONVERTER.convert(m)

    # imported struct class is generated
    assert "class SharedItem" in code
    # local struct class is generated
    assert "class Page" in code
    # imported define resolved in generated code
    assert "example.com" in code
