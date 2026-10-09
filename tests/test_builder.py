from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.targets.python.http_libs.httpx import HTTPX_FALLBACK_IMPORT


def test_builder_require_import_deduplicates_single_line() -> None:
    builder = ModuleBuilder()
    builder.require_import("import sys")
    builder.require_import("import sys")
    assert builder.imports == ["import sys"]


def test_builder_require_import_preserves_single_line_indentation() -> None:
    builder = ModuleBuilder()
    builder.require_import("    from typing import NotRequired")
    assert builder.imports == ["    from typing import NotRequired"]


def test_builder_require_import_handles_multiline_and_deduplicates() -> None:
    builder = ModuleBuilder()
    indented_block = """
        try:
            import httpx2 as httpx  # type: ignore[import-not-found]
        except ImportError:
            import httpx
    """
    builder.require_import(indented_block)
    assert builder.imports == [HTTPX_FALLBACK_IMPORT]

    # Duplicate call with identical content or already cleaned block
    builder.require_import(HTTPX_FALLBACK_IMPORT)
    assert len(builder.imports) == 1
    assert builder.imports == [HTTPX_FALLBACK_IMPORT]
