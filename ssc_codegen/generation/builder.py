"""Language-agnostic accumulator for imports and helper definitions."""

from __future__ import annotations


class ModuleBuilder:
    """Language-agnostic accumulator for imports and helper definitions.

    Collects required top-level import lines, standard library helper functions,
    and user-defined runtime extension helpers during AST traversal passes.

    Stores raw data only without target-specific rendering. Concrete visitors
    query `ModuleBuilder` during code emission to format headers, imports,
    and runtime utility blocks in the target syntax.

    Registration operations are idempotent (first registered definition wins,
    preserving definition order and deduplicating identical imports).

    Attributes:
        imports: Ordered list of unique top-level import lines registered so far.
        std_names: Names of standard helper definitions registered.
        std_defs: Mapping from helper names to tuples of ``(imports, code_body)``.
        std_imports: Deduplicated list of imports associated with std helpers.
        has_std: `True` if any std helpers have been registered.
        runtime_names: Names of custom runtime helpers registered.
        runtime_defs: Mapping from runtime helper names to ``(imports, code_body)``.
        runtime_imports: Deduplicated list of imports associated with runtime helpers.
        has_runtime: `True` if any custom runtime helpers have been registered.

    Examples:
        >>> builder = ModuleBuilder()
        >>> builder.require_import("import re")
        >>> builder.require_std("std_assert", code="def std_assert(c): pass", imports=["import sys"])
        >>> builder.imports
        ['import re']
        >>> builder.has_std
        True
    """

    def __init__(self) -> None:
        """Initialize an empty `ModuleBuilder` with clear storage dictionaries."""
        self._imports: dict[str, None] = {}
        self._std_defs: dict[str, tuple[list[str], str]] = {}
        self._std_imports: dict[str, None] = {}
        self._runtime_defs: dict[str, tuple[list[str], str]] = {}
        self._runtime_imports: dict[str, None] = {}

    # === registration (idempotent) ===

    def require_import(self, line: str) -> None:
        """Register a top-level import line.

        Deduplicated and order-preserving. The line string is stored as-is.

        Args:
            line: The verbatim import statement line for the target language.
        """
        self._imports.setdefault(line, None)

    def require_std(
        self,
        name: str,
        *,
        code: str,
        imports: list[str] | None = None,
    ) -> None:
        """Register a standard library helper definition.

        Idempotent by helper `name` (the first registration wins). Associated
        import lines are automatically deduplicated into the std import pool.

        Args:
            name: Unique identifier of the helper function.
            code: Full source code text of the helper in the target language.
            imports: Optional list of import lines required by this helper.
        """
        imps = list(imports) if imports else []
        self._std_defs.setdefault(name, (imps, code))
        for imp in imps:
            self._std_imports.setdefault(imp, None)

    def require_runtime(
        self,
        name: str,
        *,
        code: str,
        imports: list[str] | None = None,
    ) -> None:
        """Register a user or extension helper for runtime emission.

        Args:
            name: Unique identifier of the runtime helper function.
            code: Full source code text of the helper.
            imports: Optional list of import lines required by this helper.

        Raises:
            ValueError: If a helper with the same name is already registered
                with conflicting code or imports.
        """
        imps = list(imports) if imports else []
        existing = self._runtime_defs.get(name)
        definition = (imps, code)
        if existing is not None and existing != definition:
            raise ValueError(f"conflicting runtime helper definition: {name}")
        self._runtime_defs.setdefault(name, definition)
        for imp in imps:
            self._runtime_imports.setdefault(imp, None)

    def reset(self) -> None:
        """Clear all accumulated imports and helper definitions."""
        self._imports.clear()
        self._std_defs.clear()
        self._std_imports.clear()
        self._runtime_defs.clear()
        self._runtime_imports.clear()

    # === queries ===

    @property
    def imports(self) -> list[str]:
        """Ordered list of registered top-level import statements."""
        return list(self._imports)

    @property
    def std_names(self) -> list[str]:
        """List of names of all registered std helper definitions."""
        return list(self._std_defs)

    @property
    def std_defs(self) -> dict[str, tuple[list[str], str]]:
        """Dictionary of registered std helpers mapping `name` to `(imports, code)`."""
        return dict(self._std_defs)

    @property
    def std_imports(self) -> list[str]:
        """Deduplicated list of import lines required by all registered std helpers."""
        return list(self._std_imports)

    @property
    def has_std(self) -> bool:
        """`True` if at least one std helper has been registered, `False` otherwise."""
        return bool(self._std_defs)

    @property
    def runtime_names(self) -> list[str]:
        """List of names of all registered custom runtime helper definitions."""
        return list(self._runtime_defs)

    @property
    def runtime_defs(self) -> dict[str, tuple[list[str], str]]:
        """Dictionary of registered runtime helpers mapping `name` to `(imports, code)`."""
        return dict(self._runtime_defs)

    @property
    def runtime_imports(self) -> list[str]:
        """Deduplicated list of import lines required by custom runtime helpers."""
        return list(self._runtime_imports)

    @property
    def has_runtime(self) -> bool:
        """`True` if at least one custom runtime helper has been registered."""
        return bool(self._runtime_defs)
