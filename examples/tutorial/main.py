import httpx
from schema3 import MainCatalogue
from schema4 import ProductDescription
import pprint

def main() -> None:
    resp = httpx.get("https://books.toscrape.com/").text
    catalogue = MainCatalogue(resp).parse()
    # break if next_page == None
    while catalogue['next_page']:
        for book in catalogue["books"]:
            print(book["name"])
            book_resp = httpx.get(book["url"]).text
            pprint.pprint(ProductDescription(book_resp).parse(), sort_dicts=True)
        resp = httpx.get(catalogue['next_page']).text
        catalogue = MainCatalogue(resp).parse()


if __name__ == '__main__':
    main()
