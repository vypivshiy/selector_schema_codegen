import warnings
from pathlib import Path
from types import ModuleType
from typing import Type

from .ast_ssc import (
    ModuleProgram,
    ModuleImports,

    Variable,

    StructParser,
    Docstring,
    StructFieldFunction,
    PartDocFunction,
    StartParseFunction,
    PreValidateFunction,
    ReturnExpression,
    NoReturnExpression, CallStructFunctionExpression, BaseExpression)
from .document import BaseDocument
from .schema import BaseSchema, MISSING_FIELD, ItemSchema, DictSchema, ListSchema
from .tokens import VariableType, StructType, TokenType
from .. import FlattenListSchema


def check_field_expr(field: BaseDocument):
    """validate correct type expression"""
    var_cursor = VariableType.DOCUMENT
    for expr in field.stack:
        if var_cursor == expr.accept_type:
            var_cursor = expr.ret_type
            continue
        # this type always first (naive)
        elif expr.accept_type == VariableType.ANY:
            var_cursor = VariableType.DOCUMENT
            continue

        msg = f"'{expr.kind.name}' expected type '{expr.accept_type.name}', got '{var_cursor.name}'"
        raise TypeError(msg)


def _patch_non_required_attributes(schema: Type[BaseSchema], *fields: str) -> Type[BaseSchema]:
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            continue
        msg = f"'{schema.__name__}' not required {f} attribute, remove"
        warnings.warn(msg, category=SyntaxWarning)
        setattr(schema, f, MISSING_FIELD)
    return schema


def _check_required_attributes(schema: Type[BaseSchema], *fields: str) -> None:
    for f in fields:
        if getattr(schema, f, MISSING_FIELD) == MISSING_FIELD:
            msg = f"'{schema.__name__}' required '{f}' attribute"
            raise SyntaxError(msg)


def check_schema(schema: Type[BaseSchema]) -> Type[BaseSchema]:
    match schema.__SCHEMA_TYPE__:
        case StructType.ITEM:
            schema = _patch_non_required_attributes(
                schema,
                '__SPLIT_DOC__',
                '__ITEM__',
                '__KEY__',
                '__VALUE__'
            )
        case StructType.LIST:
            schema = _patch_non_required_attributes(schema, '__KEY__', '__VALUE__', '__ITEM__')
            _check_required_attributes(schema, '__SPLIT_DOC__')
        case StructType.DICT:
            schema = _patch_non_required_attributes(schema, '__ITEM__')
            _check_required_attributes(schema, '__SPLIT_DOC__', '__KEY__', '__VALUE__')
        case StructType.FLAT_LIST:
            schema = _patch_non_required_attributes(schema, '__KEY__', '__VALUE__')
            _check_required_attributes(schema, '__SPLIT_DOC__', '__ITEM__')
        case _:
            raise SyntaxError("Unknown schema type")
    return schema


def _fill_stack_variables(stack: list[BaseExpression], *, ret_expr: bool = True) -> list[BaseExpression]:
    tmp_stack = stack.copy()
    expr_count = len(stack)
    ret_type = stack[-1].ret_type
    for i, expr in enumerate(tmp_stack):
        expr.variable = Variable(num=i, count=expr_count, type=expr.accept_type)

    if ret_expr:
        tmp_stack.append(
            ReturnExpression(variable=Variable(num=expr_count - 1, count=expr_count, type=ret_type))
        )
    else:
        tmp_stack.append(
            NoReturnExpression(variable=Variable(num=expr_count - 1, count=expr_count, type=VariableType.NULL))
        )
    return tmp_stack


def build_ast_struct(schema: Type[BaseSchema]) -> StructParser:
    schema = check_schema(schema)
    doc = schema.__doc__ or ""
    fields = schema.__get_mro_fields__()
    # annotations = schema.__get_mro_annotations__() TODO: build signature
    ast_struct_parser = StructParser(
        type=schema.__SCHEMA_TYPE__,
        name=schema.__name__,
        doc=Docstring(value=doc),
        body=[])
    start_parse_body = []
    for k, f in fields.items():
        match k:
            case '__PRE_VALIDATE__':
                fn = PreValidateFunction(
                    name=k,
                    body=_fill_stack_variables(f.stack, ret_expr=False)
                )
                start_parse_body.append(
                    CallStructFunctionExpression(name=k, ret_type=VariableType.NULL)
                )
                ast_struct_parser.body.append(fn)
            case '__SPLIT_DOC__':
                if f._last_ret != VariableType.LIST_DOCUMENT:  # noqa
                    msg = f"__SPLIT_DOC__ attribute should be returns LIST_DOCUMENT, not {f._last_ret.name}"  # noqa
                    raise SyntaxError(msg)
                fn = PartDocFunction(
                    name=k,
                    body=_fill_stack_variables(f.stack)
                )
                start_parse_body.append(
                    CallStructFunctionExpression(name=k, ret_type=VariableType.LIST_DOCUMENT)
                )
                ast_struct_parser.body.append(fn)
            case _:
                if f.stack[0].kind == TokenType.EXPR_DEFAULT:
                    _default_expr = f._stack.pop(0) # noqa
                else:
                    _default_expr = None
                fn = StructFieldFunction(
                    name=k,
                    default=_default_expr,
                    body=_fill_stack_variables(f.stack)
                )
                ast_struct_parser.body.append(fn)
                start_parse_body.append(
                    CallStructFunctionExpression(name=k, ret_type=f._last_ret)  # noqa
                )
    start_fn = StartParseFunction(
        body=start_parse_body,
        type=schema.__SCHEMA_TYPE__
    )
    ast_struct_parser.body.append(start_fn)
    return ast_struct_parser


def _is_template_cls(cls: object) -> bool:
    return any(
        cls == base_cls
        for base_cls in (
            FlattenListSchema,
            ItemSchema,
            DictSchema,
            ListSchema,
            BaseSchema,
        )
    )


def _extract_schemas(module: ModuleType) -> list[Type[BaseSchema]]:
    return [
        obj
        for name, obj in module.__dict__.items()
        if not name.startswith("__")
           and hasattr(obj, "__mro__")
           and BaseSchema in obj.__mro__
           and not _is_template_cls(obj)
    ]


def build_ast_module(path: str | Path[str]) -> ModuleProgram:
    if isinstance(path, str):
        path = Path(path)
    module = ModuleType("mod")
    code = Path(path.resolve()).read_text()
    exec(code, module.__dict__)
    module_doc = Docstring(value=module.__dict__.get('__doc__') or "")
    # TODO: inject AST_IMPORTS
    ast_imports = ModuleImports(modules=[])
    ast_program = ModuleProgram(
        body=[module_doc, ast_imports] + [build_ast_struct(sc) for sc in _extract_schemas(module)],
    )
    return ast_program

