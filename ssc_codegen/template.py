import re
from typing import TYPE_CHECKING
import json

import jinja2

from ssc_codegen.objects import VariableState
from ssc_codegen.schemas import ItemSchema, DictSchema, ListSchema, BaseSchemaStrategy
from ssc_codegen.generator import StructParser
if TYPE_CHECKING:
    from generator import CodeConverter


def camelcase(s: str) -> str:
    return "".join(word[0].upper() + word[1:] for word in s.split("_"))


def snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def schema_lines_signature(st: "StructParser", prefix: str = "", end: str = '\n') -> str:
    """representation object signature for docstring i"""
    json_like = {}
    _types = {
        VariableState.NONE: "null",
        VariableState.STRING: "String",
        VariableState.LIST_STRING: "Array['String']"
    }
    for method in st.methods:
        node = method.ast[0]
        json_like[method.name] = _types.get(node.return_arg_type)
    object_signature = json.dumps(json_like, indent=4).split('\n')
    header: str = f"{st.name} view() item signature:"
    return end.join(f'{prefix}{line}' for line in [header, ""] + object_signature)


def render_code(code_converter: "CodeConverter", *schemas: "BaseSchemaStrategy") -> str:
    jinja_env = jinja2.Environment(
        loader=jinja2.PackageLoader(code_converter.templates_path, ""))

    jinja_env.globals.update(
        toCamel=camelcase,
        to_snake=snake_case,
        schema_doc_signature=schema_lines_signature
    )

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
