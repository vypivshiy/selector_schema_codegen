""""""

from typing import Callable
from ssc_codegen.str_utils import (
    go_unimport_naive,
    py_optimize_return_naive,
    py_str_format_to_fstring,
    js_pure_optimize_return,
)


class BaseCodeCallback:
    def __init__(
        self,
        *code_callbacks: Callable[[str], str],
        join_sep: str = "\n",
        remove_empty_lines: bool = False,
    ):
        self.join_sep = join_sep
        self.remove_empty_lines = remove_empty_lines
        self.callbacks = code_callbacks

    def __call__(self, lines: list[str]) -> str:
        if self.remove_empty_lines:
            code = self.join_sep.join([i for i in lines if i])
        else:
            code = self.join_sep.join(lines)
        for cb in self.callbacks:
            code = cb(code)
        return code


CB_PY_CODE = BaseCodeCallback(
    py_optimize_return_naive, py_str_format_to_fstring
)
CB_GO_CODE = BaseCodeCallback(go_unimport_naive, remove_empty_lines=True)
CB_DART_CODE = BaseCodeCallback(remove_empty_lines=True)
CB_JS_CODE = BaseCodeCallback(js_pure_optimize_return)
