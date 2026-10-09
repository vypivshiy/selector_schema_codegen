"""Target resolution and backend capability validation.

This module validates raw `TargetSpec` instances and constructs corresponding
`TargetProfile` capability descriptors with appropriate visitor/converter factories.
"""

from __future__ import annotations

from ssc_codegen.targets.profile import TargetProfile
from ssc_codegen.targets.spec import TargetSpec


class ResolutionError(ValueError):
    """Raised when target resolution, backend validation, or option validation fails.

    Examples:
        ```python
        from ssc_codegen.targets.resolver import ResolutionError, resolve
        from ssc_codegen.targets.spec import TargetSpec

        try:
            resolve(TargetSpec(lang="ruby"))
        except ResolutionError as exc:
            print(f"Unsupported target: {exc}")
        ```
    """


def resolve(spec: TargetSpec) -> TargetProfile:
    """Validate user-supplied target specification and return the matching profile.

    Inspects the language, HTML/DOM library, HTTP client options, and runtime
    separation flags in `spec`. If all options are valid and supported by the
    chosen target backend, returns a fully configured `TargetProfile`.

    Args:
        spec: Raw target options specifying language, library, and codegen flags.

    Returns:
        TargetProfile containing validated capabilities and a converter factory.

    Raises:
        ResolutionError: If the specified language is unknown or if incompatible/unsupported
            options are passed for that language (e.g. `--lib` for JS/Go, or unsupported HTTP clients).

    Examples:
        ```python
        from ssc_codegen.targets.resolver import resolve
        from ssc_codegen.targets.spec import TargetSpec

        # Resolve standard Python + BeautifulSoup4 target
        py_profile = resolve(TargetSpec(lang="python", lib="bs4"))
        converter = py_profile.create_converter()

        # Resolve JavaScript target with Fetch HTTP client
        js_profile = resolve(TargetSpec(lang="js", http_client="fetch"))

        # Resolve Go target
        go_profile = resolve(TargetSpec(lang="go"))
        ```
    """
    if spec.lang == "python":
        return _resolve_python(spec)
    if spec.lang in ("javascript", "js"):
        return _resolve_js(spec)
    if spec.lang == "go":
        return _resolve_go(spec)
    if spec.lang == "rust":
        return _resolve_rust(spec)
    raise ResolutionError(
        f"Unknown language '{spec.lang}'. Use 'python', 'js', 'go', or 'rust'."
    )


