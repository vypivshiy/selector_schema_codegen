from dataclasses import dataclass, field
from os import PathLike
from typing import Any, Optional, Callable, TYPE_CHECKING

import yaml

from src.codegen_tools import ABCExpressionTranslator, generate_code, BlockCode
from src.lexer import tokenize, Token


__all__ = ["Info", "SchemaAttribute", "Schema", "parse_config"]

CODEGEN_STRATEGY = Callable[[list[Token], ABCExpressionTranslator], BlockCode]


@dataclass
class Info:
    """meta information"""
    id: str
    name: str
    author: str
    description: str
    source: str
    tags: str


@dataclass
class SchemaAttribute:
    name: str
    alias: Optional[str]
    doc: Optional[str]
    raw_code: str

    def generate_code(self,
                      translator: ABCExpressionTranslator,
                      code_generator: Optional[CODEGEN_STRATEGY] = None):
        code_generator = code_generator or generate_code

        tokens = tokenize(self.raw_code)
        return code_generator(tokens, translator)


@dataclass
class Schema:
    name: str
    constants: list[Any]
    pre_validate_code: Optional[str]
    split_code: Optional[str]
    doc: Optional[str]
    view_keys: list[str]
    attrs: list[SchemaAttribute] = field(default_factory=list)

    @property
    def aliases(self) -> dict[str, str]:
        return {a.name: a.alias for a in self.attrs if a.alias}

    @property
    def attrs_names(self) -> list[str]:
        return [a.name for a in self.attrs]

    def generate_pre_validate_code(self,
                                   translator: ABCExpressionTranslator,
                                   code_generator: Optional[CODEGEN_STRATEGY] = None):
        code_generator = code_generator or generate_code

        if self.pre_validate_code:
            tokens = tokenize(self.pre_validate_code)
            return code_generator(tokens, translator)
        return ""

    def generate_split_code(self,
                            translator: ABCExpressionTranslator,
                            code_generator: Optional[CODEGEN_STRATEGY] = None
                            ):
        code_generator = code_generator or generate_code
        if self.split_code:
            tokens = tokenize(self.split_code)
            return code_generator(tokens, translator)
        return ""


def _parse_class(class_name: str, content: dict[str:Any]) -> Schema:
    assert content.get("steps", None)
    assert content.get("steps").get("parser", None)
    assert content.get("steps").get("view", None)

    steps = content.get("steps")
    parser_attrs = steps.get("parser")

    schema = Schema(
        constants=content.get("constants", []),
        pre_validate_code=steps.get("validate", None),
        split_code=steps.get("split", None),
        doc=content.get("doc"),
        name=class_name,
        view_keys=content.get("steps").get("view")
    )

    for attr in parser_attrs:
        assert attr.get("name")
        attr_struct = SchemaAttribute(
            name=attr.get("name"),
            alias=attr.get("alias", None),
            doc=attr.get("doc", None),
            raw_code=attr.get("run"),
        )
        schema.attrs.append(attr_struct)
    return schema


def parse_config(file: str | PathLike[str]) -> tuple[Info, list[Schema]]:
    with open(file, "r") as f:
        yaml_data = yaml.safe_load(f)

    assert len(yaml_data["id"].split()) == 1

    info = Info(id=yaml_data.pop("id"), **yaml_data.pop("info"))
    schemas: list[Schema] = [
        _parse_class(class_name, content)
        for class_name, content in yaml_data.items()
    ]
    return info, schemas
