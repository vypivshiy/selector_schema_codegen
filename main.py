import jinja2

from src.yaml_parser import parse_config
from src.configs.python_parsel import Translator
from src.configs.python_bs4 import Translator as Bs4Translator

from src.template_utils import camelcase, snake_case, meta_info

ENV = jinja2.Environment(loader=jinja2.FileSystemLoader('src/configs'))
ENV.globals.update(
    {
        "snake_case": snake_case,
        "camelcase": camelcase,
        "repr_str": lambda s: repr(s) if isinstance(s, str) else s,
        "meta_info": meta_info,
        "sep_code": lambda sep, lines: sep.join(lines)
    }
)


def main(**optimisations_keys):
    """generator entrypoint"""
    translator = Bs4Translator
    info, schemas = parse_config("example.yaml",
                                 translator=translator,
                                 generate_keys=optimisations_keys)
    template = ENV.get_template('python_parsel.j2')
    result = template.render(
        info=info,
        schemas=schemas,
        translator=translator
    )
    with open("example/books_schema.py", "w") as f:
        f.write(result)


if __name__ == '__main__':
    main(fluent_optimization=False)
