/**
Auto generated code by selector_schema_codegen

id: books.to_scrape
name: books.to_scrape
author: vypivshiy
description:
    books.toscrape selectors schema example
source: http://books.toscrape.com
tags:
    shop, books, example

WARNING: Any manual changes made to this file will be lost when this
is run again. Do not edit this file unless you know what you are doing.

**/
import 'dart:core';
import 'package:universal_html/html.dart' show Document;
import 'package:universal_html/parsing.dart' as html;

// TODO change dynamic to generic with String OR List<String>
typedef ParsedValue = Map<String, dynamic>;


class BookCatalogue{
    /// parse books from catalogue
    /// 
    /// view() elements signature:
    /// url <TEXT> - page url to product
    /// title <TEXT> - product title
    /// price <TEXT> - product price
    /// image <TEXT> - product image
    /// rating <TEXT> - product rating
    /// 
    final String document;
    late final Document selector;
    final Map<String, String> _aliases = {};
    final List<String> _viewKeys = ['url', 'title', 'price', 'image', 'rating'];
    final List<ParsedValue> _cachedResult = [];

    BookCatalogue(this.document) {
      selector = html.parseHtmlDocument(document);
    }

    void parse(){
        _preValidate(selector);
        _startParse();
    }

    void _preValidate(Document part){
        var val_0 = part.querySelector("title");
        String val_1 = val_0?.text ?? "";
        RegExp re_2 = RegExp(r"Books to Scrape - Sandbox");
        assert(re_2.firstMatch(val_1) != null);
        
    }

    // TODO typing better
    List<dynamic> _partDocument(dynamic part){
        _preValidate(selector);
        var val_0 = part.querySelectorAll(".col-lg-3");
        return val_0;
    }

    
    dynamic _parseUrl(dynamic part){
        var val_0 = part.querySelector("h3 > a");
        String val_1 = val_0.attributes["href"];
        String val_2 = "https://books.toscrape.com/catalogue/$val_1";
        return val_2;
    }
    
    dynamic _parseTitle(dynamic part){
        var val_0 = part.querySelector("h3 > a");
        String val_1 = val_0.attributes["title"];
        return val_1;
    }
    
    dynamic _parsePrice(dynamic part){
        try {
  var val_1 = part.querySelector(".price_color");
        String val_2 = val_1?.text ?? "";
        String val_3 = val_2.replaceFirst(RegExp(r'^£'), "");
        return val_3; } catch (e) {
  return "0";
        }
    }
    
    dynamic _parseImage(dynamic part){
        var val_0 = part.querySelector("img.thumbnail");
        String val_1 = val_0.attributes["src"];
        String val_2 = val_1.replaceFirst(RegExp(r'^..'), "");
        String val_3 = "https://books.toscrape.com$val_2";
        return val_3;
    }
    
    dynamic _parseRating(dynamic part){
        var val_0 = part.querySelector(".star-rating");
        String val_1 = val_0.attributes["class"];
        String val_2 = val_1.replaceFirst(RegExp(r'^star-rating '), "");
        return val_2;
    }
    

    void _startParse(){
        // clear cache
        _cachedResult.clear();
        for (var part in _partDocument(selector)){
            _cachedResult.add({
                'url': _parseUrl(part),
                'title': _parseTitle(part),
                'price': _parsePrice(part),
                'image': _parseImage(part),
                'rating': _parseRating(part),});
        }
    }

    List<ParsedValue> view() {
      ParsedValue mapFields(ParsedValue result) {
      ParsedValue viewDict = {};
      for (String k in _viewKeys) {
      var v = result[k];
      if (v != null) {
          k = _aliases[k] ?? k;
          viewDict[k] = v;
        }
      }
      return viewDict;
      }

    if (_cachedResult.length == 1) {
        return [mapFields(_cachedResult[0])];
    }
    return _cachedResult.map(mapFields).toList();
    }
}

class Book{
    /// Book from product page
    /// 
    /// view() elements signature:
    /// description <TEXT> - product description
    /// title <TEXT> - product title
    /// price <TEXT> - product price
    /// upc <TEXT> - product UPC
    /// 
    final String document;
    late final Document selector;
    final Map<String, String> _aliases = {};
    final List<String> _viewKeys = ['title', 'description', 'price', 'upc'];
    final List<ParsedValue> _cachedResult = [];

    Book(this.document) {
      selector = html.parseHtmlDocument(document);
    }

    void parse(){
        _preValidate(selector);
        _startParse();
    }

    void _preValidate(Document part){
        var val_0 = part.querySelector("title");
        String val_1 = val_0?.text ?? "";
        RegExp re_2 = RegExp(r"Books to Scrape - Sandbox");
        assert(re_2.firstMatch(val_1) != null);
        
    }

    // TODO typing better
    List<dynamic> _partDocument(dynamic part){
        _preValidate(selector);
        return [part];
    }

    
    dynamic _parseDescription(dynamic part){
        var val_0 = part.querySelector("#product_description+ p");
        String val_1 = val_0?.text ?? "";
        return val_1;
    }
    
    dynamic _parseTitle(dynamic part){
        var val_0 = part.querySelector("h1");
        String val_1 = val_0?.text ?? "";
        return val_1;
    }
    
    dynamic _parsePrice(dynamic part){
        try {
  var val_1 = part.querySelector(".product_main .price_color");
        String val_2 = val_1?.text ?? "";
        String val_3 = val_2.replaceFirst(RegExp(r'^£'), "");
        return val_3; } catch (e) {
  return "0";
        }
    }
    
    dynamic _parseUpc(dynamic part){
        var val_0 = part.querySelector("tr:nth-child(1) td");
        String val_1 = val_0?.text ?? "";
        return val_1;
    }
    

    void _startParse(){
        // clear cache
        _cachedResult.clear();
        for (var part in _partDocument(selector)){
            _cachedResult.add({
                'description': _parseDescription(part),
                'title': _parseTitle(part),
                'price': _parsePrice(part),
                'upc': _parseUpc(part),});
        }
    }

    List<ParsedValue> view() {
      ParsedValue mapFields(ParsedValue result) {
      ParsedValue viewDict = {};
      for (String k in _viewKeys) {
      var v = result[k];
      if (v != null) {
          k = _aliases[k] ?? k;
          viewDict[k] = v;
        }
      }
      return viewDict;
      }

    if (_cachedResult.length == 1) {
        return [mapFields(_cachedResult[0])];
    }
    return _cachedResult.map(mapFields).toList();
    }
}
