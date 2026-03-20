from pathlib import Path

from ssc_codegen.parser import Module, PARSER

_KDL_TEXT_ENCODING = "utf-8-sig"


def parse_ast(
    src: str | None = None,
    path: str | None = None,
    *,
    css_to_xpath: bool = False,
) -> Module:
    if not src and not path:
        raise AttributeError("required src or path argument")
    source_path: Path | None = None
    if path:
        source_path = Path(path).resolve()
        src = source_path.read_text(encoding=_KDL_TEXT_ENCODING)
    if not src:
        raise AttributeError("required src or path argument")
    module = PARSER.parse(src, source_path=source_path)
    if css_to_xpath:
        from ssc_codegen.document_utils import convert_css_to_xpath_module

        convert_css_to_xpath_module(module)
    return module
