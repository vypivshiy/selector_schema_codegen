from typing import TYPE_CHECKING

import jinja2

if TYPE_CHECKING:
    from generator import StructParser, CodeConverter

ENV = jinja2.Environment(
    loader=jinja2.PackageLoader("ssc_codegen.templates.python.parsel", ""))


def render_code(code_converter: "CodeConverter", *struct: "StructParser"):
    base_tmp = ENV.get_template('baseStruct.j2').render()
    return base_tmp + "\n\n" + ENV.get_template('itemStruct.j2').render(struct=struct, converter=code_converter)
