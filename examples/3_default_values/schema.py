# if the html page where the selector is possibly not found, you can use the default value
from ssc_codegen import D, ItemSchema


class Main(ItemSchema):
    """default value set example, if field code parse throw exception

    USAGE:
        - pass index.html document from 3_default_values folder
    """
    # NOTE: set default variable if block code for field scope throw exception
    # some examples throw an error on purpose
    title_ok = D().css('title').text()
    # accept None, str, int, float
    title_null = D().default(None).css('title').is_css('a').text()
    title_str_default = D().default("unknown").css('title').is_css('a').text()

    # last type should be returns int else codegen throw TypeError
    #                                                       v
    title_int_default = D().default(1).css('title').text().to_int()

    # last type should be returns float else codegen throw TypeError
    #                                                                v
    title_float_default = D().default(3.14).css('title').text().to_float()
