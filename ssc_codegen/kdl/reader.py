from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from .parser import (
    CSTArgEntry,
    CSTDocument,
    CSTNode,
    CSTPropEntry,
    CSTValue,
    CSTIdentifier,
    Span,
)


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# ReadDiagnostic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadDiagnostic:
    message: str
    severity: Severity
    span: Span
    path: str = ""
    hint: str = ""
    code: str = ""
    label: str | None = None
    notes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# DiagnosticCollector
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticCollector:
    _diagnostics: list[ReadDiagnostic] = field(
        default_factory=list,
    )
    _path_segments: list[str] = field(default_factory=list)

    @property
    def diagnostics(self) -> list[ReadDiagnostic]:
        return self._diagnostics

    @property
    def path(self) -> str:
        return "/".join(self._path_segments)

    def push(self, segment: str) -> None:
        self._path_segments.append(segment)

    def pop(self) -> None:
        self._path_segments.pop()

    def error(
        self,
        message: str,
        *,
        span: Span,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        self._diagnostics.append(
            ReadDiagnostic(
                message=message,
                severity=Severity.ERROR,
                span=span,
                path=self.path,
                hint=hint,
                code=code,
                label=label,
                notes=tuple(notes) if notes else (),
            )
        )

    def warning(
        self,
        message: str,
        *,
        span: Span,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        self._diagnostics.append(
            ReadDiagnostic(
                message=message,
                severity=Severity.WARNING,
                span=span,
                path=self.path,
                hint=hint,
                code=code,
                label=label,
                notes=tuple(notes) if notes else (),
            )
        )


# ---------------------------------------------------------------------------
# KdlArg
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KdlArg:
    value: Any
    span: Span
    is_identifier: bool


# ---------------------------------------------------------------------------
# KdlNode
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KdlNode:
    name: str
    type_annotation: str | None
    args: tuple[KdlArg, ...]
    properties: MappingProxyType[str, KdlArg]
    children: tuple[KdlNode, ...]
    span: Span

    @classmethod
    def from_cst(cls, node: CSTNode) -> KdlNode:
        args: list[KdlArg] = []
        properties: dict[str, KdlArg] = {}

        for entry in node.entries:
            if isinstance(entry, CSTArgEntry):
                is_id = isinstance(entry.value, CSTIdentifier)
                args.append(
                    KdlArg(
                        value=entry.value.value,
                        span=entry.span,
                        is_identifier=is_id,
                    )
                )
            elif isinstance(entry, CSTPropEntry):
                is_id = isinstance(entry.value, CSTIdentifier)
                properties[entry.key.value] = KdlArg(
                    value=entry.value.value,
                    span=entry.span,
                    is_identifier=is_id,
                )

        children = tuple(cls.from_cst(c) for c in node.children)
        type_ann = node.type_annotation.raw if node.type_annotation else None

        return cls(
            name=node.name.value,
            type_annotation=type_ann,
            args=tuple(args),
            properties=MappingProxyType(properties),
            children=children,
            span=node.span,
        )


# ---------------------------------------------------------------------------
# WalkContext
# ---------------------------------------------------------------------------


T_node = TypeVar("T_node")


@dataclass
class WalkContext(Generic[T_node]):
    walker: Walker[T_node]
    reader: Reader[T_node, Any]
    node: KdlNode
    parent: KdlNode | None
    siblings: tuple[KdlNode, ...]
    index: int
    processed: list[T_node]
    collector: DiagnosticCollector

    def error(
        self,
        message: str,
        *,
        span: Span | None = None,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        self.collector.error(
            message,
            span=span if span is not None else self.node.span,
            hint=hint,
            code=code,
            label=label,
            notes=notes,
        )

    def warning(
        self,
        message: str,
        *,
        span: Span | None = None,
        hint: str = "",
        code: str = "",
        label: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        self.collector.warning(
            message,
            span=span if span is not None else self.node.span,
            hint=hint,
            code=code,
            label=label,
            notes=notes,
        )

    def push(self, segment: str) -> None:
        self.collector.push(segment)

    def pop(self) -> None:
        self.collector.pop()

    def walk_children(self) -> list[T_node]:
        return self.walker.walk_children(self.node, self)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


R = TypeVar("R")


class Reader(ABC, Generic[T_node, R]):
    @abstractmethod
    def on_node(
        self,
        name: str,
        args: tuple[KdlArg, ...],
        properties: Mapping[str, KdlArg],
        children: tuple[KdlNode, ...],
        ctx: WalkContext[T_node],
    ) -> T_node: ...

    @abstractmethod
    def error_node(
        self,
        message: str,
        ctx: WalkContext[T_node],
    ) -> T_node: ...

    @abstractmethod
    def finalize(
        self,
        nodes: list[T_node],
        diagnostics: list[ReadDiagnostic],
    ) -> R: ...


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------


class Walker(Generic[T_node]):
    def __init__(
        self,
        reader: Reader[T_node, Any],
        *,
        strict: bool = False,
    ) -> None:
        self._reader = reader
        self._strict = strict

    @property
    def strict(self) -> bool:
        return self._strict

    def walk(
        self,
        node: KdlNode,
        parent: KdlNode | None = None,
        siblings: tuple[KdlNode, ...] = (),
        index: int = 0,
        processed: list[T_node] | None = None,
        collector: DiagnosticCollector | None = None,
    ) -> T_node:
        _collector = (
            collector if collector is not None else DiagnosticCollector()
        )
        _processed = processed if processed is not None else []

        ctx = WalkContext[T_node](
            walker=self,
            reader=self._reader,
            node=node,
            parent=parent,
            siblings=siblings,
            index=index,
            processed=_processed,
            collector=_collector,
        )

        _collector.push(node.name)
        try:
            result = self._reader.on_node(
                name=node.name,
                args=node.args,
                properties=node.properties,
                children=node.children,
                ctx=ctx,
            )
        except Exception as exc:
            if self._strict:
                result = self._reader.error_node(str(exc), ctx)
            else:
                raise
        finally:
            _collector.pop()

        _processed.append(result)
        return result

    def walk_children(
        self,
        parent: KdlNode,
        parent_ctx: WalkContext[T_node] | None = None,
    ) -> list[T_node]:
        collector = (
            parent_ctx.collector
            if parent_ctx is not None
            else DiagnosticCollector()
        )
        results: list[T_node] = []

        for i, child in enumerate(parent.children):
            self.walk(
                node=child,
                parent=parent,
                siblings=parent.children,
                index=i,
                processed=results,
                collector=collector,
            )

        return results

    def walk_document(
        self,
        document: CSTDocument,
    ) -> tuple[list[T_node], list[ReadDiagnostic]]:
        collector = DiagnosticCollector()
        children = tuple(KdlNode.from_cst(n) for n in document.nodes)
        results: list[T_node] = []

        for i, child in enumerate(children):
            self.walk(
                node=child,
                parent=None,
                siblings=children,
                index=i,
                processed=results,
                collector=collector,
            )

        return results, collector.diagnostics


# ---------------------------------------------------------------------------
# parse_into
# ---------------------------------------------------------------------------


def parse_into(
    document: CSTDocument,
    reader: Reader[T_node, R],
    *,
    strict: bool = False,
) -> tuple[R, list[ReadDiagnostic]]:
    walker = Walker(reader, strict=strict)
    nodes, diagnostics = walker.walk_document(document)
    result = reader.finalize(nodes, diagnostics)
    return result, diagnostics


__all__ = [
    "DiagnosticCollector",
    "KdlArg",
    "KdlNode",
    "ReadDiagnostic",
    "Reader",
    "Severity",
    "WalkContext",
    "Walker",
    "parse_into",
]
