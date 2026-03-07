from __future__ import annotations
from dataclasses import dataclass, field
from typing import cast

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

    name: str = ""
    struct_type: StructType = StructType.ITEM
    keep_order: bool = False  # stuct_type=StructType.FLAT specific

    def __post_init__(self):
        self.body.extend([StructDocstring(parent=self), Init(parent=self)])

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
    ret: VariableType = field(default=VariableType.DOCUMENT)


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

    name: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class SplitDoc(Node):
    """
    Splits document into items for list-type structs.
    DSL: -split-doc { ... }
    accept: DOCUMENT, ret: LIST_DOCUMENT
    Only valid in struct type=list.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class Key(Node):
    """
    Key extraction pipeline for dict-type structs.
    DSL: -key { ... }
    accept: DOCUMENT, ret: STRING
    Only valid in struct type=dict.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)


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
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class TableConfig(Node):
    """
    Selects the table element.
    DSL: -table { ... }
    accept: DOCUMENT, ret: DOCUMENT
    Only valid in struct type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.DOCUMENT)


@dataclass
class TableRow(Node):
    """
    Selects table rows.
    DSL: -row { ... }
    accept: DOCUMENT, ret: LIST_DOCUMENT
    Only valid in struct type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.LIST_DOCUMENT)


@dataclass
class TableMatchKey(Node):
    """
    Extracts key cell text from a row for match comparison.
    DSL: -match { ... }
    accept: DOCUMENT (row), ret: STRING
    Only valid in struct type=table.
    """

    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.STRING)


@dataclass
class Field(Node):
    """
    Regular output field.
    DSL: field-name { pipeline... }
    ret is resolved after pipeline is built.
    """

    name: str = ""
    accept: VariableType = field(default=VariableType.DOCUMENT)
    ret: VariableType = field(default=VariableType.AUTO)


@dataclass
class StartParse(Node):
    """Endpoint where need run parser"""

    @property
    def struct(self) -> "Struct":
        return cast(Struct, self.parent)

    @property
    def struct_type(self) -> StructType:
        return self.struct.struct_type

    @property
    def use_split_doc(self) -> bool:
        return any(isinstance(f, SplitDoc) for f in self.struct.body)

    @property
    def use_pre_validate(self) -> bool:
        return any(isinstance(f, PreValidate) for f in self.struct.body)

    @property
    def fields(self) -> list["Field"]:
        return [f for f in self.struct.body if isinstance(f, Field)]

    @property
    def fields_dict(self) -> tuple[Key, Value]:
        """specific fields for struct_type=StructType.DICT"""
        if self.struct_type != StructType.DICT:
            raise TypeError(
                "fields_dict allowed if struct_type == StructType.DICT"
            )
        fields = [f for f in self.struct.body if isinstance(f, (Key, Value))]
        key = [f for f in fields if isinstance(f, Key)][0]
        value = [f for f in fields if isinstance(f, Value)][0]
        return key, value

    @property
    def fields_table(self) -> tuple[TableConfig, TableRow, TableMatchKey]:
        """specific fields for struct_type=StructType.TABLE"""
        if self.struct_type != StructType.TABLE:
            raise TypeError(
                "fields_table allowed if struct_type == StructType.TABLE"
            )
        fields = [
            f
            for f in self.struct.body
            if isinstance(f, (TableConfig, TableRow, TableMatchKey))
        ]
        cfg = [f for f in fields if isinstance(f, TableConfig)][0]
        row = [f for f in fields if isinstance(f, TableRow)][0]
        match_key = [f for f in fields if isinstance(f, TableMatchKey)][0]
        return cfg, row, match_key
