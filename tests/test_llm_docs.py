from __future__ import annotations

import re
from pathlib import Path

import pytest
from kdlquery import Severity
from kdlquery import parse as parse_kdl

from ssc_codegen.core import format_diagnostics, parse_module
from ssc_codegen.core.linter import lint_module
from ssc_codegen.symbols import TARGETS

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_LLM_DOCS = (
    "AGENTS.md",
    "llm_overview.md",
    "docs/llm.txt",
)

REMOVED_LEGACY_PATHS = (
    "CLAUDE.md",
    "llm_types_ast.md",
    "llm_core.md",
    "llm_converters.md",
    "llm_howto.md",
    "docs/maintainers",
)

_KDL_FENCE_RE = re.compile(r"```kdl\r?\n(.*?)```", re.DOTALL)


def _extract_kdl_blocks(doc_path: Path) -> list[str]:
    text = doc_path.read_text(encoding="utf-8")
    return [match.group(1).strip() for match in _KDL_FENCE_RE.finditer(text)]


def _extract_self_contained_kdl_blocks(doc_path: Path) -> list[tuple[int, str]]:
    return [
        (idx, block)
        for idx, block in enumerate(_extract_kdl_blocks(doc_path), start=1)
        if 'import "./' not in block
    ]


@pytest.mark.parametrize("rel_path", REQUIRED_LLM_DOCS)
def test_consolidated_llm_docs_exist(rel_path: str) -> None:
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected documentation file to exist: {rel_path}"
    assert path.read_text(encoding="utf-8").strip(), (
        f"Expected non-empty file: {rel_path}"
    )


@pytest.mark.parametrize("rel_path", REMOVED_LEGACY_PATHS)
def test_legacy_llm_and_maintainer_docs_removed(rel_path: str) -> None:
    path = REPO_ROOT / rel_path
    assert not path.exists(), f"Legacy path should be removed: {rel_path}"


def test_no_dangling_references_to_removed_docs() -> None:
    checked_files = (
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "llm_overview.md",
        REPO_ROOT / "docs" / "llm.txt",
        REPO_ROOT / "mkdocs.yml",
        REPO_ROOT / "docs" / "README.md",
    )
    forbidden_refs = (
        "CLAUDE.md",
        "llm_types_ast.md",
        "llm_core.md",
        "llm_converters.md",
        "llm_howto.md",
        "docs/maintainers",
        "maintainers/",
    )
    for file_path in checked_files:
        content = file_path.read_text(encoding="utf-8")
        for ref in forbidden_refs:
            assert ref not in content, (
                f"{file_path.relative_to(REPO_ROOT)} still references removed path {ref!r}"
            )


def test_llm_txt_all_kdl_blocks_pass_structural_lint() -> None:
    blocks = _extract_kdl_blocks(REPO_ROOT / "docs" / "llm.txt")
    assert len(blocks) >= 6
    for idx, block in enumerate(blocks, start=1):
        doc = parse_kdl(block)
        diagnostics = lint_module(
            doc, f"docs/llm.txt#block-{idx}", source_text=block
        )
        errors = [d for d in diagnostics if d.severity == Severity.ERROR]
        assert not errors, (
            f"Structural lint error in docs/llm.txt block #{idx}:\n"
            f"{format_diagnostics(errors, block, path=f'docs/llm.txt#block-{idx}')}"
        )


@pytest.mark.parametrize(
    ("block_idx", "kdl_src"),
    _extract_self_contained_kdl_blocks(REPO_ROOT / "docs" / "llm.txt"),
)
def test_llm_txt_self_contained_kdl_blocks_pass_parse_module(
    block_idx: int,
    kdl_src: str,
) -> None:
    module, diagnostics = parse_module(kdl_src, targets=TARGETS)
    errors = [d for d in diagnostics if d.severity == Severity.ERROR]
    assert not errors, (
        f"docs/llm.txt KDL block #{block_idx} failed schema validation:\n"
        f"{format_diagnostics(errors, kdl_src, path=f'docs/llm.txt#block-{block_idx}')}"
    )
    assert module.body or module.extensions, (
        f"docs/llm.txt KDL block #{block_idx} produced an empty AST module"
    )
