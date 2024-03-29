# TODO remove
import pathlib

from ssc_codegen.template import render_code

from books_parser import Book, BooksCatalogue

if __name__ == '__main__':
    import os

    from ssc_codegen.converters.py_parsel import converter as parsel_converter
    from ssc_codegen.converters.py_bs4 import converter as bs4_converter
    from ssc_codegen.converters.py_selectolax import converter as slax_converter
    from ssc_codegen.converters.py_scrapy import converter as scrapy_converter
    from ssc_codegen.converters.dart_universal_html import converter as dart_converter

    pathlib.Path("parsers/books_parsel.py").write_text(render_code(parsel_converter, Book(), BooksCatalogue()))
    (pathlib
    .Path("parsers/books_parsel_xpath.py")
    .write_text(
        render_code(parsel_converter, Book(), BooksCatalogue(), xpath_to_css=True)
    ))
    pathlib.Path("parsers/books_bs4.py").write_text(render_code(bs4_converter, Book(), BooksCatalogue()))
    pathlib.Path("parsers/books_slax.py").write_text(render_code(slax_converter, Book(), BooksCatalogue()))
    pathlib.Path("parsers/books_scrapy.py").write_text(render_code(scrapy_converter, Book(), BooksCatalogue()))

    os.system(
        'black parsers/books_parsel.py parsers/books_bs4.py parsers/books_slax.py parsers/books_scrapy.py '
        'parsers/books_parsel_xpath.py')

    # dart
    pathlib.Path("../test_dart/test/schema.dart").write_text(render_code(dart_converter, Book(), BooksCatalogue()))
    os.system("dart format ../test_dart/test/schema.dart")
