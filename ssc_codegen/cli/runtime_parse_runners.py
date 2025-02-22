import json
import warnings
from pathlib import Path
from typing import Any

from ichrome import AsyncChromeDaemon

from ssc_codegen.compiler import Compiler
import httpx


def print_json_output(json_output: str | list | dict) -> None:
    if isinstance(json_output, str):
        json_output = json.loads(json_output)
    print(json.dumps(json_output, indent=2))


def assert_cls_target(compiler: Compiler, cls_target: str) -> bool:
    return compiler.class_exists(cls_target)


def parse_from_http_request(
    url: str, compiler: Compiler, cls_target: str, **http_options
) -> Any:
    response = httpx.get(url, **http_options)
    if not response.is_success:
        if response.history:
            redirects = "redirects:" + " -> ".join(
                [f"{i.url}[{i.status_code}]" for i in response.history]
            )
        else:
            redirects = ""
        msg = f"{url} returns status code {response.status_code}. {redirects}"
        warnings.warn(msg, category=RuntimeWarning)
    return compiler.run_parse(cls_target, response.text)


def parse_from_html_file(
    file: Path, compiler: Compiler, cls_target: str
) -> Any:
    text = file.read_text(encoding="utf-8")
    return compiler.run_parse(cls_target, text)


async def parse_from_chrome(
    url: str,
    js_code: str,
    page_load_timeout: float = 10,
    *,
    # chrome options
    chrome_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 9922,
    headless: bool = True,
    chrome_options: list[str],
) -> str:
    async with AsyncChromeDaemon(
        chrome_path=chrome_path,
        host=host,
        port=port,
        clear_after_shutdown=True,
        headless=headless,
        disable_image=False,
        user_data_dir=None,
        extra_config=chrome_options,
    ) as cd:
        async with cd.connect_tab(0, auto_close=True) as tab:
            await tab.goto(
                url, timeout=page_load_timeout, timeout_stop_loading=True
            )
            result = (await tab.js(js_code))["value"]
    return result
