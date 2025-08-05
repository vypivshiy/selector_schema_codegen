"""Example validators concepts usage


all validate operations does not modify previous result
"""

from ssc_codegen import ItemSchema, D, R,F


class MainValidateDemo(ItemSchema):
    __PRE_VALIDATE__ = (
        D()
        .is_css("title")
        .css("title::text")
        .is_regex(r".")
        .is_not_equal("404")
    )
    """Optional validate document before start parse document

    If assert checks not passed - throw error

    Does not modify document
    """

    title = D("not test123").css("title::text").is_equal("test123")
    """default expression capture exception and set default value"""

    # final casts int, float can be checks too
    re_int = R(0).re(r"(\d+)").to_int().is_not_equal(100)
    re_float = R(0).re(r"(\d+\.\d+)").to_float().is_not_equal(3.14)
    
    # can be used as "break" mechanism if asserts is not passed
    github_john_doe = (
        D([])
        # NOTE: in real projects use a[href*="github.com"] selector
        .css_all("a[href]::attr(href)")
        # if not passed break next steps and set default value
        .any_is_re("github\.com")
        .filter(F().contains("github.com"))
        .join(" ")
        .is_re(r"john doe", ignore_case=True)
    )

    # array checks
    urls_html_all = (
        D([]).css_all("a[href*='.html']::attr(href)").all_is_re(r"\.html")
    )
    urls_html_any = D([]).css_all("a[href]::attr(href)").any_is_re(r"\.html")
    urls_has_example_com = (
        D([]).css_all("a[href]::attr(href)").is_contains("example.com")
    )
    first_a_has_href = D(False).css("a").has_attr("href").to_bool()
