from __future__ import annotations
from dataclasses import dataclass, field

from .base import Node
from .types import VariableType


@dataclass
class TransformTarget(Node):
    """
    Per-language implementation of a transform.

    lang    — target language identifier ("py", "js").
    imports — import statements; each element is one import line.
              Multiple imports passed as separate args in DSL:
              import "from base64 import b64decode" "import hashlib"
    code    — code template lines; each element is one line.
              Codegen adds indentation automatically.
              Markers:
                {{PRV}} — variable holding the previous pipeline value (input)
                {{NXT}} — variable that will hold the result (output)
    """
    lang:    str            = ""
    imports: tuple[str, ...] = field(default_factory=tuple)
    code:    tuple[str, ...] = field(default_factory=tuple)


@dataclass
class TransformDef(Node):
    """
    Module-level transform definition.
    DSL: transform name accept=TYPE return=TYPE { lang { ... } ... }

    accept and ret must be explicit VariableType values.
    AUTO is not allowed — transform is an explicit type contract.
    body: list[TransformTarget]
    """
    name:   str          = ""
    accept: VariableType = field(default=VariableType.AUTO)
    ret:    VariableType = field(default=VariableType.AUTO)


@dataclass
class TransformCall(Node):
    """
    Pipeline op — calls a named TransformDef.
    DSL: transform name  (inside a field pipeline)

    accept and ret are copied from TransformDef at AST build time.
    Build-time errors:
      - name not found in module transforms
      - accept type mismatches pipeline cursor
    """
    name:   str          = ""
    accept: VariableType = field(default=VariableType.AUTO)
    ret:    VariableType = field(default=VariableType.AUTO)
