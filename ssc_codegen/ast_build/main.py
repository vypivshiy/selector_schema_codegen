import warnings
from pathlib import Path
from typing import Type, cast

from ssc_codegen import Json
from ssc_codegen.ast_ import (
    StructParser,
    StructInitMethod,
    BaseAstNode,
    StructPreValidateMethod,
    ModuleProgram,
    ExprCallStructMethod,
    StructPartDocMethod,
    StructFieldMethod,
    StartParseMethod,
    ExprDefaultValueStart,
    ExprDefaultValueEnd,
    Docstring,
    ModuleImports,
    JsonStruct,
    JsonStructField,
    TypeDef,
    TypeDefField,
    ExprReturn,
    ExprNoReturn,
    ExprNested,
    ExprJsonify,
)
from ssc_codegen.ast_build.utils import (
    generate_docstring_signature,
    extract_json_structs_from_module,
    exec_module_code,
    extract_schemas_from_module,
)
from ssc_codegen.document import BaseDocument
from ssc_codegen.document_utlis import (
    convert_css_to_xpath,
    convert_xpath_to_css,
)
from ssc_codegen.schema import BaseSchema
from ssc_codegen.static_checker import run_analyze_schema
from ssc_codegen.tokens import TokenType, VariableType, StructType


def build_ast_module_parser(
    path: str | Path,
    *,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
) -> ModuleProgram:
    """build ast from python sscgen config file

    WARNING!!!
        DO NOT PASS MODULES FROM UNKNOWN SOURCE/INPUT FOR SECURITY REASONS.

        THIS FUNCTION COMPILE AND EXEC PYTHON CODE in runtime WOUT CHECKS
    """
    # ast structure
    # docstring
    # imports
    # json types/structs
    # schema types/structs
    # schema parsers
    if css_to_xpath and xpath_to_css:
        raise AttributeError(
            "Should be chosen one variant (css_to_xpath OR xpath_to_css)"
        )
    py_module = exec_module_code(path)
    docstr = py_module.__dict__.get("__doc__") or ""  # type: str
    ast_module = ModuleProgram()
    module_body: list[BaseAstNode] = [
        Docstring(kwargs={"value": docstr}, parent=ast_module),
        ModuleImports(parent=ast_module),
    ]

    schemas = extract_schemas_from_module(py_module)
    json_structs = extract_json_structs_from_module(py_module)
    # TODO: API for build single json
    ast_jsons = build_ast_json(ast_module, *json_structs)
    # TODO: implement analyze-only AST function
    try:
        ast_schemas = [
            build_ast_struct_parser(
                sc,
                ast_module,
                css_to_xpath=css_to_xpath,
                xpath_to_css=xpath_to_css,
            )
            for sc in schemas
        ]
    except SyntaxError:
        # get all schemas exceptions and throw to logs:
        errors = []
        for sc in schemas:
            try:
                build_ast_struct_parser(
                    sc,
                    ast_module,
                    css_to_xpath=css_to_xpath,
                    xpath_to_css=xpath_to_css,
                )
            except SyntaxError as e:
                errors.append(e)
        raise SyntaxError(f"{path}: Founded errors: {len(errors)}")

    # TODO: API for build single typedef
    ast_typedefs = build_ast_typedef(ast_module, *ast_schemas)
    module_body.extend(ast_jsons)
    module_body.extend(ast_typedefs)
    module_body.extend(ast_schemas)
    ast_module.body.extend(module_body)
    return ast_module


def build_ast_typedef(
    ast_module: ModuleProgram | None, *ast_schemas: StructParser
) -> list[BaseAstNode]:
    ast_typedefs: list[BaseAstNode] = []
    for sc in ast_schemas:
        ast_t_def = TypeDef(
            parent=ast_module,
            kwargs={"name": sc.kwargs["name"], "struct_type": sc.struct_type},
        )
        for sc_field in sc.body:
            if sc_field.kind != TokenType.STRUCT_FIELD:
                continue
            sc_field = cast(StructFieldMethod, sc_field)
            if sc_field.body[-1].ret_type == VariableType.NESTED:
                node = [
                    i for i in sc_field.body if i.kind == TokenType.EXPR_NESTED
                ][0]
                node = cast(ExprNested, node)
                cls_name = node.kwargs["schema_name"]
                cls_nested_type = node.kwargs["schema_type"]

            elif sc_field.body[-1].ret_type == VariableType.JSON:
                node2 = [
                    i for i in sc_field.body if i.kind == TokenType.TO_JSON
                ][0]
                node2 = cast(ExprJsonify, node2)
                cls_name = node2.kwargs["json_struct_name"]
                # hack: for provide more consistent Typedef field gen api
                if node2.kwargs["is_array"]:
                    cls_nested_type = StructType.LIST
                else:
                    cls_nested_type = StructType.ITEM
            else:
                cls_name = None
                cls_nested_type = None

            ast_t_def_field = TypeDefField(
                parent=ast_t_def,
                kwargs={
                    "name": sc_field.kwargs["name"],
                    "type": sc_field.body[-1].ret_type,
                    "cls_nested": cls_name,
                    "cls_nested_type": cls_nested_type,
                },
            )
            ast_t_def.body.append(ast_t_def_field)
        ast_typedefs.append(ast_t_def)
    return ast_typedefs


