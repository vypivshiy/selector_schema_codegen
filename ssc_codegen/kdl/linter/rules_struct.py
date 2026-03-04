from ssc_codegen.kdl.linter.base import LINTER, Node, LintContext

# required reserved fields per struct type
_REQUIRED_RESERVED: dict[str, set[str]] = {
    "item":  set(),
    "list":  {"-split-doc"},
    "dict":  {"-key", "-value"},
    "table": {"-table", "-row", "-match", "-value"},
    "flat":  set(),
}

# reserved fields allowed per struct type (None = all types)
_RESERVED_ALLOWED: dict[str, set[str] | None] = {
    "-doc":          None,           # all
    "-pre-validate": None,           # all
    "-init":         None,           # all
    "-split-doc":    {"list"},
    "-key":          {"dict"},
    "-value":        {"dict", "table"},
    "-table":        {"table"},
    "-row":          {"table"},
    "-match":        {"table"},
}

_VALID_TYPES = frozenset({"item", "list", "dict", "table", "flat"})


@LINTER.rule("struct")
def rule_struct(node: Node, ctx: LintContext) -> None:
    struct_name = ctx.get_arg(node, 0)
    if not struct_name:
        ctx.error(node,
                  message="'struct' requires a name",
                  hint="example: struct MyStruct { ... }")
        return

    # validate type= property
    struct_type = ctx.get_prop(node, "type") or "item"
    if struct_type not in _VALID_TYPES:
        ctx.error(node,
                  message=f"unknown struct type '{struct_type}'",
                  hint=f"valid types: {', '.join(sorted(_VALID_TYPES))}")
        return  # дальше не проверяем — тип неизвестен

    ctx.push(f"struct {struct_name}")

    fields = ctx.get_children_nodes(node)
    field_names = [ctx.node_name(f) for f in fields]
    reserved_present = {n for n in field_names if n.startswith("-")}

    # check required reserved fields are present
    required = _REQUIRED_RESERVED[struct_type]
    for req in required:
        if req not in reserved_present:
            ctx.error(node,
                      message=f"struct type='{struct_type}' requires '{req}' field",
                      hint=f"add '{req} {{ ... }}' inside the struct")

    # check reserved fields are not used in wrong struct type
    for field in fields:
        name = ctx.node_name(field)
        if not name.startswith("-"):
            continue
        allowed = _RESERVED_ALLOWED.get(name)
        if allowed is not None and struct_type not in allowed:
            ctx.error(field,
                      message=f"'{name}' is not allowed in struct type='{struct_type}'",
                      hint=f"'{name}' is only valid in: {', '.join(sorted(allowed))}")

    # flat: all regular fields must not exist? no — they exist but pipeline
    # must return LIST_STRING — that's a type check, handled separately

    ctx.pop()