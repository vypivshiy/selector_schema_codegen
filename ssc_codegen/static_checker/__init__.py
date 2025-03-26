import logging
from typing import Type, Sequence

from ssc_codegen.schema import BaseSchema
from ssc_codegen.static_checker.callbacks import analyze_schema_item_field, analyze_schema_key_field, \
    analyze_schema_value_field, analyze_field_default_value, analyze_field_type_static, analyze_field_html_queries, \
    analyze_schema_split_doc_field, analyze_field_split_doc_ret_type, CB_SCHEMA, CB_DOCUMENT, analyze_regex_expr, \
    analyze_field_key_ret_type, analyze_other_field_type, analyze_dict_schema_fields, analyze_flat_list_schema_fields, \
    analyze_jsonify_expr

LOGGER = logging.getLogger("ssc_gen")

_DEFAULT_CB_SCHEMAS = (
    analyze_schema_split_doc_field,
    analyze_schema_value_field,
    analyze_schema_key_field,
    analyze_schema_item_field,
    analyze_dict_schema_fields,
    analyze_flat_list_schema_fields
)

_DEFAULT_CB_DOCUMENTS = (
    analyze_field_type_static,
    analyze_field_default_value,
    analyze_field_html_queries,
    analyze_field_split_doc_ret_type,
    analyze_field_key_ret_type,
    analyze_other_field_type,
    analyze_regex_expr,
    analyze_jsonify_expr
)


def run_analyze_schema(
        schema: Type[BaseSchema],
        cb_schemas: Sequence[CB_SCHEMA] = _DEFAULT_CB_SCHEMAS,
        cb_documents: Sequence[CB_DOCUMENT] = _DEFAULT_CB_DOCUMENTS
) -> int:
    """simple static analyze syntax for ssc-gen schemas"""
    errors = []
    for cb_schema in cb_schemas:
        result = cb_schema(schema)
        if not result:
            LOGGER.error(result.msg)
            errors.append(result)

    fields = schema.__get_mro_fields__()
    for name, document in fields.items():
        for cb_document in cb_documents:
            result = cb_document(schema, name, document)
            if not result:
                LOGGER.error(result.msg)
                errors.append(result)

    LOGGER.info("%s: Founded issues: %s",schema.__name__, len(errors))
    return len(errors)
