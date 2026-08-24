from pathlib import Path

import pytest
from kdlquery import Severity

from ssc_codegen.ast import ExtensionCall, FunctionDef, VariableType
from ssc_codegen.core import parse_module
from ssc_codegen.exceptions import BuildTimeError
from ssc_codegen.generation.runtime import register_runtime_file
from ssc_codegen.targets.golang.visitor import GoVisitor
from ssc_codegen.targets.javascript.visitor import JsVisitor
from ssc_codegen.targets.python.html_libs.bs4 import Bs4DomSpelling
from ssc_codegen.targets.python.visitor import PythonVisitor


EXTENSION = r"""
extension Utils {
    to-base64 {
        sig str str

        py {
            import "from base64 import b64encode"
            emit #"{{out}} = b64encode({{in}}.encode("utf-8")).decode("ascii")"#
        }

        js {
            emit #"const {{out}} = btoa({{in}});"#
        }

        go {
            import "encoding/base64"
            emit #"{{out}} := base64.StdEncoding.EncodeToString([]byte({{in}}))"#
        }
    }

    truthy {
        sig T bool
        py { emit #"{{out}} = bool({{in}})"# }
    }
}
"""


def _errors(diagnostics) -> list[str]:
    return [
        diagnostic.message
        for diagnostic in diagnostics
        if diagnostic.severity == Severity.ERROR
    ]


def test_extension_call_infers_output_type() -> None:
    module, diagnostics = parse_module(
        EXTENSION + "\n(raw)fn encode { !Utils.to-base64 }\n"
    )

    assert not _errors(diagnostics)
    fn = next(node for node in module.body if isinstance(node, FunctionDef))
    call = next(node for node in fn.body if isinstance(node, ExtensionCall))
    assert call.ret_type_info.base == VariableType.STRING
    assert fn.ret_type_info.base == VariableType.STRING


def test_python_extension_codegen_executes() -> None:
    module, diagnostics = parse_module(
        EXTENSION + "\n(raw)fn encode { !Utils.to-base64 }\n"
    )
    assert not _errors(diagnostics)

    code = PythonVisitor(dom_spelling_cls=Bs4DomSpelling).convert(module)
    namespace: dict = {}
    exec(compile(code, "generated.py", "exec"), namespace)

    assert namespace["encode"]("hello") == "aGVsbG8="
    assert code.count("from base64 import b64encode") == 1


def test_go_extension_import_is_added_to_import_block() -> None:
    module, diagnostics = parse_module(
        EXTENSION + "\n(raw)fn encode { !Utils.to-base64 }\n"
    )
    assert not _errors(diagnostics)

    code = GoVisitor().convert(module, package="main")

    assert '"encoding/base64"' in code
    assert "base64.StdEncoding.EncodeToString" in code


def test_javascript_helper_is_emitted_once() -> None:
    source = r'''
extension Utils {
    normalize {
        sig str str
        js {
            helper normalizeValue {
                source #"""
                    function normalizeValue(value) {
                      return value.trim();
                    }
                    """#
            }
            emit #"const {{out}} = normalizeValue({{in}});"#
        }
    }
}
(raw)fn first { !Utils.normalize }
(raw)fn second { !Utils.normalize }
'''
    module, diagnostics = parse_module(source)
    assert not _errors(diagnostics)

    code = JsVisitor().convert(module)

    assert code.count("function normalizeValue(value)") == 1
    assert code.count("normalizeValue(v)") == 2


def test_go_helper_moves_to_shared_runtime() -> None:
    source = r'''
extension Utils {
    normalize {
        sig str str
        go {
            helper normalizeValue {
                import "strings"
                source #"""
                    func normalizeValue(value string) string {
                        return strings.TrimSpace(value)
                    }
                    """#
            }
            emit #"{{out}} := normalizeValue({{in}})"#
        }
    }
}
(raw)fn normalize { !Utils.normalize }
'''
    module, diagnostics = parse_module(source)
    assert not _errors(diagnostics)
    converter = GoVisitor()

    code = converter.convert(module, package="main")
    runtime = converter.emit_runtime("main")

    assert "func normalizeValue" not in code
    assert "func normalizeValue" in runtime
    assert '"strings"' in runtime


