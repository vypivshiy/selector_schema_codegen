"""JS base runtime utility lines."""

JS_BASE_UTILITY_LINES: list[str] = [
    "const UNMATCHED_TABLE_ROW = Symbol('UNMATCHED_TABLE_ROW');",
    "",
    "function _replMap(s, map) {",
    "    for (const [k, v] of Object.entries(map)) s = s.split(k).join(v);",
    "    return s;",
    "}",
    "",
    "function _normalizeText(s) { return s ? s.trim().replace(/\\s+/g, ' ') : ''; }",
    "",
    "function _unescapeText(s) {",
    "    const el = document.createElement('textarea');",
    "    el.innerHTML = s; return el.value;",
    "}",
    "",
    "function _rmPrefix(s, p) { return s.startsWith(p) ? s.slice(p.length) : s; }",
    "function _rmSuffix(s, p) { return s.endsWith(p) ? s.slice(0, -p.length) : s; }",
]


def js_base_utility_lines() -> list[str]:
    return list(JS_BASE_UTILITY_LINES)
