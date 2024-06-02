from ssc_codegen.converters.generator import CodeGenerator
from ssc_codegen.converters.python import PythonCodeConverter
from ssc_codegen.tokens import TokenType

converter = PythonCodeConverter()

XPATH_ERR_MSG = "selectolax not support xpath"


@converter(TokenType.OP_XPATH)
def op_xpath(_):
    raise NotImplementedError("bs4 not support xpath")


@converter(TokenType.OP_XPATH_ALL)
def op_xpath_all(_):
    raise NotImplementedError("bs4 not support xpath")


@converter(TokenType.OP_ASSERT_XPATH)
def op_assert_xpath(_):
    raise NotImplementedError("bs4 not support xpath")


code_generator = CodeGenerator(
    templates_path="ssc_codegen.converters.templates.py",
    base_struct_path="selectolax",
    converter=converter,
)