def test_python_helper_moves_to_separate_runtime() -> None:
    source = r'''
extension Utils {
    normalize {
        sig str str
        py {
            helper normalize_value {
                import "import re"
                source #"""
                    def normalize_value(value: str) -> str:
                        return re.sub(r"\s+", " ", value)
                    """#
            }
            emit #"{{out}} = normalize_value({{in}})"#
        }
    }
}
(raw)fn normalize { !Utils.normalize }
'''
    module, diagnostics = parse_module(source)
    assert not _errors(diagnostics)
    inline = PythonVisitor(dom_spelling_cls=Bs4DomSpelling).convert(module)
    inline_namespace: dict = {}
    exec(compile(inline, "generated.py", "exec"), inline_namespace)
    assert inline_namespace["normalize"]("  a   b  ") == " a b "
    converter = PythonVisitor(dom_spelling_cls=Bs4DomSpelling)
    generate_runtime = register_runtime_file(converter, "sscgen_runtime")

    code = converter.convert(module, runtime_module="sscgen_runtime")
    runtime = generate_runtime([module])

    assert "from .sscgen_runtime import normalize_value" in code
    assert "def normalize_value" not in code
    assert "import re" in runtime
    assert "def normalize_value" in runtime
    compile(runtime, "sscgen_runtime.py", "exec")


def test_extension_import_is_explicit_and_private(tmp_path: Path) -> None:
    extensions = tmp_path / "extensions.kdl"
    extensions.write_text(EXTENSION, encoding="utf-8")
    schema = tmp_path / "schema.kdl"
    schema.write_text(
        'import "./extensions.kdl" { (extension)Utils }\n'
        "(raw)fn encode { !Utils.to-base64 }\n",
        encoding="utf-8",
    )

    module, diagnostics = parse_module(
        schema.read_text(encoding="utf-8"), source_path=schema
    )

    assert not _errors(diagnostics)
    assert "Utils.to-base64" in module.extensions


def test_imported_struct_pulls_private_extension_dependency(
    tmp_path: Path,
) -> None:
    extensions = tmp_path / "extensions.kdl"
    extensions.write_text(EXTENSION, encoding="utf-8")
    shared = tmp_path / "shared.kdl"
    shared.write_text(
        'import "./extensions.kdl" { (extension)Utils }\n'
        'struct Public { value { css ".x"; text; !Utils.to-base64 } }\n',
        encoding="utf-8",
    )
    schema = tmp_path / "schema.kdl"
    schema.write_text(
        'import "./shared.kdl" { (struct)Public }\n'
        "struct Main { value { nested Public } }\n",
        encoding="utf-8",
    )

    module, diagnostics = parse_module(
        schema.read_text(encoding="utf-8"), source_path=schema
    )

    assert not _errors(diagnostics)
    assert "Utils.to-base64" in module.extensions


def test_unimported_extension_is_not_visible(tmp_path: Path) -> None:
    extensions = tmp_path / "extensions.kdl"
    extensions.write_text(EXTENSION, encoding="utf-8")
    schema = tmp_path / "schema.kdl"
    schema.write_text("(raw)fn encode { !Utils.to-base64 }\n", encoding="utf-8")

    _, diagnostics = parse_module(
        schema.read_text(encoding="utf-8"), source_path=schema
    )

    assert any(
        "unknown extension operation" in error for error in _errors(diagnostics)
    )


def test_missing_target_fails_during_generation() -> None:
    source = r"""
extension OnlyPy {
    value {
        sig T str
        py { emit #"{{out}} = 'value'"# }
    }
}
(raw)fn value { !OnlyPy.value }
"""
    module, diagnostics = parse_module(source)
    assert not _errors(diagnostics)

    with pytest.raises(BuildTimeError, match="has no 'go' target"):
        GoVisitor().convert(module, package="main")


def test_check_accepts_bool_extension() -> None:
    source = (
        EXTENSION
        + "\n(raw)struct Main { @check valid { !Utils.truthy } value { trim } }\n"
    )

    _, diagnostics = parse_module(source)

    assert not _errors(diagnostics)
