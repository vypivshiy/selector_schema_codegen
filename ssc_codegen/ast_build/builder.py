from types import ModuleType
from typing import MutableSequence, Type, cast
import warnings
from typing_extensions import Self

from ssc_codegen.ast_ import ModuleTransformImports, ModuleUtilities
from ssc_codegen.ast_.base import BaseAstNode
from ssc_codegen.ast_.nodes_cast import ExprJsonify, ExprNested
from ssc_codegen.ast_.nodes_core import (
    CodeEnd,
    ExprCallStructClassVar,
    ExprCallStructMethod,
    ExprClassVar,
    ExprDefaultValueEnd,
    ExprDefaultValueStart,
    ExprDefaultValueWrapper,
    ExprNoReturn,
    ExprReturn,
    JsonStruct,
    JsonStructField,
    ModuleProgram,
    Docstring,
    ModuleImports,
    CodeStart,
    StartParseMethod,
    StructFieldMethod,
    StructInitMethod,
    StructParser,
    StructPartDocMethod,
    StructPreValidateMethod,
    TypeDef,
    TypeDefField,
)
from ssc_codegen.ast_build.utils import (
    generate_docstring_signature,
    extract_schemas_from_module,
    extract_json_structs_from_module,
    is_literals_only_schema,
)
from ssc_codegen.document import BaseDocument, ClassVarDocument
from ssc_codegen.document_utlis import (
    convert_css_to_xpath,
    convert_xpath_to_css,
)
from ssc_codegen.json_struct import Json
from ssc_codegen.schema import BaseSchema
from ssc_codegen.tokens import StructType, TokenType, VariableType


