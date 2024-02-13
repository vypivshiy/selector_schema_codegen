import pathlib

import pytest


@pytest.fixture(scope='session')
def page_books_catalogue():
    return pathlib.Path('tests/pages/books_cataloque.html').read_text()


@pytest.fixture(scope='session')
def page_book():
    return pathlib.Path("tests/pages/book.html").read_text()


@pytest.fixture(scope='session')
def fail_page():
    return pathlib.Path("tests/pages/fail_asset_page.html").read_text()


BOOK_RESULT = {
    'description': "It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary with this special edition. Silverstein's humorous and creative verse can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still and read these rhythmic words and laugh and smile and love th It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary with this special edition. Silverstein's humorous and creative verse can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still and read these rhythmic words and laugh and smile and love that Silverstein. Need proof of his genius? RockabyeRockabye baby, in the treetopDon't you know a treetopIs no safe place to rock?And who put you up there,And your cradle, too?Baby, I think someone down here'sGot it in for you. Shel, you never sounded so good. ...more",
    'title': 'A Light in the Attic', 'price': '£51.77', 'upc': 'a897fe39b1053632',
    'raw_table_values': ['a897fe39b1053632', 'Books', '£51.77', '£51.77', '£0.00', 'In stock (22 available)', '0']}

BOOK_CATALOGUE_RESULT = [{'url': 'https://books.toscrape.com/catalogue/catalogue/a-light-in-the-attic_1000/index.html',
                          'title': 'A Light in the Attic', 'price': '51.77',
                          'image': 'https://books.toscrape.commedia/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg',
                          'rating': 'Three'},
                         {'url': 'https://books.toscrape.com/catalogue/catalogue/tipping-the-velvet_999/index.html',
                          'title': 'Tipping the Velvet', 'price': '53.74',
                          'image': 'https://books.toscrape.commedia/cache/26/0c/260c6ae16bce31c8f8c95daddd9f4a1c.jpg',
                          'rating': 'One'},
                         {'url': 'https://books.toscrape.com/catalogue/catalogue/soumission_998/index.html',
                          'title': 'Soumission', 'price': '50.10',
                          'image': 'https://books.toscrape.commedia/cache/3e/ef/3eef99c9d9adef34639f510662022830.jpg',
                          'rating': 'One'}]
