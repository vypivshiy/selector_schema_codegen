# validation collection
from ssc_codegen.document.base import BaseDocument, TokenType, TypeVariableState
from ssc_codegen.utils.selector_validators import (
    validate_css_query,
    validate_xpath_query,
)


class DocumentOpAssert(BaseDocument):
    def assert_css(self, query: str, msg: str = ""):
        validate_css_query(query)
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(TokenType.OP_ASSERT_CSS, args=(query, msg))
        return self

    def assert_xpath(self, query: str, msg: str = ""):
        validate_xpath_query(query)
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(TokenType.OP_ASSERT_XPATH, args=(query, msg))

        return self

    def assert_eq(self, item: str, msg: str = ""):
        self._test_type_state_expr(
            TypeVariableState.STRING, TypeVariableState.NONE
        )

        self._add_expr(TokenType.OP_ASSERT_EQUAL, args=(item, msg))
        return self

    def assert_in(self, item: str, msg: str = ""):
        self._test_type_state_expr(TypeVariableState.LIST_STRING)

        self._add_expr(TokenType.OP_ASSERT_CONTAINS, args=(item, msg))
        return self

    def assert_re(self, pattern: str, msg: str = ""):
        self._test_type_state_expr(TypeVariableState.STRING)

        self._add_expr(TokenType.OP_ASSERT_RE_MATCH, args=(pattern, msg))
        return self
