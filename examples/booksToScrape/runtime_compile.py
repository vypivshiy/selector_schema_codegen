# EXPERIMENTAL FEATURE: compile ssc_gen config in runtime and run

from ssc_codegen.compiler import Compiler
from ssc_codegen.converters.py_parsel import converter
import httpx
import pprint


if __name__ == '__main__':
    compiler = Compiler.from_file("schemas/booksToScrape.py", converter=converter)
    resp = httpx.get("https://books.toscrape.com/")

    pprint.pprint(
        compiler.run_parse("CataloguePagef", resp.text),
        compact=True,
    )
