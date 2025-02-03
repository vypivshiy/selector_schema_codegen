// autogenerated by ssc-gen DO NOT_EDIT
/// Dummy parser config for http://books.toscrape.com/
import 'dart:core';
import 'package:universal_html/html.dart' show Document, LIElement;
import 'package:universal_html/parsing.dart' as html;

typedef TUrls = List<String>;
typedef TUrlsMap = Map<String, String>;
typedef TBooksITEM = ({
  String name,
  String image_url,
  String url,
  String rating,
  int price
});
typedef TBooks = List<TBooksITEM>;
typedef TCataloguePage = ({
  String title,
  TUrls urls,
  TUrlsMap urls_map,
  TBooks books
});

/// fetch add patches and urls from <a> tag
///
/// [
///     "String",
///     "..."
/// ]
class Urls {
  late final Document selector;
  Urls(String rawDocument) {
    selector = html.parseHtmlDocument(rawDocument);
  }
  Urls.fromDocument(Document document) {
    selector = document;
  }
  Urls.fromElement(LIElement element) {
    selector = html.parseHtmlDocument(element.innerHtml as String);
  }
  _splitDoc(value) {
    var value1 = value.querySelectorAll('a');
    return value1;
  }

  _parseItem(value) {
    var value1 = value?.attributes['href'];
    return value1;
  }

  TUrls parse() {
    TUrls items = [];
    for (var e in _splitDoc(selector)) {
      items.add(_parseItem(e));
    }
    return items;
  }
}

///
///
/// {
///     "<K>": "String",
///     "<KN>": "..."
/// }
class UrlsMap {
  late final Document selector;
  UrlsMap(String rawDocument) {
    selector = html.parseHtmlDocument(rawDocument);
  }
  UrlsMap.fromDocument(Document document) {
    selector = document;
  }
  UrlsMap.fromElement(LIElement element) {
    selector = html.parseHtmlDocument(element.innerHtml as String);
  }
  _splitDoc(value) {
    var value1 = value.querySelectorAll('a');
    return value1;
  }

  _parseKey(value) {
    var value1 = value?.attributes['href'];
    return value1;
  }

  _parseValue(value) {
    var value1 = value.querySelector("html")?.innerHtml;
    var value2 =
        value1.replaceFirst(RegExp("^ "), "").replaceFirst(RegExp(" \$"), "");
    return value2;
  }

  TUrlsMap parse() {
    TUrlsMap items = {};
    for (var e in _splitDoc(selector)) {
      items[_parseKey(e)] = _parseValue(e);
    }
    return items;
  }
}

///
///
/// [
///     {
///         "name": "String",
///         "image_url": "String",
///         "url": "String",
///         "rating": "String",
///         "price": "Int"
///     },
///     "..."
/// ]
class Books {
  late final Document selector;
  Books(String rawDocument) {
    selector = html.parseHtmlDocument(rawDocument);
  }
  Books.fromDocument(Document document) {
    selector = document;
  }
  Books.fromElement(LIElement element) {
    selector = html.parseHtmlDocument(element.innerHtml as String);
  }
  _splitDoc(value) {
    var value1 = value.querySelectorAll('.col-lg-3');
    return value1;
  }

  _parseName(value) {
    var value1 = value.querySelector('.thumbnail');
    var value2 = value1?.attributes['alt'];
    return value2;
  }

  _parseImageUrl(value) {
    var value1 = value.querySelector('.thumbnail');
    var value2 = value1?.attributes['src'];
    var value3 = 'https://$value2';
    return value3;
  }

  _parseUrl(value) {
    var value1 = value.querySelector('.image_container > a');
    var value2 = value1?.attributes['href'];
    return value2;
  }

  _parseRating(value) {
    var value1 = value.querySelector('.star-rating');
    var value2 = value1?.attributes['class'];
    var value3 = value2.replaceFirst(RegExp("^star\-rating "), "");
    return value3;
  }

  _parsePrice(value) {
    try {
      var value1 = value;
      var value2 = value1.querySelector('.price_color');
      var value3 = value2?.text;
      var value4 = RegExp('(\\d+)').firstMatch(value3)?.group(1);
      var value5 = int.parse(value4!);
      return value5;
    } catch (_) {
      return 0;
    }
  }

  TBooks parse() {
    List<TBooksITEM> items = [];
    for (var e in _splitDoc(selector)) {
      TBooksITEM item = (
        name: _parseName(e),
        image_url: _parseImageUrl(e),
        url: _parseUrl(e),
        rating: _parseRating(e),
        price: _parsePrice(e)
      );
      items.add(item);
    }
    return items;
  }
}

/// books.toscrape.com catalogue page entrypoint parser
///
///     USAGE:
///
///         1. GET <catalog page> (https://books.toscrape.com/, https://books.toscrape.com/catalogue/page-2.html, ...)
///         2. add another prepare instruction how to correct cook page (if needed?)
///
///     ISSUES:
///
///         1. nope! Their love being scraped!
///
///
/// {
///     "title": "String",
///     "urls": [
///         "String",
///         "..."
///     ],
///     "urls_map": {
///         "<K>": "String",
///         "<KN>": "..."
///     },
///     "books": [
///         {
///             "name": "String",
///             "image_url": "String",
///             "url": "String",
///             "rating": "String",
///             "price": "Any"
///         },
///         "..."
///     ]
/// }
class CataloguePage {
  late final Document selector;
  CataloguePage(String rawDocument) {
    selector = html.parseHtmlDocument(rawDocument);
  }
  CataloguePage.fromDocument(Document document) {
    selector = document;
  }
  CataloguePage.fromElement(LIElement element) {
    selector = html.parseHtmlDocument(element.innerHtml as String);
  }
  _preValidate(value) {
    var value1 = value.querySelector('title');
    var value2 = value1?.text;
    assert(
        value2 != null && RegExp('Books to Scrape').firstMatch(value2) != null,
        '');
    return null;
  }

  _parseTitle(value) {
    try {
      var value1 = value;
      assert(value1?.querySelector('title'), '');
      var value2 = value1;
      var value3 = value2.querySelector('title');
      var value4 = value3?.text;
      var value5 = value4.replaceAll(RegExp('^\\s+'), '');
      var value6 = value5.replaceAll(RegExp('\\s+\$'), '');
      return value6;
    } catch (_) {
      return 'test';
    }
  }

  _parseUrls(value) {
    var value1 = Urls.fromDocument(value).parse();
    return value1;
  }

  _parseUrlsMap(value) {
    var value1 = UrlsMap.fromDocument(value).parse();
    return value1;
  }

  _parseBooks(value) {
    var value1 = Books.fromDocument(value).parse();
    return value1;
  }

  TCataloguePage parse() {
    _preValidate(selector);
    TCataloguePage item = (
      title: _parseTitle(selector),
      urls: _parseUrls(selector),
      urls_map: _parseUrlsMap(selector),
      books: _parseBooks(selector)
    );
    return item;
  }
}
