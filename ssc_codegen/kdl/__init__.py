from pathlib import Path

from ssc_codegen.kdl.parser import Module, PARSER

_KDL_TEXT_ENCODING = "utf-8-sig"


def parse_ast(src: str | None = None, path: str | None = None) -> Module:
    if not src and not path:
        raise AttributeError("required src or path argument")
    if path:
        src = Path(path).read_text(encoding=_KDL_TEXT_ENCODING)
    if not src:
        raise AttributeError("required src or path argument")
    return PARSER.parse(src)
