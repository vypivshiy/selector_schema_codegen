import pprint

import requests  # OR ANY http lib

from books_to_scrape import Book, BooksCatalogue, Links


def main():
    resp = requests.get("https://example.com")

    # check pre-validate document
    try:
        Book(resp.text).parse()
    except AssertionError:
        print("WRONG document")

    resp = requests.get("http://books.toscrape.com")
    # get books catalogue
    print("BOOK CATALOGUE")
    catalogue = BooksCatalogue(resp.text).parse().view()
    pprint.pprint(catalogue, compact=True)
    print()

    # get book page
    url = catalogue[0]['url']
    resp = requests.get(url)
    # http://books.toscrape.com/catalogue/
    book = Book(resp.text).parse().view()
    print("BOOK")
    pprint.pprint(book, compact=True)
    print()

    # get <a> links
    links = Links(resp.text).parse().view()
    print("LINKS")
    pprint.pprint(links, compact=True)
    print()


if __name__ == '__main__':
    main()