import inspect

from ssc_codegen.ast import Module, Struct
from ssc_codegen.core import parse_module
from ssc_codegen.targets.javascript import JS_CONVERTER
from ssc_codegen.targets.python import PY_BS4_CONVERTER


def test_python_docs_are_literal_safe_and_preserved() -> None:
    payload = '"""\nPWNED = True\n"""\nbackslash=\\value'
    module = Module(doc=payload)
    module.body.append(Struct(parent=module, name="Safe", doc=payload))

    namespace: dict = {}
    exec(PY_BS4_CONVERTER.convert(module), namespace)

    assert inspect.cleandoc(namespace["__doc__"]) == payload
    assert inspect.cleandoc(namespace["Safe"].__doc__) == payload
    assert "PWNED" not in namespace


def test_kdl_multiline_docs_cleandoc_and_python_docstrings() -> None:
    kdl = '''
    @doc """
        Module summary line.

        Second paragraph.
    """

    struct Page {
        @doc """
            Page parser struct.
            Extracts the page title.
        """
        @request doc="""
            Fetch page HTML.
            Supports sync and async clients.
        """ """
        GET https://example.com/page HTTP/1.1
        """
        title { css "h1"; text }
    }

    (rest)struct Api {
        @doc """
            REST API client.
            Line two.
        """
        @request name="get_user" doc="""
            Fetch user by ID.
            Returns Ok or Err.
        """ """
        GET https://api.example.com/users HTTP/1.1
        """
    }

    fn extract_title {
        @doc """
            Extract title from HTML.
            Multi-line function doc.
        """
        css "h1"
        text
    }
    '''
    module, diags = parse_module(kdl)
    assert not diags
    assert module.doc == "Module summary line.\n\nSecond paragraph."

    code = PY_BS4_CONVERTER.convert(module)
    assert "'\\n" not in code

    namespace: dict = {}
    exec(code, namespace)

    assert (
        inspect.cleandoc(namespace["__doc__"])
        == "Module summary line.\n\nSecond paragraph."
    )
    assert (
        inspect.cleandoc(namespace["Page"].__doc__)
        == "Page parser struct.\nExtracts the page title."
    )
    assert (
        inspect.cleandoc(namespace["Page"].fetch.__doc__)
        == "Fetch page HTML.\nSupports sync and async clients."
    )
    assert (
        inspect.cleandoc(namespace["Api"].__doc__)
        == "REST API client.\nLine two."
    )
    assert (
        inspect.cleandoc(namespace["Api"].get_user.__doc__)
        == "Fetch user by ID.\nReturns Ok or Err."
    )
    assert (
        inspect.cleandoc(namespace["extract_title"].__doc__)
        == "Extract title from HTML.\nMulti-line function doc."
    )


def test_python_docs_trailing_quotes_single_and_multiline() -> None:
    suffixes = ('"', '""', '"""')
    for suffix in suffixes:
        single_doc = f"Single-line doc ending with {suffix}"
        multi_doc = f"Multi-line doc line 1\nLine 2 ending with {suffix}"

        mod_single = Module(doc=single_doc)
        mod_single.body.append(
            Struct(parent=mod_single, name="SingleStruct", doc=single_doc)
        )
        ns_single: dict = {}
        exec(PY_BS4_CONVERTER.convert(mod_single), ns_single)
        assert inspect.cleandoc(ns_single["__doc__"]) == single_doc
        assert inspect.cleandoc(ns_single["SingleStruct"].__doc__) == single_doc

        mod_multi = Module(doc=multi_doc)
        mod_multi.body.append(
            Struct(parent=mod_multi, name="MultiStruct", doc=multi_doc)
        )
        ns_multi: dict = {}
        exec(PY_BS4_CONVERTER.convert(mod_multi), ns_multi)
        assert inspect.cleandoc(ns_multi["__doc__"]) == multi_doc
        assert inspect.cleandoc(ns_multi["MultiStruct"].__doc__) == multi_doc


def test_javascript_docs_escape_comment_terminator() -> None:
    module = Module(doc="safe */ globalThis.PWNED = true; /*")

    code = JS_CONVERTER.convert(module)

    assert "safe *\\/ globalThis.PWNED" in code
    assert "safe */ globalThis.PWNED" not in code
