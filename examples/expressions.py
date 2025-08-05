"""Demo Expressions usage examples.

NOTE:

    This demonstation syntax usage, not use in real projects

for validation expressions see validation.py example
"""

import re
from ssc_codegen import ItemSchema, D, N, R, F


class BaseSelects(ItemSchema):
    # If you don't understand selectors,
    # read the materials on working with them and try in the browser developer console
    # cheatsheet https://www.w3schools.com/cssref/css_selectors.php
    # specs https://www.w3.org/TR/selectors/
    # 1. single select and extract text
    title = D().css("title").text()
    # 2. single select and extract raw tag (outerHTML)
    title_tag = D().css("title").raw()
    # 3. multi select operation, extract attributes
    # attribute selection for increase accurasy and decrase logic checks
    styles = D().css_all('link[rel="stylesheet"][href]').attr("href")

    # 4. pseudo selectors.
    # inspired by parsel lib https://parsel.readthedocs.io/en/latest/usage.html
    # used for more compact syntax. will be auto converted by codegen
    title_short = D().css("title::text")  # same as call .text()
    title_tag_short = D().css("title::raw")  # same as call .raw()
    styles_short = D().css_all(
        'link[rel="stylesheet"][href]::attr(href)'
    )  # same as call attr(tag_name)
    # allow extract many attrs
    all_url_like = D().css_all("[href],[src],[onclick]::attr(href,src,onclick)")

    # 5. multi attr values extracts
    # maybe used for researches (eg: detect htmx/react/vue attributes)
    link_attrs = D().css("link").attrs_map()
    links_attrs_list = D().css_all("link").attrs_map()


class BaseStringOperations(ItemSchema):
    # example of basic string operations
    # the library is focused on working with html documents.
    # In addition to CSS/XPATH selectors, it is important to be able to process strings

    # drop LEFT and RIGHT chars
    # as default, drop whitespaces
    title_trim = D().css("title::text").trim()
    # drop LEFT chars
    title_ltrim = D().css("title::text").ltrim()
    # drop RIGHT chars
    title_rtrim = D().css("title::text").rtrim()

    # most strings operations works with STRING and LIST_STRING types
    p_text_trim = D().css_all("p::text").trim()
    p_text_ltrim = D().css_all("p::text").ltrim()
    p_text_rtrim = D().css_all("p::text").rtrim()

    # drop prefix/suffix
    # differ from trim() operations in that they remove a substring
    # rather than scanning the enumerated characters
    # This is important to prevent side effects.
    #
    # pseudocode example:
    # INPUT:
    # str = "aaa_hello_aaa"
    # str.trim("a") == "_hello_"
    # str.rtrim("a") == "aaa_hello_"
    # str.ltrim("a") == "_hello_aaa"
    # str.rm_prefix_suffix("a") == "aa_hello_aa"
    # str.rm_suffix("a") == "aaa_hello_aa"
    # str.rm_prefix("a") == "aa_hello_aaa"
    title_rm_prefix = D().css("title::text").rm_prefix("a")
    title_rm_suffix = D().css("title::text").rm_suffix("a")
    title_rm_prefix_suffix = D().css("title::text").rm_prefix_suffix("a")

    # basic format operation.
    # template string required `{{}}` marker.
    # maybe used for create a full url entrypoint
    a = D().css("a[href]::attr(href)").fmt("https://{{}}")
    a_list = D().css_all("a[href]::attr(href)").fmt("https://{{}}")

    # combine all collected strings to one
    # support only LIST_STRING operation
    text_joined = D().css_all("p::text").join(" ")
    # TIP: can be combined with regex for search patterns
    # select elements scope for decrease target text and increase match speed
    re_scripts_pattern = (
        D().css_all("script,iframe::raw").join("").re_all(r"(api.*)")
    )

    # split text to array
    text_spitted = D().css("p::text").split(" ")

    # replace by substing
    text_repl = D().css("p::text").repl("foo", "bar")
    text_repl_list = D().css_all("p::text").repl("foo", "bar")
    # replace substring by map
    text_repl_map = (
        D().css_all("p::text").repl_map({"One": "1", "Two": "2", "Three": "3"})
    )
    text_repl_map_list = (
        D().css_all("p::text").repl_map({"One": "1", "Two": "2", "Three": "3"})
    )

    # regex operaions
    # for the capturing result, should be contains an ONE capture group
    # allowed use re.I, re.S, re.X flags or combinations
    # or aliases:
    # re.IGNORECASE, re.DOTALL, re.VERBOSE flags or combinations

    # find first result by pattern
    re_example = D().css("p::text").re(re.compile(r"(\d+)", re.I | re.S | re.X))
    # allowed used VERBOSE mode for increase regex readability
    re.example_x = (
        D()
        .css("p::text")
        .re(
            r"""
        # comment1
        ([a-z+])  # comment2
        ohter...pattern
        # end
""",
            re.X,
        )
    )
    # find all results by pattern
    re_all_example = D().css("p::text").re_all(r"(\d+)")

    # sub strings by pattern,
    # for prettify text output by pattern
    # for example, drop whitespaces LEFT and RIGHT
    re_sub_example = D().css("p::text").re_sub(r"(?:^\s+)|(?:\s+$)")
    re_sub_list_example = (
        D().css_all("p::text").re_sub(r"(?:^\s+)|(?:\s+$)", "").join()
    )

    # other

    # unescape text
    # maybe useful for improving text or normalizing json before serialization
    unescape_example = D().css("json[type='ld/json']::text").unescape()


class BaseArrayOperaions(ItemSchema):
    # examples operations with array-like objects
    # NOTE: for selector operations reccomended use
    # https://developer.mozilla.org/en-US/docs/Web/CSS/:nth-child pseudo selector
    # instead direct get elemenet by index for decrease logic selects
    # get element by index
    index_val = D().css_all("p::text").index(1)
    # get first element by index
    first_val = D().css_all("p::text").first()
    # get last element by index
    last_val = D().css_all("p::text").last()


class BaseCastTypeOperations(ItemSchema):
    # example simple casts to types

    # boolean
    # returns false if
    # returns None/nil value
    # empty sequence
    # empty string
    # other cases - true
    boolean = D().css("title").to_bool()
    boolean_false = D(False).css("titleobbb").to_bool()

    # cast to integer
    # NOTE: generated code does not check previous input
    # and maybe add side effect
    # eg:
    # validate value or sanitaize by `\D` regex pattern
    integer = R().re(r"(\d+)").to_int()
    array_integer = R().re_all(r"(\d+)").to_int()

    # cast to float
    # NOTE: generated code does not check previous input
    # and maybe add side effect
    # eg:
    # validate value or sanitaize by `[^\D.]` regex pattern
    float = R().re(r"(\d+\.\d+)").to_float()
    array_float = R().re_all(r"(\d+\.\d+)").to_float()

    # convert array to lenght
    array_len_elements = D().css_all("p").to_len()
    array_len_strings = D().css_all("p::text").to_len()
    # allow contert list ints/floats
    array_len_integer = R().re_all(r"(\d+)").to_int().to_len()
    array_len_float = R().re_all(r"(\d+\.\d+)").to_float().to_len()
