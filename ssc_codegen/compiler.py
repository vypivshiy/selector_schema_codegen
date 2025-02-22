"""simple compiler and evaulater generated python schemas"""

import sys
import types
from os import PathLike
from typing import Any

from ssc_codegen.ast_builder import build_ast_module
from ssc_codegen.converters.py_base import BasePyCodeConverter


class Compiler:
    _cache: dict[str, "Compiler"] = {}

    def __init__(self, module_name: str, module: types.ModuleType) -> None:
        self._module = module

    @classmethod
    def from_file(
        cls, path: PathLike[str] | str, *, converter: BasePyCodeConverter
    ) -> "Compiler":
        if not isinstance(converter, BasePyCodeConverter):
            raise TypeError("Support only python implementation converters")

        ast = build_ast_module(path)  # type: ignore
        code_parts = converter.convert_program(
            ast
        )  # return real works python code
        code = "\n".join(code_parts)

        module_name = path if isinstance(path, str) else path.__fspath__()
        module = types.ModuleType(module_name)
        if module_name in cls._cache:
            return cls._cache[module_name]
        exec(code, module.__dict__)  # type: ignore
        sys.modules[module_name] = module
        instance = cls(module_name, module)  # type: ignore
        cls._cache[module_name] = instance
        return instance

    def get_class(self, class_name: str) -> Any:
        """Retrieves a class from the compiled module by name."""
        if self._module is None:
            raise RuntimeError("Module not compiled and executed yet.")

        if not self.class_exists(class_name):
            raise AttributeError(
                f"Class '{class_name}' not found in compiled module."
            )

        return getattr(self._module, class_name)

    def class_exists(self, class_name: str) -> bool:
        return hasattr(self._module, class_name)

    def run_parse(self, schema_name: str, document: str) -> Any:
        """Gets the class by name, initializes it with the document, and calls its parse method."""
        sc_cls = self.get_class(schema_name)
        instance = sc_cls(document)  # type: ignore
        if not hasattr(instance, "parse") or not callable(
            getattr(instance, "parse")
        ):
            raise AttributeError(
                f"Class '{schema_name}' does not have a callable 'parse' method."
            )

        return instance.parse()
