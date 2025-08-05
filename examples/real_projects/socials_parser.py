"""Universal example search socials urls


TESTS (24.06.25):

ssc-gen parse-from-url "https://github.com" -t socials_parser.py:Main

{
  "git": [
    "https://github.com/features/code-search",
    "https://github.com/customer-stories/figma",
    "https://github.com/mobile",
    "https://github.com/why-github",
    "https://github.com/edu",
    ...
    "https://github.com/features"
  ],
  "contacts": {
    "phone": [],
    "email": []
  },
  "socials": [
    "https://www.youtube.com/github",
    "https://www.tiktok.com/@github",
    "https://x.com/github"
  ]
}
"""

import re
from typing import Sequence
from ssc_codegen import N, AccUniqueListSchema, ItemSchema, D, F, R

# TIP: move diffucult filters/selectors/etc to constants
# or build helper functions!
RE_JOHN_DOE = re.compile(r"john[\s\-_\.]*doe", re.IGNORECASE)

# regex implemented by projectdiscovery:
# https://github.com/projectdiscovery/katana/blob/main/pkg/utils/regex.go#L7
RE_BODY_ENDPOINT_LIKE = re.compile(
    r"""
    (
        (?:
            (?:\.\./[A-Za-z0-9\-_/\\?&@.=%]+)
            |
            (?:https?://[A-Za-z0-9_\-.]+(?:\.\./)?/[A-Za-z0-9\-_/\\?&@.=%]+)
            |
            (?:/[A-Za-z0-9\-_/\\?&@.%]+\.(?:aspx?|action|cfm|cgi|do|pl|css|x?html?|js(?:p|on)?|pdf|php5?|py|rss))
            |
            (?:[A-Za-z0-9\-_?&@.%]+/[A-Za-z0-9/\\\-_?&@.%]+\.(?:aspx?|action|cfm|cgi|do|pl|css|x?html?|js(?:p|on)?|pdf|php5?|py|rss))
        )
    )
""",
    re.I | re.X,
)

F_EXCLUDE = ~(
    F().starts("info@")
    & F().re(RE_JOHN_DOE)
    # TIP: you can manually write expr like this for increase speed
    # this expression works faster than regexp
    & (F().contains("john", "John") & F().contains("doe", "Doe"))
    # add other exclude filters
)

# spectial negative filter:
# will be used for drop metricts-like values
F_METRICS_SCRIPT = F().contains(
    "ym(",
    "gtag(",
    "yaCounter",
)


ATTRS = ["href", "src", "action", "onclick", "formaction"]


# TIP: write helper functions for decrease boilerplate
# current implementation lib not support this features
def css_has(substr: str, tag_attrs: Sequence[str] = ATTRS):
    """
    Example usage:

    css_has("spam", ("href",))
    [href*="spam"]::attr(href)

    css_has("spam", ("href", "src"))
    [href*="spam"],[src*="spam"]::attr(href,src)
    """
    query = ",".join([f'[{a}*="{substr}"]' for a in tag_attrs])
    query += "::attr(" + ",".join(tag_attrs) + ")"
    return query


class Git(AccUniqueListSchema):
    github = D([]).css_all(css_has("github.com/")).filter(F_EXCLUDE)
    gitlab = D([]).css_all(css_has("gitlab.com/")).filter(F_EXCLUDE)


class Socials(AccUniqueListSchema):
    twitter = (
        D([])
        .css_all(css_has("twitter.com"))
        .filter(F_EXCLUDE & F().contains(".twitter.com/", "/twitter.com/"))
    )
    # WARNING: 
    # shorten link selectors can be add a side effect
    # and capture urls like `example*x*.com/` or `foobar*x*.com/`.
    # this example not be coverage this corner cases
    x_com = D([]).css_all(css_has("x.com/")).filter(F_EXCLUDE)
    tiktok = D([]).css_all(css_has("tiktok.com")).filter(F_EXCLUDE)
    youtube = D([]).css_all(css_has("youtube.com")).filter(F_EXCLUDE)
    # ...

    # or add find by regex
    # WARNING: these are the most CPU-bound tasks
    # if the regular expression is not optimized or you come across a site that
    # is too large in content-length (>1_000_000)
    # - you may get "Catastrophic backtracking"
    # https://regex101.com/r/iXSKTs/1/debugger

    # you can select the necessary elements or delete unnecessary ones

    # WARNING:
    # deleting elements has a **SIDE EFFECT**:
    # if you try to find it by selector, it won't be there
    # eg: after delete ("script,svg,img") in this tags you cannot find it!
    
    # or you can use next strategy: select needed elements, 
    # join to one string and search by regex pattern
    # re_urls = D().css_all("span,p,strong,form,h1,h2,h3,div::text").join("").re_all("(PATTERN)")
    
    re_twitter = (
        D([])
        .css_remove("script,svg,img")
        .raw()
        .re_all(RE_BODY_ENDPOINT_LIKE)
        .filter(F().contains("twitter.com/"))
    )
    x_com = (
        R([])
        .re_all(RE_BODY_ENDPOINT_LIKE)
        .filter(F().contains(".x.com/", "/x.com"))
        .unique()
    )
    youtube = (
        R([])
        .re_all(RE_BODY_ENDPOINT_LIKE)
        .filter(F().contains("youtube.com", "youtu.be"))
    )
    

class Contacts(ItemSchema):
    phone = (
        D([])
        .css_all('a[href^="tel:"]::attr(href)')
        .filter(~F_METRICS_SCRIPT)
        .unique()
    )
    email = (
        D([])
        .css_all('a[href^="email:"]::attr(href)')
        .filter(~F_METRICS_SCRIPT)
        .unique()
    )


class Main(ItemSchema):
    git = N().sub_parser(Git)
    contacts = N().sub_parser(Contacts)
    socials = N().sub_parser(Socials)
