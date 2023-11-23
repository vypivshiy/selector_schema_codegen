# TODO cli script

import jinja2

from ssc_codegen.template_utils import (
    camelcase,
    generate_attr_signature,
    generate_meta_info,
    ret_type,
    snake_case,
)
from ssc_codegen.yaml_parser import Info

ENV = jinja2.Environment(loader=jinja2.PackageLoader("ssc_codegen.configs", ""))
ENV.globals.update(
    {
        "snake_case": snake_case,
        "camelcase": camelcase,
        # wrap str to quotes
        "repr_str": lambda s: repr(s) if isinstance(s, str) else s,
        "generate_meta_info": generate_meta_info,
        "sep_code": lambda sep, lines: sep.join(lines),
        "generate_attr_signature": generate_attr_signature,
        "ret_type": ret_type,
    }
)


def generate_code(info: "Info", template_path: str) -> str:
    template = ENV.get_template(template_path)
    result = template.render(
        ctx=info,
        translator=info.schemas[0].translator,  # TODO refactoring
    )
    return result
