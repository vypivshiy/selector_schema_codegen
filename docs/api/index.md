# Public API Facade

The primary programmatic entry point to `ssc_codegen` is `parse_module`, which reads and validates `.kdl` schema files into an intermediate AST `Module`. Combined with `resolve` and `TargetSpec`, the generated AST can be converted to parser code for any supported backend.

All public symbols are re-exported directly from the top-level `ssc_codegen` package namespace:

```python
from ssc_codegen import (
    BuildTimeError,
    DiscoverResult,
    HealthResult,
    ParseError,
    ResolutionError,
    ScoutResult,
    TargetProfile,
    TargetSpec,
    check_struct_health,
    format_diagnostics,
    parse_module,
    resolve,
    run_discover,
    run_scout,
)
```

---

## Parser & AST Loading

::: ssc_codegen.core.reader.parse_module

---

## Target Resolution & Profiles

::: ssc_codegen.targets.spec.TargetSpec

::: ssc_codegen.targets.profile.TargetProfile

::: ssc_codegen.targets.resolver.resolve

::: ssc_codegen.targets.resolver.ResolutionError

---

## Exceptions & Diagnostics

::: ssc_codegen.exceptions.ParseError

::: ssc_codegen.exceptions.BuildTimeError

::: ssc_codegen.core.format.format_diagnostics

---

## Health & Selector Verification

::: ssc_codegen.health.check_struct_health

::: ssc_codegen.health.HealthResult

::: ssc_codegen.health.SelectorCheck

---

## HTML Reconnaissance & Discovery

::: ssc_codegen.explore.run_scout

::: ssc_codegen.explore.ScoutResult

::: ssc_codegen.explore.run_discover

::: ssc_codegen.explore.DiscoverResult
