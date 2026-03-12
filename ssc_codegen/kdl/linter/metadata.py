"""Module metadata collection"""

from __future__ import annotations

from dataclasses import dataclass, field

from ssc_codegen.kdl.linter.types import DefineInfo, TransformInfo


@dataclass
class ModuleMetadata:
    """Метаданные модуля (defines, transforms, init fields)"""
    
    defines: dict[str, DefineInfo] = field(default_factory=dict)
    transforms: dict[str, TransformInfo] = field(default_factory=dict)
    init_fields: set[str] = field(default_factory=set)
    # cache for block-define inferred (accept, ret) pairs — populated lazily
    inferred_define_types: dict[str, tuple] = field(default_factory=dict)
