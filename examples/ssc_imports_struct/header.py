from ssc_codegen import ItemSchema, D, N


class Link(ItemSchema):
    # NOTE: implemented for demonstaition cli converter imports issues
    
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/link
    styles = D([]).css_all('link[rel="stylesheet"][href]::attr(href)')
    icon = D(None).css('link[rel*="icon"]::attr(href)')
    font = D(None).css('link[type*="font"]::attr(href)')



class Head(ItemSchema):
    title = D().css("title::text")
    links = N().sub_parser(Link)