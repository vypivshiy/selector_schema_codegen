import sys
from pathlib import Path
from typing import Type

from ssc_codegen.ast_ import ModuleProgram

from ssc_codegen.ast_build.builder import AstBuilder
from ssc_codegen.ast_build.utils import (
    extract_schemas_from_module,
    parse_module_ast,
    exec_module_from_ast,
)
from ssc_codegen.ast_build.metadata import extract_schema_metadata

from ssc_codegen.schema import BaseSchema
from ssc_codegen.static_checker.v2 import run_analyze_schema_v2
from ssc_codegen.static_checker.formatter import format_all_errors
import logging

LOGGER = logging.getLogger("ssc_gen")


def build_ast_module_parser(
    path: str | Path,
    *,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
    gen_docstring: bool = True,
) -> ModuleProgram:
    """build ast from python sscgen config file

    WARNING!!!
        DO NOT PASS MODULES FROM UNKNOWN SOURCE/INPUT FOR SECURITY REASONS.

        THIS FUNCTION COMPILE AND EXEC PYTHON CODE in runtime WOUT CHECKS
    """
    if css_to_xpath and xpath_to_css:
        raise AttributeError(
            "Should be chosen one variant (css_to_xpath OR xpath_to_css)"
        )

    ast_tree, _, filename = parse_module_ast(path)
    schema_metadata_map = extract_schema_metadata(ast_tree)
    py_module = exec_module_from_ast(ast_tree, filename)

    schemas = extract_schemas_from_module(py_module)
    if not schemas:
        LOGGER.warning(f"{path} does not contains defined schemas")

    all_errors = []
    for schema in schemas:
        schema_meta = schema_metadata_map.get(schema.__name__)
        errors = run_analyze_schema_v2(
            schema,
            schema_meta=schema_meta,
            filename=filename,
        )
        all_errors.extend(errors)

        if errors:
            LOGGER.error(f"{schema.__name__} has {len(errors)} error(s)")

    if all_errors:
        error_report = format_all_errors(all_errors)
        print(error_report, file=sys.stderr)
        exit(1)

    ast_module = AstBuilder.build_from_moduletype(
        py_module,
        css_to_xpath=css_to_xpath,
        xpath_to_css=xpath_to_css,
        gen_docstr=gen_docstring,
    )
    return ast_module


def build_ast_schemas(
    *schemas: Type[BaseSchema],
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
    gen_docstring: bool = False,
) -> ModuleProgram:
    """this func implementation compile and run parsers in runtime, drop extra errors metadata"""
    if css_to_xpath and xpath_to_css:
        raise AttributeError(
            "Should be chosen one variant (css_to_xpath OR xpath_to_css)"
        )

    all_errors = []
    for schema in schemas:
        errors = run_analyze_schema_v2(schema)
        all_errors.extend(errors)
        if errors:
            LOGGER.error(f"{schema.__name__} has {len(errors)} error(s)")

    if all_errors:
        error_report = "\n".join(
            f"error: {err.message}"
            + (f"\n= help: {err.tip}" if err.tip else "")
            for err in all_errors
        )
        print(error_report, file=sys.stderr)
        raise SyntaxError(
            f"Static analysis failed with {len(all_errors)} error(s)"
        )

    ast_module = AstBuilder.build_from_ssc_schemas(
        *schemas,
        css_to_xpath=css_to_xpath,
        xpath_to_css=xpath_to_css,
        gen_docstr=gen_docstring,
    )
    return ast_module
