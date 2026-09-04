"""Explicit, source-scoped KDL import resolution and dependency closure computation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from kdlquery import KDLParseError, KdlNode, ReadDiagnostic, Severity
from kdlquery import parse as kdl_parse

from ssc_codegen.core.contexts import ParseContext

IMPORT_KINDS = frozenset({"define", "extension", "fn", "json", "struct"})
_JSON_PRIMITIVES = frozenset({"bool", "float", "int", "nil", "null", "str"})
_DEFINE_TEMPLATE_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_-]*)\}\}")
_KDL_TEXT_ENCODING = "utf-8-sig"


@dataclass(frozen=True)
class SymbolId:
    """Globally unique identifier for an imported or exported declaration symbol.

    Attributes:
        path: Canonical filesystem path to the defining schema file.
        kind: Kind of declaration (`"define"`, `"extension"`, `"fn"`, `"json"`, `"struct"`).
        name: Declared symbol name.
    """

    path: Path
    kind: str
    name: str


@dataclass
class SourceUnit:
    """An individual KDL source file and its local symbol table.

    Attributes:
        path: Canonical filesystem path to the file.
        nodes: Parsed top-level KDL nodes.
        exports: Map of `(kind, name)` to `SymbolId` declared in this file.
        export_nodes: Mapping from `SymbolId` to the declaring `KdlNode`.
        scope: Combined symbol visibility map (local declarations + explicit imports).
        ordered_roots: Topological order of symbols declared or imported in this unit.
    """

    path: Path
    nodes: list[KdlNode]
    exports: dict[tuple[str, str], SymbolId] = field(default_factory=dict)
    export_nodes: dict[SymbolId, KdlNode] = field(default_factory=dict)
    scope: dict[tuple[str, str], SymbolId] = field(default_factory=dict)
    ordered_roots: list[SymbolId] = field(default_factory=list)


def _diagnostic(
    node: KdlNode,
    path: Path,
    message: str,
    *,
    hint: str = "",
    code: str = "E003",
) -> ReadDiagnostic:
    return ReadDiagnostic(
        message=message,
        severity=Severity.ERROR,
        span=node.span,
        path=str(path),
        hint=hint,
        code=code,
    )


def _register_sources(
    nodes: list[KdlNode], path: Path, ctx: ParseContext
) -> None:
    pending = list(nodes)
    while pending:
        node = pending.pop()
        ctx.node_source_paths[id(node)] = path
        pending.extend(node.children)


def _node_symbols(node: KdlNode, path: Path) -> list[SymbolId]:
    if node.name not in IMPORT_KINDS:
        return []
    if node.name == "define":
        if node.children and node.args:
            return [SymbolId(path, "define", str(node.args[0].value))]
        return [SymbolId(path, "define", str(name)) for name in node.properties]
    if not node.args:
        return []
    return [SymbolId(path, node.name, str(node.args[0].value))]


def _import_item(node: KdlNode) -> tuple[str, str] | None:
    annotation = node.type_annotation
    if not annotation:
        return None
    kind = annotation[1:-1]
    if kind not in IMPORT_KINDS:
        return None
    return kind, node.name


def _walk(nodes: list[KdlNode]):
    pending = list(reversed(nodes))
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.children))


class _Resolver:
    def __init__(
        self,
        root_nodes: list[KdlNode],
        root_path: Path,
        ctx: ParseContext,
        diagnostics: list[ReadDiagnostic],
    ) -> None:
        self.root_nodes = root_nodes
        self.root_path = root_path.resolve()
        self.ctx = ctx
        self.diagnostics = diagnostics
        self.units: dict[Path, SourceUnit] = {}
        self.active: list[Path] = []
        self._reported_refs: set[tuple[int, str, str]] = set()

    def resolve(self) -> list[KdlNode]:
        root = self._load_unit(
            self.root_path, nodes=self.root_nodes, lint_imported=False
        )
        if root is None:
            return []

        ordered: list[SymbolId] = []
        visiting: list[SymbolId] = []
        visited: set[SymbolId] = set()

        def visit(symbol: SymbolId) -> None:
            if symbol in visited:
                return
            if symbol in visiting:
                cycle = visiting[visiting.index(symbol) :] + [symbol]
                chain = " -> ".join(f"{s.kind} {s.name}" for s in cycle)
                node = self.units[symbol.path].export_nodes[symbol]
                self.diagnostics.append(
                    _diagnostic(
                        node,
                        symbol.path,
                        f"dependency cycle detected: {chain}",
                        code="E300",
                    )
                )
                return
            visiting.append(symbol)
            for dependency in self._dependencies(symbol):
                visit(dependency)
            visiting.pop()
            visited.add(symbol)
            ordered.append(symbol)

        for symbol in root.ordered_roots:
            visit(symbol)

        result: list[KdlNode] = [
            node for node in root.nodes if node.name == "@doc"
        ]
        selected_define_names: dict[tuple[Path, int], set[str]] = {}
        for symbol in ordered:
            if symbol.kind != "define":
                continue
            symbol_node = self.units[symbol.path].export_nodes[symbol]
            selected_define_names.setdefault(
                (symbol.path, id(symbol_node)), set()
            ).add(symbol.name)
        for (path, node_id), names in selected_define_names.items():
            define_node = next(
                node for node in self.units[path].nodes if id(node) == node_id
            )
            if not define_node.children and define_node.properties:
                define_node.properties = MappingProxyType(
                    {
                        name: value
                        for name, value in define_node.properties.items()
                        if name in names
                    }
                )

        emitted_nodes: set[tuple[Path, int]] = set()
        emitted_names: dict[tuple[str, str], SymbolId] = {}
        for symbol in ordered:
            previous = emitted_names.get((symbol.kind, symbol.name))
            if previous is not None and previous != symbol:
                node = self.units[symbol.path].export_nodes[symbol]
                self.diagnostics.append(
                    _diagnostic(
                        node,
                        symbol.path,
                        f"symbol collision: {symbol.kind} '{symbol.name}' is provided by both {previous.path} and {symbol.path}",
                    )
                )
                continue
            emitted_names[(symbol.kind, symbol.name)] = symbol
            node = self.units[symbol.path].export_nodes[symbol]
            node_key = (symbol.path, id(node))
            if node_key not in emitted_nodes:
                emitted_nodes.add(node_key)
                result.append(node)
        return result

    def _load_unit(
        self,
        path: Path,
        *,
        nodes: list[KdlNode] | None = None,
        lint_imported: bool = True,
        referer: KdlNode | None = None,
    ) -> SourceUnit | None:
        path = path.resolve()
        cached = self.units.get(path)
        if cached is not None:
            return cached
        if path in self.active:
            return None
        if nodes is None:
            try:
                source = path.read_text(encoding=_KDL_TEXT_ENCODING)
            except OSError as exc:
                if referer is not None:
                    self.diagnostics.append(
                        _diagnostic(
                            referer,
                            path,
                            f"import: cannot read file: {exc}",
                        )
                    )
                return None
            try:
                doc = kdl_parse(source)
            except KDLParseError as exc:
                if referer is not None:
                    self.diagnostics.append(
                        _diagnostic(
                            referer,
                            path,
                            f"import: parse error: {exc.msg}",
                            code="E000",
                        )
                    )
                return None
            nodes = list(doc.nodes)
            _register_sources(nodes, path, self.ctx)
            if lint_imported:
                from ssc_codegen.core.linter import lint_module

                self.diagnostics.extend(lint_module(doc, str(path)))

        unit = SourceUnit(path=path, nodes=nodes)
        self.units[path] = unit
        self.active.append(path)
        try:
            self._index_exports(unit)
            self._resolve_unit_imports(unit)
        finally:
            self.active.pop()
        return unit

    def _index_exports(self, unit: SourceUnit) -> None:
        for node in unit.nodes:
            if node.name == "import":
                continue
            symbols = _node_symbols(node, unit.path)
            for symbol in symbols:
                key = (symbol.kind, symbol.name)
                if key in unit.exports:
                    continue
                unit.exports[key] = symbol
                unit.export_nodes[symbol] = node
                unit.scope[key] = symbol
                unit.ordered_roots.append(symbol)

    def _resolve_unit_imports(self, unit: SourceUnit) -> None:
        root_order: list[SymbolId] = []
        seen_paths: set[Path] = set()
        for node in unit.nodes:
            if node.name != "import":
                root_order.extend(_node_symbols(node, unit.path))
                continue
            if not node.args:
                continue
            raw_path = str(node.args[0].value)
            imported_path = (unit.path.parent / raw_path).resolve()
            if imported_path in seen_paths:
                self.diagnostics.append(
                    _diagnostic(
                        node,
                        unit.path,
                        f"duplicate import path: {raw_path}",
                        hint="combine symbols into one import block",
                    )
                )
                continue
            seen_paths.add(imported_path)
            if imported_path in self.active:
                chain = " -> ".join(
                    str(p) for p in [*self.active, imported_path]
                )
                self.diagnostics.append(
                    _diagnostic(
                        node,
                        unit.path,
                        f"circular import detected: {chain}",
                    )
                )
                continue
            if not imported_path.is_file():
                self.diagnostics.append(
                    _diagnostic(
                        node,
                        unit.path,
                        f"import: file not found: {imported_path}",
                    )
                )
                continue
            imported = self._load_unit(imported_path, referer=node)
            if imported is None:
                continue
            for child in node.children:
                item = _import_item(child)
                if item is None:
                    continue
                kind, name = item
                symbol = imported.exports.get(item)
                if symbol is None:
                    same_name = sorted(
                        export_kind
                        for export_kind, export_name in imported.exports
                        if export_name == name
                    )
                    hint = ""
                    if same_name:
                        hint = f"use ({same_name[0]}){name}"
                    else:
                        hint = "only declarations local to the imported file can be imported"
                    self.diagnostics.append(
                        _diagnostic(
                            child,
                            unit.path,
                            f"{kind} '{name}' is not declared in {imported_path}",
                            hint=hint,
                        )
                    )
                    continue
                previous = unit.scope.get(item)
                if previous is not None and previous != symbol:
                    self.diagnostics.append(
                        _diagnostic(
                            child,
                            unit.path,
                            f"imported {kind} '{name}' conflicts with {previous.path}",
                        )
                    )
                    continue
                unit.scope[item] = symbol
                root_order.append(symbol)
        unit.ordered_roots = root_order

    def _lookup(
        self,
        unit: SourceUnit,
        kind: str,
        name: str,
        node: KdlNode,
        *,
        label: str,
    ) -> SymbolId | None:
        symbol = unit.scope.get((kind, name))
        if symbol is not None:
            return symbol
        report_key = (id(node), kind, name)
        if report_key not in self._reported_refs:
            self._reported_refs.add(report_key)
            self.diagnostics.append(
                _diagnostic(
                    node,
                    unit.path,
                    f"{label} references {kind} '{name}' which is not visible in this file",
                    hint=f"add `({kind}){name}` to an import block",
                    code="E300",
                )
            )
        return None

    def _is_declared(self, kind: str, name: str) -> bool:
        return any((kind, name) in unit.exports for unit in self.units.values())

    def _dependencies(self, symbol: SymbolId) -> list[SymbolId]:
        unit = self.units[symbol.path]
        node = unit.export_nodes[symbol]
        dependencies: list[SymbolId] = []
        seen: set[SymbolId] = set()

        def add(value: SymbolId | None) -> None:
            if value is not None and value != symbol and value not in seen:
                seen.add(value)
                dependencies.append(value)

        if symbol.kind == "extension":
            return dependencies

        for current in _walk([node]):
            if current.name.startswith("!"):
                ref = current.name[1:]
                namespace = ref.split(".", 1)[0]
                add(
                    self._lookup(
                        unit,
                        "extension",
                        namespace,
                        current,
                        label=f"custom operation '{ref}'",
                    )
                )
            if current.name == "nested" and current.args:
                name = str(current.args[0].value)
                add(self._lookup(unit, "struct", name, current, label="nested"))
            if current.name == "jsonify" and current.args:
                name = str(current.args[0].value)
                add(self._lookup(unit, "json", name, current, label="jsonify"))
            if current.name == "@request":
                response = current.get_prop("response")
                if response:
                    add(
                        self._lookup(
                            unit,
                            "json",
                            str(response),
                            current,
                            label="@request",
                        )
                    )
            if current.name == "@error" and len(current.args) >= 2:
                name = str(current.args[1].value)
                add(self._lookup(unit, "json", name, current, label="@error"))

            define = unit.scope.get(("define", current.name))
            if define is not None and current is not node:
                add(define)
            elif current is not node and self._is_declared(
                "define", current.name
            ):
                self._lookup(
                    unit,
                    "define",
                    current.name,
                    current,
                    label=f"pipeline operation '{current.name}'",
                )
            values = [arg.value for arg in current.args]
            if (
                current is node
                and symbol.kind == "define"
                and not node.children
                and symbol.name in node.properties
            ):
                values.append(node.properties[symbol.name].value)
            else:
                values.extend(
                    value.value for value in current.properties.values()
                )
            for raw in values:
                if not isinstance(raw, str):
                    continue
                exact = unit.scope.get(("define", raw))
                if exact is not None:
                    add(exact)
                for match in _DEFINE_TEMPLATE_RE.finditer(raw):
                    template = unit.scope.get(("define", match.group(1)))
                    if template is not None:
                        add(template)

        if symbol.kind == "json":
            self._json_dependencies(unit, node.children, add, set())
        return dependencies

    def _json_dependencies(
        self,
        unit: SourceUnit,
        fields: Sequence[KdlNode],
        add,
        visiting_defines: set[SymbolId],
    ) -> None:
        for field_node in fields:
            define = unit.scope.get(("define", field_node.name))
            if not field_node.args and define is not None:
                add(define)
                if define not in visiting_defines:
                    visiting_defines.add(define)
                    define_node = self.units[define.path].export_nodes[define]
                    self._json_dependencies(
                        self.units[define.path],
                        define_node.children,
                        add,
                        visiting_defines,
                    )
                continue
            if not field_node.args and self._is_declared(
                "define", field_node.name
            ):
                self._lookup(
                    unit,
                    "define",
                    field_node.name,
                    field_node,
                    label=f"json field expansion '{field_node.name}'",
                )
                continue
            type_name = ""
            for arg in field_node.args:
                value = str(arg.value)
                if not value.startswith("@"):
                    type_name = value.rstrip("?")
                    break
            if not type_name or type_name in _JSON_PRIMITIVES:
                continue
            add(
                self._lookup(
                    unit,
                    "json",
                    type_name,
                    field_node,
                    label=f"json field '{field_node.name}'",
                )
            )


def resolve_explicit_imports(
    top_nodes: list[KdlNode],
    source_path: Path | None,
    ctx: ParseContext,
    diagnostics: list[ReadDiagnostic],
) -> list[KdlNode]:
    """Resolve mandatory typed imports and return a merged, dependency-ordered node list.

    Traverses the import graph, verifies that imported symbols exist in their source
    files and match declared type annotations, detects circular dependencies (`E300`),
    and orders imported definitions topologically ahead of consumers.

    Args:
        top_nodes: Sequence of top-level KDL nodes from the root document.
        source_path: Canonical filesystem path to the root schema file.
        ctx: Global parse context for storing file origin mappings.
        diagnostics: Output list receiving import validation errors and warnings.

    Returns:
        Flattened list of KDL nodes with all imported definitions resolved and ordered.
    """
    import_nodes = [node for node in top_nodes if node.name == "import"]
    if not import_nodes:
        return top_nodes
    if source_path is None:
        for node in import_nodes:
            diagnostics.append(
                ReadDiagnostic(
                    message="Cannot use 'import' when parsing from string without a file path",
                    severity=Severity.ERROR,
                    span=node.span,
                    path="",
                    code="E003",
                )
            )
        return [node for node in top_nodes if node.name != "import"]
    return _Resolver(top_nodes, source_path, ctx, diagnostics).resolve()
