from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass
class ConverterContext:
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

    def advance(self) -> "ConverterContext":
        return replace(self, index=self.index + 1)

    def deeper(self) -> "ConverterContext":
        return replace(self, depth=self.depth + 1)
