"""net/http strategy for Go REST codegen."""

from __future__ import annotations

from ssc_codegen.targets.golang.http_libs.base import GoHttpLibStrategy


class NetHttpStrategy(GoHttpLibStrategy):
    """Standard library net/http client strategy."""

    client_type = "*http.Client"
    import_path = "net/http"

    def rest_runtime_lines(self) -> list[str]:
        return _NETHTTP_REST_RUNTIME

    @property
    def rest_imports(self) -> list[str]:
        return [
            '"fmt"',
            '"io"',
            '"net/http"',
            '"strings"',
        ]


_NETHTTP_REST_RUNTIME: list[str] = [
    "func sscRestCall(client *http.Client, matchers []sscErrMatcher, method, url string, opts *sscReqOpts) ([]byte, error) {",
    "\treq, err := http.NewRequest(method, url, nil)",
    "\tif err != nil {",
    "\t\treturn nil, &TransportErr{Cause: err.Error()}",
    "\t}",
    "\tif opts != nil {",
    "\t\tif len(opts.Headers) > 0 {",
    "\t\t\tfor k, vs := range opts.Headers {",
    "\t\t\t\tfor _, v := range vs {",
    "\t\t\t\t\treq.Header.Add(k, v)",
    "\t\t\t\t}",
    "\t\t\t}",
    "\t\t}",
    "\t\tif len(opts.Cookies) > 0 {",
    "\t\t\tfor name, vs := range opts.Cookies {",
    "\t\t\t\tfor _, v := range vs {",
    "\t\t\t\t\treq.AddCookie(&http.Cookie{Name: name, Value: v})",
    "\t\t\t\t}",
    "\t\t\t}",
    "\t\t}",
    '\t\tif opts.Body != "" {',
    "\t\t\treq.Body = io.NopCloser(strings.NewReader(opts.Body))",
    "\t\t}",
    "\t}",
    "\tresp, err := client.Do(req)",
    "\tif err != nil {",
    "\t\treturn nil, &TransportErr{Cause: err.Error()}",
    "\t}",
    "\tdefer resp.Body.Close()",
    "\tbodyBytes, _ := io.ReadAll(resp.Body)",
    "\theaders := sscHeaders{}",
    "\tfor k, vs := range resp.Header {",
    "\t\theaders[k] = vs",
    "\t}",
    "\tif errObj := sscDispatchErr(matchers, resp.StatusCode, headers, bodyBytes); errObj != nil {",
    "\t\treturn nil, errObj",
    "\t}",
    "\tif resp.StatusCode >= 400 {",
    "\t\treturn nil, &UnknownErr{Status: resp.StatusCode, Body: string(bodyBytes)}",
    "\t}",
    "\treturn bodyBytes, nil",
    "}",
    "",
]
