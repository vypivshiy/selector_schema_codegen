from ssc_codegen import D, ItemSchema


class T(ItemSchema):
    f = D().css('#regform').text()