from dataclasses import dataclass, field
from os import PathLike
from typing import Any, Optional, Type

import yaml

from src.configs.codegen_tools import ABCExpressionTranslator
from src.parser import Parser


__all__ = ["Info", "SchemaAttribute", "Schema", "parse_config"]


@dataclass
class Info:
    """meta information"""
    id: str
    name: str
    author: str
    description: str
    source: str
    tags: str
    schemas: list["Schema"] = field(default_factory=list)


@dataclass
class SchemaAttribute:
    name: str
    alias: Optional[str]
    doc: Optional[str]
    raw_code: str
    translator: Type["ABCExpressionTranslator"]
    generate_keys: dict[str, bool] = field(default_factory=dict)

    @property
    def code(self):
        return Parser(self.raw_code, self.translator, **self.generate_keys).parse()


@dataclass
class Schema:
    name: str
    constants: list[Any]
    pre_validate_code_raw: Optional[str]
    split_code_raw: Optional[str]
    view_keys: list[str]
    translator: Type[ABCExpressionTranslator]
    doc: Optional[str]
    attrs: list[SchemaAttribute] = field(default_factory=list)
    generate_keys: dict[str, bool] = field(default_factory=dict)

    @property
    def aliases(self) -> dict[str, str]:
        return {a.name: a.alias for a in self.attrs if a.alias}

    @property
    def attrs_names(self) -> list[str]:
        return [a.name for a in self.attrs]

    @property
    def pre_validate_code(self):
        if self.pre_validate_code_raw:
            return Parser(self.pre_validate_code_raw, self.translator, **self.generate_keys).parse()
        return ""

    @property
    def split_code(self):
        if self.split_code_raw:
            return Parser(self.split_code_raw, self.translator, **self.generate_keys).parse()
        return ""


def _parse_class(class_name: str, content: dict[str:Any],
                 translator: Type["ABCExpressionTranslator"],
                 generate_keys: dict[str, bool]) -> Schema:
    assert content.get("steps", None)
    assert content.get("steps").get("parser", None)
    assert content.get("steps").get("view", None)

    steps = content.get("steps")
    schema = Schema(
        name=class_name,
        constants=content.get("constants", []),  # TODO: provide constants
        pre_validate_code_raw=steps.get("validate", None),
        split_code_raw=steps.get("split", None),
        doc=content.get("doc", None),
        view_keys=content.get("steps").get("view"),
        translator=translator,
        generate_keys=generate_keys
    )

    parser_attrs = steps.get("parser")
    for attr in parser_attrs:
        assert attr.get("name")
        attr_struct = SchemaAttribute(
            name=attr.get("name"),
            alias=attr.get("alias", None),
            doc=attr.get("doc", None),
            raw_code=attr.get("run"),
            translator=translator,
            generate_keys=generate_keys
        )
        schema.attrs.append(attr_struct)
    return schema


def parse_config(file: str | PathLike[str],
                 translator: Type["ABCExpressionTranslator"],
                 generate_keys: dict[str, bool]) -> Info:
    with open(file, "r") as f:
        yaml_data = yaml.safe_load(f)

    assert len(yaml_data["id"].split()) == 1

    info = Info(id=yaml_data.pop("id"), **yaml_data.pop("info"))
    schemas: list[Schema] = [
        _parse_class(class_name, content, translator, generate_keys)
        for class_name, content in yaml_data.items()
    ]
    info.schemas = schemas
    return info
