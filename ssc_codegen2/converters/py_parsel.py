from ssc_codegen2.converters.generator import CodeGenerator
from ssc_codegen2.converters.python import PythonCodeConverter

converter = PythonCodeConverter()
code_generator = CodeGenerator(
    templates_path='ssc_codegen2.converters.templates.py',
    base_struct_path='parsel',
    converter=converter)
