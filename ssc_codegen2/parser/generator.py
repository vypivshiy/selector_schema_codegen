import json
from dataclasses import dataclass
from typing import Type, NamedTuple, Optional

from ssc_codegen2.document import D
from ssc_codegen2.expression import Expression
from ssc_codegen2.schema import DictSchema, ListSchema, ItemSchema, BaseSchema
from ssc_codegen2.type_state import TypeVariableState


def get_json_signature(schema: Type[BaseSchema], indent: int = 2) -> str:
    return json.dumps(schema.get_fields_signature(), indent=indent)


def get_doc_signature(schema: Type[BaseSchema]) -> str:
    return schema.__doc__ or ''


def make_doc_signature(schema: Type[BaseSchema], header: str = "items signature:", indent: int = 2):
    signature = get_json_signature(schema, indent=indent)
    docstr = get_doc_signature(schema)

    return f'{docstr}\n\n{header}\n\n{signature}'


@dataclass(repr=False)
class StructAST:
    fields: list['Field']
    NAME: str
    TYPE: str
    DOC: str
    SIGNATURE: str


@dataclass(repr=False)
class Field:
    name: str
    nodes: dict[int, 'Node']


@dataclass(repr=False)
class Node:
    expr: Expression
    nodes_tree: dict[int, 'Node']
    # mark num instruction
    num_prev: Optional[int]
    num_next: Optional[int]

    @property
    def num(self):
        return self.expr.num

    @property
    def var_type(self) -> TypeVariableState:
        return self.expr.VARIABLE_TYPE

    @property
    def count(self):
        return len(self.nodes_tree)

    def __repr__(self):
        return (f"Node_[{self.num},{self.count}](prev={self.num_prev}, next={self.num_next}, "
                f"var_state={self.expr.VARIABLE_TYPE.name!r}, token={self.expr.TOKEN_TYPE.name!r})")
    
    @property
    def next_node(self) -> Optional["Node"]:
        return self.nodes_tree[self.num_next] if self.num_next is not None else None

    @property
    def prev_node(self) -> Optional["Node"]:
        return self.nodes_tree[self.num_prev] if self.num_prev is not None else None


def get_fields_signature(schema: Type[BaseSchema]):
    return schema.get_fields()


def build_ast(schema: Type[BaseSchema]) -> StructAST:
    fields = schema.get_fields()



if __name__ == '__main__':

    class SpamItem(DictSchema):
        __SPLIT_DOC__ = D().css_all('a')
        __KEY__ = D().text()
        __VALUE__ = D().raw()
        __SIGNATURE__ = {"spam1": "String", "spam2": "..."}


    class BookItem(ListSchema):
        __SPLIT_DOC__ = D().css_all('div > div')
        name: str = D().text()
        url: str = D().css('a').attr('href')
        spam: SpamItem = SpamItem


    class Page(ItemSchema):
        """main page

        usage: GET example.com
        """
        title: str = D().css('title').text()
        books: BookItem = BookItem


    s = get_fields_signature(Page)
    print()
    # print(make_doc_signature(Page))
    # print(end='\n\n')
    # print(make_doc_signature(SpamItem))
    # print(Page.get_fields())
    # print(Page.get_fields_signature())