def _resolve_python(spec: TargetSpec) -> TargetProfile:
    """Resolve and validate configuration for the Python codegen backend.

    Args:
        spec: Target configuration for Python.

    Returns:
        TargetProfile for Python code generation.

    Raises:
        ResolutionError: If an unknown HTML library or unsupported HTTP client is specified.
    """
    from ssc_codegen.targets.python.html_libs.base import DomSpelling
    from ssc_codegen.targets.python.html_libs.bs4 import Bs4DomSpelling
    from ssc_codegen.targets.python.html_libs.lxml import LxmlDomSpelling
    from ssc_codegen.targets.python.html_libs.parsel import ParselDomSpelling
    from ssc_codegen.targets.python.html_libs.slax import SlaxDomSpelling
    from ssc_codegen.targets.python.visitor import PythonVisitor

    spellings: dict[str, type[DomSpelling]] = {
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

    valid_bs4_parsers = ("lxml", "html.parser", "html5lib")
    if spec.bs4_parser is not None:
        if lib != "bs4":
            raise ResolutionError(
                f"--bs4-parser is only applicable when --lib is bs4, not '{lib}'."
            )
        if spec.bs4_parser not in valid_bs4_parsers:
            raise ResolutionError(
                f"Invalid --bs4-parser '{spec.bs4_parser}'. "
                f"Permitted values: 'lxml', 'html.parser', 'html5lib'."
            )

    effective_bs4_parser = spec.bs4_parser or "lxml"
    effective_http_io = spec.http_io or "both"

    valid_http_io = ("both", "sync", "async")
    if effective_http_io not in valid_http_io:
        raise ResolutionError(
            f"Invalid --http-io '{spec.http_io}'. "
            f"Permitted values: 'both', 'sync', 'async'."
        )

    spelling_cls = spellings[lib]

    if spec.http_client is not None:
        valid = ("httpx", "httpx2", "aiohttp", "requests")
        if spec.http_client not in valid:
            raise ResolutionError(
                f"Python accepts --http-client: {', '.join(valid)}. "
                f"Got '{spec.http_client}'."
            )

    if spec.http_client == "aiohttp" and effective_http_io == "sync":
        raise ResolutionError(
            "aiohttp does not support synchronous I/O (--http-io sync). "
            "Use 'both', 'async', or a different HTTP client."
        )

    if spec.separate_runtime and lib == "lxml":
        pass  # supported, with fallback

    def _factory() -> PythonVisitor:
        return PythonVisitor(
            dom_spelling_cls=spelling_cls,
            bs4_parser=effective_bs4_parser,
            http_io=effective_http_io,
        )

    return TargetProfile(
        language="python",
        file_extension=".py",
        create_converter=_factory,
        http_clients=("httpx", "httpx2", "aiohttp", "requests"),
        supports_separate_runtime=True,
        runtime_include_fallback=(lib == "lxml"),
    )


def _reject_python_only_options(spec: TargetSpec, lang_name: str) -> None:
    """Validate that Python-only target options are not specified.

    Args:
        spec: Raw target options to validate.
        lang_name: Target backend language name for error reporting.

    Raises:
        ResolutionError: If `--bs4-parser` or `--http-io` is provided.
    """
    if spec.bs4_parser is not None:
        raise ResolutionError(
            f"--bs4-parser is not applicable for {lang_name}."
        )
    if spec.http_io is not None:
        raise ResolutionError(f"--http-io is not applicable for {lang_name}.")


def _resolve_js(spec: TargetSpec) -> TargetProfile:
    """Resolve and validate configuration for the JavaScript (DOM API) backend.

    Args:
        spec: Target configuration for JavaScript.

    Returns:
        TargetProfile for JavaScript code generation.

    Raises:
        ResolutionError: If DOM library or unsupported HTTP client is specified,
            or if separate runtime is requested.
    """
    from ssc_codegen.targets.javascript.visitor import JsVisitor

    if spec.lib is not None:
        raise ResolutionError("--lib is not applicable for JavaScript.")

    _reject_python_only_options(spec, "JavaScript")

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


def _resolve_go(spec: TargetSpec) -> TargetProfile:
    """Resolve and validate configuration for the Go (goquery + net/http) backend.

    Args:
        spec: Target configuration for Go.

    Returns:
        TargetProfile for Go code generation.

    Raises:
        ResolutionError: If DOM library, custom HTTP client, or separate runtime is requested.
    """
    from ssc_codegen.targets.golang.visitor import GoVisitor

    if spec.lib is not None:
        raise ResolutionError("--lib is not applicable for Go.")
    _reject_python_only_options(spec, "Go")
    if spec.http_client is not None:
        raise ResolutionError(
            "Go uses net/http exclusively. --http-client is not applicable."
        )
    if spec.separate_runtime:
        raise ResolutionError(
            "--separate-runtime is not applicable for Go. "
            "Go always emits helpers to sscgen_runtime.go "
            "(same package, required for namespace safety)."
        )

    return TargetProfile(
        language="go",
        file_extension=".go",
        create_converter=lambda: GoVisitor(),
        http_clients=(),
    )


def _resolve_rust(spec: TargetSpec) -> TargetProfile:
    """Resolve the Rust ``dom_query`` backend."""
    from ssc_codegen.targets.rust.visitor import RustVisitor

    if spec.lib is not None:
        raise ResolutionError("--lib is not applicable for Rust.")
    _reject_python_only_options(spec, "Rust")
    if spec.http_client is not None and spec.http_client != "reqwest":
        raise ResolutionError(
            f"Invalid HTTP client '{spec.http_client}' for Rust. Valid options: reqwest."
        )
    if spec.separate_runtime:
        raise ResolutionError(
            "Rust always emits the shared sscgen_runtime.rs module."
        )
    return TargetProfile(
        language="rust",
        file_extension=".rs",
        create_converter=lambda: RustVisitor(),
        http_clients=("reqwest",),
        supports_separate_runtime=False,
    )
