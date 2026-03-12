"""
KDL DSL linter — base infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal
from functools import wraps
from pathlib import Path
from enum import Enum, auto

from tree_sitter import Node, Tree

from ssc_codegen.kdl.linter._kdl_lang import KDL_PARSER
from ssc_codegen.kdl.linter.types import (
    RawArg, DefineKind, DefineInfo, TransformInfo,
    ErrorCode, LintError
)


# ── result ─────────────────────────────────────────────────────────────────────


@dataclass
class LintResult:
    """Результат проверки линтера"""
    
    errors: list[LintError]
    source: str
    filepath: Path | None = None
    
    @property
    def warnings(self) -> list[LintError]:
        """Фильтр только warnings"""
        return [e for e in self.errors if e.severity == "warning"]
    
    @property
    def error_count(self) -> int:
        """Количество ошибок (не warnings)"""
        return sum(1 for e in self.errors if e.severity == "error")
    
    def has_errors(self) -> bool:
        """Есть ли ошибки (не warnings)?"""
        return self.error_count > 0
    
    def format(self, style: Literal["text", "json"] = "text") -> str:
        """Форматирование вывода"""
        from ssc_codegen.kdl.linter.format_errors import format_errors
        
        if style == "json":
            import json
            return json.dumps(self.to_dict(), indent=2)
        return format_errors(self.errors, src=self.source, filepath=self.filepath)
    
    def to_dict(self) -> dict:
        """Для JSON API"""
        return {
            "errors": [e.to_dict() for e in self.errors],
            "error_count": self.error_count,
            "warning_count": len(self.warnings),
            "filepath": str(self.filepath) if self.filepath else None,
        }


# ── context ────────────────────────────────────────────────────────────────────


class LintContext:
    """Облегчённый контекст, координирует компоненты"""
    
    def __init__(self, src: bytes):
        from ssc_codegen.kdl.linter.navigation import NodeNavigator
        from ssc_codegen.kdl.linter.errors import ErrorCollector
        from ssc_codegen.kdl.linter.path import PathTracker
        from ssc_codegen.kdl.linter.metadata import ModuleMetadata
        
        self.navigator = NodeNavigator(src)
        self.collector = ErrorCollector()
        self.path = PathTracker()
        self.metadata = ModuleMetadata()

    # ── Error reporting (делегирует к collector) ───────────────────────────────
    
    @property
    def errors(self) -> list[LintError]:
        return self.collector.errors
    
    def error(self, node: Node, code: ErrorCode, message: str, hint: str = "") -> None:
        self.collector.error(node, code, message, hint, self.path.current)
    
    def warning(self, node: Node, code: ErrorCode, message: str, hint: str = "") -> None:
        self.collector.warning(node, code, message, hint, self.path.current)
    
    # ── Path tracking (делегирует к path) ──────────────────────────────────────
    
    @property
    def current_path(self) -> str:
        return self.path.current
    
    def push(self, segment: str) -> None:
        self.path.push(segment)
    
    def pop(self) -> None:
        self.path.pop()

    # ── Navigation shortcuts (делегирует к navigator) ─────────────────────────
    
    def node_name(self, node: Node) -> str:
        return self.navigator.node_name(node)
    
    def get_args(self, node: Node) -> list[str]:
        return self.navigator.get_args(node)
    
    def get_raw_args(self, node: Node) -> list[RawArg]:
        return self.navigator.get_raw_args(node)
    
    def get_arg(self, node: Node, index: int) -> str | None:
        return self.navigator.get_arg(node, index)
    
    def get_prop(self, node: Node, key: str) -> str | None:
        return self.navigator.get_prop(node, key)
    
    def get_children_nodes(self, node: Node) -> list[Node]:
        return self.navigator.get_children_nodes(node)
    
    def has_empty_block(self, node: Node) -> bool:
        return self.navigator.has_empty_block(node)
    
    def has_single_line_op(self, node: Node, op_name: str) -> bool:
        return self.navigator.has_single_line_op(node, op_name)
    
    # ── Metadata shortcuts ─────────────────────────────────────────────────────
    
    @property
    def defines(self) -> dict[str, DefineInfo]:
        return self.metadata.defines
    
    @property
    def transforms(self) -> dict[str, TransformInfo]:
        return self.metadata.transforms
    
    @property
    def init_fields(self) -> set[str]:
        return self.metadata.init_fields
    
    @property
    def inferred_define_types(self) -> dict[str, tuple]:
        return self.metadata.inferred_define_types
    
    # ── Define/transform helpers ───────────────────────────────────────────────
    
    def is_define_ref(self, arg: str) -> bool:
        """Проверить является ли аргумент ссылкой на define"""
        return arg in self.defines
    
    def resolve_scalar_arg(self, arg: str) -> str | None:
        """Разрешить scalar define значение"""
        if arg in self.defines:
            info = self.defines[arg]
            if info.kind == DefineKind.SCALAR:
                return info.value
        return None


# ── linter ─────────────────────────────────────────────────────────────────────

RuleFn = Callable[[Node, LintContext], None]


class WalkContext(Enum):
    """Контекст обхода AST"""
    MODULE = auto()           # Top-level module
    STRUCT_BODY = auto()      # Внутри struct { ... }
    INIT_BLOCK = auto()       # Внутри @init { ... }
    PIPELINE = auto()         # Внутри field { operations }
    JSON_TYPEDEF = auto()     # Внутри json { ... }
    SPECIAL_FIELD = auto()    # Внутри @pre-validate, @split-doc, etc.


# keywords that appear at module level — never inside field pipelines
_MODULE_KEYWORDS: frozenset[str] = frozenset(
    {
        "struct",
        "json",
        "define",
        "transform",
    }
)


class AstLinter:
    """
    Registry-based KDL DSL linter.

    Special wildcard key "*" — called for nodes with no specific rule.
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[RuleFn]] = {}

    def rule(self, *node_names: str, replace: bool = False) -> Callable[..., RuleFn]:
        """
        Регистрация правила (decorator).
        
        Args:
            node_names: Имена узлов для проверки
            replace: Заменить существующие правила (по умолчанию добавляет)
        
        Example:
            @LINTER.rule("css", "css-all")
            def my_css_rule(node, ctx):
                ...
            
            # Заменить существующее правило
            @LINTER.rule("css", replace=True)
            def custom_css_rule(node, ctx):
                ...
        """
        def decorator(fn: RuleFn) -> RuleFn:
            @wraps(fn)
            def wrapper(node: Node, ctx: LintContext) -> None:
                fn(node, ctx)

            for name in node_names:
                if replace:
                    self._rules[name] = [wrapper]
                else:
                    self._rules.setdefault(name, []).append(wrapper)
            return wrapper

        return decorator

    def remove_rule(self, node_name: str, fn: RuleFn | None = None) -> None:
        """
        Удалить правило.
        
        Args:
            node_name: Имя узла
            fn: Конкретная функция (если None - удалить все)
        
        Example:
            # Удалить все правила для node
            LINTER.remove_rule("deprecated-op")
            
            # Удалить конкретное правило
            LINTER.remove_rule("css", my_custom_rule)
        """
        if node_name in self._rules:
            if fn is None:
                del self._rules[node_name]
            else:
                self._rules[node_name] = [
                    r for r in self._rules[node_name] if r != fn
                ]
                if not self._rules[node_name]:
                    del self._rules[node_name]
    
    def list_rules(self) -> dict[str, int]:
        """
        Список зарегистрированных правил.
        
        Returns:
            Словарь {node_name: count_of_rules}
        
        Example:
            rules = LINTER.list_rules()
            print(f"Total rules for 'css': {rules.get('css', 0)}")
        """
        return {name: len(rules) for name, rules in self._rules.items()}

    def lint(
        self,
        src: str,
        filepath: Path | None = None,
        # Для будущего incremental linting (LSP)
        old_tree: Tree | None = None,
        edits: list | None = None,
    ) -> LintResult:
        """
        Проверить KDL схему
        
        Args:
            src: Исходный код схемы
            filepath: Путь к файлу (опционально, для вывода)
            old_tree: Старое parse tree (для incremental, не используется)
            edits: Список изменений (для incremental, не используется)
        
        Returns:
            LintResult с ошибками и методами форматирования
        
        Note:
            old_tree и edits зарезервированы для будущего incremental linting
            в LSP server. Сейчас игнорируются.
        """
        # TODO: использовать old_tree для incremental parsing
        tree = KDL_PARSER.parse(src.encode())
        ctx = LintContext(src=src.encode())
        self._collect_defines(tree.root_node, ctx)
        self._walk(tree.root_node, ctx)
        
        return LintResult(
            errors=ctx.errors,
            source=src,
            filepath=filepath
        )

    def _collect_defines(self, root: Node, ctx: LintContext) -> None:
        """
        First pass — collect module-level defines and transforms into ctx.

        Scalar: define NAME=value  → prop child, no node_children
        Block:  define NAME { }   → first positional arg + node_children
        transform NAME accept=TYPE return=TYPE { lang { ... } ... }
        """
        for node in root.children:
            node_nm = ctx.node_name(node)
            if node_nm == "transform":
                raw_args = ctx.get_raw_args(node)
                if raw_args:
                    t_name = raw_args[0].value
                    accept_str = ctx.get_prop(node, "accept") or ""
                    ret_str = ctx.get_prop(node, "return") or ""
                    lang_nodes = ctx.get_children_nodes(node)
                    langs = [ctx.node_name(ln) for ln in lang_nodes if ctx.node_name(ln)]
                    ctx.transforms[t_name] = TransformInfo(
                        name=t_name,
                        accept=accept_str,
                        ret=ret_str,
                        langs=langs,
                        node=node,
                    )
                continue
            if node_nm != "define":
                continue

            children = ctx.get_children_nodes(node)

            if children:
                # block define: name is first positional arg
                # use get_raw_args to correctly extract the identifier
                raw_args = ctx.get_raw_args(node)
                if raw_args:
                    name = raw_args[0].value
                    ctx.defines[name] = DefineInfo(
                        name=name,
                        kind=DefineKind.BLOCK,
                        value=None,
                        node=node,
                    )
            else:
                # scalar define: iterate props
                for child in node.children:
                    if child.type != "node_field":
                        continue
                    for sub in child.children:
                        if sub.type != "prop":
                            continue
                        name = sub.children[0].text.decode()
                        value = ctx.navigator._extract_value(sub.children[2])
                        ctx.defines[name] = DefineInfo(
                            name=name,
                            kind=DefineKind.SCALAR,
                            value=value,
                            node=node,
                        )

    def _apply_rules_for_context(
        self,
        name: str,
        node: Node,
        ctx: LintContext,
        walk_ctx: WalkContext
    ) -> None:
        """Применить правила в зависимости от контекста (Python 3.10+ match/case)"""
        
        match walk_ctx:
            case WalkContext.PIPELINE:
                # В pipeline проверяем все операции
                if name in self._rules:
                    for rule_fn in self._rules[name]:
                        rule_fn(node, ctx)
                else:
                    # Wildcard rule для неизвестных операций
                    for rule_fn in self._rules.get("*", []):
                        rule_fn(node, ctx)
            
            case WalkContext.MODULE:
                # На уровне модуля только module keywords
                if name in _MODULE_KEYWORDS and name in self._rules:
                    for rule_fn in self._rules[name]:
                        rule_fn(node, ctx)
            
            case WalkContext.STRUCT_BODY | WalkContext.INIT_BLOCK:
                # В struct/init body проверяем field names и special fields
                if name in self._rules:
                    for rule_fn in self._rules[name]:
                        rule_fn(node, ctx)
            
            case WalkContext.JSON_TYPEDEF:
                # В JSON typedef только структурные проверки, не операции
                if name in self._rules:
                    for rule_fn in self._rules[name]:
                        rule_fn(node, ctx)
            
            case WalkContext.SPECIAL_FIELD:
                # Special fields (@pre-validate, etc.) - без правил на этом уровне
                pass
    
    def _determine_next_context(
        self,
        node: Node,
        name: str,
        current_ctx: WalkContext
    ) -> WalkContext:
        """Определить контекст для детей узла (Python 3.10+ match/case)"""
        
        match (current_ctx, name):
            # Module level
            case (WalkContext.MODULE, "struct"):
                return WalkContext.STRUCT_BODY
            case (WalkContext.MODULE, "json"):
                return WalkContext.JSON_TYPEDEF
            case (WalkContext.MODULE, "define" | "transform"):
                return WalkContext.MODULE  # Дети defines/transforms не интересуют
            
            # Struct body - field names
            case (WalkContext.STRUCT_BODY, "@init"):
                return WalkContext.INIT_BLOCK
            case (WalkContext.STRUCT_BODY, field_name) if field_name.startswith("@"):
                return WalkContext.SPECIAL_FIELD
            case (WalkContext.STRUCT_BODY, _):
                # Regular field - дети это pipeline ops
                return WalkContext.PIPELINE
            
            # Init block - field names inside @init
            case (WalkContext.INIT_BLOCK, _):
                # InitField children are pipelines
                return WalkContext.PIPELINE
            
            # Special field - children are pipelines
            case (WalkContext.SPECIAL_FIELD, _):
                return WalkContext.PIPELINE
            
            # JSON typedef - field definitions with type annotations
            case (WalkContext.JSON_TYPEDEF, _):
                # Children are type annotation nodes, not operations
                return WalkContext.JSON_TYPEDEF
            
            # Pipeline - stays pipeline
            case (WalkContext.PIPELINE, _):
                return WalkContext.PIPELINE
            
            # Default: keep current context
            case _:
                return current_ctx
    
    def _walk(
        self,
        node: Node,
        ctx: LintContext,
        walk_ctx: WalkContext = WalkContext.MODULE,
    ) -> None:
        """Обход AST с проверкой правил (упрощенная версия с WalkContext)"""
        
        if node.type != "node":
            for child in node.children:
                self._walk(child, ctx, walk_ctx)
            return
        
        name = ctx.node_name(node)
        if not name:
            return
        
        ctx.push(name)
        
        # Применить правила для текущего узла
        self._apply_rules_for_context(name, node, ctx, walk_ctx)
        
        # Определить контекст для детей
        next_ctx = self._determine_next_context(node, name, walk_ctx)
        
        # Обработать детей
        for child in ctx.get_children_nodes(node):
            self._walk(child, ctx, next_ctx)
        
        ctx.pop()


LINTER = AstLinter()
