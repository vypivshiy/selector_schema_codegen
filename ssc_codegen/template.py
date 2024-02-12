from typing import TYPE_CHECKING

import jinja2

from ssc_codegen.structs import ItemStruct, DictStruct, ListStruct, BaseStructStrategy
from ssc_codegen.generator import StructParser
if TYPE_CHECKING:
    from generator import CodeConverter

ENV = jinja2.Environment(
    loader=jinja2.PackageLoader("ssc_codegen.templates.python.parsel", ""))


def render_code(code_converter: "CodeConverter", *structs: "BaseStructStrategy") -> str:
    base_tmp = ENV.get_template('baseStruct.j2').render()
    codes: list[str] = []
    for st in structs:
        if isinstance(st, ItemStruct):
            st = StructParser(instance=st)
            codes.append(
                ENV.get_template('itemStruct.j2').render(struct=st, converter=code_converter)
            )
        elif isinstance(st, DictStruct):
            st = StructParser(instance=st)
            codes.append(
                ENV.get_template('dictStruct.j2').render(struct=st, converter=code_converter)
            )
        elif isinstance(st, ListStruct):
            st = StructParser(instance=st)
            codes.append(
                ENV.get_template('listStruct.j2').render(struct=st, converter=code_converter)
            )
    return base_tmp + "\n\n".join(codes)
