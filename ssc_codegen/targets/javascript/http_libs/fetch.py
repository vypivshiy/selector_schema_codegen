from __future__ import annotations

from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy


class FetchStrategy(JsHttpLibStrategy):
    """Native ``fetch()`` strategy."""

    fn_name = "sscRestCall"

    def rest_call_lines(self) -> list[str]:
        return [
            "async function sscRestCall(client, _matchers, method, url, _valueFn, _opts) {",
            "    let _resp;",
            "    try {",
            "        _opts.method = method;",
            "        _resp = await client(url, _opts);",
            "    } catch (e) {",
            "        return { isOk: false, status: 0, headers: {}, value: null, cause: String(e) };",
            "    }",
            "    const _status = _resp.status;",
            "    const _headers = Object.fromEntries([..._resp.headers.entries()]);",
            "    let _body = null;",
            "    try { _body = await _resp.json(); } catch (e) {}",
            "    const _err = sscDispatchErr(_matchers, _status, _headers, _body);",
            "    if (_err !== null) return _err;",
            "    const _value = _valueFn === null ? _body : _valueFn(_body);",
            "    return { isOk: true, status: _status, headers: _headers, value: _value };",
            "}",
            "",
        ]
