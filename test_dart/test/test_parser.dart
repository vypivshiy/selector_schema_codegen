import 'package:test/test.dart';
import 'dart:io';

import 'schema.dart';

final bookResult = <String, dynamic>{
  'description':
      "It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary with this special edition. Silverstein's humorous and creative verse can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still and read these rhythmic words and laugh and smile and love th It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary with this special edition. Silverstein's humorous and creative verse can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still and read these rhythmic words and laugh and smile and love that Silverstein. Need proof of his genius? RockabyeRockabye baby, in the treetopDon't you know a treetopIs no safe place to rock?And who put you up there,And your cradle, too?Baby, I think someone down here'sGot it in for you. Shel, you never sounded so good. ...more",
  'title': 'A Light in the Attic',
  'price': '£51.77',
  'upc': 'a897fe39b1053632',
  'raw_table_values': [
    'a897fe39b1053632',
    'Books',
    '£51.77',
    '£51.77',
    '£0.00',
    'In stock (22 available)',
    '0'
  ]
};

final catalogueResult = [
  {
    'url':
        'https://books.toscrape.com/catalogue/catalogue/a-light-in-the-attic_1000/index.html',
    'title': 'A Light in the Attic',
    'price': '51.77',
    'image':
        'https://books.toscrape.commedia/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg',
    'rating': 'Three'
  },
  {
    'url':
        'https://books.toscrape.com/catalogue/catalogue/tipping-the-velvet_999/index.html',
    'title': 'Tipping the Velvet',
    'price': '53.74',
    'image':
        'https://books.toscrape.commedia/cache/26/0c/260c6ae16bce31c8f8c95daddd9f4a1c.jpg',
    'rating': 'One'
  },
  {
    'url':
        'https://books.toscrape.com/catalogue/catalogue/soumission_998/index.html',
    'title': 'Soumission',
    'price': '50.10',
    'image':
        'https://books.toscrape.commedia/cache/3e/ef/3eef99c9d9adef34639f510662022830.jpg',
    'rating': 'One'
  }
];

void main() {
  test('Book', () async {
    final String bookPage =
        File('test/book.html').readAsStringSync();
    expect(Book(bookPage).parse().view(), equals(bookResult));
  });
  test('BookCatalogue', () async {
    final String bookCatalogue =
        File('test/books_cataloque.html').readAsStringSync();

    expect(BooksCatalogue(bookCatalogue).parse().view().getRange(0, 3),
        equals(catalogueResult));
  });

  test('FailPreValidate', () async {
    final String failPage =
        File('test/fail_page.html').readAsStringSync();

    expect(() {Book(failPage).parse();}, throwsA(isA<AssertionError>()));
  });
}