def build_ast_json(
    ast_module: ModuleProgram | None, *json_structs: Type[Json]
) -> list[BaseAstNode]:
    ast_jsons: list[BaseAstNode] = []
    for jsn_st in json_structs:
        ast_jsn = JsonStruct(
            kwargs={"name": jsn_st.__name__, "is_array": jsn_st.__IS_ARRAY__},
            parent=ast_module,
        )
        for name, field_type in jsn_st.get_fields().items():
            ast_jsn.body.append(
                JsonStructField(
                    kwargs={"name": name, "type": field_type}, parent=ast_jsn
                )
            )
        ast_jsons.append(ast_jsn)
    return ast_jsons


def build_ast_struct_parser(
    schema: Type[BaseSchema],
    module_ref: ModuleProgram,
    *,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
) -> StructParser:
    errors_count = run_analyze_schema(schema)
    if errors_count > 0:
        msg = f"{schema.__name__} founded errors: {errors_count}"
        raise SyntaxError(msg)
    docstring = (
        (schema.__doc__ or "") + "\n\n" + generate_docstring_signature(schema)
    )
    st = StructParser(
        kwargs={
            "name": schema.__name__,
            "struct_type": schema.__SCHEMA_TYPE__,
            "docstring": docstring,
        },
        parent=module_ref,
    )
    # build body
    body: list[BaseAstNode] = [StructInitMethod(parent=st)]
    # names counter for CallStruct expr (Start parse entrypoint)
    body_parse_method_expr: list[BaseAstNode] = []
    fields = schema.__get_mro_fields__().copy()

    _try_fetch_pre_validate_node(body, body_parse_method_expr, fields, st)
    _try_fetch_split_doc_node(body, body_parse_method_expr, fields, st)
    _fetch_field_nodes(
        body,
        body_parse_method_expr,
        fields,
        st,
        css_to_xpath,
        xpath_to_css,
    )

    # last node - run entrypoint
    start_parse_method = StartParseMethod(parent=st)
    for i in body_parse_method_expr:
        i.parent = start_parse_method
    start_parse_method.body = body_parse_method_expr
    body.append(start_parse_method)
    st.body = body
    return st


def _fetch_field_nodes(
    body: list[BaseAstNode],
    body_parse_method_expr: list[BaseAstNode],
    fields: dict[str, BaseDocument],
    st_ref: StructParser,
    css_to_xpath: bool = False,
    xpath_to_css: bool = False,
) -> None:
    for field_name, document in fields.items():
        # check passed flags in CLI
        if css_to_xpath:
            document = convert_css_to_xpath(document)
        elif xpath_to_css:
            document = convert_xpath_to_css(document)

        ret_type = document.stack_last_ret
        method = StructFieldMethod(
            kwargs={"name": field_name},
            parent=st_ref,
            ret_type=ret_type,
        )
        # TODO: add ast tests
        # in inheritance schemas, child classes use same fields are used as in the parent class
        # avoid duplicate ExprReturn or ExprDefaultValueWrapper node
        if (
            document.stack[-1].kind != ExprReturn.kind
            and document.stack[-1].kind != TokenType.EXPR_DEFAULT_END
        ):
            document.stack.append(
                ExprReturn(accept_type=ret_type, ret_type=ret_type)
            )

        _unwrap_default_node(document, ret_type)
        for i in document.stack:
            i.parent = method
        method.body = document.stack

        body.append(method)
        if ret_type == VariableType.NESTED:
            node = [
                i for i in document.stack if i.kind == TokenType.EXPR_NESTED
            ][0]
            node = cast(ExprNested, node)
            cls_name = node.kwargs["schema_name"]
        else:
            cls_name = None
        body_parse_method_expr.append(
            ExprCallStructMethod(
                kwargs={
                    "name": field_name,
                    "type": ret_type,
                    "cls_nested": cls_name,
                },
            )
        )


