"""
KDL DSL linter — rules for keywords: dsl, expr, define (field usage).

dsl  — module-level keyword declaring a named inline code block for a target
       language.  Syntax:

           dsl NAME lang=LANG {
               import "..."        // optional, one or more import lines
               code "line1" "..."  // required, one or more code lines
           }

       NAME  — identifier (no spaces).
       lang  — target language tag (e.g. "py", "js", "go", "lua").
       Children block must contain at least one 'code' node.
       'import' is optional but must have at least one arg if present.
       'code' must have at least one arg.

expr — pipeline operation that calls a named dsl block.  Syntax:

           expr NAME

       NAME  — must match a dsl block declared at module level,
               OR be a block define name (define NAME { ... }).
       Scalar defines cannot be used as expr targets.
       No other arguments are accepted.

define (field usage) — block defines can be referenced inside field pipelines.
       Scalar defines used as ops are already caught by the wildcard rule;
       this module adds a dedicated rule so the hint text is always clear.
"""

from __future__ import annotations

from tree_sitter import Node

from ssc_codegen.kdl.linter.base import LINTER, LintContext, DefineKind


# ── helpers ────────────────────────────────────────────────────────────────────

# Valid VariableType names for dsl accept= / return= properties
_VALID_VT_NAMES: frozenset[str] = frozenset(
    {
        "DOCUMENT",
        "LIST_DOCUMENT",
        "STRING",
        "LIST_STRING",
        "INT",
        "LIST_INT",
        "FLOAT",
        "LIST_FLOAT",
        "BOOL",
        "NULL",
        "NESTED",
        "JSON",
        "OPT_STRING",
        "OPT_INT",
        "OPT_FLOAT",
    }
)


def _get_dsl_names(ctx: LintContext) -> frozenset[str]:
    """
    Return the set of dsl block names declared in the current module.

    dsl names are collected lazily from ctx.defines under a private key so
    that the linter stays single-pass without requiring a pre-pass for dsl.
    Because the tree walker visits 'dsl' nodes before 'expr' nodes in
    document order, names are always populated when needed.
    """
    return getattr(ctx, "_dsl_names", frozenset())


def _register_dsl_name(ctx: LintContext, name: str) -> None:
    """Register a dsl block name into the context."""
    existing: set[str] = getattr(ctx, "_dsl_names", set())  # type: ignore[attr-defined]
    existing.add(name)
    ctx._dsl_names = existing  # type: ignore[attr-defined]


# ── dsl ───────────────────────────────────────────────────────────────────────


@LINTER.rule("dsl")
def rule_dsl(node: Node, ctx: LintContext) -> None:
    """
    Validate a module-level dsl block.

      dsl NAME lang=LANG {
          import "..."      // optional
          code "line1"      // required
      }
    """
    # 1. NAME — first positional arg
    name = ctx.get_arg(node, 0)
    if not name:
        ctx.error(
            node,
            message="'dsl' requires a name",
            hint='example: dsl MY_TRANSFORM lang="py" { code "{{NXT}} = {{PRV}}.strip()" }',
        )
        return

    # 2. lang= property
    lang = ctx.get_prop(node, "lang")
    if not lang:
        ctx.error(
            node,
            message=f"'dsl {name}' is missing required 'lang' property",
            hint=(f'specify target language: dsl {name} lang="py" {{ ... }}\n'),
        )

    # 3. accept= / return= properties (optional, but if present must be valid types)
    for prop in ("accept", "return"):
        val = ctx.get_prop(node, prop)
        if val is not None:
            if val.upper() not in _VALID_VT_NAMES:
                ctx.error(
                    node,
                    message=f"'dsl {name}': unknown type '{val}' for property '{prop}'",
                    hint=f"valid types: {', '.join(sorted(_VALID_VT_NAMES))}",
                )

    # 4. Children block is required and must contain at least one 'code' node
    children = ctx.get_children_nodes(node)
    if not children:
        ctx.error(
            node,
            message=f"'dsl {name}' body must contain at least one 'code' node",
            hint=(
                f'example: dsl {name} lang="py" {{\n'
                '    code "{{NXT}} = {{PRV}}.strip()"\n'
                "}"
            ),
        )
        return

    child_names = [ctx.node_name(c) for c in children]

    # validate import nodes
    for child in children:
        cname = ctx.node_name(child)
        if cname == "import":
            if not ctx.get_args(child):
                ctx.error(
                    child,
                    message=f"'dsl {name}': 'import' requires at least one argument",
                    hint='example: import "from base64 import b64decode"',
                )

    # validate code nodes — must have at least one arg and use {{PRV}}/{{NXT}}
    for child in children:
        cname = ctx.node_name(child)
        if cname == "code":
            args = ctx.get_args(child)
            if not args:
                ctx.error(
                    child,
                    message=f"'dsl {name}': 'code' requires at least one code line",
                    hint='example: code "{{NXT}} = {{PRV}}.strip()"',
                )
            else:
                all_code = " ".join(args)
                has_prv = "{{PRV}}" in all_code
                has_nxt = "{{NXT}}" in all_code
                if not has_prv and not has_nxt:
                    ctx.warning(
                        child,
                        message=f"'dsl {name}': code does not use {{{{PRV}}}} or {{{{NXT}}}} markers",
                        hint=(
                            "use {{PRV}} for the input value and {{NXT}} for the output value\n"
                            'example: code "{{NXT}} = {{PRV}}.strip()"'
                        ),
                    )

    # unknown nodes inside dsl body
    for child in children:
        cname = ctx.node_name(child)
        if cname and cname not in ("import", "code"):
            ctx.error(
                child,
                message=f"'dsl {name}': unknown directive '{cname}'",
                hint="only 'import' and 'code' are allowed inside a dsl block",
            )

    has_code = "code" in child_names
    if not has_code:
        ctx.error(
            node,
            message=f"'dsl {name}' body must contain at least one 'code' node",
            hint=(
                f'example: dsl {name} lang="py" {{\n'
                '    code "{{NXT}} = {{PRV}}.strip()"\n'
                "}"
            ),
        )
        return

    # 5. Register name for expr validation
    _register_dsl_name(ctx, name)


