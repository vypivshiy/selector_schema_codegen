"""Error collection and reporting"""

from __future__ import annotations

from ssc_codegen.linter._kdl_lang import Node

from ssc_codegen.linter.types import ErrorCode, LintError


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
        *,
        label: str | None = None,
        notes: list[str] | None = None,
        end_line: int | None = None,
        end_col: int | None = None,
    ) -> None:
        """Добавить ошибку"""
        self._errors.append(
            LintError(
                code=code,
                message=message,
                hint=hint,
                path=path,
                line=node.start_point.row + 1,
                col=node.start_point.column + 1,
                end_line=end_line,
                end_col=end_col,
                label=label,
                notes=list(notes or []),
                severity="error",
            )
        )

    def warning(
        self,
        node: Node,
        code: ErrorCode,
        message: str,
        hint: str,
        path: str,
        *,
        label: str | None = None,
        notes: list[str] | None = None,
        end_line: int | None = None,
        end_col: int | None = None,
    ) -> None:
        """Добавить warning"""
        self._errors.append(
            LintError(
                code=code,
                message=message,
                hint=hint,
                path=path,
                line=node.start_point.row + 1,
                col=node.start_point.column + 1,
                end_line=end_line,
                end_col=end_col,
                label=label,
                notes=list(notes or []),
                severity="warning",
            )
        )

    @property
    def errors(self) -> list[LintError]:
        return self._errors
