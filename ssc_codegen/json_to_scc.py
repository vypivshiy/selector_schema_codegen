import json
import re
import logging

from ssc_codegen.str_utils import to_upper_camel_case

_BAD_STRING_STARTS = re.compile(r"^[\d\W]")

LOGGER = logging.getLogger("ssc_gen")


def _process_json_field(
    key: str, value, parent_name: str, accumulated_schemas: list[str]
) -> str:
    """Process a single JSON field and return the field definition line."""
    if value is None:
        LOGGER.debug("%s.%s = null", parent_name, key)
        return f"\n    {key}: None"

    elif isinstance(value, (str, int, float, bool)):
        LOGGER.debug("%s.%s = %s", parent_name, key, type(value).__name__)
        return f"\n    {key}: {type(value).__name__}"

    elif isinstance(value, list):
        return _process_list_field(key, value, parent_name, accumulated_schemas)

    elif isinstance(value, dict):
        return _process_dict_field(key, value, parent_name, accumulated_schemas)

    return ""


def _process_list_field(
    key: str, value: list, parent_name: str, accumulated_schemas: list[str]
) -> str:
    """Process a list field and return the field definition line."""
    if len(value) > 0:
        first_type = type(value[0])
    else:
        LOGGER.warning(
            "`%s.%s` key has empty array, set String.\nRequired manual fix or extra research json struct for correct detect type or structs",
            parent_name,
            key,
        )
        first_type = str
        value.append("_MISSING_TYPE")

    if any(type(item) is not first_type for item in value):
        msg = f"array field {key} items not contains a same types"
        raise TypeError(msg)

    if first_type is dict:
        sub_class_name = to_upper_camel_case(key)
        LOGGER.debug("%s.%s = Array<%s<Map>>", parent_name, key, sub_class_name)
        _generate_schema_for_data(value[0], sub_class_name, accumulated_schemas)
        return f"\n    {key}: list[{sub_class_name}]"
    else:
        LOGGER.debug(
            "%s.%s = Array<%s>", parent_name, key, type(value[0]).__name__
        )
        return f"\n    {key}: list[{type(value[0]).__name__}]"


def _process_dict_field(
    key: str, value: dict, parent_name: str, accumulated_schemas: list[str]
) -> str:
    """Process a dict field and return the field definition line."""
    sub_class_name = to_upper_camel_case(key)
    LOGGER.debug("%s.%s = %s<Map>", parent_name, key, sub_class_name)
    _generate_schema_for_data(value, sub_class_name, accumulated_schemas)
    return f"\n    {key}: {sub_class_name}"


def _generate_schema_for_data(
    data: dict, class_name: str, accumulated_schemas: list[str]
) -> None:
    """Generate schema code for a data structure and add it to accumulated schemas."""
    code = f"class {class_name}(Json):"

    for key, value in data.items():
        field_line = _process_json_field(
            key, value, class_name, accumulated_schemas
        )
        code += field_line

    accumulated_schemas.append(code)


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
        err = TypeError(f"Bad entrypoint name string char: {result[0]}")
        LOGGER.error(err)
        raise err

    if isinstance(data, str):
        data = json.loads(data)
    elif isinstance(data, list):
        # naive apologize, list contains same dict items
        if not isinstance(data[0], dict) or _sub_schemas_acc:
            err = TypeError("json response must be a starts as dict")
            LOGGER.error(err)
            raise err
        data = data[0]
        is_array_response = True

    sub_schemas_codes = _sub_schemas_acc or []
    name_entrypoint = to_upper_camel_case(name_entrypoint)
    LOGGER.debug("Entrypoint name: %s", name_entrypoint)

    code = f"class {name_entrypoint}(Json):"
    code += "\n    __IS_ARRAY__ = True" if is_array_response else ""

    for key, value in data.items():  # type: ignore[union-attr]
        field_line = _process_json_field(
            key, value, name_entrypoint, sub_schemas_codes
        )
        code += field_line

    return code, sub_schemas_codes


def convert_json_to_schema_code(
    data: str | dict,
    start_name_entrypoint: str = "Main",
    json_start_path: str = "",
) -> str:
    """convert json-like string or python dict to schema code"""
    LOGGER.debug("Start convert json")
    jsn = json.loads(data) if isinstance(data, str) else data
    parts = json_start_path.split(".")
    for i, part in enumerate(parts):
        part = int(part) if part.isdigit() else part
        try:
            jsn = jsn[part]
        except IndexError as e:
            last_part = ".".join(parts[:i])
            LOGGER.error("`%s`, json index not exists", last_part)
            raise e
        except KeyError as e:
            last_part = ".".join(parts[:i])
            LOGGER.error("`%s`, json key not exists", last_part)
            raise e

    data = json.dumps(jsn)
    code, sub_codes = json_response_to_schema_code(data, start_name_entrypoint)
    return "\n\n".join(sub_codes) + "\n\n" + code


if __name__ == "__main__":
    jsn = '{"a": ["b", "c"], "attributes": {"spam": 1.0, "eggs": "foobar", "default": null}}'
    jsn2 = """
    {"props": {
        "pageProps": {
            "findPageMeta": {
                "searchTerm": "matrix",
                "includeAdult": false,
                "isExactMatch": true,
                "searchType": "TITLE"
            }
        }
    }
    }
"""
    out = convert_json_to_schema_code(jsn, "Content")
    print(out)
    out = convert_json_to_schema_code(jsn2, "Content")
    print(out)

