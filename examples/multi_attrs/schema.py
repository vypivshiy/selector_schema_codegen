# extract multiple attrs to one field
from ssc_codegen import D, ItemSchema, AccUniqueListSchema


class AllHrefs(ItemSchema):
    # safe operation: not throw exception if attr not founded
    # use multiple selector for catch interesting tags
    urls = D().css_all("[src],[href]::attr(src,href)").unique()
    many_attrs = D().css("a[href],a[src]::attr(href,src)").unique()


class AllHrefsAcc(AccUniqueListSchema):
    src  = D().css_all("[src]::attr(src)")
    href  = D().css_all("[href]::attr(href)")
