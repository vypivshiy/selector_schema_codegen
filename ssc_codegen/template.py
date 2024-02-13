from typing import TYPE_CHECKING

import jinja2

from ssc_codegen.schemas import ItemSchema, DictSchema, ListSchema, BaseSchemaStrategy
from ssc_codegen.generator import StructParser
if TYPE_CHECKING:
    from generator import CodeConverter


def render_code(code_converter: "CodeConverter", *schemas: "BaseSchemaStrategy") -> str:
    jinja_env = jinja2.Environment(
        loader=jinja2.PackageLoader(code_converter.templates_path, ""))
    base_tmp = jinja_env.get_template('baseStruct.j2').render()
    codes: list[str] = []
    for st in schemas:
        if isinstance(st, ItemSchema):
            st = StructParser(instance=st)
            codes.append(
                jinja_env.get_template('itemStruct.j2').render(struct=st, converter=code_converter)
            )
        elif isinstance(st, DictSchema):
            st = StructParser(instance=st)
            codes.append(
                jinja_env.get_template('dictStruct.j2').render(struct=st, converter=code_converter)
            )
        elif isinstance(st, ListSchema):
            st = StructParser(instance=st)
            codes.append(
                jinja_env.get_template('listStruct.j2').render(struct=st, converter=code_converter)
            )
    return base_tmp + "\n\n".join(codes)
