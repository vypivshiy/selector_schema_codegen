"""Pure ES6 JS (DOM) codegen visitor on the BaseWalker model.

Ports all JS codegen from ``JsPure`` to the new ``list[str]`` traversal core.
Emits plain JavaScript using the browser/DOM API (``querySelector`` etc.),
suitable for modern browsers and the Node.js + jsdom test runner.

Codegen notations:

- ES8 required if ``re.DOTALL`` regex flag is needed, otherwise ES6.
- Annotations are generated in JSDoc format.
- Method (field) names are converted to ``_parseUpperCamelCase``.
"""

from __future__ import annotations

import json
import re as _re
from typing import Any

from ssc_codegen.ast import (
    Assert,
    Attr,
    CheckMethod,
    CodeEndHook,
    CodeStartHook,
    CssRemove,
    CssSelect,
    CssSelectAll,
    ErrorResponse,
    ExtensionCall,
    Fallback,
    Field,
    Filter,
    Fmt,
    FunctionDef,
    Index,
    Init,
    InitField,
    InitFieldCall,
    Join,
    JsonDef,
    JsonDefField,
    Jsonify,
    Key,
    Len,
    LogicAnd,
    LogicNot,
    LogicOr,
    Lower,
    Ltrim,
    Match,
    MatcherListDef,
    MethodFetch,
    MethodRest,
    Module,
    Nested,
    NormalizeSpace,
    PredAttrContains,
    PredAttrEnds,
    PredAttrEq,
    PredAttrNe,
    PredAttrRe,
    PredAttrStarts,
    PredContains,
    PredCountEq,
    PredCountGe,
    PredCountGt,
    PredCountLe,
    PredCountLt,
    PredCountNe,
    PredCountRange,
    PredCss,
    PredEnds,
    PredEq,
    PredHasAttr,
    PredNe,
    PredRe,
    PredReAll,
    PredReAny,
    PredStarts,
    PredTextContains,
    PredTextEnds,
    PredTextRe,
    PredTextStarts,
    PredXpath,
    PreValidate,
    Raw,
    Re,
    ReAll,
    Repl,
    ReplMap,
    ReSub,
    ResultAliasDef,
    ResultVariantDef,
    Return,
    RmPrefix,
    RmPrefixSuffix,
    RmSuffix,
    Rtrim,
    Self,
    Slice,
    Split,
    SplitDoc,
    StartParse,
    Struct,
    StructBase,
    StructRest,
    TableConfig,
    TableMatchKey,
    TableRows,
    Text,
    ToBool,
    ToFloat,
    ToInt,
    Trim,
    TypeDef,
    TypeDefField,
    TypeInfo,
    Unescape,
    Unique,
    Upper,
    Utilities,
    Value,
    XpathRemove,
    XpathSelect,
    XpathSelectAll,
)
from ssc_codegen.ast import (
    StructType as ST,
)
from ssc_codegen.ast import (
    VariableType as VT,
)
from ssc_codegen.exceptions import BuildTimeError
from ssc_codegen.generation.builder import ModuleBuilder
from ssc_codegen.naming import (
    json_descriptor_var_name,
    to_camel_case,
    to_pascal_case,
)
from ssc_codegen.targets.javascript import rest
from ssc_codegen.targets.javascript.http_libs.axios import AxiosStrategy
from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy
from ssc_codegen.targets.javascript.http_libs.fetch import FetchStrategy
from ssc_codegen.traversal.context import WalkContext
from ssc_codegen.traversal.utils import (
    DescriptorRef,
    find_predicate_container,
    json_def_descriptors,
    jsonify_path_to_segments,
    module_has_rest,
    resolve_json_def,
)
from ssc_codegen.traversal.walker import BaseWalker

_JS_JSON_PROJECT_HELPER = """class SscJsonError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SscJsonError';
  }
}
class SscJsonPathError extends SscJsonError {
  constructor(message) {
    super(message);
    this.name = 'SscJsonPathError';
  }
}
class SscJsonFieldMissingError extends SscJsonError {
  constructor(message) {
    super(message);
    this.name = 'SscJsonFieldMissingError';
  }
}
class SscJsonSchemaError extends SscJsonError {
  constructor(message) {
    super(message);
    this.name = 'SscJsonSchemaError';
  }
}

function sscResolveDotpath(data, path, isOptional) {
  let current = data;
  const parts = path.split('.');
  for (const seg of parts) {
    if (current == null) {
      if (isOptional) return null;
      throw new SscJsonPathError(`Cannot traverse segment '${seg}' on null object in path '${path}'`);
    }
    if (/^\\d+$/.test(seg)) {
      const idx = parseInt(seg, 10);
      if (!Array.isArray(current)) {
        if (isOptional) return null;
        throw new SscJsonPathError(`Expected list for index '${idx}' in path '${path}', got ${typeof current}`);
      }
      if (idx < 0 || idx >= current.length) {
        if (isOptional) return null;
        throw new SscJsonPathError(`Index ${idx} out of bounds (len=${current.length}) in path '${path}'`);
      }
      current = current[idx];
    } else if (typeof current === 'object') {
      if (!(seg in current)) {
        if (isOptional) return null;
        throw new SscJsonPathError(`Missing key '${seg}' in path '${path}'`);
      }
      current = current[seg];
    } else {
      if (isOptional) return null;
      throw new SscJsonPathError(`Cannot access key '${seg}' on non-dict ${typeof current} in path '${path}'`);
    }
  }
  return current;
}

function sscJsonProject(data, descriptors) {
  if (descriptors && descriptors.__dict__) {
    if (typeof data !== 'object' || data === null || Array.isArray(data)) {
      throw new SscJsonSchemaError(`Expected object for dict schema, got ${data === null ? 'null' : Array.isArray(data) ? 'array' : typeof data}`);
    }
    const valDesc = descriptors.__value__;
    if (valDesc == null) return data;
    const result = {};
    for (const [k, v] of Object.entries(data)) {
      if (Array.isArray(valDesc) && valDesc.length > 0) {
        result[k] = Array.isArray(v)
          ? v.map(x => (x != null ? sscJsonProject(x, valDesc[0]) : x))
          : sscJsonProject(v, valDesc[0]);
      } else {
        result[k] = sscJsonProject(v, valDesc);
      }
    }
    return result;
  }
  if (Array.isArray(data)) {
    return data.map(item => sscJsonProject(item, descriptors));
  }
  if (data == null || typeof data !== 'object') return data;

  const result = {};
  for (const [canonical, [wirePath, isOptional, isOmitempty, nested]] of Object.entries(descriptors)) {
    let val;
    if (wirePath.includes('.') || /^\\d+$/.test(wirePath)) {
      val = sscResolveDotpath(data, wirePath, isOptional || isOmitempty);
    } else {
      if (!(wirePath in data)) {
        if (isOmitempty || isOptional) {
          val = null;
        } else {
          throw new SscJsonFieldMissingError(`Required JSON field '${wirePath}' (mapped to '${canonical}') is missing`);
        }
      } else {
        val = data[wirePath];
      }
    }

    if (val === null || val === undefined) {
      if (isOmitempty) continue;
      if (!isOptional) {
        throw new SscJsonFieldMissingError(`Field '${wirePath}' is null, but '${canonical}' is not nullable`);
      }
      result[canonical] = null;
      continue;
    }

    if (nested) {
      if (typeof nested === 'object' && nested.__dict__) {
        val = sscJsonProject(val, nested);
      } else {
        val = Array.isArray(nested)
          ? (Array.isArray(val) ? val.map(x => sscJsonProject(x, nested[0])) : sscJsonProject(val, nested[0]))
          : sscJsonProject(val, nested);
      }
    }

    result[canonical] = val;
  }
  return result;
}

function sscRemapJsonKeys(value, mapping) {
  if (Array.isArray(value)) return value.map(item => sscRemapJsonKeys(item, mapping));
  if (value === null || typeof value !== 'object') return value;
  const result = {};
  for (const [source, spec] of Object.entries(mapping)) {
    if (!Object.prototype.hasOwnProperty.call(value, source)) continue;
    const output = Array.isArray(spec) ? spec[0] : spec;
    const nested = Array.isArray(spec) ? spec[1] : null;
    let item = value[source];
    if (Array.isArray(nested)) item = item.map(x => sscRemapJsonKeys(x, nested[0]));
    else if (nested !== null) item = sscRemapJsonKeys(item, nested);
    result[output] = item;
  }
  return result;
}"""


