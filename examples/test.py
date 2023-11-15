"""Auto generated code by selector_schema_codegen

id: books.to_scrape
name: books.to_scrape
author: username
description:
    books.to_scrape schema
source: source_link
tags:
    shop, books

WARNING: Any manual changes made to this file will be lost when this
is run again. Do not edit this file unless you know what you are doing.
"""

from typing import Any
import re

from parsel import Selector


class UselessElements:
    """
    useless elements extractor

    view() elements signature:

        title <TEXT> - a title page

        meta <TEXT> - all meta elements tags

        hrefs <ARRAY> - all a [href] elements

        
    """
    def __init__(self, document: str):
        self.__raw__ = document
        self.__selector__ = Selector(document)
        self.__aliases = {}
        self.__view_keys = ['title', 'meta', 'hrefs']
        self.__cached_result: list[dict[str, Any]] = []

    def parse(self):
        self.__pre_validate(self.__selector__)
        self.__start_parse()

    @staticmethod
    def __pre_validate(part: Selector):
        
    def __part_document(self, part: Selector):
        self.__pre_validate(self.__selector__)
        
    
    @staticmethod
    def __parse_title(part: Selector):
        val_0 = part.css("title")
        val_1 = val_0.xpath("./text()").get()
        return val_1
    
    @staticmethod
    def __parse_meta(part: Selector):
        val_0 = part.css("head > meta")
        val_1 = val_0.get()
        return val_1
    
    @staticmethod
    def __parse_hrefs(part: Selector):
        val_0 = part.css("a")
        val_1 = val_0.attrib["href"]
        return val_1
    
    def __start_parse(self):
        # clear cache
        self.__cached_result.clear()
        for part in self.__part_document(self.__selector__):
            self.__cached_result.append({
                'title': self.__parse_title(part),
                'meta': self.__parse_meta(part),
                'hrefs': self.__parse_hrefs(part),})

    def view(self) -> list[dict[str, Any]]:
        def map_fields(result):
            view_dict = {}
            for k in self.__view_keys:
                if v := result.get(k):
                    k = self.__aliases.get(k, k)
                    view_dict[k] = v
            return view_dict

        if len(self.__cached_result) == 1:
            return [map_fields(self.__cached_result[0])]
        return [map_fields(result) for result in self.__cached_result]

class Book:
    """
    examples book object parser

    view() elements signature:

        url_page (url) <TEXT> - page url to book

        image <TEXT> - book image

        price <TEXT> - book price

        name <TEXT> - book name

        rating <TEXT> - book rating

        
    """
    def __init__(self, document: str):
        self.__raw__ = document
        self.__selector__ = Selector(document)
        self.__aliases = {'url': 'url_page'}
        self.__view_keys = ['url', 'image', 'price', 'name', 'rating']
        self.__cached_result: list[dict[str, Any]] = []

    def parse(self):
        self.__pre_validate(self.__selector__)
        self.__start_parse()

    @staticmethod
    def __pre_validate(part: Selector):
        val_0 = part.css("div > a")
        val_1 = val_0.attrib["href"]
        assert re.search(r"cyka cyka.jpg", val_1)
        
    def __part_document(self, part: Selector):
        self.__pre_validate(self.__selector__)
        val_0 = part.css("ol.row > li")
        return val_0
    
    @staticmethod
    def __parse_url(part: Selector):
        val_0 = part.css("div.image_container > a")
        val_1 = val_0.attrib["href"]
        val_2 = "https://books.toscrape.com/catalogue/{}".format(val_1)
        return val_2
    
    @staticmethod
    def __parse_image(part: Selector):
        val_0 = part.css("div.image_container > a > img")
        val_1 = val_0.attrib["src"]
        return val_1
    
    @staticmethod
    def __parse_price(part: Selector):
        try:
            val_1 = part.css("div.product_price > p.price_color")
            val_2 = val_1.xpath("./text()").get()
            return val_2
            
        except Exception:
            return "0"
    
    @staticmethod
    def __parse_name(part: Selector):
        val_0 = part.css("h3 > a")
        val_1 = val_0.attrib["title"]
        return val_1
    
    @staticmethod
    def __parse_available(part: Selector):
        val_0 = part.css("div.product_price > p.availability > i")
        val_1 = val_0.attrib["class"]
        return val_1
    
    @staticmethod
    def __parse_rating(part: Selector):
        val_0 = part.css("p.star-rating")
        val_1 = val_0.attrib["class"]
        val_2 = val_1.lstrip("star-rating ")
        return val_2
    
    def __start_parse(self):
        # clear cache
        self.__cached_result.clear()
        for part in self.__part_document(self.__selector__):
            self.__cached_result.append({
                'url': self.__parse_url(part),
                'image': self.__parse_image(part),
                'price': self.__parse_price(part),
                'name': self.__parse_name(part),
                'available': self.__parse_available(part),
                'rating': self.__parse_rating(part),})

    def view(self) -> list[dict[str, Any]]:
        def map_fields(result):
            view_dict = {}
            for k in self.__view_keys:
                if v := result.get(k):
                    k = self.__aliases.get(k, k)
                    view_dict[k] = v
            return view_dict

        if len(self.__cached_result) == 1:
            return [map_fields(self.__cached_result[0])]
        return [map_fields(result) for result in self.__cached_result]
