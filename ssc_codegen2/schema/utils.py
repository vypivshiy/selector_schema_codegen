import json
from dataclasses import dataclass
from typing import Type, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ssc_codegen2.schema import BaseSchema

T_SCHEMA = Type["BaseSchema"]


def get_annotations(object_) -> dict[str, Type]:
    """extract annotations from object"""
    return vars(object_).get('__annotations__', {})


# help signature and AST-like build functions
def get_json_signature(schema: Type["BaseSchema"], indent: int = 2) -> str:
    return json.dumps(schema.get_fields_signature(), indent=indent)


def get_doc_signature(schema: Type["BaseSchema"]) -> str:
    return schema.__doc__ or ""


@dataclass(repr=False)
class SchemaLike:
    schema: Type["BaseSchema"]

    def items_signature(self,
                        cb: Callable[[T_SCHEMA], str] = get_json_signature):
        return cb(self.schema)

    @property
    def doc(self):
        return f"{get_doc_signature(self.schema)}\n\n{self.items_signature()}"

    def parse_nodes(self):
        ast_nodes = {}
        ast_nodes['__SPLIT_DOC__'] = self.schema.__dict__.get('__SPLIT_DOC__', None)
        ast_nodes['__PRE_VALIDATE__'] = self.schema.__dict__.get('__PRE_VALIDATE__', None)

        for i, (k, v) in enumerate(self.schema.get_fields().items()):
            ast_nodes[i] = (k, v)
