import httpx
from schema import Book, BookCatalogue

if __name__ == "__main__":
    resp = httpx.get("http://books.toscrape.com/index.html")
    sc = BookCatalogue(resp.text)
    sc.parse()
    data = sc.view()
    print(*data, sep="\n")
    print("---")
    resp2 = httpx.get(
        "http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )
    sc2 = Book(resp2.text)
    sc2.parse()
    print(*sc2.view(), sep="\n")
