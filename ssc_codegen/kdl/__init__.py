from ssc_codegen.kdl.parser import PARSER, Module
from pathlib import Path


def parse_ast(src:str | None = None, path: str | None = None) -> Module:
    if not src and not path:
        raise AttributeError("required src or path argument")
    if path:
        src = Path(path).read_text()
    if not src:
        raise AttributeError("required src or path argument")
    return PARSER.parse(src)
