"""Axios HTTP transport strategy for JavaScript code generation."""

from __future__ import annotations

import inspect

from ssc_codegen.targets.javascript.http_libs.base import JsHttpLibStrategy

_AXIOS_REST_RUNTIME: list[str] = [
    *inspect.cleandoc(
        """
        async function sscRestCallAxios(client, _matchers, method, url, _valueFn, _dslOpts = {}, opts = {}) {
            let _resp;
            try {
                const _req = sscPrepareReq(url, _dslOpts, opts, true);
                _req._kw.method = method;
                _req._kw.url = _req.url;
                _req._kw.validateStatus = () => true;
                _resp = await client.request(_req._kw);
            } catch (e) {
                return { isOk: false, status: 0, headers: {}, value: null, cause: String(e) };
            }
            const _status = _resp.status;
            const _headers = {};
            for (const [k, v] of Object.entries(_resp.headers || {})) { _headers[String(k).toLowerCase()] = String(v); }
            const _body = _resp.data;
            const _err = sscDispatchErr(_matchers, _status, _headers, _body);
            if (_err !== null) return _err;
            const _value = _valueFn === null ? _body : _valueFn(_body);
            return { isOk: true, status: _status, headers: _headers, value: _value };
        }
        """
    ).splitlines(),
    "",
]

_AXIOS_HTML_RUNTIME: list[str] = [
    *inspect.cleandoc(
        """
        async function sscFetchAxios(client, method, url, _dslOpts = {}, opts = {}) {
            const _req = sscPrepareReq(url, _dslOpts, opts, true);
            const _resp = await client.request({ method, url: _req.url, ..._req._kw });
            let _body = _resp.data;
            if (_dslOpts && _dslOpts.responsePath) {
                for (const _seg of _dslOpts.responsePath.split('.')) {
                    _body = _body[_seg];
                }
                if (_dslOpts.responseJoin) {
                    _body = _body.join(_dslOpts.responseJoin);
                }
            }
            return _body;
        }
        """
    ).splitlines(),
    "",
]


class AxiosStrategy(JsHttpLibStrategy):
    """HTTP client strategy utilizing the `axios` library."""

    fn_name = "sscRestCallAxios"
    fetch_fn_name = "sscFetchAxios"

    def rest_call_lines(self) -> list[str]:
        """Generate `sscRestCallAxios` helper source using `axios.request()`.

        Returns:
            list[str]: JavaScript source lines defining `sscRestCallAxios`.
        """
        return list(_AXIOS_REST_RUNTIME)

    def fetch_call_lines(self) -> list[str]:
        """Generate `sscFetchAxios` helper source using `axios.request()`.

        Returns:
            list[str]: JavaScript source lines defining `sscFetchAxios`.
        """
        return list(_AXIOS_HTML_RUNTIME)
