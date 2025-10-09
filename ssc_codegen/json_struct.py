"""json marker for .jsonify chain method with key customization support

NOTE: generate schemas for rest-api use tools like OpenAPI specs generators from requests and response.
this solution used for parse json inner HTML documents
"""

from dataclasses import dataclass, field
from types import GenericAlias, UnionType, NoneType
from typing import get_args, Any, Type
from ssc_codegen.tokens import JsonVariableType

JSON_SIGNATURE_MAP = {
    JsonVariableType.NULL: "null",
    JsonVariableType.BOOLEAN: "Bool",
    JsonVariableType.STRING: "String",
    JsonVariableType.NUMBER: "Int",
    JsonVariableType.FLOAT: "Float",
    JsonVariableType.OPTIONAL_BOOLEAN: "Bool | null",
    JsonVariableType.OPTIONAL_FLOAT: "Float | null",
    JsonVariableType.OPTIONAL_NUMBER: "Int | null",
    JsonVariableType.OPTIONAL_STRING: "String | null",
    JsonVariableType.ARRAY_FLOAT: "Array<Float>",
    JsonVariableType.ARRAY_STRING: "Array<String>",
    JsonVariableType.ARRAY_NUMBER: "Array<Int>",
    JsonVariableType.ARRAY_BOOLEAN: "Array<Bool>",
    JsonVariableType.ARRAY: "Array<>",
}


@dataclass()
class JsonType:
    type: JsonVariableType
    name: str = ""  # stub for link nested Json / Array<Json> types
    fields: dict[str, "JsonType"] = field(default_factory=dict)
    original_field: str = ""  # original field name as in class
    mapped_field: str = ""  # mapped JSON key name

    def get_mapped_field(self) -> str:
        """Priority get field name

        1. mapped field
        2. original field
        3. name
        """
        if self.mapped_field:
            return self.mapped_field
        elif self.original_field:
            return self.original_field
        return self.name


@dataclass()
class JsonField:
    """Descriptor for custom JSON field configuration"""

    json_key: str | None = None
    description: str = ""
    required: bool = True

    def __set_name__(self, _owner: Any, name: str) -> None:
        self.field_name = name
        if self.json_key is None:
            self.json_key = name


