from __future__ import annotations

import pytest

from ssc_codegen.symbols import (
    SymbolFinding,
    SymbolKind,
    SymbolRecord,
    SymbolScope,
    normalize_targets,
    target_symbol_plan,
)


def test_plan_accepts_normalized_records_and_preserves_metadata():
    records = (
        SymbolRecord(SymbolKind.STRUCT, "Product", "python", "Product", SymbolScope.MODULE, "schema.kdl", (1, 1)),
        SymbolRecord(SymbolKind.TYPE, "Product", "python", "ProductType", SymbolScope.MODULE, "schema.kdl", (1, 1)),
        SymbolRecord(SymbolKind.FIELD, "title", "python", "_parse_title", SymbolScope.STRUCT, "schema.kdl", (2, 1)),
        SymbolRecord(SymbolKind.METHOD, "fetch", "python", "fetch", SymbolScope.REQUEST, "schema.kdl", (3, 1)),
        SymbolRecord(SymbolKind.PLACEHOLDER, "id", "python", "id", SymbolScope.PLACEHOLDER, "schema.kdl", (3, 1)),
        SymbolRecord(SymbolKind.JSON, "ProductData", "python", "ProductDataJson", SymbolScope.MODULE, "schema.kdl", (4, 1)),
        SymbolRecord(SymbolKind.FUNCTION, "normalize", "python", "normalize", SymbolScope.MODULE, "schema.kdl", (5, 1)),
    )

    assert target_symbol_plan(records, ("python",)) == ()
    assert all(record.source == "schema.kdl" for record in records)
    assert all(record.span is not None for record in records)


def test_targets_are_normalized_and_unknown_targets_rejected():
    assert normalize_targets(("py", "js", "go", "py")) == (
        "python",
        "javascript",
        "go",
    )
    with pytest.raises(ValueError, match="Unknown target"):
        normalize_targets(("rust",))


def test_plan_reports_collision_and_invalid_identifier_in_record_order():
    records = (
        SymbolRecord(SymbolKind.FUNCTION, "foo-bar", "python", "foo_bar", SymbolScope.MODULE, "schema.kdl", (1, 1)),
        SymbolRecord(SymbolKind.FUNCTION, "foo_bar", "python", "foo_bar", SymbolScope.MODULE, "schema.kdl", (2, 1)),
        SymbolRecord(SymbolKind.FUNCTION, "class", "python", "class", SymbolScope.MODULE, "schema.kdl", (3, 1)),
    )

    findings = target_symbol_plan(records, ("python",))
    assert [finding.code for finding in findings] == ["E402", "E403"]
    assert findings[0].previous == records[0]
    assert all(isinstance(finding, SymbolFinding) for finding in findings)
