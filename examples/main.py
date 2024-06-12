import pprint

import requests  # or any http lib
from parsers.booksToScrape import CataloguePage


if __name__ == "__main__":
    resp = requests.get("https://books.toscrape.com/")

    pprint.pprint(CataloguePage(resp).parse(), compact=True)
