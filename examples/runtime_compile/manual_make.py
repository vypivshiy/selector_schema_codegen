"""example usage API interface"""

from ssc_codegen.ast_build import build_ast_module_parser
from ssc_codegen.cli.code_callbacks import CB_JS_CODE
# build-in converter
from ssc_codegen.converters.js_pure import CONVERTER

if __name__ == "__main__":
    # base ast builder

    # runtime import module and parse
    # WARNING: DO NOT PASS UNKNOWN MODULES FOR SECURITY REASONS
    # IT COMPILE AND EXEC PYTHON CODE FROM FILE IN RUNTIME
    ast = build_ast_module_parser(
        "booksToScrape.py",
        # set true, if target language required hover top on class/function docstring
        # (dart, js, go...)
    )

    code_parts = CONVERTER.convert_program(ast)
    # assembly code parts (without formatting)
    # print('\n'.join(code))

    code = CB_JS_CODE(code_parts)
    print(code)