def _unwrap_default_node(
    document: BaseDocument, ret_type: VariableType
) -> None:
    if document.stack[0].kind == TokenType.EXPR_DEFAULT:
        default_expr = document.stack.pop(0)
        value = default_expr.kwargs["value"]
        default_type = ret_type
        if value is None:
            match ret_type:
                case VariableType.STRING:
                    default_type = VariableType.OPTIONAL_STRING
                case VariableType.INT:
                    default_type = VariableType.OPTIONAL_INT
                case VariableType.FLOAT:
                    default_type = VariableType.OPTIONAL_FLOAT
                case VariableType.LIST_STRING:
                    default_type = VariableType.OPTIONAL_LIST_STRING
                case VariableType.LIST_INT:
                    default_type = VariableType.OPTIONAL_LIST_INT
                case VariableType.LIST_FLOAT:
                    default_type = VariableType.OPTIONAL_LIST_FLOAT
                # TODO: warning for BOOL type
                case _:
                    warnings.warn(
                        f"'None' default value not allowed return type '{ret_type.name}'. ",
                        category=SyntaxWarning,
                    )
                    default_type = VariableType.ANY
        elif isinstance(value, list):
            # todo: check if empty list passed
            match ret_type:
                case VariableType.LIST_STRING:
                    default_type = VariableType.LIST_STRING
                case VariableType.LIST_INT:
                    default_type = VariableType.LIST_INT
                case VariableType.LIST_FLOAT:
                    default_type = VariableType.LIST_FLOAT
                case _:
                    warnings.warn(
                        f"`empty list` default value not allowed return type `{ret_type.name}`. "
                        f"Expected types `{(VariableType.LIST_STRING.name, VariableType.LIST_INT, VariableType.LIST_FLOAT)}`",
                        category=SyntaxWarning,
                    )
                    default_type = VariableType.ANY
        expr_default_start = ExprDefaultValueStart(kwargs={"value": value})
        expr_default_end = ExprDefaultValueEnd(
            kwargs={"value": value}, ret_type=default_type
        )
        document.stack.insert(0, expr_default_start)
        document.stack.append(expr_default_end)


def _try_fetch_split_doc_node(
    body: list[BaseAstNode],
    call_methods_expr: list[BaseAstNode],
    fields: dict[str, BaseDocument],
    st_ref: StructParser,
) -> None:
    if fields.get("__SPLIT_DOC__"):
        split_doc = fields.pop("__SPLIT_DOC__")
        method = StructPartDocMethod(parent=st_ref)

        # in inheritance schemas, child classes use same fields are used as in the parent class
        # avoid duplicate ExprReturn or ExprDefaultValueWrapper node
        if (
            split_doc.stack[-1].kind != ExprReturn.kind
            and split_doc.stack[-1].kind != TokenType.EXPR_DEFAULT_END
        ):
            # always returns sequence of elements
            split_doc.stack.append(
                ExprReturn(ret_type=VariableType.LIST_DOCUMENT)
            )
        for i in split_doc.stack:
            i.parent = method
        method.body = split_doc.stack
        body.append(method)

        call_methods_expr.append(
            ExprCallStructMethod(
                kwargs={
                    "type": VariableType.LIST_DOCUMENT,
                    "name": "__SPLIT_DOC__",
                },
            )
        )


def _try_fetch_pre_validate_node(
    body: list[BaseAstNode],
    call_methods_expr: list[BaseAstNode],
    fields: dict[str, BaseDocument],
    st_ref: StructParser,
) -> None:
    if fields.get("__PRE_VALIDATE__"):
        validate_field = fields.pop("__PRE_VALIDATE__")
        method = StructPreValidateMethod(
            body=validate_field.stack, parent=st_ref
        )
        validate_field.stack.append(ExprNoReturn())
        for i in validate_field.stack:
            i.parent = method

        body.append(method)
        call_methods_expr.append(
            ExprCallStructMethod(
                kwargs={"type": VariableType.NULL, "name": "__PRE_VALIDATE__"},
            )
        )
