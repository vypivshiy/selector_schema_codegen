"""KDL-based schema code generator for web scraping parsers.

This package provides tools for parsing KDL v2.1 schemas into an intermediate
AST, validating selectors and pipelines, and compiling ASTs into native parser
code for Python (bs4, lxml, parsel, selectolax), JavaScript (DOM API), Go
(goquery + net/http), and Rust (dom_query + serde + reqwest).

Key API symbols:
    parse_module: Parse KDL schema source into a Module AST and diagnostics.
    format_diagnostics: Format diagnostics into text or JSON output.
    resolve: Resolve a TargetSpec into a concrete TargetProfile.
    TargetSpec: User-supplied target backend specification.
    TargetProfile: Validated target backend profile with converter factory.
    ResolutionError: Raised when target resolution or configuration fails.
    ParseError: Raised on DSL syntax or schema parsing errors.
    BuildTimeError: Raised on type mismatches or unresolved references at build time.
    check_struct_health: Verify selector match rates against real HTML.
    HealthResult: Container holding selector health statistics.
    run_scout: Perform HTML context distillation and structural reconnaissance.
    run_discover: Compatibility alias for full-page reconnaissance via `run_scout`.
    ScoutResult: Unified reconnaissance output from `run_scout`.
    DiscoverResult: Alias for `ScoutResult`.
"""

from __future__ import annotations

from ssc_codegen.core.format import format_diagnostics
from ssc_codegen.core.reader import parse_module
from ssc_codegen.exceptions import BuildTimeError, ParseError
from ssc_codegen.explore import (
    DiscoverResult,
    ScoutResult,
    run_discover,
    run_scout,
)
from ssc_codegen.health import HealthResult, check_struct_health
from ssc_codegen.targets.profile import TargetProfile
from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.spec import TargetSpec

__all__ = [
    "BuildTimeError",
    "DiscoverResult",
    "HealthResult",
    "ParseError",
    "ResolutionError",
    "ScoutResult",
    "TargetProfile",
    "TargetSpec",
    "check_struct_health",
    "format_diagnostics",
    "parse_module",
    "resolve",
    "run_discover",
    "run_scout",
]
