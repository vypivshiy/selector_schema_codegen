"""Target profile definitions and capability descriptors.

This module defines `TargetProfile`, which contains the fully validated configuration,
feature capabilities, output file constraints, and visitor converter factory for a
chosen codegen backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TargetProfile:
    """Fully validated target profile containing capabilities and converter factory.

    Instances of this class are constructed by `resolve()` from a `TargetSpec`
    and provide metadata needed for file layout and converter instantiation.

    Attributes:
        language: Canonical target language name (`"python"`, `"javascript"`, `"go"`, or `"rust"`).
        file_extension: File extension for generated source files (e.g. `".py"`, `".js"`, `".go"`).
        create_converter: Zero-argument factory callable returning an initialized
            visitor/converter instance capable of traversing `Module` ASTs.
        http_clients: Tuple of valid HTTP client strategy names supported by this target.
        supports_separate_runtime: Whether this backend supports separating helper
            definitions into a standalone runtime module.
        runtime_include_fallback: Internal flag indicating whether the runtime helper
            bundle requires fallback try/except utilities for this configuration (e.g. lxml).

    Examples:
        ```python
        from ssc_codegen.targets.profile import TargetProfile
        from ssc_codegen.targets.resolver import resolve
        from ssc_codegen.targets.spec import TargetSpec

        spec = TargetSpec(lang="python", lib="parsel")
        profile: TargetProfile = resolve(spec)

        print(profile.language)  # "python"
        print(profile.file_extension)  # ".py"
        converter = profile.create_converter()
        ```
    """

    language: str
    file_extension: str
    create_converter: Callable[[], Any]
    http_clients: tuple[str, ...] = ()
    supports_separate_runtime: bool = False
    runtime_include_fallback: bool = False
