import pprint

import requests  # or any http lib
from booksToScrape import CataloguePage


if __name__ == "__main__":
    resp = requests.get("https://books.toscrape.com/")

    pprint.pprint(CataloguePage(resp.text).parse(), compact=True)