# ── expr ──────────────────────────────────────────────────────────────────────


@LINTER.rule("expr")
def rule_expr(node: Node, ctx: LintContext) -> None:
    """
    Validate a pipeline 'expr' operation.

      expr NAME

    NAME must refer to a dsl block or a block define.
    Scalar defines are NOT valid expr targets.
    No extra arguments are accepted.
    """
    args = ctx.get_args(node)

    # 1. Must have exactly one arg — the name
    if not args:
        ctx.error(
            node,
            message="'expr' requires a name argument",
            hint="example: expr MY_TRANSFORM\n"
            "NAME must refer to a dsl block or a block define",
        )
        return

    if len(args) > 1:
        ctx.error(
            node,
            message=f"'expr' accepts exactly one argument, got {len(args)}",
            hint=f"example: expr {args[0]}",
        )
        # continue to validate the first arg

    target = args[0]

    # 2. Check dsl blocks first
    dsl_names = _get_dsl_names(ctx)
    if target in dsl_names:
        return  # valid dsl reference

    # 3. Check block defines
    info = ctx.defines.get(target)
    if info is not None:
        if info.kind == DefineKind.SCALAR:
            ctx.error(
                node,
                message=f"'expr {target}': '{target}' is a scalar define — cannot be used as an expr target",
                hint=(
                    f"scalar defines substitute argument values, not code blocks.\n"
                    f'Declare a dsl block: dsl {target} lang="py" {{ code "..." }}\n'
                    f"or a block define: define {target} {{ ... }}"
                ),
            )
        # block define — valid, no error
        return

    # 4. Unknown target
    ctx.error(
        node,
        message=f"'expr' target '{target}' is not declared",
        hint=(
            f'declare a dsl block: dsl {target} lang="py" {{ code "..." }}\n'
            f"or a block define: define {target} {{ ... }}"
        ),
    )


# ── define (field usage clarification) ───────────────────────────────────────


@LINTER.rule("define")
def rule_define_field_usage(node: Node, ctx: LintContext) -> None:
    """
    'define' is a module-level keyword and must not appear inside field pipelines.

    If it appears inside a pipeline context, report a clear error.
    This rule fires only when the node is visited inside a pipeline
    (i.e. the wildcard rule would otherwise catch it).  The specific
    'define' rule takes precedence over the wildcard.

    Note: module-level define validation is handled by rule_define in
    rules_struct.py.  This rule adds a guard for the rare case where
    someone writes 'define' inside a struct field.
    """
    # Check whether we are inside a pipeline by inspecting the CST parent chain.
    # A node inside a field pipeline has an ancestor node whose name is a
    # regular field (not a module keyword).  We approximate this by checking
    # if the node's parent chain contains a 'node_children' grandparent whose
    # parent is NOT 'struct' or the document root.
    #
    # Simpler heuristic: if define appears inside a node_children block whose
    # grandparent is a field node, it's misplaced.
    parent = node.parent  # node_children or document
    if parent is None:
        return

    gp = parent.parent  # field node or struct body or root
    if gp is None:
        return

    # If the grandparent is a 'node' (i.e. a field), we're inside a pipeline
    if gp.type == "node":
        field_name = ctx.node_name(gp)
        if field_name and field_name not in (
            "struct",
            "define",
            "transform",
            "json",
            "dsl",
        ):
            ctx.error(
                node,
                message="'define' is a module-level keyword and cannot appear inside a field pipeline",
                hint=(
                    "move 'define' to the top of the file (module level).\n"
                    "To reuse a block of ops, declare: define NAME { op1; op2 }\n"
                    "then reference NAME inside the field."
                ),
            )
