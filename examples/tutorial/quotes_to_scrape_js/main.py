from schema import Main
import httpx
import pprint

if __name__ == "__main__":
    resp = httpx.get("https://quotes.toscrape.com/js/")
    pprint.pprint(Main(resp.text).parse())
