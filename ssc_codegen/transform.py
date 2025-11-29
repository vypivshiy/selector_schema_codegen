from typing import Callable, ClassVar, TypedDict
from .tokens import VariableType


class EmitSpec(TypedDict):
    method_name: str
    dependencies: list[str]
    func: Callable[..., list[str]]


def target(backend: str, dependencies: list[str] | None = None):
    """decorator for provide transformation

    Args:
        backend - target lib (py_base, js_pure, py_bs4 etc)
        dependencies - optional required imports (push to ModuleImports() AST nodes)
    """
    dependencies = dependencies or []

    def decorator(fn: Callable[..., list[str]]) -> Callable[..., list[str]]:
        setattr(fn, "_emit_backend", backend)
        setattr(fn, "_emit_deps", dependencies)
        return fn

    return decorator


class BaseTransformMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        impls: dict[str, EmitSpec] = {}

        for base in reversed(cls.__mro__[1:]):
            base_impls = getattr(base, "_emit_impls", None)
            if isinstance(base_impls, dict):
                for backend, spec in base_impls.items():
                    impls.setdefault(
                        backend,
                        {
                            "method_name": spec["method_name"],
                            "dependencies": list(spec["dependencies"]),
                            "func": spec["func"],
                        },
                    )

        for attr_name, attr_value in namespace.items():
            if callable(attr_value) and hasattr(attr_value, "_emit_backend"):
                backend = getattr(attr_value, "_emit_backend")
                deps = getattr(attr_value, "_emit_deps", []) or []

                if (
                    backend in impls
                    and impls[backend]["method_name"] in namespace
                ):
                    raise ValueError(
                        f"Duplicate emit implementations for backend '{backend}' in class {name}"
                    )

                impls[backend] = EmitSpec(
                    method_name=attr_name,
                    dependencies=list(deps),
                    func=attr_value,  # type: ignore
                )

        setattr(cls, "_emit_impls", impls)
        return cls


class BaseTransform(metaclass=BaseTransformMeta):
    # change this variables for provide static analyze
    accept_type: ClassVar[VariableType]
    return_type: ClassVar[VariableType]

    _emit_impls: ClassVar[dict[str, EmitSpec]] = {}  # autofill from metaclass

    @classmethod
    def has_backend(cls, backend: str) -> bool:
        return backend in getattr(cls, "_emit_impls", {})

    @classmethod
    def get_emit_spec(cls, backend: str) -> EmitSpec | None:
        return getattr(cls, "_emit_impls", {}).get(backend)

    def collect_dependencies(self, backend: str) -> list[str]:
        spec = self.get_emit_spec(backend)
        return spec["dependencies"][:] if spec else []

    # Instance method to call emitter (wraps class method to bind self)
    def emit(self, backend: str, prv: str, nxt: str) -> list[str]:
        spec = self.get_emit_spec(backend)
        if not spec:
            return []
        fn = getattr(self, spec["method_name"])
        return fn(prv, nxt)