def _js_json_descriptors(
    node: JsonDef, definitions: dict[str, JsonDef]
) -> list[str]:
    descriptors = json_def_descriptors(node, definitions)

    def render(value: object) -> str:
        if isinstance(value, DescriptorRef):
            return json_descriptor_var_name(value.schema_name)
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, tuple):
            return "[" + ", ".join(render(x) for x in value) + "]"
        if isinstance(value, list):
            return "[" + ", ".join(render(item) for item in value) + "]"
        if isinstance(value, dict):
            return (
                "{"
                + ", ".join(
                    f"{json.dumps(key)}: {render(item)}"
                    for key, item in value.items()
                )
                + "}"
            )
        raise TypeError(f"unsupported JSON descriptor value: {value!r}")

    return [
        f"const {json_descriptor_var_name(node.name)} = {render(descriptors)};",
        "",
    ]


# ===========================================================================
# Helpers
# ===========================================================================


def _py_re_to_js_re(pattern: str, global_flag: bool = False) -> str:
    """Convert a Python regex pattern to a JS regex literal.

    Strips a leading ``(?ims)`` inline-flag group, transfers ``i``/``m``/``s``
    to the JS flags, and optionally forces ``g`` for matchAll/replace.
    """
    flags = "g" if global_flag else ""
    m = _re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags += "".join(c for c in m.group(1) if c in "ims")
        pattern = pattern[m.end() :]
    escaped = pattern.replace("/", "\\/")
    return f"/{escaped}/{flags}"


def py_sequence_to_js_array(values) -> str:
    return json.dumps(list(values))


