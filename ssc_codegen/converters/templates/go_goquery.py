from jinja2 import Template

J2_START_PARSE_ITEM_BODY = Template("""
{% for var_name, method_name in methods %}
{{ var_name }}, err := p.parse{{ method_name }}(p.Document.Selection);
if err != nil {
    return nil, err;
}
{% endfor %}

item := T{{ name }} {
{{ st_args|join(', ') }},
};
return &item, nil;
}
""")

CODE_PRE_VALIDATE_CALL = """_, err := p.preValidate(p.Document.Selection);
if err != nil}
return nil, err;
}
"""

J2_START_PARSE_LIST_BODY = Template(
    """
items := make([]T{{ name }}, 0);
docParts, err := p.splitDoc(p.Document.Selection);
if err != nil {
    return nil, err;
}

for _, i := range docParts.EachIter() {
{% for var_name, method_name in methods %}
    {{ var_name }}, err := p.parse{{ method_name }}(i);
    if err != nil {
        return nil, err;
    }
{% endfor %}

    item := T{{ name }} {
        {{ st_args|join(', ') }},
    };
    items = append(items, item);
}

return &items, nil;
}
"""
)

J2_START_PARSE_DICT_BODY = Template("""
items := make(T{{ name }});
docParts, err := p.splitDoc(p.Document.Selection);
if err != nil {
    return nil, err;
}

for _, i := range docParts.EachIter() {
    key, err := p.parseKey(i);
    if err != nil {
        return nil, err;
    }

    {{ var_value }}, err := p.parseValue(i);
    if err != nil {
        return nil, err;
    }

    items[key] = {{ var_value }};
}

return &items, nil;
}
""")

J2_START_PARSE_FLAT_LIST_BODY = Template(
    """
    items := make(T{{ name }}, 0);
    docParts, err := p.splitDoc(p.Document.Selection);
    if err != nil {
        return nil, err;
    }

    for _, i := range docParts.EachIter() {
        {{ var }}, err := p.parseItem(i);
        if err != nil {
            return nil, err;
        }

        items = append(items, {{ var }});
    }

    return &items, nil;
    }
    """
)
J2_PRE_NESTED = Template("""{{ tmp_doc }} := goquery.NewDocumentFromNode({{ prv }}.Nodes[0]);
{{ tmp_st }} := {{ sc_name }}{ {{ tmp_doc }} };
{{ nxt }}, err := {{ tmp_st }}.Parse();
if err != nil {
    return nil, err;
}
""")


J2_PRE_DEFAULT_START = Template("""defer func() {
    if r := recover(); r != nil {
        result = {{ value }};
    }
}()
{{ nxt }} := {{ prv }};
""")

J2_PRE_LIST_STR_FMT = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ nxt }} = append({{ nxt }}, fmt.Sprintf({{ template }}, {{ tmp_var }}));
}
""")

J2_PRE_LIST_STR_TRIM = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ nxt }} = append({{ nxt }}, strings.Trim({{ tmp_var }}, {{ substr }}));
}
""")

J2_PRE_LIST_STR_LEFT_TRIM = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ nxt }} = append({{ nxt }}, strings.TrimLeft({{ tmp_var }}, {{ substr }}));
}
""")

J2_PRE_LIST_STR_RIGHT_TRIM = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ nxt }} = append({{ nxt }}, strings.TrimRight({{ tmp_var }}, {{ substr }}));
}
""")

J2_PRE_LIST_STR_REPLACE = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ nxt }} = append({{ nxt }}, strings.Replace({{ tmp_var }}, {{ old }}, {{ new }}, -1));
}
""")

J2_PRE_LIST_STR_REGEX_SUB = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ nxt }} = append({{ nxt }}, string(regexp.MustCompile({{ pattern }}).ReplaceAll([]byte({{ tmp_var }}), []byte({{ repl }}))));
}
""")


J2_PRE_IS_EQUAL = Template("""{% if have_default_expr %}
if !({{ prv }} == {{ item }}) {
    panic(fmt.Errorf({{ msg }}));
}
{% elif is_pre_validate_parent %}
if !({{ prv }} == {{ item }}) {
    return nil, fmt.Errorf({{ msg }});
}
{% else %}
if !({{ prv }} == {{ item }}) {
    return {{ return_type }}, fmt.Errorf({{ msg }});
}
{% endif %}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}""")


J2_PRE_IS_NOT_EQUAL = Template("""{% if have_default_expr %}
if !({{ prv }} != {{ item }}) {
    panic(fmt.Errorf({{ msg }}));
}
{% elif is_pre_validate_parent %}
if !({{ prv }} != {{ item }}) {
    return nil, fmt.Errorf({{ msg }});
}
{% else %}
if !({{ prv }} != {{ item }}) {
    return {{ return_type }}, fmt.Errorf({{ msg }});
}
{% endif %}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}""")


