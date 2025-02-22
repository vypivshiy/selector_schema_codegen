import json
import re

from ssc_codegen.str_utils import to_upper_camel_case

_BAD_STRING_STARTS = re.compile(r"^[\d\W]")


def json_response_to_schema_code(
    data: str | dict,
    name_entrypoint: str = "Main",
    _sub_schemas_acc: list[str] | None = None,
) -> tuple[str, list[str]]:
    """generate schemas config from json response

    json string should be started as dict
    array items should have a same type
    class names auto converted to UpperCamelCase
    """
    is_array_response = False

    if result := _BAD_STRING_STARTS.match(name_entrypoint):
        raise TypeError(f"Bad entrypoint name string char: {result[0]}")
    if isinstance(data, str):
        data = json.loads(data)
    elif isinstance(data, list):
        # naive apologize, list contains same dict items
        if not isinstance(data[0], dict) or _sub_schemas_acc:
            raise TypeError("json response must be a starts as dict")
        data = data[0]
        is_array_response = True

    sub_schemas_codes = _sub_schemas_acc or []
    name_entrypoint = to_upper_camel_case(name_entrypoint)
    code = f"class {name_entrypoint}(Json):"
    code += "\n    __IS_ARRAY__ = True" if is_array_response else ""

    for k, v in data.items():
        if v is None:
            code += f"\n    {k}: None"
        elif isinstance(v, (str, int, float, bool)):
            code += f"\n    {k}: {type(v).__name__}"
        elif isinstance(v, list):
            first_type = type(v[0])
            if any(type(i) is not first_type for i in v):
                msg = f"array field {k} items not contains a same types"
                raise TypeError(msg)
            elif first_type is dict:
                sub_klass_name = to_upper_camel_case(k)
                code += f"\n    {k}: list[{sub_klass_name}]"
                # naive apologize: all items have same fields and types
                c, _ = json_response_to_schema_code(
                    v[0], sub_klass_name, sub_schemas_codes
                )
                sub_schemas_codes.append(c)
            else:
                code += f"\n    {k}: list[{type(v[0]).__name__}]"
        elif isinstance(v, dict):
            sub_klass_name = to_upper_camel_case(k)
            code += f"\n    {k}: {sub_klass_name}"
            c, _ = json_response_to_schema_code(
                v, sub_klass_name, sub_schemas_codes
            )
            sub_schemas_codes.append(c)
    return code, sub_schemas_codes


def convert_json_to_schema_code(
    data: str | dict,
    start_name_entrypoint: str = "Main",
) -> str:
    """convert json-like string or python dict to schema code"""
    code, sub_codes = json_response_to_schema_code(data, start_name_entrypoint)
    return "\n\n".join(sub_codes) + "\n\n" + code


if __name__ == "__main__":
    jsn = '{"a": ["b", "c"], "attributes": {"spam": 1.0, "eggs": "foobar", "default": null}}'
    out = convert_json_to_schema_code(jsn, "Content")
    print(out)
