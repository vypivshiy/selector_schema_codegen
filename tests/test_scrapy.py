import pytest

from parsers.books_scrapy import Book, BooksCatalogue

from fixtures import page_books_catalogue, page_book, fail_page, BOOK_RESULT, BOOK_CATALOGUE_RESULT
from scrapy.http.response.html import HtmlResponse
from scrapy.http.request import Request


def mock_scrapy_response(content: str):
    req = Request(url="https://example.com")
    resp = HtmlResponse("https://example.com", body=content, request=req, encoding="utf-8")
    return resp


def test_parse_catalogue(page_books_catalogue):
    resp = mock_scrapy_response(page_books_catalogue)
    assert BooksCatalogue(resp).parse().view()[:3] == BOOK_CATALOGUE_RESULT


def test_parse_book(page_book):
    resp = mock_scrapy_response(page_book)

    assert Book(resp).parse().view() == BOOK_RESULT


def test_fail_assert(fail_page):
    resp = mock_scrapy_response(fail_page)

    with pytest.raises(AssertionError):
        Book(resp).parse().view()