class Json:
    """marker class and fields as generate json objects

    NOTE:
        NOT FOR REST-API CONFIGURATION, its coverage case, where json-like object in html document

    MAGIC methods:
        - __IS_ARRAY__ - marks if passed raw json as list/array type
        - __KEY_MAPPING__ - dict mapping field names to custom JSON keys

    support types:
        - T:
            - int - number
            - str - string
            - bool - boolean
            - float - float
            - None - null
        - T | None - optional type
        - list[T] - array of items
        - Json[T] - same class annotate reference (map/dict). keys should be a string
    """

    __TYPE_MAPPING__ = {
        str: JsonVariableType.STRING,
        int: JsonVariableType.NUMBER,
        float: JsonVariableType.FLOAT,
        bool: JsonVariableType.BOOLEAN,
        NoneType: JsonVariableType.NULL,
    }

    __ARRAY_TYPE_MAPPING__ = {
        str: JsonVariableType.ARRAY_STRING,
        int: JsonVariableType.ARRAY_NUMBER,
        float: JsonVariableType.ARRAY_FLOAT,
        bool: JsonVariableType.ARRAY_BOOLEAN,
    }

    __IS_ARRAY__: bool = False
    """marks is array entrypoint"""

    __KEY_MAPPING__: dict[str, str] = {}
    """mapping from field name to custom JSON key"""

    @classmethod
    def _get_json_key(cls, field_name: str) -> str:
        """Get the JSON key for a field, considering custom mappings"""
        # Check __KEY_MAPPING__ mapping
        if hasattr(cls, "__KEY_MAPPING__") and cls.__KEY_MAPPING__.get(
            field_name
        ):
            return cls.__KEY_MAPPING__[field_name]

        # Default to field name
        return field_name

    @classmethod
    def _annotation_to_token(
        cls, type_: Any, original_field: str = ""
    ) -> JsonType:
        if type_ is None or type_ is NoneType:
            return JsonType(
                JsonVariableType.NULL, original_field=original_field
            )
        elif token_ := cls.__TYPE_MAPPING__.get(type_):
            return JsonType(token_, original_field=original_field)
        # list (empty)
        elif type_ is list and len(get_args(type_)) == 0:
            return JsonType(
                JsonVariableType.ARRAY, original_field=original_field
            )
        # list[T]
        elif isinstance(type_, GenericAlias):
            args = get_args(type_)
            if issubclass(args[0], Json):
                return JsonType(
                    JsonVariableType.ARRAY_OBJECTS,
                    name=args[0].__name__,
                    fields=args[0].get_fields(),
                    original_field=original_field,
                )
            if not cls.__ARRAY_TYPE_MAPPING__.get(args[0]):
                msg = f"list not support type {args[0].__name__}"
                raise TypeError(msg)
            array_type = cls.__ARRAY_TYPE_MAPPING__[args[0]]
            return JsonType(array_type, original_field=original_field)
        # T | optional
        elif isinstance(type_, UnionType):
            args = get_args(type_)
            if len(args) != 2:
                raise TypeError(
                    f"{cls.__name__}: union type requires 2 arguments"
                )
            elif len(args) > 2:
                raise TypeError(
                    f"{cls.__name__}: too many arguments: required 2"
                )
            elif args[1] != NoneType:
                if args[0] == NoneType:
                    args = (args[1], args[0])
                else:
                    t_get = args[1]
                    raise TypeError(
                        f"{cls.__name__}: union type should be a None, got {t_get!r}"
                    )
            match args[0]():
                case str():
                    return JsonType(
                        JsonVariableType.OPTIONAL_STRING,
                        original_field=original_field,
                    )
                case int():
                    return JsonType(
                        JsonVariableType.OPTIONAL_NUMBER,
                        original_field=original_field,
                    )
                case float():
                    return JsonType(
                        JsonVariableType.OPTIONAL_FLOAT,
                        original_field=original_field,
                    )
                case bool():
                    return JsonType(
                        JsonVariableType.OPTIONAL_BOOLEAN,
                        original_field=original_field,
                    )
                case _:
                    msg = f"{cls.__name__}: not support {args[0]!r} type"
                    raise TypeError(msg)

        elif issubclass(type_, Json):
            return JsonType(
                JsonVariableType.OBJECT,
                name=type_.__name__,
                fields=type_.get_fields(),
                original_field=original_field,
            )
        raise TypeError(f"{cls.__name__}: invalid type {type_} (not supported)")

    @classmethod
    def get_fields(cls) -> dict[str, JsonType]:
        """Get fields with custom JSON keys applied"""
        result = {}
        for field_name, type_ in cls.__annotations__.items():
            json_key = cls._get_json_key(field_name)

            json_type = cls._annotation_to_token(
                type_,
                original_field=field_name,
            )
            if field_name != json_key:
                json_type.mapped_field = json_key
            result[json_key] = json_type
        return result

    @classmethod
    def get_key_mapping(cls) -> dict[str, str]:
        """Get mapping from JSON keys back to field names"""
        mapping = {}
        for field_name in cls.__annotations__.keys():
            json_key = cls._get_json_key(field_name)
            mapping[json_key] = field_name
        return mapping


def json_type_to_str_signature(json_field: JsonType | str) -> Any:
    if isinstance(json_field, str):
        return json_field
    elif json_field.type == JsonVariableType.ARRAY_OBJECTS:
        return [
            {
                k: json_type_to_str_signature(v)
                for k, v in json_field.fields.items()
            },
            "...",
        ]
    elif json_field.type == JsonVariableType.OBJECT:
        return {
            k: json_type_to_str_signature(v)
            for k, v in json_field.fields.items()
        }
    elif JSON_SIGNATURE_MAP.get(json_field.type):
        return JSON_SIGNATURE_MAP.get(json_field.type)
    raise NotImplementedError("Unreachable code")


def json_struct_to_signature(json_struct: Type[Json]) -> Any:
    """function helper for generate docstring signature in schema"""
    fields = json_struct.get_fields()
    tmp_tokens = {}
    for json_key, json_type in fields.items():
        tmp_tokens[json_key] = json_type_to_str_signature(json_type)
    return [tmp_tokens, "..."] if json_struct.__IS_ARRAY__ else tmp_tokens


if __name__ == "__main__":

    class B(Json):
        __KEY_MAPPING__ = {"bar": "@--id"}
        bar: int

    class A(Json):
        __KEY_MAPPING__ = {"schema": "@schema"}
        schema: str
        foo: B

    print(A.get_fields())
    # {'@schema': JsonType(type=<JsonVariableType.STRING: 2>, name='', fields={}, original_field='schema', mapped_field='')}
