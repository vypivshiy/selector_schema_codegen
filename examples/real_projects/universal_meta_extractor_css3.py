"""
all implementation for CSS3 selectors universal opengraph and twitter cards metadata extractor
"""

from ssc_codegen import ItemSchema, DictSchema, D, N, FE

FILTER_OG_OTHER = (
    FE().has_attr("property").attr_starts("property", "og") &
    ~(
        FE().attr_eq("property", "twitter:card", "twitter:title", "twitter:description", "twitter:image")
    )
)
"""
CSS4 rule equalent:

meta[property^="og:"][content]
:not(
[property="og:title"], 
[property="og:description"], 
[property="og:url"], 
[property="og:image"]
)
"""

FILTER_TWITTER_OTHER = (
    FE().has_attr("property").attr_starts("property", "twitter:") &
    ~(
        FE().attr_eq("twitter:card", "twitter:title", "twitter:description", "twitter:image")
    )
    | FE().has_attr("name").attr_starts("name", "twitter:") &
    ~(
        FE().attr_eq("twitter:card", "twitter:title", "twitter:description", "twitter:image")
    )
)
"""
CSS4 rule equalent:

meta[property^="twitter:"][content]:not(
[property="twitter:card"],
[property="twitter:title"],
[property="twitter:description"],
[property="twitter:image"]
),
meta[name^="twitter:"][content]:not(
[name="twitter:card"],
[name="twitter:title"],
[name="twitter:description"],
[name="twitter:image"]
)
"""

class MetaBase(ItemSchema):
    """standart meta tags extractor"""

    description = D(None).css(
        'meta[name="description"][content], meta[name="Description"][content]::attr(content)'
    )
    keywords = (
        D([])
        .css(
            'meta[name="keywords"][content], meta[name="Keywords"][content]::attr(content)'
        )
        .split(",")
        .trim(" ")
    )


class MetaOpenGraphOther(DictSchema):
    __SPLIT_DOC__ = D().css_all("meta[property][content]").filter(FILTER_OG_OTHER)

    __KEY__ = D().attr("property")
    __VALUE__ = D().attr("content")


class MetaOpenGraph(ItemSchema):
    """OpenGraph (facebook/meta) metatag specs"""

    title = D(None).css('meta[property="og:title"][content]::attr(content)')
    description = D(None).css('meta[property="og:description"][content]::attr(content)')
    url = D(None).css('meta[property="og:url"][content]::attr(content)')
    image = D(None).css('meta[property="og:image"][content]::attr(content)')
    others = N().sub_parser(MetaOpenGraphOther)


class MetaTwitterOther(DictSchema):
    __SPLIT_DOC__ = D().css_all(FILTER_TWITTER_OTHER)
    # maybe contains "name" or "property" attribute 
    __KEY__ = D().attr("property", "name").first()
    __VALUE__ = D().attr("content")


class MetaTwitter(ItemSchema):
    """Twitter (x.com) metatag specs"""

    card = D(None).css(
        'meta[property="twitter:card"][content], meta[name="twitter:card"][content]::attr(content)'
    )
    title = D(None).css(
        'meta[property="twitter:title"][content], meta[name^="twitter:title"][content]::attr(content)'
    )
    description = D(None).css(
        'meta[property="twitter:description"][content], meta[name^="twitter:description"][content]::attr(content)'
    )
    image = D(None).css(
        'meta[property="twitter:image"][content], meta[name^="twitter:image"][content]::attr(content)'
    )
    others = N().sub_parser(MetaTwitterOther)


class UniversalMetaExtractor(ItemSchema):
    """entrypoint parser
    
    accept any HTML page with <meta> tags
    """
    title = D(None).css("title::text")

    canonical = D(None).css('link[rel="canonical"][href]::attr(href)')
    favicon = D(None).css('link[rel~="icon"][href]::attr(href)')
    rss_feeds = D([]).css_all(
        'link[type="application/rss+xml"][href], link[type="application/atom+xml"][href]::attr(href)'
    )

    meta = N().sub_parser(MetaBase)
    open_graph = N().sub_parser(MetaOpenGraph)
    twitter = N().sub_parser(MetaTwitter)
