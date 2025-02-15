"""json marker for .jsonify chain method


NOTE: generate schemas for rest-api use tools like OpenAPI specs generators from requests and response.
this solution used for parse json inner HTML documents
"""

from types import GenericAlias, UnionType, NoneType
from typing import get_args, Any, Union, TypeAlias

from .consts import JSON_SIGNATURE_MAP
from .tokens import JsonVariableType, JsonFieldType


_TokenValue: TypeAlias = Union[JsonVariableType, "JsonList", "Json"]


class BaseJsonType:
    TYPE = NotImplemented
    kind: JsonFieldType = NotImplemented


class JsonType(BaseJsonType):
    kind = JsonFieldType.BASIC

    def __init__(self, type_: JsonVariableType):
        self.TYPE = type_

    def __repr__(self):
        return repr(self.TYPE)


class JsonList(BaseJsonType):
    kind = JsonFieldType.ARRAY

    def __init__(self, type_: JsonVariableType | BaseJsonType) -> None:
        self.TYPE = type_

    def __repr__(self):
        return f"Array[{self.TYPE!r}]"


class JsonObject(BaseJsonType):
    kind = JsonFieldType.OBJECT

    def __init__(self, type_: dict[str, JsonVariableType], name: str) -> None:
        self.TYPE = type_
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def __repr__(self):
        return f"Object_{self.name}({self.TYPE!r})"


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

    __IS_ARRAY__: bool = False
    """marks is array entrypoint"""

    @classmethod
    def _annotation_to_token(cls, type_: Any) -> BaseJsonType:
        if type_ is None:
            return JsonType(JsonVariableType.NULL)
        elif token_ := cls.__TYPE_MAPPING__.get(type_):
            return JsonType(token_)

        elif isinstance(type_, GenericAlias):
            args = get_args(type_)
            if not args:
                msg = f"{cls.__name__}: list type required annotation"
                raise TypeError(msg)
            jsn_token = JsonList(cls._annotation_to_token(args[0]))
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
            # TODO: Refactoring
            if args[0] is str:
                return JsonType(JsonVariableType.OPTIONAL_STRING)
            elif args[0] is int:
                return JsonType(JsonVariableType.OPTIONAL_NUMBER)
            elif args[0] is float:
                return JsonType(JsonVariableType.OPTIONAL_FLOAT)
            elif args[0] is bool:
                return JsonType(JsonVariableType.OPTIONAL_BOOLEAN)
            else:
                msg = f"{cls.__name__}: not support {args[0]!r} type"
                raise TypeError(msg)

        elif issubclass(type_, Json):
            jsn_token = JsonObject(type_.tokenize(), type_.__name__)
        else:
            raise TypeError(
                f"{cls.__name__}: invalid type {type_} (not supported)"
            )
        return jsn_token

    @classmethod
    def tokenize(cls) -> dict[str, BaseJsonType | JsonVariableType]:
        return {
            key: cls._annotation_to_token(type_)
            for key, type_ in cls.__annotations__.items()
        }


def json_type_to_str_signature(json_field: BaseJsonType) -> Any:
    if isinstance(json_field, JsonType):
        return JSON_SIGNATURE_MAP.get(json_field.TYPE)
    elif isinstance(json_field, JsonObject):
        return {
            k: JSON_SIGNATURE_MAP.get(v)
            if isinstance(v, JsonVariableType)
            else json_type_to_str_signature(v)
            for k, v in json_field.TYPE.items()
        }
    elif isinstance(json_field, JsonList):
        return (
            JSON_SIGNATURE_MAP.get(json_field.TYPE)
            if isinstance(json_field, JsonVariableType)
            else json_type_to_str_signature(json_field.TYPE)
        )
    return ""


def json_struct_to_signature(json_struct: Json) -> Any:
    """function helper for generate docstring signature in schema"""
    fields = json_struct.tokenize()
    tmp_tokens = fields.copy()
    for k, field in fields.items():
        tmp_tokens[k] = json_type_to_str_signature(field)
    return [tmp_tokens, "..."] if json_struct.__IS_ARRAY__ else tmp_tokens
