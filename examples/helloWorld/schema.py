from ssc_codegen import ItemSchema, D

class HelloWorld(ItemSchema):
    title = D().css('title').text()
    a_hrefs = D().css_all('a').attr('href')