import pytest

from parsers.books_slax import Book, BooksCatalogue

from fixtures import page_books_catalogue, page_book, fail_page, BOOK_RESULT, BOOK_CATALOGUE_RESULT


def test_parse_catalogue(page_books_catalogue):
    assert BooksCatalogue(page_books_catalogue).parse().view()[:3] == BOOK_CATALOGUE_RESULT


def test_parse_book(page_book):
    assert Book(page_book).parse().view() == BOOK_RESULT


def test_fail_assert(fail_page):
    with pytest.raises(AssertionError):
        Book(fail_page).parse().view()