J2_PRE_IS_CONTAINS = Template("""{% if have_default_expr %}
if !(slices.Contains({{ prv }}, {{ item }})) {
    panic(fmt.Errorf({{ msg }}));
}
{% elif is_pre_validate_parent %}
if !(slices.Contains({{ prv }}, {{ item }})) {
    return nil, fmt.Errorf({{ msg }});
}
{% else %}
if !(slices.Contains({{ prv }}, {{ item }})) {
    return {{ return_type }}, fmt.Errorf({{ msg }});
}
{% endif %}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}""")


J2_PRE_IS_REGEX = Template("""_, {{ err_var }} := regexp.Match({{ pattern }}, []byte({{ prv }}));
if {{ err_var }} != nil {
    {% if have_default_expr %}
    panic(fmt.Errorf({{ msg }}));
    {% elif is_pre_validate_parent %}
    return nil, fmt.Errorf({{ msg }});
    {% else %}
    return {{ return_type }}, fmt.Errorf({{ msg }});
    {% endif %}
}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}""")


J2_PRE_IS_CSS = Template("""if {{ prv }}.Find({{ query }}).Length() == 0 {
    {% if have_default_expr %}
    panic(fmt.Errorf({{ msg }}));
    {% elif is_pre_validate_parent %}
    return nil, fmt.Errorf({{ msg }});
    {% else %}
    return {{ return_type }}, fmt.Errorf({{ msg }});
    {% endif %}
    
}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}
""")

J2_PRE_TO_INT = Template("""{{ nxt }}, err := strconv.Atoi({{ prv }});
if err != nil {
    {% if have_default_expr %}
    panic(err);
    {% elif is_pre_validate_parent %}
    return nil, err;
    {% else %}
    return {{ return_type }}, err;
    {% endif %}
}
""")


J2_PRE_TO_LIST_INT = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ each_var }}, err := strconv.Atoi({{ tmp_var }});
    if err != nil {
        {% if have_default_expr %}
        panic(err);
        {% elif is_pre_validate_parent %}
        return nil, err;
        {% else %}
        return {{ return_type }}, err;
        {% endif %}
    }
    {{ nxt }} = append({{ nxt }}, {{ each_var }});
}
""")


J2_PRE_TO_FLOAT = Template("""{{ nxt }}, err := strconv.ParseFloat({{ prv }}, 64);
if err != nil {
    {% if have_default_expr %}
    panic(err);
    {% elif is_pre_validate_parent %}
    return nil, err;
    {% else %}
    return {{ return_type }}, err;
    {% endif %}
}
""")


J2_PRE_TO_LIST_FLOAT = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ each_var }}, err := strconv.ParseFloat({{ tmp_var }}, 64);
    if err != nil {
        {% if have_default_expr %}
        panic(err);
        {% elif is_pre_validate_parent %}
        return nil, err;
        {% else %}
        return {{ return_type }}, err;
        {% endif %}
    }
    {{ nxt }} = append({{ nxt }}, {{ each_var }});
}
""")


J2_PRE_HTML_ATTR = Template("""{{ nxt }}, isExists := {{ prv }}.Attr({{ key }});
if !isExists {
    {% if have_default_expr %}
    panic(fmt.Errorf("attr `%s` not exists in `%v`", {{ key }}, {{ prv }}));
    {% elif is_pre_validate_parent %}
    return nil, fmt.Errorf("attr `%s` not exists in `%s`", {{ key }}, {{ prv }});
    {% else %}
    return {{ return_type }}, fmt.Errorf("attr `%s` not exists in `%s`", {{ key }}, {{ prv }});
    {% endif %}
}
""")


