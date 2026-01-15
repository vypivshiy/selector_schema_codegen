import ast
from dataclasses import dataclass


@dataclass
class FieldMetadata:
    lineno: int
    col_offset: int
    source_expr: str  # eg: "D().css('.price::text').to_float()"


@dataclass
class SchemaMetadata:
    name: str
    fields: dict[str, FieldMetadata]


def extract_schema_metadata(ast_tree: ast.Module) -> dict[str, SchemaMetadata]:
    """Extract field-level metadata (lineno, source) from AST for all SSC schemas."""
    visitor = _SchemaMetadataVisitor()
    visitor.visit(ast_tree)
    return visitor.schemas


class _SchemaMetadataVisitor(ast.NodeVisitor):
    def __init__(self):
        self.schemas: dict[str, SchemaMetadata] = {}

    def visit_ClassDef(self, node: ast.ClassDef):
        if self._is_ssc_schema(node):
            fields = {}
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    if isinstance(target, ast.Name):
                        field_name = target.id
                        # should be a works in py 3.10+
                        # https://docs.python.org/3/library/ast.html#ast.unparse
                        source_expr = ast.unparse(stmt.value)
                        fields[field_name] = FieldMetadata(
                            lineno=stmt.lineno,
                            col_offset=stmt.col_offset,
                            source_expr=source_expr,
                        )
            self.schemas[node.name] = SchemaMetadata(
                name=node.name, fields=fields
            )
        self.generic_visit(node)

    def _is_ssc_schema(self, node: ast.ClassDef) -> bool:
        """Check if class inherits from ItemSchema or ListSchema (by name)."""
        # Cannot test MRO in this step (code is not in runtime evaulated),
        # therefore we focus on base classes by name (should be enough for DSL).
        # for example, the case won't work:
        # from ssc_codegen import ItemSchema as IS
        for base in node.bases:
            if isinstance(base, ast.Name):
                if base.id in (
                    "ItemSchema",
                    "ListSchema",
                    "DictSchema",
                    "FlatListSchema",
                    "AccUniqueListSchema",
                ):
                    return True
        return False
