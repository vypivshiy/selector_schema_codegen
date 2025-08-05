"""EXPERIMENTAL FEATURE: compile ssc_gen config in runtime and run

WARNING:

    Do not use this feature in real projects, this module used for testing purposes
"""
# 

from ssc_codegen.compiler import Compiler
from ssc_codegen.converters.py_parsel import CONVERTER
import httpx
import pprint


if __name__ == '__main__':
    compiler = Compiler.from_file("booksToScrape.py", converter=CONVERTER)
    resp = httpx.get("https://books.toscrape.com/")

    pprint.pprint(
        compiler.run_parse("CataloguePage", resp.text),
        compact=True,
    )
