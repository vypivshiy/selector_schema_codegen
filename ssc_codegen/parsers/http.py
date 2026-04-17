import json
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs


def parse_query_params(url: str) -> Dict[str, Any]:
    """Parse query parameters from URL into a dict."""
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    return {}


def parse_multipart(body: str, boundary: str) -> Dict[str, str]:
    """Parse multipart/form-data body into a dict of field names to values (text fields only)."""
    parts = body.split(f'--{boundary}')
    data = {}
    for part in parts:
        part = part.strip()
        if part and part != '--':
            lines = part.splitlines()
            headers_part = {}
            i = 0
            # Skip leading empty lines
            while i < len(lines) and not lines[i].strip():
                i += 1
            # Parse headers
            while i < len(lines) and lines[i].strip():
                if ':' in lines[i]:
                    k, v = lines[i].split(':', 1)
                    headers_part[k.strip()] = v.strip()
                i += 1
            # Skip empty line after headers
            if i < len(lines) and not lines[i].strip():
                i += 1
            content = '\n'.join(lines[i:]).strip()
            # Extract name from Content-Disposition
            cd = headers_part.get('Content-Disposition', '')
            if 'name=' in cd:
                name_part = cd.split('name=')[1]
                name = name_part.split(';')[0].strip('"')
                data[name] = content
    return data


def parse_cookies(cookie_header: str) -> Dict[str, str]:
    """Parse a Cookie header string into a dict of name-value pairs."""
    cookies = {}
    for pair in cookie_header.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies[name.strip()] = value.strip()
    return cookies


def parse_http_to_httpx_kwargs(raw_http: str) -> Dict[str, Any]:
    """
    Parse a raw HTTP request string and convert it to httpx kwargs.

    Args:
        raw_http: The raw HTTP request as a string.

    Returns:
        Dict containing httpx method kwargs: url, method, headers, json/data, cookies, etc.

    Raises:
        ValueError: If the request is invalid or missing required parts.
    """
    lines = raw_http.strip().splitlines()
    if not lines:
        raise ValueError("Empty HTTP request")

    # Parse request line
    request_line = lines[0].split()
    if len(request_line) < 3:
        raise ValueError("Invalid request line")
    method = request_line[0].upper()
    path = request_line[1]
    # version = request_line[2]  # Not used

    # Parse headers
    headers = {}
    i = 1
    while i < len(lines) and lines[i].strip():
        if ':' in lines[i]:
            key, value = lines[i].split(':', 1)
            headers[key.strip()] = value.strip()
        else:
            raise ValueError(f"Invalid header line: {lines[i]}")
        i += 1

    # Skip empty line if present
    if i < len(lines) and not lines[i].strip():
        i += 1

    # Parse body
    body = '\n'.join(lines[i:]) if i < len(lines) else ''

    # Construct URL
    host = headers.get('Host')
    if host:
        url = f"https://{host}{path}"
    else:
        url = path  # Fallback to path only

    # Parse query params from URL
    params = parse_query_params(url)

    # Determine data type
    json_data = None
    data = None
    if body:
        content_type_full = headers.get('Content-Type', '')
        content_type = content_type_full.lower()
        if 'multipart/form-data' in content_type:
            # Extract boundary
            if 'boundary=' in content_type_full:
                boundary = content_type_full.split('boundary=')[1].split(';')[0].strip()
                form_data = parse_multipart(body, boundary)
                data = form_data  # as dict
            else:
                data = body  # Fallback
        elif 'application/x-www-form-urlencoded' in content_type:
            form_data = parse_qs(body, keep_blank_values=True)
            data = {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}
        elif 'application/json' in content_type:
            try:
                json_data = json.loads(body)
            except json.JSONDecodeError:
                data = body  # Fallback to raw data
        else:
            data = body

    # Parse cookies
    cookies = None
    if 'Cookie' in headers:
        cookies = parse_cookies(headers['Cookie'])
        del headers['Cookie']

    # Host is auto-set by HTTP libraries from the URL
    headers.pop('Host', None)

    # Build kwargs
    kwargs = {
        'method': method,
        'url': url,
    }

    if headers:
        kwargs['headers'] = headers

    if json_data is not None:
        kwargs['json'] = json_data
    elif data:
        kwargs['data'] = data

    if cookies:
        kwargs['cookies'] = cookies

    if params:
        kwargs['params'] = params

    return kwargs


# Example usage (for testing)
if __name__ == "__main__":
    raw_http = """POST /api/data HTTP/1.1
Host: httpbin.org
Content-Type: application/json
Content-Length: 18
Cookie: session_id=abc123; user=john

{"key": "value"}"""

    kwargs = parse_http_to_httpx_kwargs(raw_http)
    print(kwargs)

    # Test multipart
    raw_multipart = """POST /upload HTTP/1.1
Host: httpbin.org
Content-Type: multipart/form-data; boundary=WebKitFormBoundary7MA4YWxkTrZu0gW

--WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="name"

John Doe
--WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="email"

john@example.com
--WebKitFormBoundary7MA4YWxkTrZu0gW--"""

    kwargs_multipart = parse_http_to_httpx_kwargs(raw_multipart)
    print(kwargs_multipart)

    # Test form-urlencoded
    raw_form = """POST /submit HTTP/1.1
Host: example.com
Content-Type: application/x-www-form-urlencoded

name=John+Doe&email=john%40example.com"""

    kwargs_form = parse_http_to_httpx_kwargs(raw_form)
    print(kwargs_form)

    # Test query params
    raw_query = """GET /search?q=test&page=1 HTTP/1.1
Host: api.example.com"""

    kwargs_query = parse_http_to_httpx_kwargs(raw_query)
    print(kwargs_query)