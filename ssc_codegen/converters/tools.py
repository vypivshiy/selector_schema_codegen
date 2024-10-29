from typing_extensions import deprecated


@deprecated("codegen set correct indent")
def py_naive_fix_indentation(code: list[str]) -> str:
    """NOTE: is not universal solution, it's implemented for fix output code
    """
    # magic indent fix prepare (ASSERT, CallFunc issues)
    code = '\n'.join(code).split('\n')
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


@deprecated("codegen set correct indent")
def py_fix_indentation(code: list[str]) -> str:
    code = '\n'.join([i for i in code if i]).split('\n')
    ch = " "
    indent_level = 0
    indent_size = 4
    fixed_lines = []
    docstring_chars = '"""'
    is_docstring = False
    for line in code:
        # oneline docstring check
        if docstring_chars in line and (not line.startswith(docstring_chars) and not line.endswith(docstring_chars)):
            is_docstring = not is_docstring

        if line.endswith("{") and not is_docstring:
            indent_level += 1
            line = line.rstrip('{')
        elif line.endswith("}") and not is_docstring:
            indent_level -= 1
            line = line.rstrip('}')

        fixed_lines.append(ch * indent_size * indent_level + line)
    return '\n'.join(fixed_lines)


def go_naive_fix_docstring(code: list[str]) -> str:
    return '\n'.join([i for i in code if i])