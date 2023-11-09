from os import PathLike
from typing import Any, Optional
from dataclasses import dataclass, field

import yaml

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


@dataclass
class SchemaAttribute:
    name: str
    alias: Optional[str]
    doc: Optional[str]
    raw_code: str


@dataclass
class Schema:
    name: str
    constants: list[Any]
    pre_validate_code: Optional[str]
    split_code: Optional[str]
    doc: Optional[str]
    attrs: list[SchemaAttribute] = field(default_factory=list)


def _parse_class(class_name: str, content: dict[str: Any]) -> Schema:
    assert content.get('steps', None)
    assert content.get('steps').get('parser', None)
    assert content.get('steps').get('view', None)

    steps = content.get('steps')
    parser_attrs = steps.get('parser')

    schema = Schema(constants=content.get('constants', []),
                    pre_validate_code=steps.get('validate', None),
                    split_code=steps.get('split', None),
                    doc=content.get('doc'),
                    name=class_name)

    for attr in parser_attrs:
        assert attr.get('name')
        attr_struct = SchemaAttribute(
            name=attr.get('name'),
            alias=attr.get('alias', None),
            doc=attr.get('doc', None),
            raw_code=attr.get('run')
        )
        schema.attrs.append(attr_struct)
    return schema


def parse_config(file: str | PathLike[str]) -> tuple[Info, list[Schema]]:
    with open(file, "r") as f:
        yaml_data = yaml.safe_load(f)

    assert len(yaml_data['id'].split()) == 1

    info = Info(id=yaml_data.pop('id'), **yaml_data.pop('info'))
    schemas: list[Schema] = [_parse_class(class_name, content) for class_name, content in yaml_data.items()]
    return info, schemas
