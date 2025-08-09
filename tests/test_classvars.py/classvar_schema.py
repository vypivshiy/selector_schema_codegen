from ssc_codegen import ItemSchema, CV


class LiteralsSchema(ItemSchema):
    CV_NONE = CV(None)
    CV_INT = CV(100)
    CV_FLOAT = CV(3.14)
    CV_STR = CV("test")
    CV_LIST_STR = CV(["foo", "bar"])
