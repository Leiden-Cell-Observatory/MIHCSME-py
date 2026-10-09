"""Headless smoke test: the flagship app loads the example and renders the plate editor."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
pytest.importorskip("anywidget")

APP = Path(__file__).parents[1] / "examples" / "marimo" / "mihcsme_app.py"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def app_url():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "marimo", "run", str(APP), "--headless", "--no-token",
         "--port", str(port), "--no-sandbox"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            time.sleep(0.5)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.mark.slow
def test_plate_editor_renders(app_url):
    with playwright.sync_playwright() as p:
        try:
            # PLAYWRIGHT_CHROMIUM_PATH lets you reuse an already-installed browser binary
            browser = p.chromium.launch(executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH"))
        except Exception as e:  # browser binaries not installed
            pytest.skip(f"Chromium not available: {e}")
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(app_url)
        page.get_by_role("tab", name="Edit Wells").click(timeout=60000)
        circles = page.locator(".pv svg circle")
        circles.first.wait_for(timeout=60000)
        assert circles.count() in (96, 384)
        assert errors == []
        browser.close()
