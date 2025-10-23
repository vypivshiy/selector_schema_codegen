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
    """Base abstract syntax tree (AST) node.

    This is the base class for all AST nodes in the code generation system.
    It provides common functionality and properties for AST node manipulation,
    including parent-child relationships, type checking, and dynamic attribute access.

    Attributes:
        kind: The token type that identifies the kind of AST node.
        kwargs: A mapping containing arguments or properties for this node.
        body: A mutable sequence of child AST nodes.
        parent: A reference to the parent AST node, if any.
        accept_type: The variable type that this node accepts as input.
        ret_type: The variable type that this node type returns.
        exclude_types: A sequence of variable types that should be excluded from processing.
        classvar_hooks: Dictionary of class variable hooks for expression evaluation.
    """

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
        """Extract all values from the kwargs field without their keys.

        Returns:
            A tuple containing all values from the kwargs mapping, preserving their order.
        """
        return tuple(self.kwargs.values())  # type: ignore

    @property
    def index(self) -> int:
        """Get the index of this node in its parent's body.

        Returns:
            The index of this node in the parent's body sequence.
            Returns -1 if this node has no parent.
        """
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
        """Get the index of the next node in the parent's body.

        Returns:
            The index of the next node in the parent's body sequence.
            Returns -1 if there is no next node or no parent.
        """
        if self.parent and len(self.parent.body) > self.index:
            return self.index + 1
        return -1

    @property
    def index_prev(self) -> int:
        """Get the index of the previous node in the parent's body.

        Returns:
            The index of the previous node in the parent's body sequence.
            Returns -1 if there is no previous node, no parent, or current index is -1.
        """
        if self.parent and self.index == 0:
            return -1
        elif self.index == -1:
            return -1
        return self.index - 1

    def __getattr__(self, name: str) -> Any:
        """Provides dynamic attribute access from the kwargs container.

        This method allows accessing values in the kwargs dictionary as if they
        were instance attributes, enabling convenient property-like access.

        Args:
            name: The name of the attribute to access.

        Returns:
            The value from kwargs if it exists, otherwise raises AttributeError.

        Raises:
            AttributeError: If the attribute is not found in kwargs or regular attributes.
        """
        try:
            return super().__getattribute__(name)
        except AttributeError as e:
            if self.kwargs.get(name):
                return self.kwargs[name]
            raise e

    def find_node(
        self, predicate: Callable[["BaseAstNode"], bool]
    ) -> Optional["BaseAstNode"]:
        """Finds the first node in the body that matches the given filter function.

        Args:
            func: A callable that takes a BaseAstNode and returns True if it matches the criteria.

        Returns:
            The first matching node, or None if no node matches or the body is empty.
        """
        if len(self.body) == 0:
            return None

        for n in self.body:
            if predicate(n):
                return n
        return None

    def find_node_all(
        self, predicate: Callable[["BaseAstNode"], bool]
    ) -> list["BaseAstNode"]:
        """Finds all nodes in the body that match the given filter function.

        Args:
            func: A callable that takes a BaseAstNode and returns True if it matches the criteria.

        Returns:
            A list of all matching nodes, or an empty list if no nodes match or the body is empty.
        """
        if len(self.body) == 0:
            return []  # type: ignore
        return [i for i in self.body if predicate(i)]

    def find_node_by_token(
        self, token_type: TokenType
    ) -> Optional["BaseAstNode"]:
        """Finds the first node in the body with the specified token type.

        Args:
            token_type: The TokenType to search for.

        Returns:
            The first matching node, or None if no node matches or the body is empty.
        """
        return self.find_node(lambda n: n.kind == token_type)

    def find_nodes_by_token(self, token_type: TokenType) -> list["BaseAstNode"]:
        """Finds all nodes in the body with the specified token type.

        Args:
            token_type: The TokenType to search for.

        Returns:
            A list of all matching nodes, or an empty list if no nodes match or the body is empty.
        """
        return self.find_node_all(lambda n: n.kind == token_type)


@dataclass(kw_only=True)
class _DisableReprBody(BaseAstNode):
    """Special class to disable representation of unnecessary node fields.

    This class is used to prevent the 'body' field from being included in
    string representations, which can be useful for preventing excessive
    output during debugging or logging.

    Attributes:
        body: A mutable sequence of child AST nodes (not included in repr).
    """

    body: MutableSequence[BaseAstNode] = field(default_factory=list, repr=False)


@dataclass(kw_only=True)
class _DisableReprAcceptAndRetType(BaseAstNode):
    """Special class to disable representation of type fields.

    This class is used to prevent the 'accept_type' and 'ret_type' fields
    from being included in string representations, which can help reduce
    verbosity in debugging or logging output.

    Attributes:
        accept_type: The variable type that this node accepts as input (not included in repr).
        ret_type: The variable type that this node returns (not included in repr).
    """

    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)


@dataclass(kw_only=True)
class _DisableRepr(_DisableReprBody, _DisableReprAcceptAndRetType):
    """Special class to disable representation of multiple node fields.

    This class combines the functionality of _DisableReprBody and
    _DisableReprAcceptAndRetType to prevent the 'body', 'accept_type',
    and 'ret_type' fields from being included in string representations.
    This provides a more concise output for debugging and logging.

    Attributes:
        body: A mutable sequence of child AST nodes (not included in repr).
        accept_type: The variable type that this node accepts as input (not included in repr).
        ret_type: The variable type that this node returns (not included in repr).
    """

    body: MutableSequence[BaseAstNode] = field(default_factory=list, repr=False)
    accept_type: VariableType = field(default=VariableType.ANY, repr=False)
    ret_type: VariableType = field(default=VariableType.ANY, repr=False)
