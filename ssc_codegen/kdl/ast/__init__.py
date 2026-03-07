"""
AST nodes for the KDL Schema DSL.

Import everything from here:
    from kdl_ast import Module, Field, CssSelect, ...
"""
from .types import VariableType, StructType

from .base import Node

from .module import (
    Module,
    CodeStartHook,
    CodeEndHook,
    Docstring,
    Imports,
    Utilities,
)

from .typedef import TypeDef, TypeDefField

from .jsondef import JsonDef, JsonDefField

from .struct import (
    Struct,
    StructDocstring,
    PreValidate,
    Init,
    InitField,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableRow,
    TableMatchKey,
    Field,
    TableField,
    StartParse
)

from .selectors import (
    CssSelect,
    CssSelectAll,
    XpathSelect,
    XpathSelectAll,
    CssRemove,
    XpathRemove,
)

from .extract import Text, Raw, Attr

from .string import (
    Trim,
    Ltrim,
    Rtrim,
    NormalizeSpace,
    RmPrefix,
    RmSuffix,
    RmPrefixSuffix,
    Fmt,
    Repl,
    ReplMap,
    Lower,
    Upper,
    Split,
    Join,
    Unescape,
)

from .regex import Re, ReAll, ReSub

from .array import Index, Slice, Len, Unique

from .cast import ToInt, ToFloat, ToBool, Jsonify, Nested

from .control import Self, Fallback, FallbackStart, FallbackEnd, Return

from .predicate_containers import Filter, Assert, Match

from .predicate_ops import (
    PredEq,
    PredNe,
    PredGt,
    PredLt,
    PredGe,
    PredLe,
    PredRange,
    PredStarts,
    PredEnds,
    PredContains,
    PredIn,
    PredRe,
    PredReAny,
    PredReAll,
    PredCss,
    PredXpath,
    PredHasAttr,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredAttrContains,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    LogicNot,
    LogicAnd,
    LogicOr,
)

from .transform import TransformDef, TransformTarget, TransformCall

__all__ = [
    # types
    "VariableType", "StructType",
    # base
    "Node",
    # module
    "Module", "CodeStartHook", "CodeEndHook",
    "Docstring", "Imports", "Utilities",
    # typedef
    "TypeDef", "TypeDefField",
    # jsondef
    "JsonDef", "JsonDefField",
    # struct
    "Struct", "StructDocstring", "PreValidate",
    "Init", "InitField", "SplitDoc",
    "Key", "Value",
    "TableConfig", "TableRow", "TableMatchKey",
    "Field", "StartParse",
    # selectors
    "CssSelect", "CssSelectAll",
    "XpathSelect", "XpathSelectAll",
    "CssRemove", "XpathRemove",
    # extract
    "Text", "Raw", "Attr",
    # string
    "Trim", "Ltrim", "Rtrim", "NormalizeSpace",
    "RmPrefix", "RmSuffix", "RmPrefixSuffix",
    "Fmt", "Repl", "ReplMap",
    "Lower", "Upper", "Split", "Join", "Unescape",
    # regex
    "Re", "ReAll", "ReSub",
    # array
    "Index", "Slice", "Len", "Unique",
    # cast
    "ToInt", "ToFloat", "ToBool", "Jsonify", "Nested",
    # control
    "Self", "Fallback", "FallbackStart", "FallbackEnd", "Return",
    # predicate containers
    "Filter", "Assert", "Match",
    # predicate ops
    "PredEq", "PredNe",
    "PredGt", "PredLt", "PredGe", "PredLe", "PredRange",
    "PredStarts", "PredEnds", "PredContains", "PredIn",
    "PredRe", "PredReAny", "PredReAll",
    "PredCss", "PredXpath", "PredHasAttr",
    "PredAttrEq", "PredAttrNe",
    "PredAttrStarts", "PredAttrEnds", "PredAttrContains", "PredAttrRe",
    "PredTextStarts", "PredTextEnds", "PredTextContains", "PredTextRe",
    "PredCountEq", "PredCountGt", "PredCountLt",
    "LogicNot", "LogicAnd", "LogicOr",
    # transform
    "TransformDef", "TransformTarget", "TransformCall",
]
