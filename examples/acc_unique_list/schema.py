"""example usage case this structure"""
from ssc_codegen import D, AccUniqueListSchema


class Urls(AccUniqueListSchema):

    # NOTES:
    # 1. ALL FIELDS SHOULD BE returns Array<String> type
    # 2. for avoid exceptions, you can stub default value as empty array
    # 3. keys used for readability and generate methods blocks code
    # 4. output - Array[String] with removed duplicates
    images = D([]).css_all("img[src] ::attr(src)")
    hrefs = D([]).css_all("a[href] ::attr(href)")
    embed = D([]).css_all("embed[src] ::attr(src)")
    scripts = D([]).css_all("script[src] ::attr(src)")
    # other patterns
