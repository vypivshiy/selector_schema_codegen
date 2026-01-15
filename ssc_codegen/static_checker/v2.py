from typing import List, Optional, Type

from ssc_codegen.schema import BaseSchema
from ssc_codegen.ast_build.metadata import SchemaMetadata
from ssc_codegen.static_checker.schema_checks import (
    check_dict_schema_fields,
    check_flat_list_schema_fields,
    check_schema_acc_list,
    check_schema_split_doc_field,
    check_schema_key_field,
    check_schema_value_field,
    check_schema_item_field,
    check_self_classvar_variables_schema,
)
from ssc_codegen.static_checker.field_checks import (
    check_field_type_static,
    check_field_default_value,
    check_field_html_queries,
    check_field_split_doc_ret_type,
    check_field_key_ret_type,
    check_other_field_type,
    check_regex_expr,
    check_jsonify_expr,
)
from ssc_codegen.static_checker.utils import (
    SchemaCheckContext,
    FieldCheckContext,
    AnalysisError,
)


def run_analyze_schema_v2(
    schema: Type[BaseSchema],
    schema_meta: Optional[SchemaMetadata] = None,
    filename: Optional[str] = None,
) -> List[AnalysisError]:
    errors: List[AnalysisError] = []

    # Schema-level checks
    sctx = SchemaCheckContext(schema, schema_meta, filename)
    errors.extend(check_dict_schema_fields(sctx))
    errors.extend(check_flat_list_schema_fields(sctx))
    errors.extend(check_schema_acc_list(sctx))
    errors.extend(check_schema_split_doc_field(sctx))
    errors.extend(check_schema_key_field(sctx))
    errors.extend(check_schema_value_field(sctx))
    errors.extend(check_schema_item_field(sctx))
    errors.extend(check_self_classvar_variables_schema(sctx))

    # Field-level checks
    fields = schema.__get_mro_fields__()
    for name, document in fields.items():
        field_meta = schema_meta.fields.get(name) if schema_meta else None
        fctx = FieldCheckContext(schema, name, document, field_meta, filename)
        errors.extend(check_field_type_static(fctx))
        errors.extend(check_field_default_value(fctx))
        errors.extend(check_field_html_queries(fctx))
        errors.extend(check_field_split_doc_ret_type(fctx))
        errors.extend(check_field_key_ret_type(fctx))
        errors.extend(check_other_field_type(fctx))
        errors.extend(check_regex_expr(fctx))
        errors.extend(check_jsonify_expr(fctx))

    return errors
