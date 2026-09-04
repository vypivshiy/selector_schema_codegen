"""Immutable traversal context for AST code generators."""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass
class WalkContext:
    """Immutable traversal context passed through AST walker operations.

    Tracks variable naming (index-based pipeline chaining), indentation
    depth, and build options across traversal passes.

    Attributes:
        index: Current sequential pipeline step index (0, 1, 2, ...).
        depth: Current block indentation nesting level (0, 1, 2, ...).
        var_name: Base variable prefix for pipeline chaining (default: ``"v"``).
        indent_char: Indentation unit string (default: 4 spaces).
        meta: Arbitrary dictionary for passing converter-wide options,
            target settings, or file layout flags.

    Examples:
        >>> ctx = WalkContext()
        >>> ctx.prv
        'v'
        >>> ctx.nxt
        'v1'
        >>> step1 = ctx.advance()
        >>> step1.prv
        'v1'
        >>> step1.nxt
        'v2'
        >>> step1.deeper().indent
        '        '
    """

    index: int = 0
    depth: int = 0
    var_name: str = "v"
    indent_char: str = " " * 4
    meta: dict = field(default_factory=dict)

    @property
    def prv(self) -> str:
        """Name of the input variable for the current pipeline step.

        Returns ``"v"`` when ``index == 0``, and ``"v{index}"`` for subsequent steps.
        """
        return (
            self.var_name if self.index == 0 else f"{self.var_name}{self.index}"
        )

    @property
    def nxt(self) -> str:
        """Name of the output variable for the current pipeline step.

        Always evaluates to ``"v{index + 1}"``.
        """
        return f"{self.var_name}{self.index + 1}"

    @property
    def indent(self) -> str:
        """Full whitespace indentation prefix string for the current `depth`."""
        return self.indent_char * self.depth

    def advance(self) -> WalkContext:
        """Create a new context with incremented variable index (`index + 1`).

        Returns:
            A new `WalkContext` with ``index = self.index + 1``.
        """
        return replace(self, index=self.index + 1)

    def advance_n(self, n: int) -> WalkContext:
        """Create a new context advanced by `n` pipeline steps.

        Args:
            n: Number of pipeline steps to advance.

        Returns:
            A new `WalkContext` with ``index = self.index + n``.
        """
        return replace(self, index=self.index + n)

    def deeper(self) -> WalkContext:
        """Create a new context with incremented nesting depth (`depth + 1`).

        Returns:
            A new `WalkContext` with ``depth = self.depth + 1``.
        """
        return replace(self, depth=self.depth + 1)

    def reset_index(self) -> WalkContext:
        """Create a new context with variable index reset to 0.

        Returns:
            A new `WalkContext` with ``index = 0``, retaining `depth` and `meta`.
        """
        return replace(self, index=0)
