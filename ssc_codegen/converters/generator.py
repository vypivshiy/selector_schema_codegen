from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Type, NamedTuple

import jinja2

from ssc_codegen.converters.utils import to_camelcase, to_snake_case
from ssc_codegen.schema import (
    DictSchema,
    FlattenListSchema,
    ItemSchema,
    ListSchema,
)
from ssc_codegen.schema.constants import SchemaKeywords
from ssc_codegen.type_state import TypeVariableState

if TYPE_CHECKING:
    from ssc_codegen.converters.base import BaseCodeConverter
    from ssc_codegen.schema.base import BaseSchema, AstStruct


class TypeAnnotation(NamedTuple):
    name: str
    code: str
    ret_type: str


@dataclass
class TemplateStruct:
    klass_schema: Type["BaseSchema"]
    converter: "BaseCodeConverter"

    # templates_path_map: dict[Type["BaseSchema"], str] = {
    #     ItemSchema: 'itemStruct.j2',
    #     DictSchema: 'dictStruct.j2',
    #     FlattenListSchema: 'flattenListStruct.j2',
    #     ListSchema: 'listStruct.j2'
    #                     }

    @property
    def name(self) -> str:
        return self.klass_schema.__name__

    @property
    def ast(self) -> "AstStruct":
        return self.klass_schema.get_ast_struct()

    @property
    def types(self) -> TypeAnnotation:
        return self.converter.cb_type_converter(self)

    @property
    def docstring(self) -> str:
        return self.converter.convert(self.klass_schema.__expr_doc__())

    def convert_css_to_xpath(self, xpath_prefix: str) -> None:
        for field in self.ast.fields:
            field.document.convert_css_to_xpath(xpath_prefix)

    def convert_xpath_to_css(self) -> None:
        for field in self.ast.fields:
            field.document.convert_xpath_to_css()

    def methods_code(
            self, sep: str = "\n\t", default_wrapper_sep: str = "\n\t\t"
    ) -> list[str]:
        codes = []
        for field in self.ast.fields:
            head = self.converter.convert(field.method)
            code = [self.converter.convert(c) for c in field.expressions]
            if field.default:
                dws = default_wrapper_sep
                wrapper = self.converter.convert(field.default)
                # str.format does not work in structures with '{', '}' characters
                codes.append(
                    head + sep + wrapper.replace("{}", dws.join(code), 1)
                )
            else:
                codes.append(head + sep + sep.join(code))
        return codes

    @property
    def methods_names(self) -> List[str]:
        # python <3.11 version don't have __contains__ method
        return [
            f.name
            for f in self.ast.fields
            if f.name not in SchemaKeywords.__members__.values()
        ]

    @property
    def methods_ret_types(self) -> List[TypeVariableState]:
        return [
            f.ret_type
            for f in self.ast.fields
            if f.name not in SchemaKeywords.__members__.values()
        ]


class CodeGenerator:
    def __init__(
            self,
            templates_path: str,
            base_struct_path: str,
            converter: "BaseCodeConverter",
            css_to_xpath: bool = False,
            xpath_to_css: bool = False,
            xpath_prefix: str = "descendant-or-self::",
            allow_typing: bool = False,
    ):
        if css_to_xpath and xpath_to_css:
            raise AttributeError("should be css_to_xpath or xpath_to_css")
        self._css_to_xpath = css_to_xpath
        self._xpath_to_css = xpath_to_css

        self._xpath_prefix = xpath_prefix
        self._converter = converter
        self._template_path = templates_path
        self.base_class_path = base_struct_path
        self._allow_typing = allow_typing
        # j2 config
        self.template_loader = jinja2.PackageLoader(self._template_path, "")
        self.env = jinja2.Environment(loader=self.template_loader)
        self.env.globals["to_camelcase"] = to_camelcase
        self.env.globals["to_snakecase"] = to_snake_case

    @staticmethod
    def _is_sc_class(sce, base):
        return base.__name__ in [c.__name__ for c in sce.mro()]

    def generate_code(self, *schemas: Type["BaseSchema"]) -> list[str]:
        codes: List[str] = []

        if self._allow_typing:
            tmp = self.env.get_template('typing.j2')
            codes.append(
                tmp.render(structs=(TemplateStruct(sc, converter=self._converter)
                                    for sc in schemas)
                           ).replace("\t", " " * 4)
            )

        for sc in schemas:
            st = TemplateStruct(sc, self._converter)

            if self._css_to_xpath:
                st.convert_css_to_xpath(self._xpath_prefix)
            elif self._xpath_to_css:
                st.convert_xpath_to_css()

            if self._is_sc_class(sc, ItemSchema):
                tmp = self.env.get_template("itemStruct.j2")
            elif self._is_sc_class(sc, DictSchema):
                tmp = self.env.get_template("dictStruct.j2")
            elif self._is_sc_class(sc, ListSchema):
                tmp = self.env.get_template("listStruct.j2")
            elif self._is_sc_class(sc, FlattenListSchema):
                tmp = self.env.get_template("flattenListStruct.j2")
            else:
                raise RuntimeError("Template not founded")
            # TODO: fix tabulation issue
            codes.append(tmp.render(struct=st).replace("\t", " " * 4))
        return codes

    def generate_types(self, *schemas: Type["BaseSchema"]) -> str:
        code = ""
        for sc in schemas:
            st = TemplateStruct(sc, self._converter)
            code += st.types.code + '\n'
        return code

    def generate_base_class(self) -> str:
        tmp = self.env.get_template(f"{self.base_class_path}/baseStruct.j2")
        return tmp.render()

    def generate_base_imports(self) -> str:
        tmp = self.env.get_template("base_imports.j2")
        return tmp.render()

    def generate_required_imports(self):
        tmp = self.env.get_template(f"{self.base_class_path}/imports.j2")
        return tmp.render()