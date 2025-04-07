from jinja2 import Template

J2_STRUCT_INIT = """
constructor(doc){
if (typeof doc === 'string'){
this._doc = new DOMParser().parseFromString(doc, 'text/html');
} else if (doc instanceof Document || doc instanceof Element){
this._doc = doc;
} else {
throw new Error("Invalid input: Expected a Document, Element, or string");}
}
"""

J2_START_PARSE_DICT = "return Array.from(this._splitDoc(this._doc)).reduce((item, e) => (item[this._parseKey(e)] = this._parseValue(e), item), {});"
J2_START_PARSE_FLAT_LIST = "return Array.from(this._splitDoc(this._doc)).map((e) => this._parseItem(e));"

J2_START_PARSE_ITEM = Template("""return {
    {% for expr in exprs %}
{{ expr.name }}: this._parse{{ expr.upper_name }}(this._doc),
    {% endfor %}
};""")

J2_START_PARSE_LIST_PARSE = Template("""return Array.from(this._splitDoc(this._doc)).map((e) => ({
    {% for expr in exprs %}
{{ expr.name }}: this._parse{{ expr.upper_name }}(e),
    {% endfor %}
}));""")

J2_PRE_STR_TRIM = Template(
    """
    let {{ nxt }} = (function (str, chars) {
        return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');
    })({{ prv }}, {{ substr }});
    """
)


J2_PRE_LIST_STR_TRIM = Template(
    """
    let {{ nxt }} = {{ prv }}.map(e =>
        (function (str, chars) {
            return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');
        })(e, {{ substr }})
    ); 
    """
)

J2_PRE_STR_LEFT_TRIM = Template(
    """
    let {{ nxt }} = (function (str, chars) {
        return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');
    })({{ prv }}, {{ substr }});
    """
)

J2_PRE_LIST_STR_LEFT_TRIM = Template(
    """
    let {{ nxt }} = {{ prv }}.map(e =>
        (function (str, chars) {
            return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');
        })(e, {{ substr }})
    );
    """
)

J2_PRE_STR_RIGHT_TRIM = Template(
    """
    let {{ nxt }} = (function (str, chars) {
        return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
    })({{ prv }}, {{ substr }});
    """
)

J2_PRE_LIST_STR_RIGHT_TRIM = Template(
    """
    let {{ nxt }} = {{ prv }}.map(e =>
        (function (str, chars) {
            return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');
        })(e, {{ substr }})
    );
    """
)

J2_PRE_XPATH = Template("""
let {{ nxt }} = document.evaluate(
    "{{ query }}", {{ prv }}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
).singleNodeValue;
""")

J2_PRE_XPATH_ALL = Template("""
let {{ snapshot_var }} = {{ prv }}.evaluate(
    "{{ query }}", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null
); 
let {{ nxt }} = Array.from({ length: {{ snapshot_var }}.snapshotLength }, (_, i) => 
    {{ snapshot_var }}.snapshotItem(i)
);
""")


J2_IS_XPATH = Template("""
if (document.evaluate("{{ query }}", {{ prv }}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue === null) throw new Error({{ msg }});
""")
# TODO: use in covverter
JS_HAS_ATTR = Template("""
if (!{{prv}}?.hasAttribute({{key}}) throw new Error({{ msg }});
""")


JS_HAS_ATTR_ALL = Template("""
if (!{{prv}}.every(e => e?.hasAttribute({{key}}));}) throw new Error({{ msg }});
""")
