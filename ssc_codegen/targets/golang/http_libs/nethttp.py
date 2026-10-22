"""Standard library net/http transport strategy for Go code generation."""

from __future__ import annotations

import inspect

from ssc_codegen.targets.golang.http_libs.base import GoHttpLibStrategy


class NetHttpStrategy(GoHttpLibStrategy):
    """Standard library `net/http` client transport strategy for Go."""

    client_type = "*http.Client"
    import_path = "net/http"

    def rest_runtime_lines(self) -> list[str]:
        """Return the standard `net/http` REST runtime execution function."""
        return _NETHTTP_REST_RUNTIME

    @property
    def rest_imports(self) -> list[str]:
        """Return the list of standard packages required by `_NETHTTP_REST_RUNTIME`."""
        return [
            '"context"',
            '"encoding/json"',
            '"fmt"',
            '"github.com/tidwall/gjson"',
            '"io"',
            '"net/http"',
            '"strings"',
        ]


_NETHTTP_REST_RUNTIME: list[str] = inspect.cleandoc(
    """
    func sscDoRequest(ctx context.Context, client *http.Client, method, reqURL string, dslOpts *sscReqOpts, opts ...sscReqOpt) (*http.Response, []byte, error) {
    	req, err := http.NewRequestWithContext(ctx, method, reqURL, nil)
    	if err != nil {
    		return nil, nil, err
    	}
    	_opts := dslOpts
    	if _opts == nil {
    		_opts = &sscReqOpts{}
    	}
    	for _, o := range opts {
    		o(_opts)
    	}
    	if len(_opts.Headers) > 0 {
    		for k, vs := range _opts.Headers {
    			for _, v := range vs {
    				req.Header.Add(k, v)
    			}
    		}
    	}
    	if len(_opts.Cookies) > 0 {
    		for name, vs := range _opts.Cookies {
    			for _, v := range vs {
    				req.AddCookie(&http.Cookie{Name: name, Value: v})
    			}
    		}
    	}
    	if _opts.Body != "" {
    		req.Body = io.NopCloser(strings.NewReader(_opts.Body))
    	}
    	resp, err := client.Do(req)
    	if err != nil {
    		return nil, nil, err
    	}
    	defer resp.Body.Close()
    	body, err := io.ReadAll(resp.Body)
    	if err != nil {
    		return resp, nil, err
    	}
    	return resp, body, nil
    }

    func sscExtractJSONSlice(raw []byte, responsePath string) []byte {
    	if responsePath != "" {
    		return []byte(gjson.GetBytes(raw, responsePath).Raw)
    	}
    	return raw
    }

    func sscRestCall(client *http.Client, matchers []sscErrMatcher, method, url string, dslOpts *sscReqOpts, opts ...sscReqOpt) ([]byte, error) {
    	resp, bodyBytes, err := sscDoRequest(context.Background(), client, method, url, dslOpts, opts...)
    	if err != nil {
    		return nil, &TransportErr{Cause: err.Error()}
    	}
    	headers := sscHeaders{}
    	for k, vs := range resp.Header {
    		headers[k] = vs
    	}
    	if errObj := sscDispatchErr(matchers, resp.StatusCode, headers, bodyBytes); errObj != nil {
    		return nil, errObj
    	}
    	if resp.StatusCode >= 400 {
    		return nil, &UnknownErr{Status: resp.StatusCode, Body: string(bodyBytes)}
    	}
    	return bodyBytes, nil
    }

    func sscRestCallValue[T any](client *http.Client, matchers []sscErrMatcher, method, url, responsePath string, dslOpts *sscReqOpts, opts ...sscReqOpt) (*T, error) {
    	body, err := sscRestCall(client, matchers, method, url, dslOpts, opts...)
    	if err != nil {
    		return nil, err
    	}
    	body = sscExtractJSONSlice(body, responsePath)
    	var val T
    	if perr := json.Unmarshal(body, &val); perr != nil {
    		return nil, fmt.Errorf("ssc-gen: parse %T: %w", val, perr)
    	}
    	return &val, nil
    }

    func sscRestCallSlice[T any](client *http.Client, matchers []sscErrMatcher, method, url, responsePath string, dslOpts *sscReqOpts, opts ...sscReqOpt) ([]T, error) {
    	body, err := sscRestCall(client, matchers, method, url, dslOpts, opts...)
    	if err != nil {
    		return nil, err
    	}
    	body = sscExtractJSONSlice(body, responsePath)
    	var val []T
    	if perr := json.Unmarshal(body, &val); perr != nil {
    		return nil, fmt.Errorf("ssc-gen: parse %T: %w", val, perr)
    	}
    	return val, nil
    }

    func sscRestCallVoid(client *http.Client, matchers []sscErrMatcher, method, url string, dslOpts *sscReqOpts, opts ...sscReqOpt) (struct{}, error) {
    	_, err := sscRestCall(client, matchers, method, url, dslOpts, opts...)
    	if err != nil {
    		return struct{}{}, err
    	}
    	return struct{}{}, nil
    }

    func sscFetchHTML(ctx context.Context, client *http.Client, structName, method, url, responsePath, responseJoin string, dslOpts *sscReqOpts, opts ...sscReqOpt) (string, error) {
    	resp, body, err := sscDoRequest(ctx, client, method, url, dslOpts, opts...)
    	if err != nil {
    		return "", err
    	}
    	if resp.StatusCode >= 400 {
    		return "", fmt.Errorf("%s: HTTP %d: %s", structName, resp.StatusCode, string(body))
    	}
    	if responsePath != "" {
    		if responseJoin != "" {
    			_parts := gjson.GetBytes(body, responsePath).Array()
    			_partsStrs := make([]string, len(_parts))
    			for _i, _p := range _parts {
    				_partsStrs[_i] = _p.String()
    			}
    			return strings.Join(_partsStrs, responseJoin), nil
    		}
    		return gjson.GetBytes(body, responsePath).String(), nil
    	}
    	return string(body), nil
    }
    """
).splitlines()
