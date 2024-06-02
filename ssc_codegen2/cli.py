# TODO refactoring
import importlib
import subprocess
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Annotated as A  # type: ignore
from typing import List

import typer

from ssc_codegen2.converters.generator import CodeGenerator
from ssc_codegen2.schema import BaseSchema, FlattenListSchema, ItemSchema, DictSchema, ListSchema

DEFAULT_PATH = Path.cwd() / Path('src') / Path('ssc_gen')


class Converters(str, Enum):
    PY_BS4 = 'py.bs4',
    PY_PARSEL = 'py.parsel'
    PY_SLAX = 'py.selectolax'
    PY_SCRAPY = 'py.scrapy'
    DART = 'dart'


def _is_template_cls(cls):
    return any(cls == base_cls for base_cls in (FlattenListSchema, ItemSchema, DictSchema, ListSchema, BaseSchema))


def extract_schemas(module: ModuleType) -> List[BaseSchema]:
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith('__')
           and hasattr(obj, '__mro__')
           and BaseSchema in obj.__mro__
           and not _is_template_cls(obj)
    ]


def main(configs: A[list[str], typer.Argument(help='config files')],
         converter: A[Converters, typer.Option(
             help='code converter', show_default=False)
         ],
         output_folder: A[Path, typer.Option(
             help='folder output. Default get current working directory and create src/ssc_gen path',
             show_default=False)] = DEFAULT_PATH,
         css_to_xpath: A[bool, typer.Option(
             '--to-xpath',
             help='convert css queries to xpath (works not guaranteed)')] = False,
         xpath_to_css: A[bool, typer.Option(
             '--to-css',
             help='convert xpath queries to css')] = False,
         xpath_prefix: A[str, typer.Option(help='xpath prefix (for --to-xpath argument)')] = "descendant-or-self::",
         no_format: A[bool, typer.Option(help='skip format code')] = False
         ):
    if css_to_xpath and xpath_to_css:
        print("ERROR! Should be passed --to-css OR --to-xpath", file=sys.stderr)
        raise typer.Abort()

    print("Start generate code")
    output_folder.mkdir(exist_ok=True, parents=True)

    configs = [c.rstrip('.py')
               .replace('/', '.')
               .replace('\\', '.')
               for c in configs]
    print(f'Start parse {len(configs)} schemas')
    converter = converter.value.replace('.', '_')
    # todo rename to ssc_codegen
    converter_module = importlib.import_module(f"ssc_codegen2.converters.{converter}")
    codegen: CodeGenerator = converter_module.code_generator
    print('Load code generator')

    for config in configs:
        module = importlib.import_module(config)
        schemas = extract_schemas(module)
        if css_to_xpath:
            for s in schemas:
                for f in s.get_fields().values():
                    # Document object
                    f.convert_css_to_xpath(xpath_prefix)  # type: ignore
        elif xpath_to_css:
            for s in schemas:
                for f in s.get_fields().values():
                    # Document object
                    f.convert_xpath_to_css()  # type: ignore

        # TODO detect extension
        base_module_name = "baseStruct.py" if str(converter).startswith('py_') else 'baseStruct.dart'
        base_module_output = output_folder / Path(base_module_name)
        with open(base_module_output, 'w') as f:
            f.write(codegen.generate_base_class())

        # TODO detect extension
        parser_module_name = f'{config}.py' if converter.startswith('py_') else f"{config}.dart"

        codes = [codegen.generate_imports()]
        codes.extend(codegen.generate_code(*schemas))
        output_file = output_folder / Path(parser_module_name)
        with open(output_file, 'w') as f:
            f.write("\n".join(codes))

    if not no_format:
        # TODO detect extension
        if converter == 'dart':
            subprocess.Popen(f'dart format {output_folder.resolve()}', shell=True)
        else:
            subprocess.Popen(f'black {output_folder.resolve()}', shell=True)

    print('Done.')
    exit(0)


if __name__ == '__main__':
    typer.run(main)
