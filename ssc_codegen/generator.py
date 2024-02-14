import inspect
import warnings
from dataclasses import dataclass
from typing import Optional, Callable

from ssc_codegen.converters.base import CodeConverter
from ssc_codegen.document import Document
from ssc_codegen.objects import Node, TokenType, EXPR_INIT, create_default_expr, EXPR_RET, EXPR_NO_RET
from ssc_codegen.schemas import BaseSchemaStrategy, SchemaType


@dataclass(repr=False, kw_only=True)
class Method:
    instance: Callable[[Document], Document]
    IS_VALIDATOR: bool = False
    IS_SPLIT_DOCUMENT: bool = False

    @property
    def name(self) -> str:
        return self.instance.__name__

    @property
    def docstring(self) -> Optional[str]:
        return self.instance.__doc__

    @property
    def ast(self) -> dict[int, Node]:
        doc = self.instance(Document())
        return build_ast(doc, name=self.name, is_validator=self.IS_VALIDATOR, is_split_document=self.IS_SPLIT_DOCUMENT)

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
                    IS_SPLIT_DOCUMENT=True
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


def build_ast(doc: Document, name: Optional[str] = None, is_validator: bool = False, is_split_document: bool = False):
    # head_expr = create_expr_head(name)
    init_expr = EXPR_INIT
    ret_expr = EXPR_NO_RET if is_validator else EXPR_RET

    # check correct stack operations
    if not is_validator and not is_split_document and doc.get_stack[-1].token_type in (TokenType.OP_CSS,
                                                                                       TokenType.OP_CSS_ALL,
                                                                                       TokenType.OP_XPATH,
                                                                                       TokenType.OP_XPATH_ALL):
        msg = 'Final operation must not end with operations (`css`, `css_all`, `xpath`, `xpath_all`)'
        raise SyntaxError(msg)

    elif is_split_document and doc.get_stack[-1].token_type not in (TokenType.OP_XPATH_ALL, TokenType.OP_CSS_ALL):
        msg = 'Split document method should be end with operation `css_all` or `xpath_all`'
        raise SyntaxError(msg)

    # wrap code to try/except
    if doc.get_stack[0].token_type == TokenType.OP_DEFAULT:
        doc = create_default_expr(doc)

    # push return expr before OP_DEFAULT_END expr
    if doc.get_stack[0].token_type == TokenType.OP_DEFAULT_START:
        doc.insert(-1, ret_expr)

    elif doc.get_stack[-1].token_type not in (TokenType.OP_RET, TokenType.OP_NO_RET):
        doc.append(ret_expr)

    # init constructor (generated variables provider)
    # eg:
    # def spam(_, doc: Document):
    #   var_0 = doc
    #   ...
    doc.insert(0, init_expr)
    return document_to_ast(doc)


def translate_to_struct(obj: BaseSchemaStrategy):
    return StructParser(
        instance=obj)
