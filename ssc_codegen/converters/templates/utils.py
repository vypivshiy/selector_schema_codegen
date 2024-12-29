import re
from typing import TYPE_CHECKING, Callable, Union, TypeAlias

if TYPE_CHECKING:
    from ssc_codegen.tokens import TokenType, StructType

T_TEMPLATE_BIND: TypeAlias = Union[str, Callable[[tuple[str, ...]], str]]
T_GETITEM_BIND: TypeAlias = Union["TokenType", tuple["TokenType", str, ...]]


class TemplateBindings:
    """Class helper for bindings string template by "TokenType"

    Accepts string with template format positions (call str.format) or callable
    """

    def __init__(self):
        self._bindings: dict["TokenType", T_TEMPLATE_BIND] = {}

    @property
    def bindings(self) -> dict["TokenType", T_TEMPLATE_BIND]:
        return self._bindings

    def __setitem__(self, key: "TokenType", template: T_TEMPLATE_BIND) -> None:
        self._bindings[key] = template

    def bind(self, key: "TokenType", template: T_TEMPLATE_BIND) -> None:
        return self.__setitem__(key, template)

    def __getitem__(self, key: T_GETITEM_BIND) -> str:
        if isinstance(key, tuple):
            key, args = key[0], key[1:]
        else:
            args = ()
        if not self._bindings.get(key):
            msg = f"Missing {key.name} binding"
            raise KeyError(msg)
        template = self._bindings.get(key)
        if isinstance(template, str):
            takes_args = len(re.findall(r'\{.*?\}', template))
            if takes_args != len(args):
                msg = f"{key.name} binding takes {takes_args} arguments but {len(args)} were given"
                raise TypeError(msg)
            return template.format(*args)
        elif callable(template):
            return template(*args)
        raise TypeError(f"Unsupported type {type(template).__name__}")


class TemplateTypeBindings:
    def __init__(self, type_prefix: str = "T_"):
        self._type_prefix = type_prefix
        self._bindings: dict["StructType", str | Callable[[str], str]] = {}

    @property
    def type_prefix(self) -> str:
        return self._type_prefix

    def create_name(self, name: str) -> str:
        return f"{self._type_prefix}{name}"

    @property
    def bindings(self) -> dict["StructType", str | Callable[[str], str]]:
        return self._bindings

    def __setitem__(self, key: "StructType", template: str | Callable[[str], str]) -> None:
        self._bindings[key] = template

    def bind(self, key: "StructType", template: str | Callable[[str], str]) -> None:
        return self.__setitem__(key, template)

    def __getitem__(self, key: Union["StructType", tuple["StructType", str, ...]]) -> str:
        if isinstance(key, tuple):
            key, args = key[0], key[1:]
        else:
            args = ()
        if not self._bindings.get(key):
            msg = f"Missing {key.name} binding"
            raise KeyError(msg)
        template = self._bindings.get(key)
        if isinstance(template, str):
            takes_args = len(re.findall(r'\{.*?\}', template))
            if takes_args != len(args):
                msg = f"{key.name} binding takes {takes_args} arguments but {len(args)} were given"
                raise TypeError(msg)
            return template.format(*args)
        elif callable(template):
            return template(*args)
        raise TypeError(f"Unsupported type {type(template).__name__}")