def _js_literal(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def _logic_prefix(op: str, ctx: WalkContext) -> str:
    if ctx.index == 0:
        return ctx.indent + "("
    return ctx.indent + f"{op} ("


def _js_docblock(lines: list[str]) -> list[str]:
    if not lines:
        return []
    safe = [line.replace("*/", "*\\/") for line in lines]
    return ["/**", *(f" * {line}" if line else " *" for line in safe), " */"]


def _pred_target(node, ctx: WalkContext) -> str:
    container = find_predicate_container(node)
    if isinstance(container, Filter):
        return "i"
    if isinstance(container, (Match, Assert, PreValidate)):
        return getattr(container, "_local_name", "i")
    return ctx.prv


def _pred_text_target(node, ctx: WalkContext) -> str:
    target = _pred_target(node, ctx)
    container = find_predicate_container(node)
    if target == "i" and isinstance(container, Filter):
        return "i.textContent"
    return target


def _pred_attr_target(node, ctx: WalkContext) -> str:
    return _pred_target(node, ctx)


# ===========================================================================
# StartParse helpers
# ===========================================================================


def _js_method_name(field_name: str) -> str:
    n = to_camel_case(field_name)
    return f"_parse{n[0].upper() + n[1:]}"


def _js_struct_header(node: StructBase) -> list[str]:
    doc_lines = _js_docblock(node.doc.splitlines()) if node.doc else []
    return [*doc_lines, f"class {to_pascal_case(node.name)} {{"]


# ===========================================================================
# JsVisitor
# ===========================================================================


class JsVisitor(BaseWalker):
    """Pure ES6 / DOM JavaScript code generator visitor.

    Emits standard JavaScript parser classes targeting the browser DOM or Node.js
    `jsdom` environment. Uses standard `querySelector`, `querySelectorAll`,
    `textContent`, and `getAttribute` DOM APIs.

    Attributes:
        TYPES: Mapping from `VariableType` enums to JSDoc type annotations.
        DEFAULT_TYPE: Fallback JSDoc type string (``"any"``).
        ARRAY_TYPE_FMT: Array type formatting template (``"{}[]"``).
        OPTIONAL_TYPE_FMT: Optional type formatting template (``"{}|null"``).
        DOCUMENT_TYPE: JSDoc type for DOM documents/elements (``"Document|Element"``).
        DOCUMENT_ARRAY_TYPE: JSDoc type for collections of elements (``"Array<Element>"``).
        STD_MODULE_NAME: Default module name for separate runtime exports (``"sscgen_runtime"``).
        var_name: Base prefix for pipeline intermediate variables (default: ``"v"``).
        indent: Indentation unit string (default: 2 spaces).
    """

    TYPES = {
        VT.STRING: "string",
        VT.BOOL: "boolean",
        VT.INT: "number",
        VT.FLOAT: "number",
        VT.NULL: "null",
        VT.JSON: "any",
        VT.NESTED: "any",
        VT.AUTO: "any",
    }
    DEFAULT_TYPE = "any"
    ARRAY_TYPE_FMT = "{}[]"
    OPTIONAL_TYPE_FMT = "{}|null"
    OPTIONAL_ON_OMITEMPTY = True
    DOCUMENT_TYPE = "Document|Element"
    DOCUMENT_ARRAY_TYPE = "Array<Element>"
    STD_MODULE_NAME = "sscgen_runtime"

    _HTTP_STRATEGIES: dict[str, type[JsHttpLibStrategy]] = {
        "fetch": FetchStrategy,
        "axios": AxiosStrategy,
    }

    def __init__(self, var_name: str = "v", indent: str = " " * 2) -> None:
        """Initialize the JavaScript visitor.

        Args:
            var_name: Base prefix for intermediate variables (default: ``"v"``).
            indent: Indentation unit string (default: 2 spaces).
        """
        self.var_name = var_name
        self.indent = indent
        self._file_providers: dict[str, Any] = {}
        self._reset_state()

    # === STATE ===

    def _reset_state(self) -> None:
        self._builder = ModuleBuilder()
        self._http: JsHttpLibStrategy = FetchStrategy()

    def _make_ctx(self, meta: dict) -> WalkContext:
        return WalkContext(
            var_name=self.var_name, indent_char=self.indent, meta=dict(meta)
        )

    # === FILE PROVIDERS ===

    def file(self, filename: str):
        """Decorator for registering companion file generator functions."""

        def decorator(fn):
            self._file_providers[filename] = fn
            return fn

        return decorator

    # === PUBLIC API ===

    def convert(self, module_ast: Module, **meta: Any) -> str:
        """Convert a `Module` AST to a single generated JavaScript source string.

        Args:
            module_ast: The root `Module` AST node to convert.
            **meta: Options passed to `WalkContext.meta` (e.g. `http_client`).

        Returns:
            Generated JavaScript source code string.
        """
        return self.convert_all(module_ast, **meta)[""]

    def convert_all(self, module_ast: Module, **meta: Any) -> dict[str, str]:
        """Convert a `Module` AST in a two-pass traversal, emitting main and companion files.

        Pass 1 populates `ModuleBuilder` with required std helpers.
        Pass 2 generates the complete JavaScript source code.

        Args:
            module_ast: The root `Module` AST node to convert.
            **meta: Options controlling generation (e.g. `http_client`).

        Returns:
            Mapping from filenames (``""`` for the main module) to generated source texts.
        """
        self._reset_state()
        client = meta.get("http_client")
        if client and client in self._HTTP_STRATEGIES:
            self._http = self._HTTP_STRATEGIES[client]()
        ctx = self._make_ctx(meta)
        self._walk_module(module_ast, ctx)
        lines = self._walk_module(module_ast, ctx)
        out: dict[str, str] = {"": "\n".join(lines)}
        for fname, provider in self._file_providers.items():
            out[fname] = provider(module_ast, ctx.meta)
        return out

    def _walk_module(self, module_ast: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = list(self.visit_module(module_ast, ctx))
        for node in module_ast.body:
            lines.extend(self.walk(node, ctx))
        return lines

    # === STD RENDERING ===

    def _render_std_section(self, ctx: WalkContext) -> list[str]:
        if not self._builder.has_std and not self._builder.has_runtime:
            return []
        body: list[str] = [
            item
            for item in self._builder.runtime_imports
            if item not in self._builder.imports
        ]
        if body:
            body.append("")
        for _imps, code in self._builder.runtime_defs.values():
            body.extend(code.splitlines())
            body.append("")
        for _imps, code in self._builder.std_defs.values():
            body.extend(code.splitlines())
            body.append("")
        return body

    # === TYPE RESOLUTION ===

    def _resolve_type(self, type_info: TypeInfo | None) -> str:
        if type_info is None:
            return self.DEFAULT_TYPE
        if type_info.is_dict:
            key_map = {
                VT.STRING: "string",
                VT.INT: "number",
                VT.FLOAT: "number",
                VT.BOOL: "boolean",
            }
            key_base = (
                type_info.key_type_info.base
                if type_info.key_type_info
                else VT.STRING
            )
            key_type = key_map.get(key_base, "string")
            val_type = (
                self._resolve_type(type_info.value_type_info)
                if type_info.value_type_info
                else self.DEFAULT_TYPE
            )
            t = f"Record<{key_type}, {val_type}>"
            if type_info.is_array:
                t = self.ARRAY_TYPE_FMT.format(t)
            if type_info.is_optional or (
                self.OPTIONAL_ON_OMITEMPTY and type_info.omitempty
            ):
                t = self.OPTIONAL_TYPE_FMT.format(t)
            return t
        if type_info.base == VT.NESTED and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Type"
        elif type_info.base == VT.JSON and type_info.ref:
            t = f"{to_pascal_case(type_info.ref)}Json"
        elif type_info.base == VT.DOCUMENT:
            t = (
                self.DOCUMENT_ARRAY_TYPE
                if type_info.is_array
                else self.DOCUMENT_TYPE
            )
        else:
            t = self.TYPES.get(type_info.base, self.DEFAULT_TYPE)
        if type_info.is_array and type_info.base != VT.DOCUMENT:
            t = self.ARRAY_TYPE_FMT.format(t)
        if type_info.is_optional or (
            self.OPTIONAL_ON_OMITEMPTY and type_info.omitempty
        ):
            t = self.OPTIONAL_TYPE_FMT.format(t)
        return t

    # === MODULE ===

    def visit_module(self, node: Module, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if node.doc:
            lines.extend(_js_docblock(node.doc.splitlines()))
        lines.append('"use strict";')
        lines.append("// autogenerated by ssc-gen. DO NOT EDIT")
        return lines

    def visit_utilities(self, node: Utilities, ctx: WalkContext) -> list[str]:
        lines: list[str] = [*self._builder.imports]
        if lines:
            lines.append("")
        lines.extend(
            [
                "const UNMATCHED_TABLE_ROW = Symbol('UNMATCHED_TABLE_ROW');",
                "",
            ]
        )
        mod = node.parent
        if isinstance(mod, Module) and module_has_rest(mod):
            lines.extend(rest.REST_SHARED)
            lines.extend(FetchStrategy().rest_call_lines())
            lines.extend(AxiosStrategy().rest_call_lines())
            self._builder.require_std(
                "sscJsonProject", code=_JS_JSON_PROJECT_HELPER
            )
        lines.extend(self._render_std_section(ctx))
        return lines

    def visit_code_start_hook(
        self, node: CodeStartHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_code_end_hook(
        self, node: CodeEndHook, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_error_response(
        self, node: ErrorResponse, ctx: WalkContext
    ) -> list[str]:
        return []

    def visit_extension_call(
        self, node: ExtensionCall, ctx: WalkContext
    ) -> list[str]:
        definition = node.definition
        target = definition.targets.get("js") if definition else None
        if target is None:
            raise BuildTimeError(
                f"extension operation '{node.qualified_name}' has no 'js' target"
            )
        for item in target.imports:
            self._builder.require_import(item.value)
        for helper in target.helpers:
            self._builder.require_runtime(
                helper.name,
                code=helper.source,
                imports=[item.value for item in helper.imports],
            )
        replacements = {
            "{{in}}": ctx.prv,
            "{{out}}": ctx.nxt,
            "{{in_type}}": self._resolve_type(node.accept_type_info),
            "{{out_type}}": self._resolve_type(node.ret_type_info),
        }
        rendered = target.emit
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        return [ctx.indent + line for line in rendered.splitlines()]

    # === TYPES ===

    def visit_jsondef(self, node: JsonDef, ctx: WalkContext) -> list[str]:
        name = to_pascal_case(node.name)
        if node.is_dict:
            key_map = {
                VT.STRING: "string",
                VT.INT: "number",
                VT.FLOAT: "number",
                VT.BOOL: "boolean",
            }
            key_base = (
                node.key_type_info.base if node.key_type_info else VT.STRING
            )
            key_type = key_map.get(key_base, "string")
            val_type = (
                self._resolve_type(node.value_type_info)
                if node.value_type_info
                else self.DEFAULT_TYPE
            )
            lines = [
                "/**",
                f" * @typedef {{Record<{key_type}, {val_type}>}} {name}Json",
                " */",
            ]
            module = node.parent
            while module is not None and not isinstance(module, Module):
                module = module.parent
            if isinstance(module, Module):
                definitions = {
                    n.name: n for n in module.body if isinstance(n, JsonDef)
                }
                lines.extend(_js_json_descriptors(node, definitions))
                self._builder.require_std(
                    "sscJsonProject", code=_JS_JSON_PROJECT_HELPER
                )
            return lines

        lines = ["/**", f" * @typedef {{Object}} {name}Json"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(" */")
        module = node.parent
        while module is not None and not isinstance(module, Module):
            module = module.parent
        if isinstance(module, Module):
            definitions = {
                n.name: n for n in module.body if isinstance(n, JsonDef)
            }
            lines.extend(_js_json_descriptors(node, definitions))
            self._builder.require_std(
                "sscJsonProject", code=_JS_JSON_PROJECT_HELPER
            )
        return lines

    def visit_jsondef_field(
        self, node: JsonDefField, ctx: WalkContext
    ) -> list[str]:
        if node.ret_type_info and node.ret_type_info.skip:
            return []
        name = node.name
        type_ = self._resolve_type(node.ret_type_info)
        if node.ret_type_info.omitempty:
            return [f" * @property {{{type_}}} {name} (OMITEMPTY)"]
        return [f" * @property {{{type_}}} {name}"]

    def visit_typedef(self, node: TypeDef, ctx: WalkContext) -> list[str]:
        if node.struct_type == ST.REST:
            return []
        name = to_pascal_case(node.name)
        if node.struct_type == ST.FLAT:
            return [f"/** @typedef {{Array<string>}} {name}Type */"]
        if node.struct_type == ST.DICT:
            value_field = next(
                f for f in node.fields if to_camel_case(f.name) == "value"
            )
            value_type = self._resolve_type(value_field.ret_type_info)
            return [
                "/**",
                f" * @typedef {{Object.<string, {value_type}>}} {name}Type",
                " */",
            ]
        lines = ["/**", f" * @typedef {{Object}} {name}Type"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(" */")
        return lines

    def visit_typedef_field(
        self, node: TypeDefField, ctx: WalkContext
    ) -> list[str]:
        if node.typedef.struct_type in (ST.DICT, ST.FLAT):
            return []
        name = to_camel_case(node.name)
        if node.typedef.struct_type == ST.TABLE and name == "value":
            return []
        type_ = self._resolve_type(node.ret_type_info)
        return [f" * @property {{{type_}}} {name}"]

    # === STRUCT ===

    def visit_struct(self, node: Struct, ctx: WalkContext) -> list[str]:
        lines = list(_js_struct_header(node))
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        return lines

    def visit_struct_rest(
        self, node: StructRest, ctx: WalkContext
    ) -> list[str]:
        lines = list(_js_struct_header(node))
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        return lines

    def visit_result_variant_def(
        self, node: ResultVariantDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_result_variant_def(node)

    def visit_result_alias_def(
        self, node: ResultAliasDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_result_alias_def(node)

    def visit_matcher_list_def(
        self, node: MatcherListDef, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_matcher_list_def(node)

    def visit_init(self, node: Init, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, StructRest):
            return []
        i1, i2, i3 = ctx.indent, ctx.indent * 2, ctx.indent * 3
        struct = node.parent
        is_raw = isinstance(struct, Struct) and struct.type == ST.RAW
        if is_raw:
            lines = [
                f"{i1}constructor(document) {{",
                f"{i2}this._doc = document;",
            ]
        else:
            lines = [
                f"{i1}constructor(document) {{",
                f"{i2}if (typeof document === 'string') {{",
                f"{i3}this._doc = (new DOMParser()).parseFromString(document, 'text/html');",
                f"{i2}}} else {{",
                f"{i3}this._doc = document;",
                f"{i2}}}",
            ]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{i1}}}")
        return lines

    def visit_init_field_call(
        self, node: InitFieldCall, ctx: WalkContext
    ) -> list[str]:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        return [f"{ctx.indent}this._{name} = this._init{cap}(this._doc);"]

    def visit_init_field(self, node: InitField, ctx: WalkContext) -> list[str]:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        lines = [f"{ctx.indent}_init{cap}(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_field(self, node: Field, ctx: WalkContext) -> list[str]:
        name = to_camel_case(node.name)
        cap = name[0].upper() + name[1:]
        lines = [f"{ctx.indent}_parse{cap}(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_pre_validate(
        self, node: PreValidate, ctx: WalkContext
    ) -> list[str]:
        lines = [f"{ctx.indent}_preValidate(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_check_method(
        self, node: CheckMethod, ctx: WalkContext
    ) -> list[str]:
        method_name = to_camel_case(node.name)
        lines = [
            f"{ctx.indent}{method_name}() {{",
            f"{ctx.deeper().indent}let {ctx.var_name} = this._doc;",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        return lines

    def visit_function_def(
        self, node: FunctionDef, ctx: WalkContext
    ) -> list[str]:
        name = to_camel_case(node.name)
        inner = ctx.deeper()
        lines: list[str] = []
        if node.doc:
            lines.extend(_js_docblock(node.doc.splitlines()))
        lines.append(f"function {name}(document) {{")
        if node.is_raw:
            lines.append(f"{inner.indent}let {inner.var_name} = document;")
        else:
            lines.append(f"{inner.indent}let {inner.var_name};")
            lines.append(f"{inner.indent}if (typeof document === 'string') {{")
            lines.append(
                f"{inner.deeper().indent}{inner.var_name} = (new DOMParser()).parseFromString(document, 'text/html');"
            )
            lines.append(f"{inner.indent}}} else {{")
            lines.append(f"{inner.deeper().indent}{inner.var_name} = document;")
            lines.append(f"{inner.indent}}}")
        lines.extend(self.walk_children(node, ctx))
        lines.append("}")
        lines.append("")
        return lines

    def visit_split_doc(self, node: SplitDoc, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_splitDoc(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_key(self, node: Key, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_parseKey(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_value(self, node: Value, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_parseValue(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_table_config(
        self, node: TableConfig, ctx: WalkContext
    ) -> list[str]:
        lines = [f"{ctx.indent}_tableConfig(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_table_match_key(
        self, node: TableMatchKey, ctx: WalkContext
    ) -> list[str]:
        lines = [f"{ctx.indent}_tableMatchKey(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    def visit_table_rows(self, node: TableRows, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}_tableRows(v) {{"]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.indent}}}")
        return lines

    # === START_PARSE ===

    def visit_start_parse(
        self, node: StartParse, ctx: WalkContext
    ) -> list[str]:
        struct = node.struct
        name = to_pascal_case(struct.name)
        st = struct.type
        if st == ST.ITEM:
            ret_type = f"{name}Type"
        elif st == ST.LIST:
            ret_type = f"Array<{name}Type>"
        elif st == ST.FLAT:
            ret_type = "Array<string>"
        elif st == ST.RAW:
            has_split = any(isinstance(n, SplitDoc) for n in struct.body)
            ret_type = f"Array<{name}Type>" if has_split else f"{name}Type"
        else:
            ret_type = f"{name}Type"
        i1, i2, i3 = ctx.indent, ctx.indent * 2, ctx.indent * 3
        lines: list[str] = [
            f"{i1}/**",
            f"{i1}* @returns {{{ret_type}}}",
            f"{i1}*/",
            f"{i1}parse() {{",
        ]
        if node.use_pre_validate:
            lines.append(f"{i2}this._preValidate(this._doc);")
        if st == ST.ITEM:
            lines.append(f"{i2}return {{")
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(
                    f"{i3}{n}: this.{_js_method_name(f.name)}(this._doc),"
                )
            lines.append(f"{i2}}};")
        elif st == ST.LIST:
            lines.append(
                f"{i2}return Array.from(this._splitDoc(this._doc)).map(i => ({{"
            )
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(f"{i3}{n}: this.{_js_method_name(f.name)}(i),")
            lines.append(f"{i2}}}));")
        elif st == ST.FLAT:
            lines.append(f"{i2}let _result = [];")
            for f in node.fields:
                mname = _js_method_name(f.name)
                if f.ret_type_info.is_array:
                    lines.append(
                        f"{i2}_result = _result.concat(this.{mname}(this._doc));"
                    )
                else:
                    lines.append(f"{i2}_result.push(this.{mname}(this._doc));")
            if struct.keep_order:
                lines.append(
                    f"{i2}return [...new Map(_result.map(x=>[x,x])).keys()];"
                )
            else:
                lines.append(f"{i2}return [...new Set(_result)];")
        elif st == ST.DICT:
            lines.extend(
                [
                    f"{i2}return Array.from(this._splitDoc(this._doc)).reduce((acc, e) => {{",
                    f"{i3}acc[this._parseKey(e)] = this._parseValue(e);",
                    f"{i3}return acc;",
                    f"{i2}}}, {{}});",
                ]
            )
        elif st == ST.TABLE:
            lines.append(f"{i2}let _result = {{}};")
            lines.append(f"{i2}let _table = this._tableConfig(this._doc);")
            lines.append(f"{i2}for (let _row of this._tableRows(_table)) {{")
            for f in node.fields:
                n = to_camel_case(f.name)
                lines.append(
                    f"{i3}let _{n} = this.{_js_method_name(f.name)}(_row);"
                )
                lines.append(
                    f"{i3}if (_{n} !== UNMATCHED_TABLE_ROW "
                    f"&& !Object.prototype.hasOwnProperty.call(_result, {n!r})) "
                    f"_result[{n!r}] = _{n};"
                )
            lines.append(f"{i2}}}")
            lines.append(f"{i2}return _result;")
        elif st == ST.RAW:
            has_split = node.use_split_doc
            if has_split:
                lines.append(
                    f"{i2}return Array.from(this._splitDoc(this._doc)).map(i => ({{"
                )
                for f in node.fields:
                    n = to_camel_case(f.name)
                    lines.append(f"{i3}{n}: this.{_js_method_name(f.name)}(i),")
                lines.append(f"{i2}}}));")
            else:
                lines.append(f"{i2}return {{")
                for f in node.fields:
                    n = to_camel_case(f.name)
                    lines.append(
                        f"{i3}{n}: this.{_js_method_name(f.name)}(this._doc),"
                    )
                lines.append(f"{i2}}};")
        lines.append(f"{i1}}}")
        return lines

    # === SELECTORS ===

    def visit_css_select(self, node: CssSelect, ctx: WalkContext) -> list[str]:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.append(
                        f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.querySelector({q});"
                    )
                else:
                    lines.append(
                        f"{ctx.indent}if ({ctx.nxt} === null) {ctx.nxt} = {ctx.prv}.querySelector({q});"
                    )
            return lines
        q = repr(node.query)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.querySelector({q});"]

    def visit_css_select_all(
        self, node: CssSelectAll, ctx: WalkContext
    ) -> list[str]:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.append(
                        f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"
                    )
                else:
                    lines.append(
                        f"{ctx.indent}if ({ctx.nxt}.length === 0) {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"
                    )
            return lines
        q = repr(node.query)
        return [
            f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.querySelectorAll({q}));"
        ]

    def visit_css_remove(self, node: CssRemove, ctx: WalkContext) -> list[str]:
        q = repr(node.query)
        return [
            f"{ctx.indent}{ctx.prv}.querySelectorAll({q}).forEach(e => e.remove());",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]

    def visit_xpath_select(
        self, node: XpathSelect, ctx: WalkContext
    ) -> list[str]:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.extend(
                        [
                            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
                            f"{ctx.indent}let {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"{ctx.indent}if ({ctx.nxt} === null) {{",
                            f"{ctx.indent}    xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
                            f"{ctx.indent}    {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
                            f"{ctx.indent}}}",
                        ]
                    )
            return lines
        q = repr(node.query)
        return [
            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);",
            f"{ctx.indent}let {ctx.nxt} = xr{ctx.nxt}.singleNodeValue;",
        ]

    def visit_xpath_select_all(
        self, node: XpathSelectAll, ctx: WalkContext
    ) -> list[str]:
        if node.queries:
            lines: list[str] = []
            for i, query in enumerate(node.queries):
                q = repr(query)
                if i == 0:
                    lines.extend(
                        [
                            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
                            f"{ctx.indent}let {ctx.nxt} = []; let xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
                            f"{ctx.indent}while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
                        ]
                    )
                else:
                    lines.extend(
                        [
                            f"{ctx.indent}if ({ctx.nxt}.length === 0) {{",
                            f"{ctx.indent}    xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
                            f"{ctx.indent}    xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
                            f"{ctx.indent}    while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
                            f"{ctx.indent}}}",
                        ]
                    )
            return lines
        q = repr(node.query)
        return [
            f"{ctx.indent}let xr{ctx.nxt} = document.evaluate({q}, {ctx.prv}, null, XPathResult.ORDERED_NODE_ITERATOR_TYPE, null);",
            f"{ctx.indent}let {ctx.nxt} = []; let xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext();",
            f"{ctx.indent}while (xrn{ctx.nxt}) {{ {ctx.nxt}.push(xrn{ctx.nxt}); xrn{ctx.nxt} = xr{ctx.nxt}.iterateNext(); }}",
        ]

    def visit_xpath_remove(
        self, node: XpathRemove, ctx: WalkContext
    ) -> list[str]:
        q = repr(node.query)
        return [
            f"for (let {ctx.prv}r = document.evaluate({q}, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null), {ctx.prv}i = {ctx.prv}r.snapshotLength; {ctx.prv}i--; ) {ctx.prv}r.snapshotItem({ctx.prv}i).remove();",
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv};",
        ]

    def visit_text(self, node: Text, ctx: WalkContext) -> list[str]:
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.textContent;"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.textContent);"
        ]

    def visit_raw(self, node: Raw, ctx: WalkContext) -> list[str]:
        prop = "innerHTML" if node.mode == "inner" else "outerHTML"
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.{prop};"]
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.{prop});"]

    def visit_attr(self, node: Attr, ctx: WalkContext) -> list[str]:
        keys = node.keys
        if not node.ret_type_info.is_array:
            if len(keys) == 1:
                return [
                    f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.getAttribute({keys[0]!r});"
                ]
            kl = py_sequence_to_js_array(keys)
            return [
                f"{ctx.indent}let {ctx.nxt} = {kl}.map(k => {ctx.prv}.getAttribute(k)).filter(Boolean);"
            ]
        if len(keys) == 1:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(el => el.getAttribute({keys[0]!r}));"
            ]
        kl = py_sequence_to_js_array(keys)
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.flatMap(el => {kl}.map(k => el.getAttribute(k)).filter(Boolean));"
        ]

    # === STRING ===

    def visit_trim(self, node: Trim, ctx: WalkContext) -> list[str]:
        substr = node.substr
        if not node.ret_type_info.is_array:
            if not substr:
                return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trim();"]
            return [
                f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
                f"}})({ctx.prv}, {substr!r});",
            ]
        if not substr:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trim());"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
            "(function (str, chars) {",
            "return str.replace(new RegExp(`^[${chars}]+|[${chars}]+$`, 'g'), '');",
            f"}})(e, {substr!r})",
            ");",
        ]

    def visit_l_trim(self, node: Ltrim, ctx: WalkContext) -> list[str]:
        substr = node.substr
        if not node.ret_type_info.is_array:
            if not substr:
                return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimStart();"]
            return [
                f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
                f"}})({ctx.prv}, {substr!r});",
            ]
        if not substr:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimStart());"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(e =>",
            "(function (str, chars) {",
            "return str.replace(new RegExp(`^[${chars}]+`, 'g'), '');",
            f"}})(e, {substr!r})",
            ");",
        ]

    def visit_r_trim(self, node: Rtrim, ctx: WalkContext) -> list[str]:
        substr = node.substr
        if not node.ret_type_info.is_array:
            if not substr:
                return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.trimEnd();"]
            return [
                f"{ctx.indent}let {ctx.nxt} = (function (str, chars) {{",
                "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
                f"}})({ctx.prv}, {substr!r});",
            ]
        if not substr:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.trimEnd());"
            ]
        return [
            f"let {ctx.nxt} = {ctx.prv}.map(e =>",
            "(function (str, chars) {",
            "return str.replace(new RegExp(`[${chars}]+$`, 'g'), '');",
            f"}})(e, {substr!r})",
            ");",
        ]

    def visit_rm_prefix(self, node: RmPrefix, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_rmPrefix",
            code="function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _rmPrefix({ctx.prv}, {v});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmPrefix(s, {v}));"
        ]

    def visit_rm_suffix(self, node: RmSuffix, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_rmSuffix",
            code="function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _rmSuffix({ctx.prv}, {v});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(s, {v}));"
        ]

    def visit_rm_prefix_suffix(
        self, node: RmPrefixSuffix, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_std(
            "_rmPrefix",
            code="function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
        )
        self._builder.require_std(
            "_rmSuffix",
            code="function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
        )
        v = repr(node.substr)
        if not node.ret_type_info.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = _rmSuffix(_rmPrefix({ctx.prv}, {v}), {v});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _rmSuffix(_rmPrefix(s, {v}), {v}));"
        ]

    def visit_format(self, node: Fmt, ctx: WalkContext) -> list[str]:
        tmpl = node.template.replace("{{}}", "${_v}").replace("`", "\\`")
        js_tmpl = "`" + tmpl + "`"
        if not node.ret_type_info.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = ((_v) => {js_tmpl})({ctx.prv});"
            ]
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(_v => {js_tmpl});"]

    def visit_repl(self, node: Repl, ctx: WalkContext) -> list[str]:
        old = repr(node.old)
        new = repr(node.new)
        if not node.ret_type_info.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replaceAll({old}, {new});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replaceAll({old}, {new}));"
        ]

    def visit_repl_map(self, node: ReplMap, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_replMap",
            code=(
                "function _replMap(s, map) {\n"
                "    for (const [k, v] of Object.entries(map)) s = s.split(k).join(v);\n"
                "    return s;\n"
                "}"
            ),
        )
        rmap = repr(dict(node.replacements))
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _replMap({ctx.prv}, {rmap});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _replMap(s, {rmap}));"
        ]

    def visit_lower(self, node: Lower, ctx: WalkContext) -> list[str]:
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toLowerCase();"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toLowerCase());"
        ]

    def visit_upper(self, node: Upper, ctx: WalkContext) -> list[str]:
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.toUpperCase();"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.toUpperCase());"
        ]

    def visit_split(self, node: Split, ctx: WalkContext) -> list[str]:
        sep = repr(node.sep)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.split({sep});"]

    def visit_join(self, node: Join, ctx: WalkContext) -> list[str]:
        sep = repr(node.sep)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.join({sep});"]

    def visit_norm_space(
        self, node: NormalizeSpace, ctx: WalkContext
    ) -> list[str]:
        self._builder.require_std(
            "_normalizeText",
            code="function _normalizeText(s) { return s ? s.trim().replace(/\\s+/g, ' ') : ''; }",
        )
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _normalizeText({ctx.prv});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _normalizeText(s));"
        ]

    def visit_unescape(self, node: Unescape, ctx: WalkContext) -> list[str]:
        self._builder.require_std(
            "_unescapeText",
            code=(
                "function _unescapeText(s) {\n"
                "    const el = document.createElement('textarea');\n"
                "    el.innerHTML = s; return el.value;\n"
                "}"
            ),
        )
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = _unescapeText({ctx.prv});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _unescapeText(s));"
        ]

    # === REGEX ===

    def visit_re(self, node: Re, ctx: WalkContext) -> list[str]:
        location = self._resolve_location(node)
        src_file = self._resolve_source_file(node)
        span = node.span
        src_line = span.start.line if span else 0
        src_col = span.start.column if span else 0
        loc_str = f" at {location}" if location else ""
        msg = (
            f"{src_file}:{src_line}:{src_col} "
            f"re-match failed{loc_str} pattern={node.pattern}"
        )
        self._builder.require_std(
            "_stdReSearch",
            code=(
                "class SscRegexError extends Error {}\n"
                "function _stdReSearch(pattern, value, msg = '') {\n"
                "    const m = value.match(pattern);\n"
                "    if (m === null) throw new SscRegexError(msg || 'ssc-gen re-match failed');\n"
                "    return m[1];\n"
                "}"
            ),
        )
        rx = _py_re_to_js_re(node.pattern)
        msg_literal = _js_literal(msg)
        if not node.ret_type_info.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = _stdReSearch({rx}, {ctx.prv}, {msg_literal});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => _stdReSearch({rx}, s, {msg_literal}));"
        ]

    def visit_re_all(self, node: ReAll, ctx: WalkContext) -> list[str]:
        rx_g = _py_re_to_js_re(node.pattern, global_flag=True)
        return [
            f"{ctx.indent}let {ctx.nxt} = Array.from({ctx.prv}.matchAll({rx_g}), m => m[1]);"
        ]

    def visit_re_sub(self, node: ReSub, ctx: WalkContext) -> list[str]:
        rx_g = _py_re_to_js_re(node.pattern, global_flag=True)
        repl = repr(node.repl)
        if not node.ret_type_info.is_array:
            return [
                f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.replace({rx_g}, {repl});"
            ]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => s.replace({rx_g}, {repl}));"
        ]

    # === ARRAY ===

    def visit_index(self, node: Index, ctx: WalkContext) -> list[str]:
        i = node.i
        i_expr = f"{ctx.prv}.length - {i}" if i < 0 else str(i)
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}[{i_expr}];"]

    def visit_slice(self, node: Slice, ctx: WalkContext) -> list[str]:
        start = node.start
        end = node.end
        start_expr = f"{ctx.prv}.length - {start}" if start < 0 else str(start)
        end_expr = f"{ctx.prv}.length - {end}" if end < 0 else str(end)
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.slice({start_expr}, {end_expr});"
        ]

    def visit_len(self, node: Len, ctx: WalkContext) -> list[str]:
        return [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.length;"]

    def visit_unique(self, node: Unique, ctx: WalkContext) -> list[str]:
        if node.keep_order:
            return [
                f"{ctx.indent}let {ctx.nxt} = [...new Map({ctx.prv}.map(x=>[x,x])).keys()];"
            ]
        return [f"{ctx.indent}let {ctx.nxt} = [...new Set({ctx.prv})];"]

    # === CASTS ===

    def visit_to_int(self, node: ToInt, ctx: WalkContext) -> list[str]:
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = parseInt({ctx.prv}, 10);"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseInt(s, 10));"
        ]

    def visit_to_float(self, node: ToFloat, ctx: WalkContext) -> list[str]:
        if not node.ret_type_info.is_array:
            return [f"{ctx.indent}let {ctx.nxt} = parseFloat({ctx.prv});"]
        return [
            f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.map(s => parseFloat(s));"
        ]

    def visit_to_bool(self, node: ToBool, ctx: WalkContext) -> list[str]:
        return [f"{ctx.indent}let {ctx.nxt} = Boolean({ctx.prv});"]

    def visit_jsonify(self, node: Jsonify, ctx: WalkContext) -> list[str]:
        if node.path:
            parts = jsonify_path_to_segments(node.path)
            path = "".join(f"[{p}]" for p in parts)
            raw_expr = f"JSON.parse({ctx.prv}){path}"
        else:
            raw_expr = f"JSON.parse({ctx.prv})"

        json_def = resolve_json_def(node, node.schema_name)
        if json_def:
            self._builder.require_std(
                "sscJsonProject", code=_JS_JSON_PROJECT_HELPER
            )
            desc_name = json_descriptor_var_name(node.schema_name)
            return [
                f"{ctx.indent}let {ctx.nxt} = sscJsonProject({raw_expr}, {desc_name});"
            ]

        return [f"{ctx.indent}let {ctx.nxt} = {raw_expr};"]

    def visit_nested(self, node: Nested, ctx: WalkContext) -> list[str]:
        cls = to_pascal_case(node.struct_name)
        return [f"{ctx.indent}let {ctx.nxt} = new {cls}({ctx.prv}).parse();"]

    # === CONTROL ===

    def visit_self(self, node: Self, ctx: WalkContext) -> list[str]:
        name = to_camel_case(node.name)
        return [f"{ctx.indent}let {ctx.nxt} = this._{name};"]

    def visit_return(self, node: Return, ctx: WalkContext) -> list[str]:
        if isinstance(node.parent, PreValidate):
            return [f"{ctx.indent}return;"]
        body = getattr(node.parent, "body", None) or []
        try:
            idx = body.index(node)
        except ValueError:
            idx = -1
        if idx > 0 and isinstance(body[idx - 1], Fallback):
            return []
        return [f"{ctx.indent}return {ctx.prv};"]

    def visit_fallback(self, node: Fallback, ctx: WalkContext) -> list[str]:
        inner_ctx = ctx.deeper()
        inner_indent = inner_ctx.indent
        last_idx = ctx.index + len(node.body)
        last_var = (
            ctx.var_name if last_idx == 0 else f"{ctx.var_name}{last_idx}"
        )
        val = _js_literal(node.value)
        lines = [f"{ctx.indent}try {{"]
        lines.extend(self.walk_pipeline(node.body, inner_ctx))
        lines.extend(
            [
                f"{inner_indent}return {last_var};",
                f"{ctx.indent}}} catch (e) {{",
                f"{inner_indent}return {val};",
                f"{ctx.indent}}}",
            ]
        )
        return lines

    # === PREDICATE CONTAINERS ===

    def visit_filter(self, node: Filter, ctx: WalkContext) -> list[str]:
        lines = [f"{ctx.indent}let {ctx.nxt} = {ctx.prv}.filter(i => ("]
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.deeper().indent}));")
        return lines

    def _resolve_location(self, node) -> str:
        """Walk parent chain for language-agnostic ``{Struct}.{field}``.

        Mirrors the Python visitor's resolver: returns ``@pre-validate``
        marker when the assert is inside ``pre-validate { ... }``.
        Uses raw KDL names — message format is intentionally
        language-agnostic so consumers can map errors back to source
        ``.kdl`` files.
        """
        struct_name = ""
        field_part = ""
        current = node.parent
        while current is not None:
            if isinstance(current, PreValidate) and not field_part:
                field_part = "@pre-validate"
            elif isinstance(current, (Field, Key, Value)) and not field_part:
                field_part = getattr(current, "name", "") or (
                    "value" if isinstance(current, Value) else "key"
                )
            if isinstance(current, StructBase):
                struct_name = to_pascal_case(current.name)
                break
            current = current.parent
        if field_part:
            return f"{struct_name}.{field_part}" if struct_name else field_part
        return struct_name

    def _resolve_assert_location(self, node: Assert) -> str:
        """Back-compat shim; delegates to :meth:`_resolve_location`."""
        return self._resolve_location(node)

    def _resolve_source_file(self, node) -> str:
        """Walk parent chain to Module; return ``Module.source_file`` basename."""
        current = node
        while current is not None:
            if isinstance(current, Module):
                return current.source_file
            current = current.parent
        return ""

    def visit_assert(self, node: Assert, ctx: WalkContext) -> list[str]:
        location = self._resolve_location(node)
        if node.message:
            msg = node.message
        else:
            loc_str = f" at {location}" if location else ""
            src_file = self._resolve_source_file(node)
            span = node.span
            src_line = span.start.line if span else 0
            src_col = span.start.column if span else 0
            msg = f"{src_file}:{src_line}:{src_col} assertion failed{loc_str}"
        self._builder.require_std(
            "_stdAssert",
            code=(
                "class SscAssertionError extends Error {}\n"
                "function _stdAssert(cond, msg = '') {\n"
                "    if (!cond) throw new SscAssertionError(msg || 'ssc-gen assertion failed');\n"
                "}"
            ),
        )
        msg_literal = _js_literal(msg)
        lines: list[str] = []
        if isinstance(node.parent, PreValidate):
            # pre-validate asserts operate on the incoming document (v);
            # no local var binding.
            setattr(node, "_local_name", "v")
            lines.append(f"{ctx.indent}_stdAssert(")
        else:
            local = f"i{ctx.prv}"
            setattr(node, "_local_name", local)
            lines.extend(
                [
                    f"{ctx.indent}let {local} = {ctx.prv};",
                    f"{ctx.indent}_stdAssert(",
                ]
            )
        # condition expression — wrapped in parens to disambiguate from
        # the trailing msg argument.
        lines.append(f"{ctx.deeper().indent}(")
        lines.extend(self.walk_children(node, ctx))
        lines.append(f"{ctx.deeper().indent}),")
        lines.append(f"{ctx.deeper().indent}{msg_literal},")
        lines.append(f"{ctx.indent});")
        if not isinstance(node.parent, PreValidate):
            lines.append(f"{ctx.indent}let {ctx.nxt} = {ctx.prv};")
        return lines

    def visit_match(self, node: Match, ctx: WalkContext) -> list[str]:
        local = f"i{ctx.prv}"
        setattr(node, "_local_name", local)
        lines = [
            f"{ctx.indent}let {local} = this._tableMatchKey({ctx.prv});",
            f"{ctx.indent}if (!(",
        ]
        lines.extend(self.walk_children(node, ctx))
        lines.extend(
            [
                f"{ctx.indent})) {{ return UNMATCHED_TABLE_ROW; }}",
                f"{ctx.indent}let {ctx.nxt} = this._parseValue({ctx.prv});",
            ]
        )
        return lines

    # === LOGIC ===

    def visit_logic_and(self, node: LogicAnd, ctx: WalkContext) -> list[str]:
        lines = [_logic_prefix("&&", ctx)]
        lines.extend(self.walk_children(node, ctx))
        lines.append(ctx.indent + ")")
        return lines

    def visit_logic_or(self, node: LogicOr, ctx: WalkContext) -> list[str]:
        lines = [_logic_prefix("||", ctx)]
        lines.extend(self.walk_children(node, ctx))
        lines.append(ctx.indent + ")")
        return lines

    def visit_logic_not(self, node: LogicNot, ctx: WalkContext) -> list[str]:
        lines: list[str] = []
        if ctx.index == 0:
            lines.append(f"{ctx.indent}!(")
        else:
            lines.append(f"{ctx.indent}&& !(")
        lines.extend(self.walk_children(node, ctx))
        lines.append(ctx.indent + ")")
        return lines

    # === PREDICATES ===

    def visit_predicate_css(self, node: PredCss, ctx: WalkContext) -> list[str]:
        q = repr(node.query)
        target = _pred_target(node, ctx)
        cond = f"{target}.querySelector({q}) !== null"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_xpath(
        self, node: PredXpath, ctx: WalkContext
    ) -> list[str]:
        q = repr(node.query)
        target = _pred_target(node, ctx)
        cond = (
            f"document.evaluate({q}, {target}, null, "
            f"XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue "
            f"!== null"
        )
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_has_attr(
        self, node: PredHasAttr, ctx: WalkContext
    ) -> list[str]:
        keys = node.attrs
        target = _pred_attr_target(node, ctx)
        if len(keys) == 1:
            cond = f"{target}.hasAttribute({keys[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(keys)}.some(k => {target}.hasAttribute(k))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_attr_eq(
        self, node: PredAttrEq, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.getAttribute({name!r}) === {values[0]!r}"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.getAttribute({name!r}) === v)"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_attr_ne(
        self, node: PredAttrNe, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.getAttribute({name!r}) !== {values[0]!r}"
        else:
            cond = f"{py_sequence_to_js_array(values)}.every(v => {target}.getAttribute({name!r}) !== v)"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_attr_starts(
        self, node: PredAttrStarts, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"({target}.getAttribute({name!r}) ?? '').startsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').startsWith(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_attr_ends(
        self, node: PredAttrEnds, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"({target}.getAttribute({name!r}) ?? '').endsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').endsWith(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_attr_contains(
        self, node: PredAttrContains, ctx: WalkContext
    ) -> list[str]:
        name, values = node.name, node.values
        target = _pred_attr_target(node, ctx)
        if len(values) == 1:
            cond = f"({target}.getAttribute({name!r}) ?? '').includes({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => ({target}.getAttribute({name!r}) ?? '').includes(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_attr_re(
        self, node: PredAttrRe, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_attr_target(node, ctx)
        cond = f"{rx}.test({target}.getAttribute({node.name!r}) ?? '')"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_text_contains(
        self, node: PredTextContains, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_text_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.includes({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_text_starts(
        self, node: PredTextStarts, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_text_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.startsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_text_ends(
        self, node: PredTextEnds, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_text_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.endsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_text_re(
        self, node: PredTextRe, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_text_target(node, ctx)
        cond = f"{rx}.test({target})"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_contains(
        self, node: PredContains, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.includes({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.includes(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_eq(self, node: PredEq, ctx: WalkContext) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if isinstance(values[0], int):
            cond = f"{target}.length === {values[0]}"
        elif len(values) == 1:
            cond = f"{target} === {values[0]!r}"
        else:
            cond = (
                f"{py_sequence_to_js_array(values)}.some(v => {target} === v)"
            )
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_ne(self, node: PredNe, ctx: WalkContext) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if isinstance(values[0], int):
            cond = f"{target}.length !== {values[0]}"
        elif len(values) == 1:
            cond = f"{target} !== {values[0]!r}"
        else:
            cond = (
                f"{py_sequence_to_js_array(values)}.every(v => {target} !== v)"
            )
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_starts(
        self, node: PredStarts, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.startsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.startsWith(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_ends(
        self, node: PredEnds, ctx: WalkContext
    ) -> list[str]:
        values = node.values
        target = _pred_target(node, ctx)
        if len(values) == 1:
            cond = f"{target}.endsWith({values[0]!r})"
        else:
            cond = f"{py_sequence_to_js_array(values)}.some(v => {target}.endsWith(v))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_count_eq(
        self, node: PredCountEq, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{target}.length === {node.value}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_count_gt(
        self, node: PredCountGt, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{target}.length > {node.value}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_count_lt(
        self, node: PredCountLt, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{target}.length < {node.value}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_count_ne(
        self, node: PredCountNe, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{target}.length !== {node.value}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_count_ge(
        self, node: PredCountGe, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{target}.length >= {node.value}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_count_le(
        self, node: PredCountLe, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{target}.length <= {node.value}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_pred_count_range(
        self, node: PredCountRange, ctx: WalkContext
    ) -> list[str]:
        target = _pred_target(node, ctx)
        cond = f"{node.start} < {target}.length && {target}.length < {node.end}"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_re(self, node: PredRe, ctx: WalkContext) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_target(node, ctx)
        cond = f"{rx}.test({target})"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_re_all(
        self, node: PredReAll, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_target(node, ctx)
        cond = f"{target}.every(j => {rx}.test(j))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    def visit_predicate_re_any(
        self, node: PredReAny, ctx: WalkContext
    ) -> list[str]:
        rx = _py_re_to_js_re(node.pattern)
        target = _pred_target(node, ctx)
        cond = f"{target}.some(j => {rx}.test(j))"
        prefix = "" if ctx.index == 0 else "&& "
        return [f"{ctx.indent}{prefix}{cond}"]

    # === REST / FETCH ===

    def visit_method_rest(
        self, node: MethodRest, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_method_rest(node, ctx, self._http)

    def visit_method_fetch(
        self, node: MethodFetch, ctx: WalkContext
    ) -> list[str]:
        return rest.emit_method_fetch(node, ctx, self._http)
