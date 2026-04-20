"""Interactive REPL shell for testing KDL schema parsers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from code import InteractiveConsole
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ssc_codegen.ast import Field, Struct
from ssc_codegen.ast.types import StructType
from ssc_codegen.converters.helpers import to_pascal_case
from ssc_codegen.parser import PARSER, parse_document

_CONVERTERS: dict[str, str] = {
    "py-bs4": "ssc_codegen.converters.py_bs4:PY_BASE_CONVERTER",
    "py-lxml": "ssc_codegen.converters.py_lxml:PY_LXML_CONVERTER",
    "py-parsel": "ssc_codegen.converters.py_parsel:PY_PARSEL_CONVERTER",
    "py-slax": "ssc_codegen.converters.py_slax:PY_SLAX_CONVERTER",
}
_PY_TARGETS = set(_CONVERTERS)


def _get_converter(target: str):
    mod_path, attr = _CONVERTERS[target].rsplit(":", 1)
    import importlib

    mod = importlib.import_module(mod_path)
    return getattr(mod, attr)


def _fetch_html(url: str) -> str:
    try:
        import httpx

        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except ImportError:
        raise RuntimeError(
            "httpx is required for URL fetching. "
            "Install with: pip install ssc-gen[repl]"
        )


def _build_doc(html: str, target: str):
    if target == "py-bs4":
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "lxml")
    if target == "py-lxml":
        from lxml import etree

        return etree.HTML(html)
    if target == "py-parsel":
        from parsel import Selector

        return Selector(html)
    if target == "py-slax":
        from selectolax.parser import HTMLParser

        return HTMLParser(html)
    raise ValueError(f"Unsupported target: {target}")


@dataclass
class ReplState:
    module_ast: Any = None
    struct_name: str = ""
    html: str = ""
    target: str = "py-bs4"
    http_client: str = "httpx"
    schema_path: Path | None = None
    kdl_source: str = ""
    verbose: bool = False
    css_to_xpath: bool = False


class Repl:
    def __init__(self, state: ReplState) -> None:
        self.state = state
        self.namespace: dict[str, Any] = {}
        self._console = InteractiveConsole(locals=self.namespace)
        self._generated_code: str = ""
        self._multiline_kdl: list[str] | None = None

    def cmdloop(self) -> None:
        if self.state.module_ast:
            self._rebuild()
        self._print_banner()
        while True:
            try:
                prompt = (
                    "kdl...> "
                    if self._multiline_kdl is not None
                    else "ssc-gen> "
                )
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            line = line.strip()
            if not line:
                continue
            if self._multiline_kdl is not None:
                if line == ":end":
                    self._finish_kdl()
                else:
                    self._multiline_kdl.append(line)
                continue
            if line.startswith(":"):
                self._handle_command(line)
            else:
                self._handle_python(line)

    # ── namespace builders ─────────────────────────────────────────

    def _current_struct(self) -> Struct | None:
        if self.state.module_ast is None:
            return None
        for node in self.state.module_ast.body:
            if isinstance(node, Struct) and node.name == self.state.struct_name:
                return node
        return None

    def _is_rest(self) -> bool:
        st = self._current_struct()
        return st is not None and st.struct_type == StructType.REST

    def _rebuild(self) -> None:
        if self.state.module_ast is None:
            return
        st = self._current_struct()
        if st is None:
            return
        converter = _get_converter(self.state.target)
        meta: dict[str, Any] = {}
        if self._is_rest():
            meta["http_client"] = self.state.http_client
        self._generated_code = converter.convert(self.state.module_ast, **meta)
        self.namespace = {}
        try:
            exec(self._generated_code, self.namespace)  # noqa: S102
        except Exception as exc:
            print(f"Error executing generated code: {exc}", file=sys.stderr)
            return
        class_name = to_pascal_case(self.state.struct_name)
        if self._is_rest():
            self._build_namespace_rest(class_name)
        else:
            self._build_namespace_parse(class_name)
        self._console.locals = self.namespace

    def _build_namespace_parse(self, class_name: str) -> None:
        cls = self.namespace.get(class_name)
        if cls is None:
            return
        if not self.state.html:
            return
        instance = cls(self.state.html)
        self.namespace["response"] = self.state.html
        try:
            self.namespace["doc"] = _build_doc(
                self.state.html, self.state.target
            )
        except Exception:
            pass
        self.namespace["parser"] = instance
        self.namespace[class_name] = cls
        self.namespace["fetch"] = _fetch_html

        def parse():
            return instance.parse()

        self.namespace["parse"] = parse

        def view(field_name: str):
            method = getattr(instance, f"_parse_{field_name}", None)
            if method is None:
                print(f"No such field: {field_name}", file=sys.stderr)
                return None
            result = method(instance._doc)
            if isinstance(result, str):
                print(result)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return result

        self.namespace["view"] = view

        for attr in dir(cls):
            if attr.startswith("_parse_"):
                fname = attr[len("_parse_") :]
                self.namespace[f"parse_{fname}"] = getattr(instance, attr)

    def _build_namespace_rest(self, class_name: str) -> None:
        cls = self.namespace.get(class_name)
        if cls is None:
            return
        try:
            if self.state.http_client == "httpx":
                import httpx

                client = httpx.Client()
            else:
                import requests  # type: ignore[import-untyped]

                client = requests.Session()
        except ImportError as exc:
            print(f"HTTP client not available: {exc}", file=sys.stderr)
            return
        self.namespace["client"] = client
        self.namespace[class_name] = cls
        self.namespace["fetch"] = _fetch_html
        for attr in dir(cls):
            if not attr.startswith("_") and callable(getattr(cls, attr)):
                self.namespace[attr] = getattr(cls, attr)

    # ── command dispatch ───────────────────────────────────────────

    def _handle_command(self, line: str) -> None:
        parts = line.split(None, 1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        handler = getattr(self, f"do_{cmd[1:].replace('-', '_')}", None)
        if handler:
            handler(args)
        else:
            print(f"Unknown command: {cmd}. Type :help for available commands.")

    def _handle_python(self, line: str) -> None:
        try:
            result = eval(line, self.namespace)  # noqa: S307
            if result is not None:
                self._pprint(result)
        except SyntaxError:
            self._console.push(line)
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)

    def _pprint(self, obj: Any) -> None:
        if isinstance(obj, (dict, list)):
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            print(repr(obj))

    # ── commands ───────────────────────────────────────────────────

    def do_load(self, args: str) -> None:
        from ssc_codegen import parse_ast

        if not args:
            print("Usage: :load <path.kdl[:StructName]>")
            return
        if ":" in args:
            path_part, struct_name = args.rsplit(":", 1)
        else:
            path_part = args
            struct_name = ""
        kdl_path = Path(path_part)
        if not kdl_path.is_file():
            print(f"File not found: {kdl_path}", file=sys.stderr)
            return
        try:
            module_ast = parse_ast(
                path=str(kdl_path), css_to_xpath=self.state.css_to_xpath
            )
        except Exception as exc:
            print(f"Parse error: {exc}", file=sys.stderr)
            return
        structs = [n for n in module_ast.body if isinstance(n, Struct)]
        if not struct_name:
            if not structs:
                print("No structs found in schema.", file=sys.stderr)
                return
            struct_name = structs[0].name
        struct_names = [s.name for s in structs]
        if struct_name not in struct_names:
            print(
                f"Struct '{struct_name}' not found. "
                f"Available: {', '.join(struct_names)}",
                file=sys.stderr,
            )
            return
        self.state.module_ast = module_ast
        self.state.struct_name = struct_name
        self.state.schema_path = kdl_path
        self.state.kdl_source = kdl_path.read_text(encoding="utf-8-sig")
        self._rebuild()
        st = self._current_struct()
        kind = (
            "rest" if st and st.is_rest else st.struct_type.value if st else "?"
        )
        print(f"Loaded {kdl_path.name}:{struct_name} (type={kind})")

    def do_html(self, args: str) -> None:
        if not args:
            print("Usage: :html <path>")
            return
        path = Path(args.strip())
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            return
        self.state.html = path.read_text(encoding="utf-8")
        self._rebuild()
        print(f"Loaded HTML ({len(self.state.html)} chars)")

    def do_fetch(self, args: str) -> None:
        if not args:
            print("Usage: :fetch <url>")
            return
        url = args.strip()
        print(f"Fetching {url}...", file=sys.stderr)
        try:
            self.state.html = _fetch_html(url)
        except Exception as exc:
            print(f"Fetch error: {exc}", file=sys.stderr)
            return
        self._rebuild()
        print(f"Loaded HTML ({len(self.state.html)} chars)")

    def do_target(self, args: str) -> None:
        if not args:
            print(f"Current target: {self.state.target}")
            print(f"Available: {', '.join(sorted(_CONVERTERS))}")
            return
        target = args.strip()
        if target not in _CONVERTERS:
            print(
                f"Unknown target: {target}. Available: {', '.join(sorted(_CONVERTERS))}"
            )
            return
        self.state.target = target
        self._rebuild()
        print(f"Target set to {target}")

    def do_http_client(self, args: str) -> None:
        if not args:
            print(f"Current HTTP client: {self.state.http_client}")
            return
        client = args.strip()
        if client not in ("httpx", "requests"):
            print("Available: httpx, requests")
            return
        self.state.http_client = client
        self._rebuild()
        print(f"HTTP client set to {client}")

    def do_field(self, args: str) -> None:
        if not args:
            print("Usage: :field <name> [target] { pipeline... }")
            return
        st = self._current_struct()
        if st is None:
            print("No struct loaded. Use :load first.", file=sys.stderr)
            return
        if self._is_rest():
            print("REST structs use :request, not :field.", file=sys.stderr)
            return
        target_override: str | None = None
        rest = args.strip()
        for t in _PY_TARGETS:
            if rest.endswith(t) or (t in rest and "{" not in rest.split(t)[0]):
                if t not in rest.split("{")[0]:
                    continue
                target_override = t
                rest = rest.replace(t, "", 1).strip()
                break
        brace_idx = rest.find("{")
        if brace_idx < 0:
            print("Missing { ... } block.", file=sys.stderr)
            return
        field_name = rest[:brace_idx].strip()
        body = rest[brace_idx:]
        kdl_src = f"struct _repl_temp {{ {field_name} {body} }}"
        try:
            doc = parse_document(kdl_src)
        except Exception as exc:
            print(f"KDL parse error: {exc}", file=sys.stderr)
            return
        if not doc.nodes or not doc.nodes[0].children:
            print("Empty field body.", file=sys.stderr)
            return
        field_node = doc.nodes[0].children[0]
        new_field = Field(parent=st, name=field_name)
        try:
            PARSER._parse_expressions(field_node.children, new_field)
        except Exception as exc:
            print(f"Expression parse error: {exc}", file=sys.stderr)
            return
        for i, node in enumerate(st.body):
            if isinstance(node, Field) and node.name == field_name:
                st.body[i] = new_field
                break
        else:
            st.body.insert(-1, new_field)
        save_target = self.state.target
        if target_override:
            self.state.target = target_override
        self._rebuild()
        if target_override:
            print(f"Field '{field_name}' updated (target={target_override})")
            self.state.target = save_target
            self._rebuild()
        else:
            print(f"Field '{field_name}' updated")
            if self.state.html and "parse_" + field_name in self.namespace:
                result = self.namespace["parse_" + field_name](
                    self.namespace.get("parser")._doc
                )
                print(f"  → {result!r}")

    def do_request(self, args: str) -> None:
        if not args:
            print(
                'Usage: :request <name> [doc="..."] [response=Schema] """HTTP..."""'
            )
            return
        st = self._current_struct()
        if st is None:
            print("No struct loaded. Use :load first.", file=sys.stderr)
            return
        if not self._is_rest():
            print(":request is only for type=rest structs.", file=sys.stderr)
            return
        from ssc_codegen.ast.struct import RequestConfig

        parts = args.strip().split(None, 1)
        req_name = parts[0] if parts else ""
        body_text = parts[1] if len(parts) > 1 else ""
        doc_val = ""
        response_val = ""
        import re

        m = re.search(r'doc="([^"]*)"', body_text)
        if m:
            doc_val = m.group(1)
        m = re.search(r"response=(\S+)", body_text)
        if m:
            response_val = m.group(1)
        payload_match = re.search(r'"""(.*?)"""', body_text, re.DOTALL)
        if not payload_match:
            payload_match = re.search(r'"([^"]*(?:\n[^"]*)*)"', body_text)
        raw_payload = payload_match.group(1) if payload_match else ""
        new_req = RequestConfig(parent=st)
        new_req.name = req_name
        new_req.raw_payload = raw_payload
        new_req.doc = doc_val
        new_req.response_schema = response_val
        for i, node in enumerate(st.body):
            if (
                isinstance(RequestConfig, type(node))
                and hasattr(node, "name")
                and node.name == req_name
            ):
                st.body[i] = new_req
                break
        else:
            st.body.insert(len(st.body) - 1, new_req)
        self._rebuild()
        print(f"Request '{req_name}' updated")

    def do_kdl(self, args: str) -> None:
        if args.strip():
            self._multiline_kdl = [args.strip()]
        else:
            self._multiline_kdl = []
        print("Enter KDL, finish with :end", file=sys.stderr)

    def _finish_kdl(self) -> None:
        assert self._multiline_kdl is not None
        kdl_text = "\n".join(self._multiline_kdl)
        self._multiline_kdl = None
        from ssc_codegen import parse_ast

        try:
            new_module = parse_ast(
                src=kdl_text, css_to_xpath=self.state.css_to_xpath
            )
        except Exception as exc:
            print(f"KDL parse error: {exc}", file=sys.stderr)
            return
        if self.state.module_ast is None:
            self.state.module_ast = new_module
            structs = [n for n in new_module.body if isinstance(n, Struct)]
            if structs:
                self.state.struct_name = structs[0].name
        else:
            for node in new_module.body:
                if isinstance(node, Struct):
                    replaced = False
                    for i, existing in enumerate(self.state.module_ast.body):
                        if (
                            isinstance(existing, Struct)
                            and existing.name == node.name
                        ):
                            self.state.module_ast.body[i] = node
                            replaced = True
                            break
                    if not replaced:
                        self.state.module_ast.body.append(node)
        self._rebuild()
        print("KDL snippet applied")

    def do_edit(self, args: str) -> None:
        path = self.state.schema_path
        if path is None:
            fd, tmp = tempfile.mkstemp(suffix=".kdl")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(self.state.kdl_source or "")
            except Exception:
                os.close(fd)
                raise
            path = Path(tmp)
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
        if not editor:
            editor = "notepad" if sys.platform == "win32" else "vi"
        try:
            subprocess.call([editor, str(path)])
        except FileNotFoundError:
            print(f"Editor not found: {editor}", file=sys.stderr)
            return
        new_src = path.read_text(encoding="utf-8-sig")
        if new_src == self.state.kdl_source:
            print("No changes detected.")
            return
        self.state.kdl_source = new_src
        from ssc_codegen import parse_ast

        try:
            self.state.module_ast = parse_ast(
                src=new_src, css_to_xpath=self.state.css_to_xpath
            )
        except Exception as exc:
            print(f"Parse error after edit: {exc}", file=sys.stderr)
            return
        self._rebuild()
        print("Schema reloaded from editor.")

    def do_health(self, args: str) -> None:
        from ssc_codegen.health import check_struct_health

        st = self._current_struct()
        if st is None:
            print("No struct loaded.", file=sys.stderr)
            return
        if not self.state.html:
            print("No HTML loaded. Use :html or :fetch first.", file=sys.stderr)
            return
        result = check_struct_health(
            st, self.state.html, module=self.state.module_ast
        )
        print(result.format("text"))

    def do_view(self, args: str) -> None:
        if not self.state.html:
            print("No HTML loaded.", file=sys.stderr)
            return
        field_name = args.strip()
        if field_name:
            if "view" in self.namespace:
                self.namespace["view"](field_name)
            else:
                print("Parser not available.", file=sys.stderr)
        else:
            if "parse" in self.namespace:
                result = self.namespace["parse"]()
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("Parser not available.", file=sys.stderr)

    def do_code(self, args: str) -> None:
        if self._generated_code:
            print(self._generated_code)
        else:
            print("No code generated yet.", file=sys.stderr)

    def do_help(self, args: str) -> None:
        print(
            "\nCommands:\n"
            "  :load <path.kdl[:Struct]>  Load schema\n"
            "  :html <path>               Load HTML from file\n"
            "  :fetch <url>               Fetch HTML from URL\n"
            "  :target <name>             Set converter target (py-bs4, py-lxml, ...)\n"
            "  :field <name> [tgt] {...}  Override/add field inline\n"
            "  :kdl ... :end              Insert KDL snippet\n"
            "  :edit                      Open schema in $EDITOR\n"
            "  :health                    Check selectors against HTML\n"
            "  :view [field]              Show parse result (all or single field)\n"
            "  :code                      Show generated code\n"
            "  :request <name> ...        Override @request (REST structs)\n"
            "  :http-client <name>        Set HTTP client (httpx, requests)\n"
            "  :help                      This message\n"
            "\nPython expressions are evaluated in the current namespace."
        )

    # ── banner ─────────────────────────────────────────────────────

    def _print_banner(self) -> None:
        lines = ["[ssc-gen shell] Interactive KDL schema REPL"]
        if self.state.module_ast:
            st = self._current_struct()
            kind = (
                "rest"
                if st and st.is_rest
                else st.struct_type.value
                if st
                else "?"
            )
            lines.append(f"  Struct: {self.state.struct_name} (type={kind})")
            lines.append(f"  Target: {self.state.target}")
            if self.state.html:
                lines.append(f"  HTML:   {len(self.state.html)} chars loaded")
        else:
            lines.append("  No schema loaded. Use :load <path.kdl>")
        lines.append("  Type :help for commands, Ctrl+D to exit.")
        print("\n".join(lines))
