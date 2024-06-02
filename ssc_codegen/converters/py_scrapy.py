from ssc_codegen.converters.generator import CodeGenerator
from ssc_codegen.converters.python import PythonCodeConverter

converter = PythonCodeConverter()
code_generator = CodeGenerator(
    templates_path='ssc_codegen.converters.templates.py',
    base_struct_path='scrapy',
    converter=converter)
