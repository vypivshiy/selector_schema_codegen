import re


def remove_empty_lines(code: list[str]) -> str:
    return "\n".join([i for i in code if i])


def go_unimport_naive(go_code: str) -> str:
    """remove unused imports in golang code"""
    imports_block = re.search(r"import\s*\(\s*([\s\S]*?)\s*\)", go_code)
    if not imports_block:
        return go_code
    imports_code = imports_block.group(1)
    import_libs = re.findall(r'"([^"]+)"', imports_code)
    for absolute_lib in import_libs:
        lib = (
            absolute_lib.split("/")[-1]
            if absolute_lib.find("/") != -1
            else absolute_lib
        )
        if not re.search(lib + "\\.", go_code):
            sub_pattern = f'\\s*"{absolute_lib}"'
            go_code = re.sub(sub_pattern, "", go_code)
    return go_code
