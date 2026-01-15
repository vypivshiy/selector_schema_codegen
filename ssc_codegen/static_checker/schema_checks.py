from typing import List

from ssc_codegen.tokens import StructType, VariableType
from ssc_codegen.static_checker.utils import (
    SchemaCheckContext,
    AnalysisError,
    _prettify_expr_at,
)


def check_dict_schema_fields(ctx: SchemaCheckContext) -> List[AnalysisError]:
    if ctx.schema.__SCHEMA_TYPE__ != StructType.DICT:
        return []
    fields = ctx.schema.__get_mro_fields__()
    skip_fields = {"__SPLIT_DOC__", "__PRE_VALIDATE__", "__KEY__", "__VALUE__"}
    non_required = [name for name in fields.keys() if name not in skip_fields]
    if non_required:
        msg = f"{ctx.schema.__name__} (DICT) unnecessary fields (remove required): `{', '.join(non_required)}`"
        return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_flat_list_schema_fields(
    ctx: SchemaCheckContext,
) -> List[AnalysisError]:
    if ctx.schema.__SCHEMA_TYPE__ != StructType.FLAT_LIST:
        return []
    fields = ctx.schema.__get_mro_fields__()
    skip_fields = {"__SPLIT_DOC__", "__PRE_VALIDATE__", "__ITEM__"}
    non_required = [name for name in fields.keys() if name not in skip_fields]
    if non_required:
        msg = f"{ctx.schema.__name__} (FLAT_LIST) unnecessary fields (remove required): `{', '.join(non_required)}`"
        return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_schema_acc_list(ctx: SchemaCheckContext) -> List[AnalysisError]:
    if ctx.schema.__SCHEMA_TYPE__ != StructType.ACC_LIST:
        return []
    skip_fields = {"__SPLIT_DOC__", "__PRE_VALIDATE__"}
    err_fields = {
        name: field
        for name, field in ctx.schema.__get_mro_fields__().items()
        if name not in skip_fields
        and field.stack_last_ret != VariableType.LIST_STRING
    }
    if err_fields:
        msg = "\n".join(
            f"{ctx.schema.__name__}.{name} expected type(s) {VariableType.LIST_STRING.name}, got {field.stack_last_ret}"
            for name, field in err_fields.items()
        )
        return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_schema_split_doc_field(
    ctx: SchemaCheckContext,
) -> List[AnalysisError]:
    stype = ctx.schema.__SCHEMA_TYPE__
    if stype in (StructType.LIST, StructType.DICT, StructType.FLAT_LIST):
        fields = ctx.schema.__get_mro_fields__()
        if "__SPLIT_DOC__" not in fields:
            msg = f"{ctx.schema.__name__} missing __SPLIT_DOC__ field"
            return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_schema_key_field(ctx: SchemaCheckContext) -> List[AnalysisError]:
    if ctx.schema.__SCHEMA_TYPE__ == StructType.DICT:
        fields = ctx.schema.__get_mro_fields__()
        if "__KEY__" not in fields:
            msg = f"{ctx.schema.__name__} missing __KEY__ field"
            return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_schema_value_field(ctx: SchemaCheckContext) -> List[AnalysisError]:
    if ctx.schema.__SCHEMA_TYPE__ == StructType.DICT:
        fields = ctx.schema.__get_mro_fields__()
        if "__VALUE__" not in fields:
            msg = f"{ctx.schema.__name__} missing __VALUE__ field"
            return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_schema_item_field(ctx: SchemaCheckContext) -> List[AnalysisError]:
    if ctx.schema.__SCHEMA_TYPE__ == StructType.FLAT_LIST:
        fields = ctx.schema.__get_mro_fields__()
        if "__ITEM__" not in fields:
            msg = f"{ctx.schema.__name__} missing __ITEM__ field"
            return [AnalysisError(message=msg, filename=ctx.filename)]
    return []


def check_self_classvar_variables_schema(
    ctx: SchemaCheckContext,
) -> List[AnalysisError]:
    if not ctx.schema.__get_mro_classvars__():
        return []
    fields = ctx.schema.__get_mro_fields__()
    for name, field in fields.items():
        for i, expr in enumerate(field.stack):
            for value in expr.classvar_hooks.values():
                if all(not ref for ref in value.literal_ref_name):
                    trace = _prettify_expr_at(field, i)
                    msg = f"{ctx.schema.__name__}.{name} = {trace}  # classvar missing struct_name and struct_field"
                    tip = (
                        "Provide manually reference classvar's name in format `<st_name>.<st_field>`\n"
                        "Example:\n\n"
                        "class Struct(ItemSchema):\n"
                        '    CVAR = CV("title", "Struct.CVAR")  #  <---\n'
                        "    title = D().css(CVAR).text()"
                    )
                    return [
                        AnalysisError(
                            message=msg,
                            tip=tip,
                            field_name=name,
                            lineno=ctx.schema_meta.fields[name].lineno
                            if ctx.schema_meta
                            and name in ctx.schema_meta.fields
                            else None,
                            filename=ctx.filename,
                        )
                    ]
    return []
