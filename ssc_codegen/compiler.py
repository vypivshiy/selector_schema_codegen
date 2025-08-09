"""simple compiler and evaulater generated python schemas"""

import sys
import types
from os import PathLike
from typing import Any, Type

from ssc_codegen.ast_.nodes_core import ModuleImports, ModuleProgram
from ssc_codegen.ast_build import build_ast_module_parser
from ssc_codegen.ast_build.main import build_ast_struct_parser
from ssc_codegen.converters.py_base import BasePyCodeConverter
from ssc_codegen.schema import BaseSchema


def compile(
    *schemas: Type[BaseSchema], converter: BasePyCodeConverter
) -> types.ModuleType:
    """ssc-gen gen compiler to a real cpython code in runtime

    this function implemented for test schemas in runtime and not recommended used in production.

    after recompiling the modules, the code of the previous schemes is overwritten.

    returns:
        types.ModuleType object. Compile code in runtime, push compiled classes to sys.modules["_ssc_single_eval"]


    Usage example:

        ```python
        import requests
        from ssc_codegen import ItemSchema, CV

        class Demo(ItemSchema):
            CVAR = CV("Some classvar")
            title = D().css("title::text")
            urls = D().css_all("a[href]::attr(href)")

        module = compile(Demo())
        print(module.Demo.CVAR)  # "Some classvar"
        # pass html document
        document = requests.get("https://example.com")
        print(module.Demo(document.text).parse())
        ```
    """

    module = ModuleProgram()
    module.body.append(ModuleImports())

    structs = []
    for s in schemas:
        struct = build_ast_struct_parser(s, module, gen_docstring=False)
        structs.append(struct)
    module.body.extend(structs)

    code_parts = converter.convert_program(module)
    module = types.ModuleType("_ssc_single_eval")
    code = "\n".join(code_parts)
    exec(code, module.__dict__)
    sys.modules["_ssc_single_eval"] = module


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

        ast = build_ast_module_parser(path)  # type: ignore
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

    @property
    def cache(self):
        return self._cache

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
