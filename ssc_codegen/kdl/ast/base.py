"""Base AST node."""
from __future__ import annotations

from dataclasses import dataclass, field, fields, MISSING
from typing import (
    Callable,
    ClassVar,
    Mapping,
    TypeVar,
    Generic,
    Any,
    Optional,
    MutableSequence,
    Sequence,
)
from ssc_codegen.kdl.tokens import TokenType, VariableType

T_KWARGS = TypeVar("T_KWARGS", bound=Mapping[str, Any])
T_ARGS = TypeVar("T_ARGS")


@dataclass(kw_only=True)
class BaseAstNode(Generic[T_KWARGS, T_ARGS]):
    """
    Базовый AST-узел.

    Правила:
    - `kind` — ClassVar, идентифицирует тип узла (TokenType).
    - `accept_type` / `ret_type` — **instance fields**, задаются явно при создании узла.
      Нет никаких ClassVar-дефолтов: каждый подкласс обязан задать значения
      через `field(default=...)`.
    - `exclude_types` — ClassVar, список типов запрещённых на входе.
    - `kwargs` — параметры узла (TypedDict).
    - `body` — дочерние узлы (пайплайн поля или вложенные блоки).
    - `parent` — ссылка на родителя, исключена из repr (защита от циклов).
    """

    # ── тип узла (обязателен в каждом подклассе) ───────────────────────────
    kind: ClassVar[TokenType]

    # ── типы запрещённые на входе (опциональный ClassVar) ──────────────────
    exclude_types: ClassVar[Sequence[VariableType]] = ()

    # ── типы данных (instance fields — задаются в каждом подклассе) ────────
    accept_type: VariableType = field(default=VariableType.ANY)
    ret_type: VariableType = field(default=VariableType.ANY)

    # ── данные узла ─────────────────────────────────────────────────────────
    kwargs: T_KWARGS = field(default_factory=dict)  # type: ignore[assignment]

    # ── дочерние узлы (включены в repr для удобного pprint) ─────────────────
    body: MutableSequence[BaseAstNode] = field(default_factory=list)

    # ── родитель (исключён из repr — защита от циклов) ──────────────────────
    parent: Optional[BaseAstNode] = field(default=None, repr=False)

    # ════════════════════════════════════════════════════════════════════════
    # ИНИЦИАЛИЗАЦИЯ
    # ════════════════════════════════════════════════════════════════════════

    def __post_init__(self) -> None:
        self._validate_kwargs()
        self._validate_types()

    # ════════════════════════════════════════════════════════════════════════
    # ВАЛИДАЦИЯ
    # ════════════════════════════════════════════════════════════════════════

    def _validate_kwargs(self) -> None:
        """Проверяем наличие обязательных ключей из TypedDict-аннотации kwargs."""
        from typing import get_type_hints
        try:
            hints = get_type_hints(type(self))
            kwargs_type = hints.get("kwargs")
            if kwargs_type and hasattr(kwargs_type, "__required_keys__"):
                for key in kwargs_type.__required_keys__:
                    if key not in self.kwargs:
                        raise ValueError(
                            f"{type(self).__name__}: missing required kwarg '{key}'"
                        )
        except (TypeError, AttributeError):
            pass

    def _validate_types(self) -> None:
        """Проверяем, что accept_type не в exclude_types."""
        if self.accept_type in self.exclude_types:
            raise ValueError(
                f"{type(self).__name__}: accept_type={self.accept_type.name} "
                f"is excluded"
            )

    def validate_pipeline(self, prev_node: Optional[BaseAstNode]) -> bool:
        """
        Проверяем совместимость типов с предыдущим узлом в пайплайне.

        Returns:
            True — типы совместимы.

        Raises:
            TypeError — несовместимые типы.
        """
        if prev_node is None:
            return True

        prev_ret = prev_node.ret_type
        cur_accept = self.accept_type

        if cur_accept == VariableType.ANY or prev_ret == VariableType.ANY:
            return True

        if self._is_compatible(prev_ret, cur_accept):
            return True

        raise TypeError(
            f"Type mismatch: "
            f"{type(prev_node).__name__}.ret_type={prev_ret.name} "
            f"→ {type(self).__name__}.accept_type={cur_accept.name}"
        )

    @staticmethod
    def _is_compatible(from_type: VariableType, to_type: VariableType) -> bool:
        """
        Правила совместимости типов.

        - Точное совпадение.
        - LIST_ANY принимает любой конкретный список.
        - DOCUMENT → LIST_DOCUMENT (единичный элемент в список).
        - STRING → LIST_STRING (единичный элемент в список).
        """
        if from_type == to_type:
            return True

        if to_type == VariableType.LIST_ANY:
            return from_type in (
                VariableType.LIST_STRING,
                VariableType.LIST_INT,
                VariableType.LIST_FLOAT,
                VariableType.LIST_DOCUMENT,
            )

        if from_type == VariableType.DOCUMENT and to_type == VariableType.LIST_DOCUMENT:
            return True

        if from_type == VariableType.STRING and to_type == VariableType.LIST_STRING:
            return True

        return False

    # ════════════════════════════════════════════════════════════════════════
    # НАВИГАЦИЯ
    # ════════════════════════════════════════════════════════════════════════

    def unpack_args(self) -> T_ARGS:
        """Возвращает значения kwargs как tuple."""
        return tuple(self.kwargs.values())  # type: ignore[return-value]

    @property
    def index(self) -> int:
        """Индекс этого узла в parent.body. -1 если нет родителя."""
        if self.parent is None:
            return -1
        for i, child in enumerate(self.parent.body):
            if child is self:
                return i
        return -1

    @property
    def next_sibling(self) -> Optional[BaseAstNode]:
        """Следующий узел в parent.body."""
        idx = self.index
        if idx == -1 or self.parent is None:
            return None
        nxt = idx + 1
        if nxt < len(self.parent.body):
            return self.parent.body[nxt]
        return None

    @property
    def prev_sibling(self) -> Optional[BaseAstNode]:
        """Предыдущий узел в parent.body."""
        idx = self.index
        if idx <= 0 or self.parent is None:
            return None
        return self.parent.body[idx - 1]

    # ════════════════════════════════════════════════════════════════════════
    # ПОИСК
    # ════════════════════════════════════════════════════════════════════════

    def find_node(
        self, predicate: Callable[[BaseAstNode], bool]
    ) -> Optional[BaseAstNode]:
        """Первый узел удовлетворяющий предикату (DFS)."""
        for child in self.body:
            if predicate(child):
                return child
            result = child.find_node(predicate)
            if result is not None:
                return result
        return None

    def find_nodes(
        self, predicate: Callable[[BaseAstNode], bool]
    ) -> list[BaseAstNode]:
        """Все узлы удовлетворяющие предикату (DFS)."""
        result: list[BaseAstNode] = []
        for child in self.body:
            if predicate(child):
                result.append(child)
            result.extend(child.find_nodes(predicate))
        return result

    def find_by_token(self, token_type: TokenType) -> Optional[BaseAstNode]:
        """Первый узел по TokenType."""
        return self.find_node(lambda n: n.kind == token_type)

    def find_all_by_token(self, token_type: TokenType) -> list[BaseAstNode]:
        """Все узлы по TokenType."""
        return self.find_nodes(lambda n: n.kind == token_type)

    # ════════════════════════════════════════════════════════════════════════
    # REPR (защита от циклов через parent)
    # ════════════════════════════════════════════════════════════════════════

    def __repr__(self) -> str:
        return self._repr_impl(depth=0, seen=set())

    def _repr_impl(self, depth: int, seen: set[int]) -> str:
        node_id = id(self)
        if node_id in seen:
            return f"<{type(self).__name__} ...cycle...>"
        if depth > 4:
            return f"<{type(self).__name__} ...>"

        seen = seen | {node_id}  # копия, не мутируем

        parts: list[str] = []
        for f in fields(self):
            if not f.repr:
                continue
            value = getattr(self, f.name)

            # пропускаем дефолтные пустые значения
            if f.default is not MISSING and value == f.default:
                continue
            if f.default_factory is not MISSING and value == f.default_factory():  # type: ignore[misc]
                continue

            if isinstance(value, BaseAstNode):
                vr = value._repr_impl(depth + 1, seen)
            elif isinstance(value, (list, tuple)):
                items = [
                    v._repr_impl(depth + 1, seen) if isinstance(v, BaseAstNode) else repr(v)
                    for v in value
                ]
                vr = "[" + ", ".join(items) + "]"
            else:
                vr = repr(value)

            parts.append(f"{f.name}={vr}")

        inner = ", ".join(parts)
        return f"{type(self).__name__}({inner})" if inner else f"{type(self).__name__}()"