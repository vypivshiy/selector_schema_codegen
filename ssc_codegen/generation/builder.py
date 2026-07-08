from __future__ import annotations


class ModuleBuilder:
    """Language-agnostic accumulator for imports and std-helper definitions.

    Replaces the hidden signal pools (``_std_defs``, ``_main_imports``,
    ``_std_imports``) that lived inside the old ``Visitor``.

    Stores raw data only — no rendering. Target-specific code is responsible
    for deciding how imports and helpers are formatted in the output language.

    Registration is idempotent: first emission for a name/line wins.
    """

    def __init__(self) -> None:
        self._imports: dict[str, None] = {}
        self._std_defs: dict[str, tuple[list[str], str]] = {}
        self._std_imports: dict[str, None] = {}

    # === registration (idempotent) ===

    def require_import(self, line: str) -> None:
        """Register an import line (deduped, order-preserving).

        The line is stored as-is — target-specific code decides the syntax.
        """
        self._imports.setdefault(line, None)

    def require_std(
        self,
        name: str,
        *,
        code: str,
        imports: list[str] | None = None,
    ) -> None:
        """Register a std helper definition (idempotent by ``name``).

        ``code`` is the helper source in the target language.
        ``imports`` are associated with this helper (deduped into the std pool).
        """
        imps = list(imports) if imports else []
        self._std_defs.setdefault(name, (imps, code))
        for imp in imps:
            self._std_imports.setdefault(imp, None)

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._imports.clear()
        self._std_defs.clear()
        self._std_imports.clear()

    # === queries ===

    @property
    def imports(self) -> list[str]:
        return list(self._imports)

    @property
    def std_names(self) -> list[str]:
        return list(self._std_defs)

    @property
    def std_defs(self) -> dict[str, tuple[list[str], str]]:
        return dict(self._std_defs)

    @property
    def std_imports(self) -> list[str]:
        return list(self._std_imports)

    @property
    def has_std(self) -> bool:
        return bool(self._std_defs)
