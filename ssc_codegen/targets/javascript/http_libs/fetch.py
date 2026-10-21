"""Native fetch HTTP transport strategy for JavaScript code generation."""

from __future__ import annotations

import inspect

from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy

_FETCH_REST_RUNTIME: list[str] = [
    *inspect.cleandoc(
        """
        async function sscRestCall(client, _matchers, method, url, _valueFn, _dslOpts = {}, opts = {}) {
            let _resp;
            try {
                const _req = sscPrepareReq(url, _dslOpts, opts, false);
                _req._kw.method = method;
                _resp = await client(_req.url, _req._kw);
            } catch (e) {
                return { isOk: false, status: 0, headers: {}, value: null, cause: String(e) };
            }
            const _status = _resp.status;
            const _headers = Object.fromEntries([..._resp.headers.entries()]);
            let _body = null;
            try { _body = await _resp.json(); } catch (e) {}
            const _err = sscDispatchErr(_matchers, _status, _headers, _body);
            if (_err !== null) return _err;
            const _value = _valueFn === null ? _body : _valueFn(_body);
            return { isOk: true, status: _status, headers: _headers, value: _value };
        }
        """
    ).splitlines(),
    "",
]

_FETCH_HTML_RUNTIME: list[str] = [
    *inspect.cleandoc(
        """
        async function sscFetch(client, method, url, _dslOpts = {}, opts = {}) {
            const _req = sscPrepareReq(url, _dslOpts, opts, false);
            _req._kw.method = method;
            const _resp = await client(_req.url, _req._kw);
            if (!_resp.ok) throw new Error(`HTTP ${_resp.status}`);
            if (_dslOpts && _dslOpts.responsePath) {
                let _body = await _resp.json();
                for (const _seg of _dslOpts.responsePath.split('.')) {
                    _body = _body[_seg];
                }
                if (_dslOpts.responseJoin) {
                    _body = _body.join(_dslOpts.responseJoin);
                }
                return _body;
            }
            return await _resp.text();
        }
        """
    ).splitlines(),
    "",
]


class FetchStrategy(JsHttpLibStrategy):
    """HTTP client strategy utilizing the standard browser/Node.js `fetch()` API."""

    fn_name = "sscRestCall"
    fetch_fn_name = "sscFetch"

    def rest_call_lines(self) -> list[str]:
        """Generate `sscRestCall` helper source using standard `fetch()`."""
        return list(_FETCH_REST_RUNTIME)

    def fetch_call_lines(self) -> list[str]:
        """Generate `sscFetch` helper source using standard `fetch()`."""
        return list(_FETCH_HTML_RUNTIME)
