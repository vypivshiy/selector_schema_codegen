"""Experimental PoC research CSS translator for https://github.com/msva/lua-htmlparser lib

Made to convert modules to PURE lua without C dependencies, performance is not guaranteed!
"""

from tinycss2 import parse_component_value_list
from tinycss2.ast import (
    Node,
    FunctionBlock,
    IdentToken,
    LiteralToken,
    NumberToken,
)


def css_query_to_lua_htmlparser_code(
    query: str, prv_var: str, nxt_var: str
) -> list[str]:
    """Convert CSS selector to equivalent Lua code for lua-htmlparser lib.

    if all passed selectors supports - return one generated line of code

    Args:
        query: CSS selector string
        prv_var: previous variable (ElementNode type)
        nxt_var: next variable to write output

    Returns:
        List of Lua code lines

    Buildins shortcut API:

    Combinators:

        - `,` - CssExt.combine_comma(root, left_result, right_selector)
        - `>` - CssExt.combine_child(parent_elements, child_selector)
        - `+` - CssExt.combine_plus(first_elements, second_selector)
        - `~` - CssExt.combine_tilde(first_elements, second_selector)

    Pseudo classes:

        - `:nth-child(N)` - CssExt.nth_child(elements, n), where N - integer. NOT IMPELENTED odd, even, dimensions
        - `:first-child` - CssExt.first_child(elements)
        - `:last-child` - CssExt.last_child(elements)
    """
    tokens: list[Node] = parse_component_value_list(query, skip_comments=True)

    # Find tokens that need special handling
    patch_positions: dict[int, Node] = {}
    for i, token in enumerate(tokens):
        if isinstance(token, LiteralToken) and token.value in {"+", "~", ","}:
            patch_positions[i] = token
        # if the previous token needs to be converted
        # then you need to use an auxiliary function to save the behavior.
        elif (
            isinstance(token, LiteralToken)
            and token.value == ">"
            and patch_positions.get(i - 1)
        ):
            patch_positions[i] = token
        elif isinstance(token, FunctionBlock):
            if token.lower_name == "not":
                # https://github.com/msva/lua-htmlparser/blob/master/tst/init.lua#L234
                assert len(token.arguments) == 1, (
                    f":not() accepted 1 argument, got {len(token.arguments)}"
                )
                continue  # supported, skip
            elif token.lower_name in {"nth-child", "first-child", "last-child"}:
                patch_positions[i] = token
            else:
                raise TypeError(
                    f"lua-htmlparser does not support CSS3 part `{token.serialize()}`"
                )
        elif isinstance(token, IdentToken) and token.lower_value in {
            "last-child",
            "first-child",
        }:
            patch_positions[i] = token

    # skip translate query syntax
    if not patch_positions:
        serialized = "".join(t.serialize() for t in tokens)
        return [f"local {nxt_var} = {prv_var}:select({serialized!r})"]

    # Complex case - apply patches
    code_lines = [f"local {nxt_var}"]
    buffer = ""
    i = 0

    while i < len(tokens):
        token = tokens[i]
        patch_token = patch_positions.get(i)

        if patch_token:
            # Process accumulated buffer with supported selectors
            if buffer:
                buffer = buffer.strip().rstrip(":")
                code_lines.append(f"{nxt_var} = {prv_var}:select({buffer!r})")
                buffer = ""

            if isinstance(patch_token, FunctionBlock):
                if patch_token.lower_name == "nth-child":
                    args = patch_token.arguments
                    if len(args) != 1 or not isinstance(args[0], NumberToken):
                        raise ValueError(
                            "nth-child accepts only 1 numeric argument"
                        )
                    arg = args[0].serialize()
                    code_lines.append(
                        f"{nxt_var} = CssExt.nth_child({nxt_var}, {arg})"
                    )
                i += 1

            elif isinstance(patch_token, IdentToken):
                if patch_token.lower_value == "first-child":
                    code_lines.append(
                        f"{nxt_var} = CssExt.first_child({nxt_var})"
                    )
                elif patch_token.lower_value == "last-child":
                    code_lines.append(
                        f"{nxt_var} = CssExt.last_child({nxt_var})"
                    )
                i += 1

            elif isinstance(patch_token, LiteralToken):
                # Collect right side tokens until next patch or end
                right_buffer = ""
                while True:
                    i += 1
                    if i >= len(tokens) or patch_positions.get(i):
                        break
                    right_buffer += tokens[i].serialize()

                # drop whitespaces and literal `:`
                right_buffer = right_buffer.strip().rstrip(":")
                # Generate appropriate combinator call
                if patch_token.value == ",":
                    code_lines.append(
                        f"{nxt_var} = CssExt.combine_comma({prv_var}, {nxt_var}, {right_buffer!r})"
                    )
                elif patch_token.value == "+":
                    code_lines.append(
                        f"{nxt_var} = CssExt.combine_plus({nxt_var}, {right_buffer!r})"
                    )
                elif patch_token.value == "~":
                    code_lines.append(
                        f"{nxt_var} = CssExt.combine_tilde({nxt_var}, {right_buffer!r})"
                    )
                elif patch_token.value == ">":
                    code_lines.append(
                        f"{nxt_var} = CssExt.combine_child({nxt_var}, {right_buffer!r})"
                    )
        else:
            buffer += token.serialize()
            i += 1

    return code_lines