class AstBuilder:
    """USAGE:

    builder = AstBuilder()
    builder.add_header("test").add_json_types(*[]).add_struct_parsers(*[]).module
    """

    def __init__(
        self,
        gen_docstr: bool = True,
        css_to_xpath: bool = False,
        xpath_to_css: bool = False,
    ):
        self.module = ModuleProgram()
        self.gen_docstr = gen_docstr
        if css_to_xpath and xpath_to_css:
            raise TypeError("allowed css_to_xpath=True or xpath_to_css=True")
        self.css_to_xpath = css_to_xpath
        self.xpath_to_css = xpath_to_css

    @classmethod
    def build_from_moduletype(
        cls,
        module: ModuleType,
        gen_docstr: bool = True,
        css_to_xpath: bool = False,
        xpath_to_css: bool = False,
    ) -> ModuleProgram:
        builder = cls(
            gen_docstr=gen_docstr,
            css_to_xpath=css_to_xpath,
            xpath_to_css=xpath_to_css,
        )
        structs = extract_schemas_from_module(module)
        jsons = extract_json_structs_from_module(module)
        return (
            builder.add_header(module.__dict__.get("__doc__", None))
            .add_json_types(*jsons)
            .add_struct_parsers(*structs)
            .module
        )

    @classmethod
    def build_from_ssc_schemas(
        cls,
        *schemas: Type[BaseSchema],  # TODO: it not support json serialized
        gen_docstr: bool = False,
        css_to_xpath: bool = False,
        xpath_to_css: bool = False,
    ) -> ModuleProgram:
        builder = cls(
            gen_docstr=gen_docstr,
            css_to_xpath=css_to_xpath,
            xpath_to_css=xpath_to_css,
        )
        return (
            builder.add_header(module_doc=None)
            .add_struct_parsers(*schemas)
            .module
        )

    def add_header(self, module_doc: str | None = None) -> Self:
        if self.gen_docstr and module_doc:
            self.module.body.append(
                Docstring(kwargs={"value": module_doc}, parent=self.module)
            )
        # import node
        # fallback add ModuleImports.kwargs["transform"] if target language not allowed use multiple import directives
        self.module.body.append(
            ModuleImports(parent=self.module, kwargs={"transforms": []})
        )
        self.module.body.append(
            ModuleTransformImports(
                parent=self.module, kwargs={"transforms": []}
            )
        )
        self.module.body.append(ModuleUtilities(parent=self.module))
        # CodeStart hook node
        self.module.body.append(CodeStart(parent=self.module))
        return self

    def _json_field_nodes(
        self, jsn_obj: Type[Json], ast_jsn: JsonStruct
    ) -> None:
        for name, field_type in jsn_obj.get_fields().items():
            ast_jsn.body.append(
                JsonStructField(
                    kwargs={"name": name, "type": field_type}, parent=ast_jsn
                )
            )

    def add_json_types(self, *json_structs: Type[Json]) -> Self:
        ast_jsons = []
        for jsn_st in json_structs:
            ast_jsn = JsonStruct(
                kwargs={
                    "name": jsn_st.__name__,
                    "is_array": jsn_st.__IS_ARRAY__,
                },
                parent=self.module,
            )
            self._json_field_nodes(jsn_st, ast_jsn)
            ast_jsons.append(ast_jsn)
        self.module.body.extend(ast_jsons)
        return self

    def _ref_body_parent(self, node: BaseAstNode) -> None:
        parent = node
        for child in node.body:
            child.parent = parent

    def _literal_struct_node(self, schema: Type[BaseSchema]) -> StructParser:
        # dont required TypeDef struct generate
        literals = schema.__get_mro_classvars__().copy()
        st = StructParser(
            kwargs={
                "name": schema.__name__,
                "struct_type": StructType.CONFIG_CLASSVARS,
                "docstring": schema.__doc__ or "" if self.gen_docstr else "",
            },
            body=[f.expr() for f in literals.values()],
            parent=self.module,
        )
        self._ref_body_parent(st)
        return st

    def _ref_filter_expr(
        self, parent: BaseAstNode, parent_body: MutableSequence[BaseAstNode]
    ) -> None:
        for i in parent_body:
            i.parent = parent
            if i.body:
                self._ref_filter_expr(i, i.body)

    def _ref_method_exprs(self, node_method: BaseAstNode) -> None:
        parent = node_method
        for expr in node_method.body:
            expr.parent = parent
            if expr.kind in (TokenType.EXPR_FILTER, TokenType.EXPR_DOC_FILTER):
                self._ref_filter_expr(expr, expr.body)

    def _unwrap_default_node(
        self,
        stack: list[BaseAstNode],  # noqa (use sideeffect for path stack exprs)
        ret_type: VariableType,
    ) -> None:
        if stack[0].kind == ExprDefaultValueWrapper.kind:
            default_expr = stack.pop(0)
            value = default_expr.kwargs["value"]
            classvar_hooks = default_expr.classvar_hooks
            default_type = ret_type
            if value is None:
                match ret_type:
                    case VariableType.STRING:
                        default_type = VariableType.OPTIONAL_STRING
                    case VariableType.INT:
                        default_type = VariableType.OPTIONAL_INT
                    case VariableType.FLOAT:
                        default_type = VariableType.OPTIONAL_FLOAT
                    case VariableType.LIST_STRING:
                        default_type = VariableType.OPTIONAL_LIST_STRING
                    case VariableType.LIST_INT:
                        default_type = VariableType.OPTIONAL_LIST_INT
                    case VariableType.LIST_FLOAT:
                        default_type = VariableType.OPTIONAL_LIST_FLOAT
                    # TODO: warning for BOOL type
                    case _:
                        warnings.warn(
                            f"'None' default value not allowed return type '{ret_type.name}'. ",
                            category=SyntaxWarning,
                        )
                        default_type = VariableType.ANY
            elif isinstance(value, list):
                # todo: check if empty list passed
                match ret_type:
                    case VariableType.LIST_STRING:
                        default_type = VariableType.LIST_STRING
                    case VariableType.LIST_INT:
                        default_type = VariableType.LIST_INT
                    case VariableType.LIST_FLOAT:
                        default_type = VariableType.LIST_FLOAT
                    case _:
                        warnings.warn(
                            f"`empty list` default value not allowed return type `{ret_type.name}`. "
                            f"Expected types `{(VariableType.LIST_STRING.name, VariableType.LIST_INT, VariableType.LIST_FLOAT)}`",
                            category=SyntaxWarning,
                        )
                        default_type = VariableType.ANY
            expr_default_start = ExprDefaultValueStart(
                kwargs={"value": value}, classvar_hooks=classvar_hooks
            )
            expr_default_end = ExprDefaultValueEnd(
                kwargs={"value": value},
                ret_type=default_type,
                classvar_hooks=classvar_hooks,
            )
            stack.insert(0, expr_default_start)
            stack.append(expr_default_end)

    def _struct_pop_pre_validate(
        self,
        node_start_parse: StartParseMethod,
        fields: dict[str, BaseDocument],
    ) -> StructPreValidateMethod:
        # fmt: off
        assert "__PRE_VALIDATE__" in fields, "check `__PRE_VALIDATE__` key before extract"

        validate_field = fields.pop("__PRE_VALIDATE__")
        method = StructPreValidateMethod()
        exprs = validate_field.stack.copy()
        # not allowed use default exprs, skip check
        exprs.append(ExprNoReturn())
        method.body.extend(exprs)
        self._ref_method_exprs(method)
        node_start_parse.body.append(ExprCallStructMethod(kwargs={"type": VariableType.NULL, "name": "__PRE_VALIDATE__",}, ret_type=VariableType.NULL))
        return method
        # fmt: on

    def _struct_pop_split_doc(
        self,
        node_start_parse: StartParseMethod,
        fields: dict[str, BaseDocument],
    ) -> StructPartDocMethod:
        # fmt: off
        assert "__SPLIT_DOC__" in fields, "check `__SPLIT_DOC__` key before extract"

        split_field = fields.pop("__SPLIT_DOC__")
        method = StructPartDocMethod()
        exprs = split_field.stack.copy()
        # not allowed use default exprs, skip check
        exprs.append(ExprReturn(ret_type=VariableType.LIST_DOCUMENT))
        method.body.extend(exprs)
        self._ref_method_exprs(method)
        node_start_parse.body.append(
            ExprCallStructMethod(
                kwargs={"type": VariableType.LIST_DOCUMENT, "name": "__SPLIT_DOC__",}, 
                ret_type=VariableType.LIST_DOCUMENT)
            )
        return method
        # fmt: on

    def _struct_call_literals(
        self,
        node_start_parse: StartParseMethod,
        literals: dict[str, ClassVarDocument],
    ) -> None:
        # fmt: off
        for literal in literals.values():
            expr = literal.expr()
            if expr.kwargs["parse_returns"]:
                _, struct_name, field_name, _, _ = expr.unpack_args()
                node_start_parse.body.append(
                    ExprCallStructClassVar(
                        kwargs={"struct_name": struct_name, "field_name": field_name, "type": expr.ret_type,}))
        # fmt: on

    def _struct_fields_parse(
        self,
        node_start_parse: StartParseMethod,
        fields: dict[str, BaseDocument],
    ) -> list[StructFieldMethod]:
        st_fields = []
        # fmt: off
        for field_name, document in fields.items():
            if self.css_to_xpath:
                document = convert_css_to_xpath(document)
            elif self.xpath_to_css:
                document = convert_xpath_to_css(document)
            
            ret_type = document.stack_last_ret
            method = StructFieldMethod(kwargs={"name": field_name}, ret_type=ret_type,)
            exprs = document.stack.copy()
            # in inheritance schemas, child classes use same fields are used as in the parent class
            # avoid duplicate ExprReturn or ExprDefaultValueWrapper node
            if (exprs[-1].kind != ExprReturn.kind and exprs[-1].kind != ExprDefaultValueEnd.kind):
                exprs.append(ExprReturn(accept_type=ret_type, ret_type=ret_type))
            self._unwrap_default_node(exprs, exprs[-1].ret_type)
            method.body.extend(exprs)
            self._ref_method_exprs(method)
            st_fields.append(method)
            node_start_parse.body.append(
                ExprCallStructMethod(kwargs={"type": exprs[-1].ret_type, "name": field_name,}, ret_type=exprs[-1].ret_type))
        return st_fields
        # fmt: on

    def _node_typedef(self, struct: StructParser) -> TypeDef | None:
        # fmt: off
        if struct.struct_type == StructType.CONFIG_CLASSVARS:
            return None
        typedef = TypeDef(
            parent=self.module,
            kwargs={"name": struct.kwargs["name"], "struct_type": struct.struct_type},
        )
        for sc_field in struct.body:
            if sc_field.kind not in (TokenType.STRUCT_FIELD, TokenType.CLASSVAR,):
                continue
            elif sc_field.kind == ExprClassVar.kind and sc_field.kwargs["parse_returns"]:
                _value, _struct_name, field_name, _parse_returns, _is_regex = sc_field.unpack_args()
                tdef_field = TypeDefField(
                    parent=typedef,
                    # cls_nested: always self-used field, set None
                    kwargs={"name": field_name, "type": sc_field.ret_type, "cls_nested": None, "cls_nested_type": None,},
                )
                typedef.body.append(tdef_field)
            elif sc_field.kind == StructFieldMethod.kind:
                if sc_field.body[-1].ret_type == VariableType.NESTED:
                    node = [i for i in sc_field.body if i.kind == TokenType.EXPR_NESTED][0]
                    node = cast(ExprNested, node)
                    cls_name = node.kwargs["schema_name"]
                    cls_nested_type = node.kwargs["schema_type"]
                elif sc_field.body[-1].ret_type == VariableType.JSON:
                    node = [i for i in sc_field.body if i.kind == TokenType.TO_JSON][0]
                    node = cast(ExprJsonify, node)
                    cls_name = node.kwargs["json_struct_name"]
                    # hack: for provide more consistent Typedef field gen api reuse StructType enum 
                    # or perceive it as bad AST design
                    cls_nested_type = StructType.LIST if node.kwargs["is_array"] else StructType.ITEM 
                else:
                    cls_name, cls_nested_type = None, None
                tdef_field = TypeDefField(
                    parent=typedef,
                    kwargs={"name": sc_field.kwargs["name"], "type": sc_field.body[-1].ret_type, 
                            "cls_nested": cls_name, "cls_nested_type": cls_nested_type,}
                    )
                typedef.body.append(tdef_field)
        return typedef
        # fmt: on

    def _parser_struct_node(self, schema: Type[BaseSchema]) -> StructParser:
        # fmt: off
        docstring = ((schema.__doc__ or "") + "\n\n" + generate_docstring_signature(schema))
        st = StructParser(
            kwargs={"name": schema.__name__, "struct_type": schema.__SCHEMA_TYPE__, "docstring": docstring if self.gen_docstr else "",},
            parent=self.module,
            )
        literals = schema.__get_mro_classvars__().copy()

        for literal in literals.values():
            st.body.append(literal.expr())
        st.body.append(StructInitMethod())

        fields = schema.__get_mro_fields__().copy()
        node_start_parse = StartParseMethod(parent=st)  # insert to END
        if "__PRE_VALIDATE__" in fields:
            pre_validate = self._struct_pop_pre_validate(node_start_parse, fields)
            st.body.append(pre_validate)

        if fields.get("__SPLIT_DOC__"):
            split_doc = self._struct_pop_split_doc(node_start_parse, fields)
            st.body.append(split_doc)
        # literals call (if required return)
        self._struct_call_literals(node_start_parse, literals)

        fields_st = self._struct_fields_parse(node_start_parse, fields)
        # assembly struct node
        st.body.extend(fields_st)
        st.body.append(node_start_parse)
        self._ref_body_parent(st)
        # generate typedef as annotation node
        return st

    @staticmethod
    def is_collected_type_transform(transforms: list, target: object) -> bool:
        for t in transforms:
            if isinstance(t, type(target)):
                return True
        return False

    def add_struct_parsers(self, *struct_parsers: Type[BaseSchema]) -> Self:
        ssc_structs = []
        ssc_typedefs = []
        ssc_transforms = []
        for schema in struct_parsers:
            if schema.__SSC_TRANSFORMS__:
                # check current used transforms for avoid generate duplicate imports
                for t in schema.__SSC_TRANSFORMS__:
                    if not any(isinstance(i, type(t)) for i in ssc_transforms):
                        ssc_transforms.append(t)
            if is_literals_only_schema(schema):
                if schema.__SCHEMA_TYPE__ != StructType.ITEM:
                    raise TypeError(
                        "Literals-only init allowed only ItemSchema"
                    )
                struct = self._literal_struct_node(schema)
                ssc_structs.append(struct)
                continue
            else:
                struct = self._parser_struct_node(schema)
                ssc_structs.append(struct)
        for struct in ssc_structs:
            typedef = self._node_typedef(struct)
            # literals-only schema skip
            if not typedef:
                continue
            ssc_typedefs.append(typedef)
        # assembly

        # insert transforms imports (in high-level API provide insert dependencies)

        node_transform_import = self.module.find_node_by_token(
            ModuleTransformImports.kind
        )
        node_transform_import = cast(
            ModuleTransformImports, node_transform_import
        )
        node_transform_import.kwargs["transforms"] = ssc_transforms.copy()

        node_import = self.module.find_node_by_token(ModuleImports.kind)
        node_import = cast(ModuleImports, node_import)
        node_import.kwargs["transform"] = ssc_transforms.copy()

        self.module.body.extend(ssc_typedefs)
        self.module.body.extend(ssc_structs)
        self.module.body.append(CodeEnd(parent=self.module))
        return self
