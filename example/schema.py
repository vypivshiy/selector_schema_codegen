"""Dummy parser config for http://books.toscrape.com/"""
import os

from ssc_codegen2.document import D, N
from ssc_codegen2.schema import ItemSchema, ListSchema, FlattenListSchema, DictSchema


class Urls(FlattenListSchema):
    __SPLIT_DOC__ = D().css_all('a')
    __ITEM__ = D().attr('href')


class Books(ListSchema):
    __SPLIT_DOC__ = D().css_all('.col-lg-3')

    name = D().css('.thumbnail').attr('alt')
    image = D().css('.thumbnail').attr('src')
    url = D().css('.image_container > a').attr('href')
    rating = D().css('.star-rating').attr('class').ltrim('star-rating ')
    price = D().css('.price_color').text()


class CataloguePage(ItemSchema):
    __PRE_VALIDATE__ = D().css('title').text().assert_re(r'Books to Scrape')
    title = D().css('title').text()
    urls: Urls = N().sub_parser(Urls)
    books: Books = N().sub_parser(Books)


def gen_python():
    from ssc_codegen2.converters.py_selectolax import code_generator

    with open("py/parsers/baseStruct.py", 'w') as f:
        f.write(code_generator.generate_base_class())

    codes = []
    codes.append(code_generator.generate_imports())
    codes.extend(code_generator.generate_code(Urls, Books, CataloguePage))
    codes = "\n".join(codes)
    with open("py/parsers/booksToScrape.py", "w") as f:
        f.write(codes)
    os.system("black py/parsers/")


def gen_dart():
    from ssc_codegen2.converters.dart import code_generator as dart_gen

    with open("dart/parsers/baseStruct.dart", 'w') as f:
        f.write(dart_gen.generate_base_class())

    codes = []
    codes.append(dart_gen.generate_imports())
    codes.extend(dart_gen.generate_code(Urls, Books, CataloguePage))
    codes = "\n".join(codes)
    with open("dart/parsers/booksToScrape.dart", "w") as f:
        f.write(codes)
    os.system("dart format dart/parsers/")

if __name__ == '__main__':
    # gen_python()
    gen_dart()