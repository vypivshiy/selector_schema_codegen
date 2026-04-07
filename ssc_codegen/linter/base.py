"""
KDL DSL linter — base infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal
from functools import wraps
from pathlib import Path
from enum import Enum, auto
import re

from tree_sitter import Node, Tree

from ssc_codegen.linter._kdl_lang import KDL_PARSER
from ssc_codegen.linter.types import (
    RawArg,
    DefineKind,
    DefineInfo,
    TransformInfo,
    ErrorCode,
    LintError,
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

    def format(self, style: Literal["text", "json"] = "text", **kwargs) -> str:
        """Форматирование вывода"""
        from ssc_codegen.linter.format_errors import format_errors

        if style == "json":
            import json

            return json.dumps(self.to_dict(), indent=2)
        return format_errors(
            self.errors,
            src=self.source,
            filepath=self.filepath,
            use_color=kwargs.get("use_color"),
            context_lines=kwargs.get("context_lines", 1),
        )

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
        from ssc_codegen.linter.navigation import NodeNavigator
        from ssc_codegen.linter.errors import ErrorCollector
        from ssc_codegen.linter.path import PathTracker
        from ssc_codegen.linter.metadata import ModuleMetadata

        self.navigator = NodeNavigator(src)
        self.collector = ErrorCollector()
        self.path = PathTracker()
        self.metadata = ModuleMetadata()

    # ── Error reporting (делегирует к collector) ───────────────────────────────

    @property
    def errors(self) -> list[LintError]:
        return self.collector.errors

    def error(
        self,
        node: Node,
        code: ErrorCode,
        message: str,
        hint: str = "",
        *,
        label: str | None = None,
        notes: list[str] | None = None,
        end_line: int | None = None,
        end_col: int | None = None,
    ) -> None:
        self.collector.error(
            node,
            code,
            message,
            hint,
            self.path.current,
            label=label,
            notes=notes,
            end_line=end_line,
            end_col=end_col,
        )

    def warning(
        self,
        node: Node,
        code: ErrorCode,
        message: str,
        hint: str = "",
        *,
        label: str | None = None,
        notes: list[str] | None = None,
        end_line: int | None = None,
        end_col: int | None = None,
    ) -> None:
        self.collector.warning(
            node,
            code,
            message,
            hint,
            self.path.current,
            label=label,
            notes=notes,
            end_line=end_line,
            end_col=end_col,
        )

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

    def get_bare_op_container(self, node: Node) -> Node | None:
        return self.navigator.get_bare_op_container(node)

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

    MODULE = auto()  # Top-level module
    STRUCT_BODY = auto()  # Внутри struct { ... }
    INIT_BLOCK = auto()  # Внутри @init { ... }
    PIPELINE = auto()  # Внутри field { operations }
    JSON_TYPEDEF = auto()  # Внутри json { ... }
    SPECIAL_FIELD = auto()  # Внутри @pre-validate, @split-doc, etc.


# keywords that appear at module level — never inside field pipelines
_MODULE_KEYWORDS: frozenset[str] = frozenset(
    {
        "struct",
        "json",
        "define",
        "transform",
        "import",
    }
)


class AstLinter:
    """
    Registry-based KDL DSL linter.

    Special wildcard key "*" — called for nodes with no specific rule.
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[RuleFn]] = {}

    def rule(
        self, *node_names: str, replace: bool = False
    ) -> Callable[..., RuleFn]:
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
        syntax_errors = self._collect_syntax_errors(tree.root_node, src)
        if syntax_errors:
            return LintResult(
                errors=syntax_errors,
                source=src,
                filepath=filepath,
            )

        ctx = LintContext(src=src.encode())
        self._collect_imports(tree.root_node, ctx, filepath)
        self._collect_defines(tree.root_node, ctx)
        self._walk(tree.root_node, ctx)

        return LintResult(errors=ctx.errors, source=src, filepath=filepath)

    def _collect_syntax_errors(self, root: Node, src: str) -> list[LintError]:
        """Collect parser-level syntax diagnostics from tree-sitter error nodes."""
        if not root.has_error:
            return []

        errors: list[LintError] = []
        seen: set[tuple[str, int, int, int, int]] = set()
        lines = src.splitlines()

        def visit(node: Node) -> None:
            is_missing = bool(getattr(node, "is_missing", False))
            is_error_node = node.type == "ERROR"
            if is_error_node or is_missing:
                start_line = node.start_point.row + 1
                start_col = node.start_point.column + 1
                end_line = node.end_point.row + 1
                end_col = node.end_point.column + 1
                key = (node.type, start_line, start_col, end_line, end_col)
                if key not in seen:
                    seen.add(key)
                    errors.append(
                        self._syntax_error_from_node(
                            node,
                            lines=lines,
                            start_line=start_line,
                            start_col=start_col,
                            end_line=end_line,
                            end_col=end_col,
                        )
                    )
            for child in node.children:
                visit(child)

        visit(root)
        errors.sort(key=lambda e: (e.line, e.col, e.code.value))
        return errors

    def _syntax_error_from_node(
        self,
        node: Node,
        *,
        lines: list[str],
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
    ) -> LintError:
        """Convert a tree-sitter parse error node to a LintError."""
        if bool(getattr(node, "is_missing", False)):
            expected = self._format_expected_node(node.type)
            message = f"invalid KDL syntax: expected {expected}"
            hint = "fix the incomplete construct and ensure all required tokens are present"
            label = f"expected {expected}"
            notes = [
                "parser inserted a missing node while recovering from invalid syntax"
            ]
        else:
            snippet = self._node_snippet(node, lines)
            if self._looks_like_eof_syntax_error(node, lines):
                message = "invalid KDL syntax: unexpected end of input"
                hint = "close all opened strings, braces, and blocks before semantic linting"
                label = "unexpected end of input"
            else:
                message = "invalid KDL syntax"
                hint = "fix malformed tokens, quotes, braces, or block structure before semantic linting"
                label = "invalid syntax"
            notes = (
                [f"parser could not recover from: {snippet}"] if snippet else []
            )

        return LintError(
            code=ErrorCode.INVALID_SYNTAX,
            message=message,
            hint=hint,
            path="syntax",
            line=start_line,
            col=start_col,
            end_line=end_line,
            end_col=end_col,
            label=label,
            notes=notes,
            severity="error",
        )

    def _node_snippet(
        self, node: Node, lines: list[str], limit: int = 80
    ) -> str:
        """Extract a compact text snippet for a parse error node."""
        if not lines:
            return ""

        start_row = node.start_point.row
        end_row = node.end_point.row
        start_col = node.start_point.column
        end_col = node.end_point.column

        if start_row >= len(lines):
            return ""

        if start_row == end_row and start_row < len(lines):
            snippet = lines[start_row][start_col:end_col]
        else:
            parts: list[str] = []
            for idx in range(start_row, min(end_row + 1, len(lines))):
                line = lines[idx]
                if idx == start_row:
                    parts.append(line[start_col:])
                elif idx == end_row:
                    parts.append(line[:end_col])
                else:
                    parts.append(line)
            snippet = "\\n".join(parts)

        snippet = re.sub(r"\s+", " ", snippet).strip()
        if len(snippet) > limit:
            snippet = snippet[: limit - 3].rstrip() + "..."
        return snippet

    def _looks_like_eof_syntax_error(
        self, node: Node, lines: list[str]
    ) -> bool:
        """Heuristic for parse errors caused by unexpected end-of-input."""
        if not lines:
            return False
        last_line_no = len(lines)
        last_line_len = len(lines[-1])
        end_line = node.end_point.row + 1
        end_col = node.end_point.column + 1
        return end_line > last_line_no or (
            end_line == last_line_no and end_col >= last_line_len + 1
        )

    def _format_expected_node(self, node_type: str) -> str:
        """Render a human-readable expected token/node name."""
        if not node_type:
            return "token"
        if node_type.isidentifier():
            return node_type
        return repr(node_type)

    _KDL_TEXT_ENCODING = "utf-8-sig"

    def _collect_imports(
        self,
        root: Node,
        ctx: LintContext,
        filepath: Path | None,
        visited: set[str] | None = None,
    ) -> None:
        """Resolve import nodes and merge imported defines/transforms into ctx."""
        if visited is None:
            visited = set()
        if filepath is not None:
            visited.add(str(filepath.resolve()))

        for node in root.children:
            node_nm = ctx.node_name(node)
            if node_nm != "import":
                continue
            if filepath is None:
                continue  # can't resolve imports without a file path

            raw_args = ctx.get_raw_args(node)
            if not raw_args:
                continue
            raw_path = raw_args[0].value
            import_path = (filepath.parent / raw_path).resolve()
            import_key = str(import_path)

            if import_key in visited:
                continue  # circular or already imported
            if not import_path.is_file():
                continue  # parser will catch this error

            # selective names
            children = ctx.get_children_nodes(node)
            selective: set[str] | None = None
            if children:
                selective = set()
                for child in children:
                    nm = ctx.node_name(child)
                    if nm:
                        selective.add(nm)

            visited.add(import_key)
            try:
                imp_src = import_path.read_text(encoding=self._KDL_TEXT_ENCODING)
            except OSError:
                continue
            imp_tree = KDL_PARSER.parse(imp_src.encode())
            imp_ctx = LintContext(src=imp_src.encode())

            # recursively collect imports from imported file
            self._collect_imports(imp_tree.root_node, imp_ctx, import_path, visited)
            # collect defines/transforms from imported file
            self._collect_defines(imp_tree.root_node, imp_ctx)

            # merge into current context (filtered by selective if set)
            for name, info in imp_ctx.defines.items():
                if selective is not None and name not in selective:
                    continue
                ctx.defines.setdefault(name, info)
            for name, info in imp_ctx.transforms.items():
                if selective is not None and name not in selective:
                    continue
                ctx.transforms.setdefault(name, info)

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
                    langs = [
                        ctx.node_name(ln)
                        for ln in lang_nodes
                        if ctx.node_name(ln)
                    ]
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
        self, name: str, node: Node, ctx: LintContext, walk_ctx: WalkContext
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
                # В JSON typedef поля — это объявления типов, не pipeline-операции.
                # Правила операций не применяются (они предназначены только для pipeline).
                pass

            case WalkContext.SPECIAL_FIELD:
                # Special fields (@pre-validate, etc.) - без правил на этом уровне
                pass

    def _determine_next_context(
        self, node: Node, name: str, current_ctx: WalkContext
    ) -> WalkContext:
        """Определить контекст для детей узла (Python 3.10+ match/case)"""

        match (current_ctx, name):
            # Module level
            case (WalkContext.MODULE, "struct"):
                return WalkContext.STRUCT_BODY
            case (WalkContext.MODULE, "json"):
                return WalkContext.JSON_TYPEDEF
            case (WalkContext.MODULE, "define" | "transform"):
                return (
                    WalkContext.MODULE
                )  # Дети defines/transforms не интересуют

            # Struct body - field names
            case (WalkContext.STRUCT_BODY, "@init"):
                return WalkContext.INIT_BLOCK
            case (WalkContext.STRUCT_BODY, field_name) if field_name.startswith(
                "@"
            ):
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

    # Nodes whose children block contains data (not pipeline ops)
    # and should not be walked as operations.
    _DATA_CHILDREN_NODES: frozenset[str] = frozenset(
        {
            "repl",
            "css",
            "css-all",
            "xpath",
            "xpath-all",
            "css-remove",
            "xpath-remove",
        }
    )

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

        # Skip walking children of data-only nodes (e.g. repl { "old" "new" })
        if name not in self._DATA_CHILDREN_NODES:
            # Обработать wrapped children (nodes terminated by `;` or newline)
            for child in ctx.get_children_nodes(node):
                self._walk(child, ctx, next_ctx)

            # Process bare trailing op (last op without `;` in a children block).
            # In KDL 2.0, tree-sitter represents this as bare identifier + node_field
            # directly inside node_children, not wrapped in a `node` element.
            bare_container = ctx.get_bare_op_container(node)
            if bare_container is not None and next_ctx == WalkContext.PIPELINE:
                bare_name = ctx.node_name(bare_container)
                if bare_name:
                    ctx.push(bare_name)
                    self._apply_rules_for_context(
                        bare_name, bare_container, ctx, next_ctx
                    )
                    ctx.pop()

        ctx.pop()


LINTER = AstLinter()
