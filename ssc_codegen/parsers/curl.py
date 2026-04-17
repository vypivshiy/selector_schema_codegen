import shlex
import json
from typing import Dict, Any, Iterable
from urllib.parse import urlparse, parse_qs


def parse_query_params(url: str) -> Dict[str, Any]:
    """Parse query parameters from URL into a dict."""
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    return {}


def parse_cookies(cookie_header: str) -> Dict[str, str]:
    """Parse a Cookie header string into a dict of name-value pairs."""
    cookies = {}
    for pair in cookie_header.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies[name.strip()] = value.strip()
    return cookies


def parse_curl_to_httpx_kwargs(curl_command: str, ignored_flags: Iterable[str] = ("--compressed",)) -> Dict[str, Any]:
    """
    Parse a curl command string and convert it to httpx kwargs.

    Note: POSIX only support, not windows

    Args:
        curl_command: The curl command as a string.
        ignored_flags: Iterable of curl flags to ignore (default: ("--compressed",)).

    Returns:
        Dict containing httpx method kwargs: url, method, headers, json/data, auth, cookies, etc.

    Raises:
        ValueError: If the command is invalid or missing required parts.
    """
    try:
        parts = shlex.split(curl_command.strip())
    except ValueError as e:
        raise ValueError(f"Invalid shell syntax in curl command: {e}")

    if not parts or parts[0].lower() != 'curl':
        raise ValueError("Input is not a curl command")

    # Remove 'curl' from parts
    parts = parts[1:]

    method = 'GET'
    url = None
    headers = {}
    data = None
    json_data = None
    auth = None
    params = {}
    form_data = {}

    # Convert ignored_flags to set for fast lookup
    ignored_flags_set = set(ignored_flags)

    i = 0
    while i < len(parts):
        part = parts[i]
        if part in ('-X', '--request'):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing method after -X/--request")
            method = parts[i].upper()
            if method not in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'):
                raise ValueError(f"Unsupported HTTP method: {method}")
        elif part in ('-H', '--header'):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing header after -H/--header")
            header = parts[i]
            if ':' not in header:
                raise ValueError(f"Invalid header format: {header}")
            key, value = header.split(':', 1)
            headers[key.strip()] = value.strip()
        elif part in ('-d', '--data'):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing data after -d/--data")
            data = parts[i]
        elif part == '--json':
            i += 1
            if i >= len(parts):
                raise ValueError("Missing JSON data after --json")
            try:
                json_data = json.loads(parts[i])
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in --json: {e}")
        elif part in ('-u', '--user'):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing user credentials after -u/--user")
            auth = parts[i]
        elif part in ('-F', '--form'):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing form data after -F/--form")
            form_part = parts[i]
            if '=' in form_part:
                key, value = form_part.split('=', 1)
                if not value.startswith('@'):  # Ignore files
                    form_data[key] = value
        elif part.startswith('--data-urlencode'):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing data after --data-urlencode")
            param_part = parts[i]
            if '=' in param_part:
                key, value = param_part.split('=', 1)
                params[key] = value
            else:
                raise ValueError("Invalid --data-urlencode format, expected key=value")
        elif part in ignored_flags_set:
            # Skip ignored flags
            pass
        elif not part.startswith('-'):
            if url is not None:
                raise ValueError("Multiple URLs provided")
            url = part
        else:
            raise ValueError(f"Unsupported curl option: {part}")
        i += 1

    if url is None:
        raise ValueError("No URL found in curl command")

    # Parse query params from URL
    params.update(parse_query_params(url))

    # If data looks like JSON and no --json was specified, try to parse as JSON
    if data and not json_data:
        try:
            json_data = json.loads(data)
            data = None
        except json.JSONDecodeError:
            pass

    # Build kwargs dict
    kwargs = {
        'method': method,
        'url': url,
    }

    if headers:
        kwargs['headers'] = headers

    # Parse cookies from headers if present
    if 'Cookie' in headers:
        kwargs['cookies'] = parse_cookies(headers['Cookie'])
        del headers['Cookie']
        if not headers and 'headers' in kwargs:
            del kwargs['headers']

    if form_data:
        kwargs['data'] = form_data
    elif json_data is not None:
        kwargs['json'] = json_data
    elif data:
        kwargs['data'] = data

    if auth:
        if ':' not in auth:
            raise ValueError("Invalid auth format, expected 'user:pass'")
        user, passwd = auth.split(':', 1)
        kwargs['auth'] = (user, passwd)

    if params:
        kwargs['params'] = params

    return kwargs


# Example usage (for testing)
if __name__ == "__main__":
    curl_cmd = 'curl -X POST -H "Content-Type: application/json" -d \'{"key": "value"}\' https://httpbin.org/post'
    kwargs = parse_curl_to_httpx_kwargs(curl_cmd)
    print(kwargs)

    # Test multipart form
    curl_form = 'curl -F "name=John" -F "age=30" -F "file=@image.jpg" https://httpbin.org/post'
    kwargs_form = parse_curl_to_httpx_kwargs(curl_form)
    print(kwargs_form)

    # Test data-urlencode
    curl_params = 'curl --data-urlencode "query=search term" --data-urlencode "page=1" https://api.example.com/search'
    kwargs_params = parse_curl_to_httpx_kwargs(curl_params)
    print(kwargs_params)
    cmd2 = """

    
    curl 'https://github.com/johndoe?tab=repositories' \
  --compressed \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0' \
  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
  -H 'Accept-Language: en-US,en;q=0.9' \
  -H 'Accept-Encoding: gzip, deflate, br, zstd' \
  -H 'Referer: https://github.com/johndoe' \
  -H 'Upgrade-Insecure-Requests: 1' \
  -H 'Sec-Fetch-Dest: document' \
  -H 'Sec-Fetch-Mode: navigate' \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'Connection: keep-alive' \
  -H 'Cookie: _octo=GH1.1.841914157.1771153873; logged_in=yes; _device_id=3621fc0987958ac5f20fda83f00e0abc; tz=Europe%2FMoscow' \
  -H 'If-None-Match: W/"69cf989dda53499a4315a1135c335c4b"' \
  

  -H 'Priority: u=0, i'

  
  """
    print(parse_curl_to_httpx_kwargs(cmd2))
