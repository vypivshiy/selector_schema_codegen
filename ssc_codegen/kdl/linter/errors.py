"""Error collection and reporting"""

from __future__ import annotations

from tree_sitter import Node

from ssc_codegen.kdl.linter.types import LintError, ErrorCode


class ErrorCollector:
    """Сбор ошибок с контекстом"""
    
    def __init__(self):
        self._errors: list[LintError] = []
    
    def error(
        self,
        node: Node,
        code: ErrorCode,
        message: str,
        hint: str,
        path: str,
    ) -> None:
        """Добавить ошибку"""
        self._errors.append(LintError(
            code=code,
            message=message,
            hint=hint,
            path=path,
            line=node.start_point.row + 1,
            col=node.start_point.column + 1,
            severity="error",
        ))
    
    def warning(
        self,
        node: Node,
        code: ErrorCode,
        message: str,
        hint: str,
        path: str,
    ) -> None:
        """Добавить warning"""
        self._errors.append(LintError(
            code=code,
            message=message,
            hint=hint,
            path=path,
            line=node.start_point.row + 1,
            col=node.start_point.column + 1,
            severity="warning",
        ))
    
    @property
    def errors(self) -> list[LintError]:
        return self._errors
