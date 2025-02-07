from booksToScrapeExtend import CataloguePage
import httpx

if __name__ == '__main__':
    resp = httpx.get('https://books.toscrape.com/')
    data = CataloguePage(resp.text).parse()
    print()