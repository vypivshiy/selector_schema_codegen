# if the html page where the selector is possibly not found, you can use the default value
from ssc_codegen import D, ItemSchema


class Main(ItemSchema):
    # ISSUES in docstring - an example of how to document a potential error.
    # Convenient to view documentation on-site in the IDE!
    """Example validate document input and fields

    USAGE:
        - pass index.html document from 4_validation folder

    ISSUES:
        - if title not equal Demo page - throw error
    """
    # special magic field:
    # its pre validate passed before parse without modify document
    __PRE_VALIDATE__ = (
        D()
        .is_css("title")  # if not founded by css query - throw error
        .css("title")
        .text()
        .is_equal("Demo page") # if value not equal - throw error
        .is_not_equal("Real page") # if value equal - throw error
        .is_regex('[dD]...\s*p...')  # if not matched result - throw error
        .split(' ')
        .is_contains('Demo') # if sequence not contains - throw error
    )

    # you can use checks in fields
    title = D().css('title').text().is_equal("Demo page")
    # or use with feature for set default value
    title_rescue_assert = D().default('I SAY ITS DEMO PAGE').css('title').text().is_equal("IM not demo page!")
