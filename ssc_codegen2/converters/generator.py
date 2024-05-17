from dataclasses import dataclass
from typing import TYPE_CHECKING, Type, List

from ssc_codegen2.schema import ItemSchema, DictSchema, ListSchema, FlattenListSchema
from ssc_codegen2.schema.constants import SchemaKeywords

if TYPE_CHECKING:
    from ssc_codegen2.converters.base import BaseCodeConverter
    from ssc_codegen2.schema.base import BaseSchema


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
    def name(self):
        return self.klass_schema.__name__

    @property
    def ast(self):
        return self.klass_schema.get_ast_struct()

    @property
    def docstring(self) -> str:
        return self.converter.convert(self.klass_schema.__expr_doc__())

    def methods_code(self, sep: str = "\n\t", default_wrapper_sep: str = '\n\t\t') -> list[str]:
        codes = []
        for field in self.ast.fields:
            head = self.converter.convert(field.method)
            code = [self.converter.convert(c) for c in field.expressions]
            if field.default:
                dws = default_wrapper_sep
                wrapper = self.converter.convert(field.default)
                codes.append(head + sep + wrapper.format(dws.join(code)))
            else:
                codes.append(head + sep + sep.join(code))
        return codes

    @property
    def methods_names(self) -> List[str]:
        return [f.name for f in self.ast.fields if f.name not in SchemaKeywords]


def generate_code_from_schemas(path: str, converter: "BaseCodeConverter", *schemas: Type["BaseSchema"]):

    def is_sc_class(sce, base):
        return base.__name__ in  [c.__name__ for c in sce.mro()]

    import jinja2
    template_loader = jinja2.FileSystemLoader(searchpath=path)
    env = jinja2.Environment(loader=template_loader)
    for sc in schemas:
        st = TemplateStruct(sc, converter)
        # TODO

        if is_sc_class(sc, ItemSchema):
            tmp = env.get_template('itemStruct.j2')
        elif is_sc_class(sc, DictSchema):
            tmp = env.get_template('dictStruct.j2')
        elif is_sc_class(sc, ListSchema):
            tmp = env.get_template('listStruct.j2')
        elif is_sc_class(sc, FlattenListSchema):
            tmp = env.get_template('flattenListStruct.j2')
        else:
            raise Exception
        print(tmp.render(struct=st))
