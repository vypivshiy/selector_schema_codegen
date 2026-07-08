from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass
class WalkContext:
    """Immutable traversal context passed through every ``walk_*`` call.

    Tracks variable naming (index-based), indentation depth, and build options.

    - ``prv`` / ``nxt`` compute variable names from ``index``.
    - ``advance()`` returns a new context with index+1 (pipeline step).
    - ``deeper()`` returns a new context with depth+1 (nesting level).
    """

    index: int = 0
    depth: int = 0
    var_name: str = "v"
    indent_char: str = " " * 4
    meta: dict = field(default_factory=dict)

    @property
    def prv(self) -> str:
        return (
            self.var_name if self.index == 0 else f"{self.var_name}{self.index}"
        )

    @property
    def nxt(self) -> str:
        return f"{self.var_name}{self.index + 1}"

    @property
    def indent(self) -> str:
        return self.indent_char * self.depth

    def advance(self) -> WalkContext:
        return replace(self, index=self.index + 1)

    def advance_n(self, n: int) -> WalkContext:
        return replace(self, index=self.index + n)

    def deeper(self) -> WalkContext:
        return replace(self, depth=self.depth + 1)

    def reset_index(self) -> WalkContext:
        return replace(self, index=0)
