import pprint

import httpx  # or any http lib
from booksToScrape import CataloguePage


if __name__ == "__main__":
    resp = httpx.get("https://books.toscrape.com/")

    pprint.pprint(CataloguePage(resp.text).parse(), compact=True)
