from jinja2 import Template

# used functions instead consts arrow functions for allow rewrite it wout errors
HELPER_FUNCTIONS = r"""
function sscUnescape(v) {
  return v
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&#x2F;/g, '/')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#x([0-9a-fA-F]+);/g, function(_, hex) {
      return String.fromCharCode(parseInt(hex, 16));
    })
    .replace(/\\u([0-9a-fA-F]{4})/g, function(_, hex) {
      return String.fromCharCode(parseInt(hex, 16));
    })
    .replace(/\\x([0-9a-fA-F]{2})/g, function(_, hex) {
      return String.fromCharCode(parseInt(hex, 16));
    })
    .replace(/\\([bfnrt])/g, function(_, ch) {
      return { b: '\b', f: '\f', n: '\n', r: '\r', t: '\t' }[ch];
    });
}

function sscRmPrefix(v, p) {
  return v.startsWith(p) ? v.slice(p.length) : v;
}

function sscRmSuffix(v, s) {
  return v.endsWith(s) ? v.slice(0, -s.length) : v;
}

function sscRmPrefixSuffix(v, p, s) {
  return sscRmSuffix(sscRmPrefix(v, p), s);
}
 
"""

J2_STRUCT_INIT = """
constructor(doc){
if (typeof doc === 'string'){
this._doc = new DOMParser().parseFromString(doc, 'text/html');
} else if (doc instanceof Document || doc instanceof Element){
this._doc = doc.cloneNode(true);
} else {
throw new Error("Invalid input: Expected a Document, Element, or string");}
}
"""

J2_START_PARSE_DICT = "return Array.from(this._splitDoc(this._doc)).reduce((item, e) => (item[this._parseKey(e)] = this._parseValue(e), item), {});"
J2_START_PARSE_FLAT_LIST = "return Array.from(this._splitDoc(this._doc)).map((e) => this._parseItem(e));"
J2_START_PARSE_ACC_LIST = Template(
    """
return [...new Set([
{% for expr in exprs %}
this._parse{{ expr.upper_name }}(this._doc),
{% endfor %}
].flat())];
"""
)
J2_START_PARSE_ITEM = Template("""return {
{% for expr in exprs %}
    {%- if expr.is_classvar -%}
        {{ expr.name }}: {{ expr.upper_name }},
    {%- else -%}
        {{ expr.name }}: this._parse{{ expr.upper_name }}(this._doc),
    {%- endif -%}
{% endfor %}
};""")

J2_START_PARSE_LIST_PARSE = Template("""return Array.from(this._splitDoc(this._doc)).map((e) => ({
{% for expr in exprs %}
    {%- if expr.is_classvar -%}
        {{ expr.name }}: {{ expr.upper_name }},
    {%- else -%}
        {{ expr.name }}: this._parse{{ expr.upper_name }}(e),
    {%- endif -%}
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
