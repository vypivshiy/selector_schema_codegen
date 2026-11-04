import json
from typing import Any
from urllib.parse import parse_qs, urlparse


def find_header(headers: dict[str, str], name: str) -> str | None:
    """Look up an HTTP header value case-insensitively.

    Args:
        headers: Mapping of HTTP header names to values.
        name: Header name to look up (case-insensitive).

    Returns:
        The matching header value if found, or `None` otherwise.
    """
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def parse_query_params(url: str) -> dict[str, Any]:
    """Parse query parameters from a URL into a dictionary.

    Args:
        url: Full or relative URL string potentially containing a query component.

    Returns:
        Dictionary mapping query parameter names to single string values or lists
        of strings when a parameter is repeated.
    """
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    return {}


def parse_multipart(body: str, boundary: str) -> dict[str, str]:
    """Parse multipart/form-data body into a dict of field names to values (text fields only)."""
    parts = body.split(f"--{boundary}")
    data = {}
    for part in parts:
        part = part.strip()
        if part and part != "--":
            lines = part.splitlines()
            headers_part = {}
            i = 0
            # Skip leading empty lines
            while i < len(lines) and not lines[i].strip():
                i += 1
            # Parse headers
            while i < len(lines) and lines[i].strip():
                if ":" in lines[i]:
                    k, v = lines[i].split(":", 1)
                    headers_part[k.strip()] = v.strip()
                i += 1
            # Skip empty line after headers
            if i < len(lines) and not lines[i].strip():
                i += 1
            content = "\n".join(lines[i:]).strip()
            # Extract name from Content-Disposition
            cd = headers_part.get("Content-Disposition", "")
            if "name=" in cd:
                name_part = cd.split("name=")[1]
                name = name_part.split(";")[0].strip('"')
                data[name] = content
    return data


def parse_cookies(cookie_header: str) -> dict[str, str]:
    """Parse a Cookie header string into a dictionary of name-value pairs.

    Args:
        cookie_header: Raw `Cookie` header string (semicolon-separated `name=value` pairs).

    Returns:
        Dictionary mapping cookie names to cookie values.
    """
    cookies = {}
    for pair in cookie_header.split(";"):
        pair = pair.strip()
        if "=" in pair:
            name, value = pair.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


def parse_http_request(raw_http: str) -> dict[str, Any]:
    """
    Parse a raw HTTP request string into a generic kwargs dict.

    Args:
        raw_http: The raw HTTP request as a string.

    Returns:
        Dict containing: method, url, headers, json/data, cookies, params, etc.

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
        if ":" in lines[i]:
            key, value = lines[i].split(":", 1)
            headers[key.strip()] = value.strip()
        else:
            raise ValueError(f"Invalid header line: {lines[i]}")
        i += 1

    # Skip empty line if present
    if i < len(lines) and not lines[i].strip():
        i += 1

    # Parse body
    body = "\n".join(lines[i:]) if i < len(lines) else ""

    # Construct URL
    host = find_header(headers, "Host")
    if host:
        url = f"https://{host}{path}"
    else:
        url = path  # Fallback to path only

    # Parse query params from URL
    params = parse_query_params(url)

    # Determine data type
    json_data: Any = None
    data: dict[str, Any] | str | None = None
    if body:
        content_type_full = find_header(headers, "Content-Type") or ""
        content_type = content_type_full.lower()
        if "multipart/form-data" in content_type:
            # Extract boundary
            if "boundary=" in content_type_full:
                boundary = (
                    content_type_full.split("boundary=")[1]
                    .split(";")[0]
                    .strip()
                )
                form_data = parse_multipart(body, boundary)
                data = form_data
            else:
                data = body  # Fallback
        elif "application/x-www-form-urlencoded" in content_type:
            urlencoded = parse_qs(body, keep_blank_values=True)
            data = {
                k: v[0] if len(v) == 1 else v for k, v in urlencoded.items()
            }
        elif "application/json" in content_type:
            try:
                json_data = json.loads(body)
            except json.JSONDecodeError:
                data = body  # Fallback to raw data
        else:
            data = body

    # Parse cookies
    cookies = None
    cookie_header = find_header(headers, "Cookie")
    if cookie_header is not None:
        cookies = parse_cookies(cookie_header)
        for k in [k for k in headers if k.lower() == "cookie"]:
            del headers[k]

    # Host is auto-set by HTTP libraries from the URL
    if host is not None:
        for k in [k for k in headers if k.lower() == "host"]:
            del headers[k]

    # Build kwargs
    kwargs: dict[str, Any] = {
        "method": method,
        "url": url,
    }

    if headers:
        kwargs["headers"] = headers

    if json_data is not None:
        kwargs["json"] = json_data
    elif data:
        kwargs["data"] = data

    if cookies:
        kwargs["cookies"] = cookies

    if params:
        kwargs["params"] = params

    return kwargs