J2_PRE_HTML_ATTR_ALL = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ raw_var }}, isExists := {{ tmp_var }}.Attr({{ key }});
    if !isExists {
        {% if have_default_expr %}
        panic(fmt.Errorf("attr `%s` not exists in `%v`", {{ key }}, {{ tmp_var }}));
        {% elif is_pre_validate_parent %}
        return nil, fmt.Errorf("attr `%s` not exists in `%v`", {{ key }}, {{ tmp_var }}));
        {% else %}
        return {{ return_type }}, fmt.Errorf("attr `%s` not exists in `%v`", {{ key }}, {{ tmp_var }}));
        {% endif %}
    }
    {{ nxt }} = append({{ nxt }}, {{ raw_var }});
}
""")


J2_PRE_HTML_RAW = Template("""{{ nxt }}, err := {{ prv }}.Html();
if err != nil {
    {% if have_default_expr %}
    panic(err);
    {% elif is_pre_validate_parent %}
    return nil, err;
    {% else %}
    return {{ return_type }}, err;
    {% endif %}
}
""")


J2_PRE_HTML_RAW_ALL = Template("""{{ nxt }} := make({{ arr_type }}, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    {{ raw_var }}, err := {{ tmp_var }}.Html();
    if err != nil {
        {% if have_default_expr %}
        panic(err);
        {% elif is_pre_validate_parent %}
        return nil, err;
        {% else %}
        return {{ return_type }}, err;
        {% endif %}
    }
    {{ nxt }} = append({{ nxt }}, {{ raw_var }});
}
""")


J2_PRE_STR_RM_PREFIX = Template("""
{{ nxt }} := {{ prv }}
if strings.HasPrefix({{ prv }}, {{ substr }}) {
    {{ nxt }} = {{ prv }}[len({{ substr }}):];
}
""")

J2_PRE_LIST_STR_RM_PREFIX = Template("""
{{ nxt }} := make([]string, 0);
for _, {{ tmp_var }} := range {{ prv }} {
    if strings.HasPrefix({{ tmp_var }}, {{ substr }}) {
        {{ tmp_var }} = {{ tmp_var }}[len({{ substr }}):];
} 
    {{ nxt }} = append({{ nxt }}, {{ tmp_var }});
}
""")


J2_PRE_STR_RM_SUFFIX = Template("""
{{ nxt }} := {{ prv }};
if strings.HasSuffix({{ prv }}, {{ substr }}) {
    {{ nxt }} = {{ prv }}[:len({{ prv }})-len({{ substr }})];
}
""")

J2_PRE_LIST_STR_RM_SUFFIX = Template("""
{{ nxt }} := make([]string, 0); 
for _, {{ tmp_var }} := range {{ prv }} {
    if strings.HasSuffix({{ tmp_var }}, {{ substr }}) {
        {{ tmp_var }} = {{ tmp_var }}[:len({{ tmp_var }})-len({{ substr }})];
} 
    {{nxt}} = append({{ nxt }}, {{ tmp_var }});
}
""")

J2_PRE_STR_RM_PREFIX_AND_SUFFIX = Template("""
{{ nxt }} := {{ prv }};
if strings.HasPrefix({{ nxt }}, {{ substr }}) {
    {{ nxt }} = {{ nxt }}[len({{ substr }}):];
} 
if strings.HasSuffix({{ nxt }}, {{ substr }}) {
    {{ nxt }} = {{ nxt }}[:len({{ nxt }})-len({{ substr }})];
} 
""")

J2_PRE_LIST_STR_RM_PREFIX_AND_SUFFIX = Template("""
{{ nxt }} := make([]string, 0); 
for _, {{ tmp_var }} := range {{ prv }} {
    if strings.HasSuffix({{ tmp_var }}, {{ substr }}) {
        {{ tmp_var }} = {{ tmp_var }}[:len({{ tmp_var }})-len({{ substr }})];
    } 
    if strings.HasPrefix({{ tmp_var }}, {{ substr }}) {
        {{ tmp_var }} = {{ tmp_var }}[len({{ substr }}):];
    } 
    {{nxt}} = append({{ nxt }}, {{ tmp_var }});
}
""")


J2_PRE_LIST_STR_ANY_IS_RE = Template("""
re{{ nxt }} :=  regexp.MustCompile({{ pattern }});
for _, {{ tmp_var }} := range {{ prv }} {
    if re{{ nxt }}.MatchString({{ tmp_var }}) {
        break;
    }
    {% if have_default_expr %}
    panic(fmt.Errorf({{ msg }}));
    {% elif is_pre_validate_parent %}
    return nil, fmt.Errorf({{ msg }});
    {% else %}
    return {{ return_type }}, fmt.Errorf({{ msg }});
    {% endif %}
}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}
""")


J2_PRE_LIST_STR_ALL_IS_RE = Template("""
re{{ nxt }} :=  regexp.MustCompile({{ pattern }});
for _, {{ tmp_var }} := range {{ prv }} {
    if !re{{ nxt }}.MatchString({{ tmp_var }}) {
        {% if have_default_expr %}
        panic(fmt.Errorf({{ msg }}));
        {% elif is_pre_validate_parent %}
        return nil, fmt.Errorf({{ msg }});
        {% else %}
        return {{ return_type }}, fmt.Errorf({{ msg }});
        {% endif %}
    }
}
{% if not is_last_var_no_ret %}
{{ nxt }} := {{ prv }};
{% endif %}
""")
