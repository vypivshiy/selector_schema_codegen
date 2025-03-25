from dataclasses import dataclass, field
from typing import (
    ClassVar,
    Mapping,
    TypeVar,
    Generic,
    Any,
    TypedDict,
    Optional,
    MutableSequence,
    Sequence,
)

from ssc_codegen.tokens import TokenType, VariableType

T_ARGUMENTS = TypeVar("T_ARGUMENTS")
T_MAPPING_FIELD = TypeVar("T_MAPPING_FIELD", bound=Mapping[str, Any])
T_EMPTY_KWARGS = TypedDict("T_EMPTY_KWARGS", {})


@dataclass(kw_only=True)
class BaseAstNode(Generic[T_MAPPING_FIELD, T_ARGUMENTS]):
    """base AST container"""

    kind: ClassVar[TokenType]
    kwargs: T_MAPPING_FIELD = field(default_factory=dict)  # type: ignore[assignment]

    body: MutableSequence["BaseAstNode"] = field(default_factory=list)
    parent: Optional["BaseAstNode"] = field(default=None, repr=False)

    # used for type check expressions
    accept_type: VariableType = VariableType.ANY
    ret_type: VariableType = VariableType.ANY
    exclude_types: Sequence[VariableType] = field(default_factory=tuple)

    def unpack_args(self) -> T_ARGUMENTS:
        """extract all values from kwargs field wout keys"""
        return tuple(self.kwargs.values())  # type: ignore

    # todo: cached property?
    @property
    def index(self) -> int:
        if self.parent:
            return self.parent.body.index(self)
        return -1

    @property
    def index_next(self) -> int:
        if self.parent and len(self.parent.body) > self.index:
            return self.index + 1
        return -1

    @property
    def index_prev(self) -> int:
        if self.parent and self.index == 0:
            return -1
        elif self.index == -1:
            return -1
        return self.index - 1

    def __getattr__(self, name: str) -> Any:
        # modify for provide extract argument from kwargs container (like property)
        try:
            return super().__getattribute__(name)
        except AttributeError as e:
            if self.kwargs.get(name):
                return self.kwargs[name]
            raise e


@dataclass(kw_only=True)
class _DisableReprBody(BaseAstNode):
    """special class for disable repr unnecessary node fields"""

    body: MutableSequence[BaseAstNode] = field(default_factory=list, repr=False)


@dataclass(kw_only=True)
class _DisableReprAcceptAndRetType(BaseAstNode):
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)


@dataclass(kw_only=True)
class _DisableRepr(_DisableReprBody, _DisableReprAcceptAndRetType):
    body: MutableSequence[BaseAstNode] = field(default_factory=list, repr=False)
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)
