from dataclasses import dataclass
from typing import Optional, Type, TYPE_CHECKING

from ssc_codegen.schema import BaseSchema
from ssc_codegen.document import BaseDocument
from ssc_codegen.ast_build.metadata import SchemaMetadata, FieldMetadata


if TYPE_CHECKING:
    pass


@dataclass
class AnalysisError:
    message: str
    tip: str = ""
    field_name: Optional[str] = None
    lineno: Optional[int] = None
    filename: Optional[str] = None
    problem_method: Optional[str] = None


@dataclass
class SchemaCheckContext:
    schema: Type[BaseSchema]
    schema_meta: Optional[SchemaMetadata] = None
    filename: Optional[str] = None


@dataclass
class FieldCheckContext:
    schema: Type[BaseSchema]
    field_name: str
    document: BaseDocument
    field_meta: Optional[FieldMetadata] = None
    filename: Optional[str] = None
