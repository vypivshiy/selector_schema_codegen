"""Example web scraper config for https://news.ycombinator.com/


News:

select tag signature:

```html
<tr class="athing submission" id="123">
    <td align="right" valign="top" class="title"><span class="rank">1.</span></td>
    <td valign="top" class="votelinks">
        <center>
            <a id="up_123" href="vote?id=123&amp;how=up&amp;goto=news">
                <div class="votearrow" title="upvote"></div>
            </a>
        </center>
    </td>
    <td class="title"><span class="titleline"><a href="https://example.com">Example title</a>
    <span class="sitebit comhead"> (<a href="from?site=example.com"><span
    class="sitestr">example.com</span></a>)</span></span></td>
</tr>
```

Ratings:

select signature

```html
<span class="subline">
    <span class="score" id="score_123">9000 points</span> by <a href="user?id=admin" class="hnuser">admin</a>
    <span class="age" title="2010-06-22T14:56:44 1750604204">
        <a href="item?id=123">20 hours ago</a></span>
    <span id="unv_123"></span> | <a href="hide?id=123&amp;goto=news">hide</a>
    | <a href="item?id=123">55&nbsp;comments</a> </span>
```

"""

from ssc_codegen import ItemSchema, D, N
from ssc_codegen.schema import ListSchema


FMT_URL = "https://news.ycombinator.com/{{}}"


# see first dostring tags examples about selector implementatsions
class News(ListSchema):
    __SPLIT_DOC__ = D().css_all(".submission")

    title = D().css(".title > .titleline > a::text")
    # hack: sanitaize non-digit values by `\D` regex
    rank = D().css(".rank::text").re_sub("\D").to_int()
    id = D(None).attr("id")

    # maybe exclude votelink feauture
    votelink = D(None).css(".votelinks a[href]::attr(href)").fmt(FMT_URL)
    url = D().css(".title > .titleline > a[href]::attr(href)")


class Ratings(ListSchema):
    __SPLIT_DOC__ = D().css_all("tr > .subtext > .subline")

    score = D(0).css('span.score[id^="score_"]::text').re_sub("\D").to_int()
    author = D(None).css("a.hnuser[href]::attr(href)").fmt(FMT_URL)
    date = D(None).css("span.age[title]::attr(title)")
    date_text = D(None).css("span.age[title]::text")
    url = D().css('a[href^="item?"]::attr(href)').fmt(FMT_URL)
    # url selector selects comments tag
    # <a href="item?id=123">55&nbsp;comments</a>
    comments = D(0).css('a[href^="item?"]::text').re_sub("\D").to_int()


class MainPage(ItemSchema):
    """Main hacker news page

    Page entrypoints examples:
        GET https://news.ycombinator.com
        GET https://news.ycombinator.com/?p=2

    NOTE:
        news.votelink can be null
    """

    news = N().sub_parser(News)
    ratings = N().sub_parser(Ratings)


class Comments(ListSchema):
    __SPLIT_DOC__ = D().css_all("table.comment-tree tr.comtr[id] > td > table")
    # maybe used for render tree discussion
    indent = D(0).css(".ind[indent]::attr(indent)").to_int()

    user = D().css(".comhead > a.hnuser::text")
    user_url = D().css(".comhead > a.hnuser[href]::attr(href)").fmt(FMT_URL)
    date = D(None).css(".comhead .age[title]::attr(title)")
    date_text = D(None).css('.comhead .age[title] >a[href^="item?"]::text')

    # NOTE: not uncluded unwrap features, inner urls returns "as it"
    text = D().css(".default > .comment > .commtext::text")
    reply = D(None).css(".reply a[href]::attr(href)").fmt(FMT_URL)


class MainDiscussionPage(ItemSchema):
    """Main hackernews discussion page

    PAGE entrypoin examples:
        GET https://news.ycombinator.com/item?id=1
        GET https://news.ycombinator.com/item?id=2

    NOTE:
        comments.reply can be null
    """

    title = D().css(".titleline > a::text")
    url = D().css(".titleline > a[href]::attr(href)")
    score = D(0).css(".subline > .score::text").re_sub("\D").to_int()
    user = D().css(".subline .hnuser").text()
    user_url = D().css(".subline .hnuser[href]::attr(href)").fmt(FMT_URL)

    date = D().css(".subline .age[title]::attr(title)")
    date_text = D().css('.subline .age[title] > a[href^="item?"]::text')
    comments_count = (
        D(0).css('.subline > a[href^="item?"]::text').re_sub("\D").to_int()
    )
    comments = N().sub_parser(Comments)
