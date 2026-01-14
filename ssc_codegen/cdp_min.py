"""simple chrome-cdp runner"""

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import tempfile
import time
from typing import List, Optional

import httpx
from websockets.sync.client import connect as ws_connect

logger = logging.getLogger(__name__)


def find_chrome_executable() -> Optional[str]:
    """Try to find Chrome/Chromium executable on common paths."""
    system = platform.system()
    if system == "Windows":
        candidates = [
            os.path.expandvars(
                r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(
                r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
            ),
            shutil.which("chrome"),
            shutil.which("chromium"),
        ]
    elif system == "Darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            shutil.which("google-chrome"),
            shutil.which("chromium"),
            shutil.which("chrome"),
        ]
    else:  # Linux
        candidates = [
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            shutil.which("chromium-browser"),
            shutil.which("chromium"),
            shutil.which("chrome"),
        ]

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


def parse_from_chrome(
    url: str,
    js_code: str,
    page_load_timeout: float = 10,
    chrome_path: Optional[str] = None,
    host: str = "127.0.0.1",
    port: int = 9922,
    headless: bool = True,
    chrome_options: Optional[List[str]] = None,
) -> str:
    chrome_options = chrome_options or []

    # Find Chrome binary
    if chrome_path is None:
        chrome_path = find_chrome_executable()
        if not chrome_path:
            raise RuntimeError(
                "Chrome/Chromium executable not found. Please specify --system-chrome."
            )
    # Ensure port is free (optional safety)
    if not is_port_free(host, port):
        raise RuntimeError(f"Port {port} on {host} is already in use.")
    user_data_dir = tempfile.mkdtemp()
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--metrics-recording-only",
        "--mute-audio",
    ]
    if headless:
        cmd.append("--headless=new")
    cmd.extend(["--no-sandbox", "--disable-gpu"])
    cmd.extend(chrome_options)

    proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        # Wait for CDP endpoint to be ready
        cdp_url = f"http://{host}:{port}"
        max_wait = 10
        start = time.time()
        while time.time() - start < max_wait:
            try:
                resp = httpx.get(f"{cdp_url}/json/version", timeout=1)
                if resp.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError(
                "Chrome DevTools Protocol did not become ready in time."
            )

        # Create new tab
        new_tab_resp = httpx.put(f"{cdp_url}/json/new", timeout=5)
        new_tab_resp.raise_for_status()
        tab_info = new_tab_resp.json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        # Connect via WebSocket
        with ws_connect(ws_url) as ws:
            # Enable needed domains
            ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
            ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
            # Drain initial messages
            for _ in range(2):
                ws.recv()

            # Navigate
            nav_id = 3
            ws.send(
                json.dumps(
                    {
                        "id": nav_id,
                        "method": "Page.navigate",
                        "params": {"url": url},
                    }
                )
            )
            # Wait for load or timeout
            start = time.time()
            load_event_received = False
            while time.time() - start < page_load_timeout:
                try:
                    raw = ws.recv(timeout=0.1)
                    msg = json.loads(raw)
                    if msg.get("method") == "Page.loadEventFired":
                        load_event_received = True
                        break
                except TimeoutError:
                    continue
            if not load_event_received:
                logger.warning("Page load timeout reached; proceeding anyway.")

            # Evaluate JS
            eval_id = 4
            ws.send(
                json.dumps(
                    {
                        "id": eval_id,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": js_code,
                            "returnByValue": True,
                        },
                    }
                )
            )
            result_msg = None
            while True:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("id") == eval_id:
                    result_msg = msg
                    break

            if "result" not in result_msg:
                raise RuntimeError(f"JS evaluation failed: {result_msg}")

            cdp_result = result_msg["result"]
            if cdp_result.get("exceptionDetails"):
                raise RuntimeError(
                    f"JS exception: {cdp_result['exceptionDetails']}"
                )

            remote_obj = cdp_result.get("result", {})
            if "value" not in remote_obj:  # undefined
                return ""
            value = remote_obj["value"]
            if isinstance(value, str):
                return value
            else:
                return json.dumps(value)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(user_data_dir, ignore_errors=True)
