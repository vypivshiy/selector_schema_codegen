from ssc_codegen.document.base import (
    BaseDocument,
    Expression,
    TokenType,
    TypeVariableState,
)
from ssc_codegen.utils.selector_validators import (
    css_to_xpath,
    validate_css_query,
    validate_xpath_query,
    xpath_to_css,
)


class DocumentOpSelectorConverter(BaseDocument):
    def convert_css_to_xpath(
        self, xpath_prefix: str = "descendant-or-self::"
    ) -> None:
        """convert all css operations to XPATH (guaranteed)"""
        stack_copy = self._stack_instructions.copy()

        for i, expr in enumerate(self._stack_instructions):
            if expr.TOKEN_TYPE == TokenType.OP_CSS:
                css_query = expr.arguments[0]
                xpath_query = css_to_xpath(css_query, xpath_prefix)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(xpath_query,),
                    TOKEN_TYPE=TokenType.OP_XPATH,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                )

            elif expr.TOKEN_TYPE == TokenType.OP_CSS_ALL:
                css_query = expr.arguments[0]
                xpath_query = css_to_xpath(css_query, xpath_prefix)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(xpath_query,),
                    TOKEN_TYPE=TokenType.OP_XPATH_ALL,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                )

            elif expr.TOKEN_TYPE == TokenType.OP_ASSERT_CSS:
                css_query = expr.arguments[0]
                xpath_query = css_to_xpath(css_query, xpath_prefix)
                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(xpath_query,),
                    TOKEN_TYPE=TokenType.OP_ASSERT_XPATH,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                )
        self._stack_instructions = stack_copy

    def convert_xpath_to_css(self) -> None:
        """convert all css operations to XPATH (works with simple expressions)

        EG OK:

            IN: //div[@class="product_price"]/p[@class="instock availability"]/i

            OUT: div[class="product_price"] > p[class="instock availability"] > i

        EG FAIL:

            IN: //p[contains(@class, "star-rating")]

            OUT: ERROR
        """
        stack_copy = self._stack_instructions.copy()

        for i, expr in enumerate(stack_copy):
            if expr.TOKEN_TYPE == TokenType.OP_XPATH:
                xpath_query = expr.arguments[0]
                css_query = xpath_to_css(xpath_query)

                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(css_query,),
                    TOKEN_TYPE=TokenType.OP_CSS,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                )

            elif expr.TOKEN_TYPE == TokenType.OP_XPATH_ALL:
                xpath_query = expr.arguments[0]
                css_query = xpath_to_css(xpath_query)

                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(css_query,),
                    TOKEN_TYPE=TokenType.OP_CSS_ALL,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                )

            elif expr.TOKEN_TYPE == TokenType.OP_ASSERT_XPATH:
                xpath_query = expr.arguments[0]
                css_query = xpath_to_css(xpath_query)

                stack_copy[i] = Expression(
                    num=expr.num,
                    arguments=(css_query,),
                    TOKEN_TYPE=TokenType.OP_ASSERT_CSS,
                    VARIABLE_TYPE=expr.VARIABLE_TYPE,
                )
            self._stack_instructions = stack_copy


class DocumentOpHtmlMany(BaseDocument):
    def css_all(self, query: str):
        """get all elements by css query"""
        validate_css_query(query)
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(
            TokenType.OP_CSS_ALL,
            new_var_state=TypeVariableState.LIST_DOCUMENT,
            args=(query,),
        )
        return self

    def xpath_all(self, query: str):
        """get all elements by xpath query"""
        validate_xpath_query(query)
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(
            TokenType.OP_XPATH_ALL,
            new_var_state=TypeVariableState.LIST_DOCUMENT,
            args=(query,),
        )
        return self


class DocumentOpHtmlSingle(BaseDocument):
    """implemented for Nested fields"""

    def css(self, query: str):
        """get first element by css query"""
        validate_css_query(query)
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(TokenType.OP_CSS, args=(query,))
        return self

    def xpath(self, query: str):
        """get first element by xpath query"""
        validate_xpath_query(query)
        self._test_type_state_expr(TypeVariableState.DOCUMENT)

        self._add_expr(TokenType.OP_XPATH, args=(query,))
        return self


class DocumentOpHtml(
    DocumentOpHtmlSingle, DocumentOpHtmlMany, DocumentOpSelectorConverter
):

    def attr(self, name: str):
        """get attribute value from element"""
        self._test_type_state_expr(
            TypeVariableState.DOCUMENT, TypeVariableState.LIST_DOCUMENT
        )

        #  (name,))
        if self.last_var_type is TypeVariableState.DOCUMENT:
            self._add_expr(
                TokenType.OP_ATTR,
                args=(name,),
                new_var_state=TypeVariableState.STRING,
            )
        elif self.last_var_type is TypeVariableState.LIST_DOCUMENT:
            self._add_expr(
                TokenType.OP_ATTR,
                args=(name,),
                new_var_state=TypeVariableState.LIST_STRING,
            )
        else:
            raise SyntaxError("TODO")
        return self

    def text(self):
        """get inner text from element"""
        self._test_type_state_expr(
            TypeVariableState.DOCUMENT, TypeVariableState.LIST_DOCUMENT
        )

        if self.last_var_type is TypeVariableState.DOCUMENT:
            self._add_expr(
                TokenType.OP_ATTR_TEXT, new_var_state=TypeVariableState.STRING
            )
        elif self.last_var_type is TypeVariableState.LIST_DOCUMENT:
            self._add_expr(
                TokenType.OP_ATTR_TEXT,
                new_var_state=TypeVariableState.LIST_STRING,
            )
        else:
            raise SyntaxError("TODO")
        return self

    def raw(self):
        """get raw element tag"""
        self._test_type_state_expr(
            TypeVariableState.DOCUMENT, TypeVariableState.LIST_DOCUMENT
        )

        if self.last_var_type is TypeVariableState.DOCUMENT:
            self._add_expr(
                TokenType.OP_ATTR_TEXT, new_var_state=TypeVariableState.STRING
            )
        elif self.last_var_type is TypeVariableState.LIST_DOCUMENT:
            self._add_expr(
                TokenType.OP_ATTR_TEXT,
                new_var_state=TypeVariableState.LIST_STRING,
            )
        else:
            raise SyntaxError("TODO")
        return self
