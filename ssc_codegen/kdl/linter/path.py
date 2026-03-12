"""Path tracking for error context"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator


class PathTracker:
    """Отслеживание пути в AST (breadcrumb)"""
    
    def __init__(self):
        self._segments: list[str] = []
    
    def push(self, segment: str) -> None:
        """Добавить сегмент пути"""
        self._segments.append(segment)
    
    def pop(self) -> None:
        """Удалить последний сегмент"""
        if self._segments:
            self._segments.pop()
    
    @property
    def current(self) -> str:
        """Текущий путь"""
        return " > ".join(self._segments) if self._segments else "<module>"
    
    @contextmanager
    def scope(self, segment: str) -> Generator[None, None, None]:
        """Context manager для автоматического push/pop"""
        self.push(segment)
        try:
            yield
        finally:
            self.pop()
