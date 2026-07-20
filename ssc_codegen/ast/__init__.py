# mypy: ignore-errors
"""
AST nodes for the KDL Schema DSL.

Import everything from here:
    from kdl_ast import Module, Field, CssSelect, ...
"""

from .types import VariableType, StructType, TypeInfo, VT

from kdlquery.parser import Span

from .base import Node

from .module import (
    Module,
    CodeStartHook,
    CodeEndHook,
    Docstring,
    Utilities,
)

from .typedef import TypeDef, TypeDefField

from .jsondef import JsonDef, JsonDefField

from .rest import (
    ResultVariantDef,
    ResultAliasDef,
    MatcherEntry,
    MatcherListDef,
)

from .struct import (
    StructBase,
    Struct,
    StructRest,
    StructDocstring,
    PreValidate,
    CheckMethod,
    Init,
    InitFieldCall,
    InitField,
    SplitDoc,
    Key,
    Value,
    TableConfig,
    TableRows,
    TableMatchKey,
    RequestHttp,
    MethodBase,
    MethodFetch,
    MethodRest,
    ErrorResponse,
    PlaceholderSpec,
    PlaceholderTemplate,
    Field,
    StartParse,
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

from .control import Self, Fallback, Return

from .predicate_containers import Filter, Assert, Match

from .predicate_ops import (
    PredEq,
    PredNe,
    PredStarts,
    PredEnds,
    PredContains,
    PredRe,
    PredReAny,
    PredReAll,
    PredCss,
    PredXpath,
    PredHasAttr,
    PredCountEq,
    PredCountGt,
    PredCountLt,
    PredCountNe,
    PredCountGe,
    PredCountLe,
    PredCountRange,
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

__all__ = [
    # types
    "VariableType",
    "StructType",
    "TypeInfo",
    "VT",
    # source location
    "Span",
    # base
    "Node",
    # module
    "Module",
    "CodeStartHook",
    "CodeEndHook",
    "Docstring",
    "Utilities",
    # typedef
    "TypeDef",
    "TypeDefField",
    # jsondef
    "JsonDef",
    "JsonDefField",
    # struct
    "StructBase",
    "Struct",
    "StructRest",
    "StructDocstring",
    "PreValidate",
    "CheckMethod",
    "Init",
    "InitFieldCall",
    "InitField",
    "SplitDoc",
    "Key",
    "Value",
    "TableConfig",
    "TableRows",
    "TableMatchKey",
    "RequestHttp",
    "MethodBase",
    "MethodFetch",
    "MethodRest",
    "ErrorResponse",
    "PlaceholderSpec",
    "PlaceholderTemplate",
    "Field",
    "StartParse",
    # REST result artifacts (synthesized)
    "ResultVariantDef",
    "ResultAliasDef",
    "MatcherEntry",
    "MatcherListDef",
    # selectors
    "CssSelect",
    "CssSelectAll",
    "XpathSelect",
    "XpathSelectAll",
    "CssRemove",
    "XpathRemove",
    # extract
    "Text",
    "Raw",
    "Attr",
    # string
    "Trim",
    "Ltrim",
    "Rtrim",
    "NormalizeSpace",
    "RmPrefix",
    "RmSuffix",
    "RmPrefixSuffix",
    "Fmt",
    "Repl",
    "ReplMap",
    "Lower",
    "Upper",
    "Split",
    "Join",
    "Unescape",
    # regex
    "Re",
    "ReAll",
    "ReSub",
    # array
    "Index",
    "Slice",
    "Len",
    "Unique",
    # cast
    "ToInt",
    "ToFloat",
    "ToBool",
    "Jsonify",
    "Nested",
    # control
    "Self",
    "Fallback",
    "Return",
    # predicate containers
    "Filter",
    "Assert",
    "Match",
    # predicate ops
    "PredEq",
    "PredNe",
    "PredStarts",
    "PredEnds",
    "PredContains",
    "PredRe",
    "PredReAny",
    "PredReAll",
    "PredCss",
    "PredXpath",
    "PredHasAttr",
    "PredAttrEq",
    "PredAttrNe",
    "PredAttrStarts",
    "PredAttrEnds",
    "PredAttrContains",
    "PredAttrRe",
    "PredTextStarts",
    "PredTextEnds",
    "PredTextContains",
    "PredTextRe",
    "PredCountEq",
    "PredCountGt",
    "PredCountLt",
    "PredCountNe",
    "PredCountGe",
    "PredCountLe",
    "PredCountRange",
    "LogicNot",
    "LogicAnd",
    "LogicOr",
]
