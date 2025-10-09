from dataclasses import dataclass, field
from typing import (
    Callable,
    ClassVar,
    Mapping,
    TypeVar,
    Generic,
    Any,
    TypedDict,
    Optional,
    MutableSequence,
    Sequence,
    TYPE_CHECKING,
)

from ssc_codegen.tokens import TokenType, VariableType

if TYPE_CHECKING:
    from ssc_codegen.ast_.nodes_core import ExprClassVar

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
    exclude_types: Sequence[VariableType] = field(
        default_factory=tuple, repr=False
    )
    classvar_hooks: dict[str, "ExprClassVar"] = field(default_factory=dict)

    def unpack_args(self) -> T_ARGUMENTS:
        """extract all values from kwargs field wout keys"""
        return tuple(self.kwargs.values())  # type: ignore

    @property
    def index(self) -> int:
        if self.parent:
            # self.parent.body.index(self) add side effect if expr has same operations:
            #      0      1      1       1
            # D().raw().trim().trim().trim()
            # use compare by id
            for i, child in enumerate(self.parent.body):
                if id(child) == id(self):
                    return i
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

    def find_node(
        self, func: Callable[["BaseAstNode"], bool]
    ) -> Optional["BaseAstNode"]:
        """find nodes in body by func filter

        return None if node not founded or node.body is empty
        """
        if len(self.body) == 0:
            return None

        for n in self.body:
            if func(n):
                return n
        return None

    def find_node_all(
        self, func: Callable[["BaseAstNode"], bool]
    ) -> list["BaseAstNode"]:
        """find nodes in body by func filter"""
        if len(self.body) == 0:
            return []  # type: ignore
        return [i for i in self.body if i.kind == func(i)]

    def find_node_by_token(
        self, token_type: TokenType
    ) -> Optional["BaseAstNode"]:
        """find node by TokenType"""
        return self.find_node(lambda n: n.kind == token_type)

    def find_nodes_by_token(self, token_type: TokenType) -> list["BaseAstNode"]:
        """find nodes by TokenType"""
        return self.find_nodes_by_token(lambda n: n.kind == token_type)  # type: ignore[arg-type]


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
