from __future__ import annotations

from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy


class AxiosStrategy(JsHttpLibStrategy):
    """Axios client strategy."""

    fn_name = "sscRestCallAxios"

    def rest_call_lines(self) -> list[str]:
        return [
            "async function sscRestCallAxios(client, _matchers, method, url, _valueFn, _opts) {",
            "    let _resp;",
            "    try {",
            "        _opts.method = method;",
            "        _opts.url = url;",
            "        _opts.validateStatus = () => true;",
            "        _resp = await client.request(_opts);",
            "    } catch (e) {",
            "        return { isOk: false, status: 0, headers: {}, value: null, cause: String(e) };",
            "    }",
            "    const _status = _resp.status;",
            "    const _headers = {};",
            "    for (const [k, v] of Object.entries(_resp.headers || {})) "
            "{ _headers[String(k).toLowerCase()] = String(v); }",
            "    const _body = _resp.data;",
            "    const _err = sscDispatchErr(_matchers, _status, _headers, _body);",
            "    if (_err !== null) return _err;",
            "    const _value = _valueFn === null ? _body : _valueFn(_body);",
            "    return { isOk: true, status: _status, headers: _headers, value: _value };",
            "}",
            "",
        ]
