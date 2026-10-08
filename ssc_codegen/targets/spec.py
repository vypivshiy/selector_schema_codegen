"""User-supplied target configuration data model.

This module defines `TargetSpec`, which represents the raw, unvalidated backend
configuration provided by CLI options or programmatic callers prior to validation
by `resolve()`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetSpec:
    """Raw target backend configuration before validation.

    Represents caller-supplied options specifying the target language, HTML/DOM
    library, HTTP transport client, and runtime distribution strategy.

    Attributes:
        lang: Target programming language identifier (`"python"`, `"javascript"` / `"js"`, `"go"`, `"rust"`).
        lib: HTML parser or DOM library (Python only: `"bs4"`, `"lxml"`, `"parsel"`, `"slax"`).
            Defaults to None (which resolves to `"bs4"` for Python).
        http_client: HTTP client strategy for `@request` REST code generation.
            Supported Python clients: `"httpx"`, `"httpx2"`, `"aiohttp"`, `"requests"`.
            Supported JavaScript clients: `"fetch"`, `"axios"`.
            Defaults to None (which selects default client for the backend).
        separate_runtime: Whether to extract utility/helper functions into a standalone
            runtime module rather than inlining them into each generated file.
            Supported for Python. Defaults to False.
        bs4_parser: Underlying HTML parser engine for BeautifulSoup4 ("lxml", "html.parser", "html5lib").
            Python bs4 only. Defaults to None (resolves to "lxml").
        http_io: HTTP method generation mode ("both", "sync", "async").
            Python only. Defaults to "both".

    Examples:
        ```python
        from ssc_codegen.targets.spec import TargetSpec

        # Standard Python + BeautifulSoup4 target
        spec_bs4 = TargetSpec(lang="python", lib="bs4")

        # Python + Selectolax with httpx REST transport and separate runtime
        spec_slax = TargetSpec(
            lang="python",
            lib="slax",
            http_client="httpx",
            separate_runtime=True,
        )

        # JavaScript with Fetch API
        spec_js = TargetSpec(lang="js", http_client="fetch")

        # Go with standard library net/http and goquery
        spec_go = TargetSpec(lang="go")

        # Rust with dom_query and serde
        spec_rust = TargetSpec(lang="rust")
        ```
    """

    lang: str
    lib: str | None = None
    http_client: str | None = None
    separate_runtime: bool = False
    bs4_parser: str | None = None
    http_io: str = "both"
