from ssc_codegen.ast import Module, Struct
from ssc_codegen.targets.javascript import JS_CONVERTER
from ssc_codegen.targets.python import PY_BS4_CONVERTER


def test_python_docs_are_literal_safe_and_preserved() -> None:
    payload = '"""\nPWNED = True\n"""\nbackslash=\\value'
    module = Module(doc=payload)
    module.body.append(Struct(parent=module, name="Safe", doc=payload))

    namespace: dict = {}
    exec(PY_BS4_CONVERTER.convert(module), namespace)

    assert namespace["__doc__"] == payload
    assert namespace["Safe"].__doc__ == payload
    assert "PWNED" not in namespace


def test_javascript_docs_escape_comment_terminator() -> None:
    module = Module(doc="safe */ globalThis.PWNED = true; /*")

    code = JS_CONVERTER.convert(module)

    assert "safe *\\/ globalThis.PWNED" in code
    assert "safe */ globalThis.PWNED" not in code
