import jinja2

from src.yaml_parser import parse_config

from src.template_utils import camelcase, snake_case, generate_meta_info, generate_attr_signature

ENV = jinja2.Environment(loader=jinja2.FileSystemLoader('src/configs'))
ENV.globals.update(
    {
        "snake_case": snake_case,
        "camelcase": camelcase,
        # wrap str to quotes
        "repr_str": lambda s: repr(s) if isinstance(s, str) else s,
        "generate_meta_info": generate_meta_info,
        "sep_code": lambda sep, lines: sep.join(lines),
        "generate_attr_signature": generate_attr_signature
    }
)


def main(choice: int):
    """generator entrypoint"""
    if choice == 0:
        from src.configs.python.python_parsel import Translator

        template = "python/python_any.j2"
        out = "test.py"

    elif choice == 1:
        from src.configs.dart.dart_html import Translator
        template = "dart/dart_html.j2"
        out = "test.dart"
    else:
        exit(-1)

    translator = Translator
    info = parse_config("example.yaml",
                        translator=translator,
                        )
    template = ENV.get_template(template)
    result = template.render(
        ctx=info,
        translator=translator,
    )
    with open(f"example/{out}", "w") as f:
        f.write(result)


if __name__ == '__main__':
    # 0 python 1 dart
    main(0)
