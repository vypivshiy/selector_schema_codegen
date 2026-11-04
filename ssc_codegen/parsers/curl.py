import json
import re as _re
import shlex
from collections.abc import Iterable
from typing import Any

from ssc_codegen.parsers.http import (
    find_header,
    parse_cookies,
    parse_query_params,
)


def parse_curl_command(
    curl_command: str, ignored_flags: Iterable[str] = ("--compressed",)
) -> dict[str, Any]:
    """
    Parse a POSIX curl command string into a generic kwargs dict.

    Note: POSIX only, not windows

    Args:
        curl_command: The curl command as a string.
        ignored_flags: Iterable of curl flags to ignore (default: ("--compressed",)).

    Returns:
        Dict containing httpx method kwargs: url, method, headers, json/data, auth, cookies, etc.

    Raises:
        ValueError: If the command is invalid or missing required parts.
    """
    # Normalize shell line continuations: \<optional spaces/tabs>\n<optional indent> → single space.
    # This handles editors that leave trailing whitespace after the backslash,
    # which would otherwise confuse shlex into producing spurious whitespace tokens.
    normalized = _re.sub(r"\\[ \t]*\n[ \t]*", " ", curl_command.strip())
    try:
        parts = shlex.split(normalized)
    except ValueError as e:
        raise ValueError(f"Invalid shell syntax in curl command: {e}")

    if not parts or parts[0].lower() != "curl":
        raise ValueError("Input is not a curl command")

    # Remove 'curl' from parts
    parts = parts[1:]

    method = "GET"
    method_explicit = False
    url = None
    headers = {}
    data = None
    json_data: Any = None
    auth = None
    params: dict[str, Any] = {}
    form_data: dict[str, str] = {}
    urlencoded_data: dict[str, str] = {}

    # Convert ignored_flags to set for fast lookup
    ignored_flags_set = set(ignored_flags)

    i = 0
    while i < len(parts):
        part = parts[i]
        if part in ("-X", "--request"):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing method after -X/--request")
            method = parts[i].upper()
            method_explicit = True
            if method not in (
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
                "HEAD",
                "OPTIONS",
            ):
                raise ValueError(f"Unsupported HTTP method: {method}")
        elif part in ("-H", "--header"):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing header after -H/--header")
            header = parts[i]
            if ":" not in header:
                raise ValueError(f"Invalid header format: {header}")
            key, value = header.split(":", 1)
            headers[key.strip()] = value.strip()
        elif part in ("-d", "--data", "--data-raw"):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing data after -d/--data/--data-raw")
            data = parts[i]
        elif part == "--json":
            i += 1
            if i >= len(parts):
                raise ValueError("Missing JSON data after --json")
            json_data = parts[i]
        elif part in ("-u", "--user"):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing user credentials after -u/--user")
            auth = parts[i]
        elif part in ("-F", "--form"):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing form data after -F/--form")
            form_part = parts[i]
            if "=" in form_part:
                key, value = form_part.split("=", 1)
                if not value.startswith("@"):  # Ignore files
                    form_data[key] = value
        elif part.startswith("--data-urlencode"):
            i += 1
            if i >= len(parts):
                raise ValueError("Missing data after --data-urlencode")
            param_part = parts[i]
            if "=" in param_part:
                key, value = param_part.split("=", 1)
                urlencoded_data[key] = value
            else:
                raise ValueError(
                    "Invalid --data-urlencode format, expected key=value"
                )
        elif part in ignored_flags_set:
            # Skip ignored flags
            pass
        elif not part.startswith("-"):
            if not part.strip():
                pass  # skip blank tokens produced by malformed line continuations
            elif url is not None:
                raise ValueError("Multiple URLs provided")
            else:
                url = part
        else:
            raise ValueError(f"Unsupported curl option: {part}")
        i += 1

    if url is None:
        raise ValueError("No URL found in curl command")

    if not method_explicit and (
        data is not None
        or json_data is not None
        or form_data
        or urlencoded_data
    ):
        method = "POST"

    # Parse query params from URL
    params.update(parse_query_params(url))

    # If data looks like JSON and no --json was specified, try to parse as JSON
    if data and json_data is None:
        try:
            json_data = json.loads(data)
            data = None
        except json.JSONDecodeError:
            pass

    # Build kwargs dict
    kwargs: dict[str, Any] = {
        "method": method,
        "url": url,
    }

    if headers:
        kwargs["headers"] = headers

    # Parse cookies from headers if present
    cookie_header = find_header(headers, "Cookie")
    if cookie_header is not None:
        kwargs["cookies"] = parse_cookies(cookie_header)
        for k in [k for k in headers if k.lower() == "cookie"]:
            del headers[k]
        if not headers and "headers" in kwargs:
            del kwargs["headers"]

    if form_data:
        kwargs["data"] = form_data
    elif urlencoded_data:
        kwargs["data"] = urlencoded_data
    elif json_data is not None:
        kwargs["json"] = json_data
    elif data:
        kwargs["data"] = data

    if auth:
        if ":" not in auth:
            raise ValueError("Invalid auth format, expected 'user:pass'")
        user, passwd = auth.split(":", 1)
        kwargs["auth"] = (user, passwd)

    if params:
        kwargs["params"] = params

    return kwargs
