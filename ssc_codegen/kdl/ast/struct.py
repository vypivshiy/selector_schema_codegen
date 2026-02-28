from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType, StructType


@dataclass
class Struct(Node):
    """
    Parser schema definition.
    DSL: struct Name type=item|list|dict|table|flat { ... }

    body order:
      StructDocstring? → PreValidate? → Init? → SplitDoc?
      → Key? → Value? → TableConfig? → TableRow? → TableMatchKey?
      → Field...
    """
    name:        str        = ""
    struct_type: StructType = StructType.ITEM

    def __post_init__(self):
        self.body.extend(
            [
                StructDocstring(parent=self),
                Init(parent=self),
            ]
        )

    @property
    def docstring(self) -> StructDocstring:
        return self.body[0]  # type: ignore
    

    @property
    def init(self) -> Init:
        return self.body[1]  # type: ignore


@dataclass
class StructDocstring(Node):
    """DSL: -doc "text" """
    value: str = ""


@dataclass
class PreValidate(Node):
    """
    Validates the document before parsing begins.
    Raises error on failure (caught by fallback if present).
    DSL: -pre-validate { ... }
    accept: DOCUMENT, ret: DOCUMENT (pass-through)
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class Init(Node):
    """
    Pre-computed named values cached before field parsing.
    Execution order: after PreValidate, before SplitDoc and Fields.
    DSL: -init { name { pipeline... } ... }
    body: list[InitField]
    """
    pass


@dataclass
class InitField(Node):
    """
    Single named cached pipeline inside -init.
    Referenced in Fields via Self(name=...).
    ret is resolved after pipeline is built.

    Separate node from Field — semantics differ:
    InitField is cached and reachable via Self; Field produces output.
    """
    name:   str          = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.AUTO)


@dataclass
class SplitDoc(Node):
    """
    Splits document into items for list-type structs.
    DSL: -split-doc { ... }
    accept: DOCUMENT, ret: LIST_DOCUMENT
    Only valid in struct type=list.
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class Key(Node):
    """
    Key extraction pipeline for dict-type structs.
    DSL: -key { ... }
    accept: DOCUMENT, ret: STRING
    Only valid in struct type=dict.
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.STRING)


@dataclass
class Value(Node):
    """
    Value extraction pipeline for dict/table-type structs.
    DSL: -value { ... }
    dict:  ret can be any type.
    table: ret must be STRING.
    Only valid in struct type=dict or type=table.
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.AUTO)


@dataclass
class TableConfig(Node):
    """
    Selects the table element.
    DSL: -table { ... }
    accept: DOCUMENT, ret: DOCUMENT
    Only valid in struct type=table.
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class TableRow(Node):
    """
    Selects table rows.
    DSL: -row { ... }
    accept: DOCUMENT, ret: LIST_DOCUMENT
    Only valid in struct type=table.
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class TableMatchKey(Node):
    """
    Extracts key cell text from a row for match comparison.
    DSL: -match { ... }
    accept: DOCUMENT (row), ret: STRING
    Only valid in struct type=table.
    """
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.STRING)


@dataclass
class Field(Node):
    """
    Regular output field.
    DSL: field-name { pipeline... }
    ret is resolved after pipeline is built.
    """
    name:   str          = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret:    VariableType = field(default=VariableType.AUTO)
