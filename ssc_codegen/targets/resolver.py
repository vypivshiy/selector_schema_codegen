"""Resolve a TargetSpec into a validated TargetProfile."""

from __future__ import annotations

from ssc_codegen.targets.profile import TargetProfile
from ssc_codegen.targets.spec import TargetSpec


class ResolutionError(ValueError):
    """Target resolution or validation failed."""


def resolve(spec: TargetSpec) -> TargetProfile:
    """Validate user input and return the matching profile."""
    if spec.lang == "python":
        return _resolve_python(spec)
    if spec.lang in ("javascript", "js"):
        return _resolve_js(spec)
    raise ResolutionError(
        f"Unknown language '{spec.lang}'. Use 'python' or 'js'."
    )


def _resolve_python(spec: TargetSpec) -> TargetProfile:
    from ssc_codegen.targets.python.html_libs.bs4 import Bs4DomSpelling
    from ssc_codegen.targets.python.html_libs.lxml import LxmlDomSpelling
    from ssc_codegen.targets.python.html_libs.parsel import ParselDomSpelling
    from ssc_codegen.targets.python.html_libs.slax import SlaxDomSpelling
    from ssc_codegen.targets.python.visitor import PythonVisitor

    spellings = {
        "bs4": Bs4DomSpelling,
        "lxml": LxmlDomSpelling,
        "parsel": ParselDomSpelling,
        "slax": SlaxDomSpelling,
    }

    lib = spec.lib or "bs4"
    if lib not in spellings:
        raise ResolutionError(
            f"Unknown HTML library '{lib}'. "
            f"Available: {', '.join(sorted(spellings))}."
        )

    spelling_cls = spellings[lib]

    if spec.http_client is not None:
        valid = ("httpx", "aiohttp", "requests")
        if spec.http_client not in valid:
            raise ResolutionError(
                f"Python accepts --http-client: {', '.join(valid)}. "
                f"Got '{spec.http_client}'."
            )

    if spec.separate_runtime and lib == "lxml":
        pass  # supported, with fallback

    def _factory() -> PythonVisitor:
        return PythonVisitor(dom_spelling_cls=spelling_cls)

    return TargetProfile(
        language="python",
        file_extension=".py",
        create_converter=_factory,
        http_clients=("httpx", "aiohttp", "requests"),
        supports_separate_runtime=True,
        runtime_include_fallback=(lib == "lxml"),
    )


def _resolve_js(spec: TargetSpec) -> TargetProfile:
    from ssc_codegen.targets.javascript.visitor import JsVisitor

    if spec.lib is not None:
        raise ResolutionError("--lib is not applicable for JavaScript.")

    if spec.http_client is not None:
        valid = ("fetch", "axios")
        if spec.http_client not in valid:
            raise ResolutionError(
                f"JavaScript accepts --http-client: {', '.join(valid)}. "
                f"Got '{spec.http_client}'."
            )

    if spec.separate_runtime:
        raise ResolutionError(
            "--separate-runtime is not applicable for JavaScript."
        )

    return TargetProfile(
        language="javascript",
        file_extension=".js",
        create_converter=lambda: JsVisitor(),
        http_clients=("fetch", "axios"),
    )
