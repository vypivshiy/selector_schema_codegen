import pprint

import requests  # OR ANY http lib

from parsers.booksToScrape import CataloguePage


def main():
    resp = requests.get("https://example.com")

    # check pre-validate document
    # try:
    #     CataloguePage(resp.text).parse()
    # except AssertionError:
    #     print("WRONG document")

    resp = requests.get("http://books.toscrape.com")
    # get books catalogue
    print("BOOK CATALOGUE")
    from time import time
    st = time()
    catalogue = CataloguePage(resp.text).parse()
    print(time()-st)
    pprint.pprint(catalogue, compact=True)
    print()


if __name__ == '__main__':
    main()