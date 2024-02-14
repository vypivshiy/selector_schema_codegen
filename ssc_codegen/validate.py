from typing import Optional, TypeVar, TYPE_CHECKING

from ssc_codegen.objects import VariableState, TokenType, Expression
from ssc_codegen.document import Document

__all__ = ["assert_"]

T_DOCUMENT = TypeVar("T_DOCUMENT", bound=Document)


class Assert:
    """assert expr realisation"""
    @classmethod
    def css(cls, doc: T_DOCUMENT, query: str, msg: Optional[str] = None):
        """pass assert if css not return None/null"""
        doc._is_valid_variable(VariableState.DOCUMENT)
        e = Expression(
            doc.counter,
            VariableState.NONE,
            TokenType.OP_ASSERT_CSS,
            (query,),
            msg
        )
        doc.append(e)
        return doc

    @classmethod
    def xpath(cls, doc: T_DOCUMENT, query: str, msg: Optional[str] = None):
        """pass assert if xpath not return None/null"""
        doc._is_valid_variable(VariableState.DOCUMENT)
        e = Expression(
            doc.counter,
            VariableState.NONE,
            TokenType.OP_ASSERT_XPATH,
            (query,),
            msg
        )
        doc.append(e)
        return doc

    @classmethod
    def equal(cls, doc: T_DOCUMENT, value: str, msg: Optional[str] = None):
        """pass assert if value equal (==)"""
        doc._is_valid_variable(VariableState.STRING)
        e = Expression(
            doc.counter,
            VariableState.NONE,
            TokenType.OP_ASSERT_EQUAL,
            (value,),
            msg
        )
        doc.append(e)
        return doc

    @classmethod
    def re(cls, doc: T_DOCUMENT, expr: str, msg: Optional[str] = None):
        """pass assert if regex not return None/null"""
        doc._is_valid_variable(VariableState.STRING)
        e = Expression(
            doc.counter,
            VariableState.NONE,
            TokenType.OP_ASSERT_RE_MATCH,
            (expr,),
            msg
        )
        doc.append(e)
        return doc

    @classmethod
    def contains(cls, doc: T_DOCUMENT, value: str, msg: Optional[str] = None):
        """pass assert if string contains value"""
        doc._is_valid_variable(VariableState.STRING)
        e = Expression(
            doc.counter,
            VariableState.NONE,
            TokenType.OP_ASSERT_CONTAINS,
            (value,),
            msg
        )
        doc.append(e)
        return doc


assert_ = Assert
