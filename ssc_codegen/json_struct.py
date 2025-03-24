"""json marker for .jsonify chain method


NOTE: generate schemas for rest-api use tools like OpenAPI specs generators from requests and response.
this solution used for parse json inner HTML documents
"""

from dataclasses import dataclass, field
from types import GenericAlias, UnionType, NoneType
from typing import get_args, Any, Union, TypeAlias, Type

from ssc_codegen.consts import JSON_SIGNATURE_MAP
from ssc_codegen.tokens import JsonVariableType

_TokenValue: TypeAlias = Union["JsonType"]


@dataclass()
class JsonType:
    type: JsonVariableType
    name: str = ""  # stub for link nested Json / Array<Json> types
    fields: dict[str, "JsonType"] = field(default_factory=dict)


class Json:
    """marker class and fields as generate json objects

    NOTE:
        NOT FOR REST-API CONFIGURATION, its coverage case, where json-like object in html document

    MAGIC methods:
        - __IS_ARRAY__ - marks if passed raw json as list/array type

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

    @classmethod
    def _annotation_to_token(cls, type_: Any) -> JsonType:
        if type_ is None or type_ is NoneType:
            return JsonType(JsonVariableType.NULL)
        elif token_ := cls.__TYPE_MAPPING__.get(type_):
            return JsonType(token_)
        # list (empty)
        elif type_ is list and len(get_args(type_)) == 0:
            return JsonType(JsonVariableType.ARRAY)
        # list[T]
        elif isinstance(type_, GenericAlias):
            args = get_args(type_)
            if issubclass(args[0], Json):
                return JsonType(
                    JsonVariableType.ARRAY_OBJECTS,
                    name=args[0].__name__,
                    fields=args[0].get_fields(),
                )
            if not cls.__ARRAY_TYPE_MAPPING__.get(args[0]):
                msg = f"list not support type {args[0].__name__}"
                raise TypeError(msg)
            array_type = cls.__ARRAY_TYPE_MAPPING__[args[0]]
            return JsonType(array_type)
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
                    return JsonType(JsonVariableType.OPTIONAL_STRING)
                case int():
                    return JsonType(JsonVariableType.OPTIONAL_NUMBER)
                case float():
                    return JsonType(JsonVariableType.OPTIONAL_FLOAT)
                case bool():
                    return JsonType(JsonVariableType.OPTIONAL_BOOLEAN)
                case _:
                    msg = f"{cls.__name__}: not support {args[0]!r} type"
                    raise TypeError(msg)

        elif issubclass(type_, Json):
            return JsonType(
                JsonVariableType.OBJECT,
                name=type_.__name__,
                fields=type_.get_fields(),
            )
        raise TypeError(f"{cls.__name__}: invalid type {type_} (not supported)")

    @classmethod
    def get_fields(cls) -> dict[str, JsonType]:
        return {
            key: cls._annotation_to_token(type_)
            for key, type_ in cls.__annotations__.items()
        }


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
    tmp_tokens = fields.copy()
    for k, doc_field in fields.items():
        tmp_tokens[k] = json_type_to_str_signature(doc_field)
    return [tmp_tokens, "..."] if json_struct.__IS_ARRAY__ else tmp_tokens
