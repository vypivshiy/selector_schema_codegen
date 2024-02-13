import inspect
import warnings
from dataclasses import dataclass
from typing import Optional, Callable

from ssc_codegen.converters.base import CodeConverter
from ssc_codegen.document import Document
from ssc_codegen.objects import Node, TokenType, EXPR_INIT, EXPR_RET, EXPR_NO_RET, \
    create_default_expr
from ssc_codegen.schemas import BaseSchemaStrategy, SchemaType


@dataclass(repr=False, kw_only=True)
class Method:
    instance: Callable[[Document], Document]
    IS_VALIDATOR: bool = False

    @property
    def name(self) -> str:
        return self.instance.__name__

    @property
    def docstring(self) -> Optional[str]:
        return self.instance.__doc__

    @property
    def ast(self) -> dict[int, Node]:
        doc = self.instance(Document())
        return build_ast(doc, name=self.name, is_validator=self.IS_VALIDATOR)

    def code(self, converter: CodeConverter):
        return [converter.convert(node) for i, node in self.ast.items()]

    def __repr__(self):
        return f"{self.name}({self.ast})"


@dataclass(repr=False, kw_only=True)
class StructParser:
    _ATTR_PRE_VALIDATE = "__pre_validate_document__"
    _ATTR_SPLIT_DOCUMENT = "__split_document_entrypoint__"

    instance: BaseSchemaStrategy

    @property
    def pre_validate(self) -> Optional[Method]:
        if method := getattr(self.instance, self._ATTR_PRE_VALIDATE, None):
            if method(Document()):
                return Method(
                    instance=method,
                    IS_VALIDATOR=True
                )
        return None

    @property
    def split_document(self) -> Optional[Method]:
        if self.instance.TYPE is SchemaType.ITEM:
            warnings.warn('ItemStruct type not allowed split method, skip')
        elif method := getattr(self.instance, self._ATTR_SPLIT_DOCUMENT, None):
            if method(Document()):
                return Method(
                    instance=method,
                )
        return None

    @property
    def name(self):
        return self.instance.__class__.__name__

    @property
    def docstring(self):
        return self.instance.__class__.__doc__

    @property
    def methods(self) -> list[Method]:
        methods: list[Method] = []
        for attr_name in self.instance.__class__.__dict__.keys():
            if attr_name.startswith("__") and attr_name.endswith("__"):
                continue
            method: Callable[[Document], Document] = getattr(self.instance, attr_name)
            args = inspect.signature(method).parameters
            document_param_name = list(args.keys())[0]
            if (doc_param := args.get(document_param_name)) and doc_param.annotation.__name__ == Document.__name__:
                doc = method(Document())
                _ast = build_ast(doc)
                methods.append(
                    Method(instance=method)
                )
        return methods

    def __repr__(self):
        return (f"{self.name}(validate={bool(self.pre_validate) or None}, split={bool(self.split_document) or None} "
                f"methods={len(self.methods)})")


def document_to_ast(doc: Document) -> dict[int, Node]:
    count = len(doc.get_stack)
    _tree: dict[int, Node] = {}

    for i, e in enumerate(doc.get_stack):
        node = Node(
            num=i,
            count=count,
            expression=e,
            prev=None,
            next=None,
            ast_tree=_tree,
        )
        if i - 1 >= 0:
            node.prev = i - 1
        if i + 1 < count:
            node.next = i + 1

        _tree[i] = node
    return _tree


def build_ast(doc: Document, name: Optional[str] = None, is_validator: bool = False):
    # head_expr = create_expr_head(name)
    init_expr = EXPR_INIT
    ret_expr = EXPR_NO_RET if is_validator else EXPR_RET

    # wrap code to try/except
    if doc.get_stack[0].token_type == TokenType.OP_DEFAULT:
        doc = create_default_expr(doc)

    # form function, return expr
    if doc.get_stack[0].token_type is not TokenType.OP_FUNCTION_HEAD:
        doc.insert(0, init_expr)
        # doc.insert(0, head_expr)

    if doc.get_stack[-1].token_type not in (TokenType.OP_RET, TokenType.OP_NO_RET):
        doc.append(ret_expr)
    return document_to_ast(doc)


def translate_to_struct(obj: BaseSchemaStrategy):
    return StructParser(
        instance=obj)
