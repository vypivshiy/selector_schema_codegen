"""AST nodes for KDL-based schema codegen."""

# Base
from .base import BaseAstNode

# Types (TypedDict kwargs)
from .types import (
    KwargsSelect,
    KwargsExtract,
    KwargsStringOp,
    KwargsRegex,
    KwargsCast,
    KwargsFilterCompare,
    KwargsFilterString,
    KwargsFilterDef,
    KwargsStruct,
    KwargsField,
    KwargsTable,
    KwargsTableMatchKey,
    KwargsTableMatchValue,
    KwargsTableMatch,
    KwargsAssert,
    KwargsDefault,
    KwargsJsonDef,
    KwargsJsonDefField,
)

# Module nodes
from .module import Module, Define, Docstring, Imports, Utilities

# Struct nodes
from .struct import (
    Struct,
    StructField,
    StructSplit,
    StructPreValidate,
    StructParse,
    StructInit,
    StructNested,
)

# Table nodes
from .table import (
    TableConfig,
    TableRow,
    TableMatchKey,
    TableMatchValue,
    TableMatch,
)

# TypeDef nodes
from .typedef import TypeDef, TypeDefField

# JSON definition nodes (top-level mapping)
from .json import JsonDef, JsonDefField, JsonStruct, JsonField

# Selector nodes
from .selectors import Select, Remove

# Extract nodes
from .extract import Extract

# String nodes
from .string import StringOp, Format, Replace, ReplaceMap, Join, Unescape

# Regex nodes
from .regex import Regex

# Array nodes
from .array import Index, Len, Unique

# Cast nodes
from .cast import Cast, Jsonify, JsonifyDynamic, Nested

# Filter nodes (string pipeline)
from .filter import FilterDef, Filter, FilterCmp, FilterStr, FilterRe, FilterLen

# Filter nodes (document pipeline)
from .filter_doc import (
    FilterDoc,
    FilterDocSelect,
    FilterDocAttr,
    FilterDocText,
    FilterDocRaw,
    FilterDocHasAttr,
)

# Logic nodes
from .logic import LogicAnd, LogicOr, LogicNot

# Validate nodes
from .validate import (
    Assert,
    AssertCmp,
    AssertRe,
    AssertSelect,
    AssertHasAttr,
    AssertContains,
)

# Transform nodes
from .transform import Transform, TransformImports

# Control nodes
from .control import Default, DefaultStart, DefaultEnd, Return


__all__ = [
    # Base
    "BaseAstNode",

    # Types
    "KwargsSelect",
    "KwargsExtract",
    "KwargsStringOp",
    "KwargsRegex",
    "KwargsCast",
    "KwargsFilterCompare",
    "KwargsFilterString",
    "KwargsFilterDef",
    "KwargsStruct",
    "KwargsField",
    "KwargsTable",
    "KwargsTableMatchKey",
    "KwargsTableMatchValue",
    "KwargsTableMatch",
    "KwargsAssert",
    "KwargsDefault",
    "KwargsJsonDef",
    "KwargsJsonDefField",

    # Module
    "Module",
    "Define",
    "Docstring",
    "Imports",
    "Utilities",

    # Struct
    "Struct",
    "StructField",
    "StructSplit",
    "StructPreValidate",
    "StructParse",
    "StructInit",
    "StructNested",

    # Table
    "TableConfig",
    "TableRow",
    "TableMatchKey",
    "TableMatchValue",
    "TableMatch",

    # TypeDef
    "TypeDef",
    "TypeDefField",

    # JSON
    "JsonDef",
    "JsonDefField",
    "JsonStruct",
    "JsonField",

    # Selectors
    "Select",
    "Remove",

    # Extract
    "Extract",

    # String
    "StringOp",
    "Format",
    "Replace",
    "ReplaceMap",
    "Join",
    "Unescape",

    # Regex
    "Regex",

    # Array
    "Index",
    "Len",
    "Unique",

    # Cast
    "Cast",
    "Jsonify",
    "JsonifyDynamic",
    "Nested",

    # Filter (string)
    "FilterDef",
    "Filter",
    "FilterCmp",
    "FilterStr",
    "FilterRe",
    "FilterLen",

    # Filter (document)
    "FilterDoc",
    "FilterDocSelect",
    "FilterDocAttr",
    "FilterDocText",
    "FilterDocRaw",
    "FilterDocHasAttr",

    # Logic
    "LogicAnd",
    "LogicOr",
    "LogicNot",

    # Validate
    "Assert",
    "AssertCmp",
    "AssertRe",
    "AssertSelect",
    "AssertHasAttr",
    "AssertContains",

    # Transform
    "Transform",
    "TransformImports",

    # Control
    "Default",
    "DefaultStart",
    "DefaultEnd",
    "Return",
]