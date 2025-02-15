from typing import Literal, TypeAlias

from ssc_codegen.tokens import VariableType, JsonVariableType

RESERVED_METHODS = {
    "__PRE_VALIDATE__",
    "__SPLIT_DOC__",
    "__KEY__",
    "__VALUE__",
    "__ITEM__",
    "__START_PARSE__",
}

M_START_PARSE: TypeAlias = Literal["__START_PARSE__"]
M_PRE_VALIDATE: TypeAlias = Literal["__PRE_VALIDATE__"]
M_SPLIT_DOC: TypeAlias = Literal["__SPLIT_DOC__"]
M_ITEM: TypeAlias = Literal["__ITEM__"]
M_KEY: TypeAlias = Literal["__KEY__"]
M_VALUE: TypeAlias = Literal["__VALUE__"]


SIGNATURE_MAP = {
    VariableType.STRING: "String",
    VariableType.LIST_STRING: "Array<String>",
    VariableType.OPTIONAL_STRING: "String | null",
    VariableType.OPTIONAL_LIST_STRING: "Array<String> | null",
    VariableType.NULL: "null",
    VariableType.INT: "Int",
    VariableType.OPTIONAL_INT: "Int | null",
    VariableType.LIST_INT: "Array<Int>",
    VariableType.OPTIONAL_LIST_INT: "Array<Int> | null",
    VariableType.FLOAT: "Float",
    VariableType.OPTIONAL_FLOAT: "Float | null",
    VariableType.OPTIONAL_LIST_FLOAT: "Array<Float> | null",
    VariableType.LIST_FLOAT: "Array<Float>",
    VariableType.ANY: "Any",
}

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
}
