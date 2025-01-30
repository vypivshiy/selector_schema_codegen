"""example usage API interface"""
if __name__ == '__main__':
    # base ast builder
    from ssc_codegen.ast_builder import build_ast_module
    # build-in converter
    from ssc_codegen.converters.go_goquery import converter
    # runtime import module and parse
    # WARNING: DO NOT PASS UNKNOWN MODULES FOR SECURITY REASONS
    # IT COMPILE AND EXEC PYTHON CODE FROM FILE IN RUNTIME
    ast = build_ast_module(
        'schemas/booksToScrape.py',
        # set true, if target language required hover top on class/function docstring
        # (dart, js, go...)
        docstring_class_top=True
    )
    # optional set debug token comments
    # useful for development and fix generated code parts
    # should be starts as comment prefix
    # converter.set_debug_prefix("// ")

    # python comment prefix
    # converter.set_debug_prefix('# ')

    # disable add debug comments
    # converter.disable_debug()
    # generate code (formatting exclude)
    code = converter.convert_program(ast)
    print("\n".join(code))
