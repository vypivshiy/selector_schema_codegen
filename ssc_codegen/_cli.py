import subprocess
from pathlib import Path
from typing import NamedTuple
import argparse
import importlib.util

from ssc_codegen import render_code
from ssc_codegen.converters import py_scrapy, py_bs4, py_parsel, py_selectolax, dart_universal_html
from ssc_codegen.schemas import BaseSchemaStrategy


_CONVERTER_NAMESPACES = {
        "py.bs4": py_bs4.converter,
        "py.parsel": py_parsel.converter,
        "py.selectolax": py_selectolax.converter,
        "py.scrapy": py_scrapy.converter,
        "dart": dart_universal_html.converter,
    }


_EXT_PYTONIC = {"py.bs4", "py.parsel", "py.selectolax", "py.scrapy"}
_EXT_DART = {"dart", }

# formatters
_FMT_DART = "dart format {}"
_FMT_PYTHON = "black {}"


class ArgsNamespace(NamedTuple):
    scenario: str
    lang: str
    out: str
    OVERWRITE: bool
    XPATH_TO_CSS: bool
    CSS_TO_XPATH: bool
    XPATH_PREFIX: str
    NO_FORMAT: bool


def parse_arguments() -> ArgsNamespace:
    parser = argparse.ArgumentParser(
        prog="Selector schema generator",
        description="Generate selector schemas from config file",
        usage="ssc-gen my_conf.py py.bs4 -o out_file",
    )

    parser.add_argument("scenario", help="ssc_gen python file")
    parser.add_argument(
        "lang",
        choices=list(_CONVERTER_NAMESPACES.keys()),
        help="Programming language and lib choice",
    )

    parser.add_argument(
        "-o",
        "--out",
        default=f"schema.{{}}",
        help="Output directory (default: current working directory/schema.<ext>)",
    )
    parser.add_argument(
        "-y",
        dest="OVERWRITE",
        default=False,
        action="store_true",
        help="Suggest overwrite file",
    )
    parser.add_argument("--xpath-to-css",
                        dest="XPATH_TO_CSS",
                        default=False,
                        action="store_true",
                        help="Convert xpath selectors to css (work not guaranteed)")

    parser.add_argument("--css-to-xpath",
                        dest="CSS_TO_XPATH",
                        default=False,
                        action="store_true",
                        help="convert css selectors to xpath")
    parser.add_argument("--xpath-prefix",
                        dest="XPATH_PREFIX",
                        default='descendant-or-self::',
                        type=str,
                        help="Xpath prefix for --css-to-xpath autoconverter. Default `descendant-or-self::`")

    parser.add_argument(
        "--no-format",
        dest="NO_FORMAT",
        default=False,
        action="store_true",
        help="Disable code format by third party solutions",
    )

    namespace: ArgsNamespace = parser.parse_args()  # type: ignore
    return namespace


def _extract_schemas(path: str):
    spec = importlib.util.spec_from_file_location("script_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schemas: list[BaseSchemaStrategy] = []
    # Check if __all__ is defined in the module
    if hasattr(module, '__all__'):
        for obj_name in module.__all__:
            obj = getattr(module, obj_name)
            if issubclass(obj, BaseSchemaStrategy):
                print("Founded", f"'{obj.__name__}'")
                schemas.append(obj())
    else:
        print("Not founded objects, exit")
        exit(1)

    if len(schemas) == 0:
        print("Not founded schemas, exit")
        exit(1)

    return schemas


def _suggest_overwrite(path_out: str, overwrite: bool):
    if Path(path_out).exists() and not overwrite:
        choice = input("Overwrite? (y/n)? ")
        if choice.lower() != "y":
            print("Cancel operation")
            exit(1)


def _file_out(out: str, lang: str):
    if out == "schema.{}":
        if lang in _EXT_PYTONIC:
            ext = "py"
        elif lang in _EXT_DART:
            ext = "dart"
        else:
            print("not founded extension, exit")
            exit(1)
        return out.format(ext)
    return out


def main():
    args = parse_arguments()
    if args.CSS_TO_XPATH and args.XPATH_TO_CSS:
        print('Should be choice --css-to-xpath or --xpath-to-css')
        exit(1)

    converter = _CONVERTER_NAMESPACES.get(args.lang)
    print(f"Load '{args.lang}' converter")
    schemas = _extract_schemas(args.scenario)
    output = _file_out(args.out, args.lang)
    _suggest_overwrite(output, args.OVERWRITE)

    print("Render code")
    if args.CSS_TO_XPATH:
        print(F"convert CSS to XPATH with prefix '{args.XPATH_PREFIX}'")
    elif args.XPATH_TO_CSS:
        print(f"convert XPATH to CSS")

    code = render_code(converter,
                       *schemas,
                       css_to_xpath=args.CSS_TO_XPATH,
                       xpath_to_css=args.XPATH_TO_CSS,
                       xpath_prefix=args.XPATH_PREFIX)
    print(f"Save to {output}")
    Path(output).write_text(code)
    if not args.NO_FORMAT:
        print("Format code...")
        if args.lang.startswith('py.'):
            subprocess.call(_FMT_PYTHON.format(output), shell=True)
        elif args.lang == "dart":
            subprocess.call(_FMT_DART.format(output), shell=True)
    print("done.")


if __name__ == '__main__':
    main()
