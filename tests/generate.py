import pathlib

from ssc_codegen.template import render_code

from books_parser import Book, BooksCatalogue


if __name__ == '__main__':
    import os

    from ssc_codegen.converters.py_parsel import converter as parsel_converter
    from ssc_codegen.converters.py_bs4 import converter as bs4_converter
    from ssc_codegen.converters.py_selectolax import converter as slax_converter

    pathlib.Path("parsers/books_parsel.py").write_text(render_code(parsel_converter, Book(), BooksCatalogue()))
    pathlib.Path("parsers/books_bs4.py").write_text(render_code(bs4_converter, Book(), BooksCatalogue()))
    pathlib.Path("parsers/books_slax.py").write_text(render_code(slax_converter, Book(), BooksCatalogue()))

    os.system('black parsers/books_parsel.py parsers/books_bs4.py parsers/books_slax.py')
