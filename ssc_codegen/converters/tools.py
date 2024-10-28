def py_naive_fix_indentation(code: list[str]) -> str:
    """NOTE: is not universal solution, it's implemented for fix output code
    """
    lines = [i for i in code if i]
    ch = " "
    indent_level = 0
    indent_size = 4
    fixed_lines = []
    prev_line = ''
    for line in lines:
        line = line.strip()
        if line.startswith("class"):
            indent_level = 0
        elif line.startswith("def"):
            indent_level = 1

        # default wrapper
        if prev_line.startswith("return") and line.startswith('return'):
            indent_level = 2
        elif prev_line.startswith("return") and not line.startswith('class'):
            indent_level = 1
        elif prev_line.startswith("class"):
            indent_level = 1
        elif prev_line.startswith("def"):
            indent_level = 2
        elif prev_line.startswith("with"):
            indent_level = 3

        fixed_lines.append(ch * indent_size * indent_level + line)
        prev_line = line
    return '\n'.join(fixed_lines)


def go_naive_fix_docstring(code: list[str]) -> str:
    return '\n'.join([i for i in code if i])