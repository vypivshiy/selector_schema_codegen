from pathlib import Path
from typing import Type

from ssc_codegen.ast_ import ModuleProgram

from ssc_codegen.ast_build.builder import AstBuilder
from ssc_codegen.ast_build.utils import (
    exec_module_code,
    extract_schemas_from_module,
)

from ssc_codegen.schema import BaseSchema
from ssc_codegen.static_checker import run_analyze_schema
import logging

LOGGER = logging.getLogger("ssc-gen")


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
    py_module = exec_module_code(path)
    # check code configs before build AST
    schemas = extract_schemas_from_module(py_module)
    count_errors = 0
    for schema in schemas:
        errors = run_analyze_schema(schema)
        if errors > 0:
            msg = f"{schema.__name__} founded errors: {errors}"
            LOGGER.error(msg)
            count_errors += errors

    if count_errors > 0:
        msg = f"{path} errors count: {count_errors}"
        LOGGER.error(msg)
        raise SyntaxError("")

    ast_module = AstBuilder.build_from_moduletype(
        py_module,
        css_to_xpath=css_to_xpath,
        xpath_to_css=xpath_to_css,
        gen_docstr=gen_docstring,
    )
    return ast_module
    # static check


def build_ast_schemas(
    *schemas: Type[BaseSchema],
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
    gen_docstring: bool = False,
) -> ModuleProgram:
    if css_to_xpath and xpath_to_css:
        raise AttributeError(
            "Should be chosen one variant (css_to_xpath OR xpath_to_css)"
        )
    count_errors = 0
    for schema in schemas:
        errors = run_analyze_schema(schema)
        if errors > 0:
            msg = f"{schema.__name__} founded errors: {errors}"
            LOGGER.error(msg)
            count_errors += errors

    if count_errors > 0:
        msg = f"scehmas errors count: {count_errors}"
        LOGGER.error(msg)
        raise SyntaxError
    ast_module = AstBuilder.build_from_ssc_schemas(
        *schemas,
        css_to_xpath=css_to_xpath,
        xpath_to_css=xpath_to_css,
        gen_docstr=gen_docstring,
    )
    return ast_module
