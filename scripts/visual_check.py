#!/usr/bin/env python3
"""
visual_check.py — FAILSAFE-only headless screenshot tool (P1 enforcement)

⚠️  PRIMARY P1 PATH IS CHROME MCP (mcp__Claude_in_Chrome__*).
This playwright-based script exists ONLY as a fallback for:
  - pre-commit hook runs when Claude is not in the loop
  - headless / CI environments without Chrome MCP
  - cases where Chrome MCP is genuinely unavailable

For day-to-day interactive QA, Claude should drive Chrome MCP directly:
    1. Start local server: python3 -m http.server 8765
    2. mcp__Claude_in_Chrome__navigate → http://localhost:8765/index.html
    3. mcp__Claude_in_Chrome__resize_window + computer.screenshot per viewport
    4. mcp__Claude_in_Chrome__javascript_tool to inspect DOM state

Usage (failsafe):
    python3 scripts/visual_check.py <html_file> [--out screenshots/<label>]

Produces 5 screenshots:
  desktop_wide.png   1440×900
  desktop_narrow.png 1024×768
  tablet.png         768×1024
  mobile.png         375×812
  panel_top.png      1440×900 scrolled to top
"""

import sys
import os
import subprocess
import threading
import http.server
import socket
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip3 install playwright && python3 -m playwright install chromium")
    sys.exit(1)


VIEWPORTS = [
    ("desktop_wide",   1440, 900),
    ("desktop_narrow", 1024, 768),
    ("tablet",          768, 1024),
    ("mobile",          375, 812),
    ("panel_top",      1440, 900),   # same as wide but explicit scroll-to-top
]


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def start_server(root: Path) -> tuple[int, threading.Thread]:
    port = find_free_port()
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.HTTPServer(('localhost', port), handler)
    httpd.timeout = 1

    def serve():
        os.chdir(root)
        httpd.serve_forever()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return port, httpd


def git_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        return result.stdout.strip() or "no-commit"
    except Exception:
        return "no-git"


def describe_page(page, label: str) -> str:
    """Extract basic visible text to confirm Claude 'saw' the page."""
    title = page.title()
    h1s = page.locator("h1").all_text_contents()
    h2s = page.locator("h2").all_text_contents()[:3]
    body_excerpt = (page.locator("body").inner_text() or "")[:300].replace("\n", " ")
    return (
        f"[{label}] title={title!r} "
        f"h1={h1s} h2={h2s[:3]} "
        f"body_excerpt={body_excerpt!r}"
    )


def run(html_path: str, out_dir: str | None = None):
    html_path = Path(html_path).resolve()
    if not html_path.exists():
        print(f"ERROR: {html_path} not found")
        sys.exit(1)

    label = out_dir or "latest"
    out = Path(__file__).parent.parent / "screenshots" / label
    out.mkdir(parents=True, exist_ok=True)

    # Start local HTTP server so fetch() works (file:// blocks CORS)
    root = html_path.parent
    port, httpd = start_server(root)
    rel = html_path.relative_to(root)
    page_url = f"http://localhost:{port}/{rel}"

    print(f"\n=== visual_check.py ===")
    print(f"File : {html_path}")
    print(f"URL  : {page_url}")
    print(f"Out  : {out}")
    print(f"Git  : {git_hash()}")
    print()

    descriptions = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for name, width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(page_url, wait_until="networkidle", timeout=15000)

            if name == "panel_top":
                page.evaluate("window.scrollTo(0, 0)")

            png_path = out / f"{name}.png"
            page.screenshot(path=str(png_path), full_page=(name == "mobile"))
            desc = describe_page(page, name)
            descriptions.append(desc)
            print(f"✅ {name:18s} → {png_path.name}   [{width}×{height}]")
            print(f"   {desc[:120]}")
            page.close()

        browser.close()

    httpd.shutdown()

    # Write manifest
    manifest_path = out / "manifest.txt"
    with open(manifest_path, "w") as f:
        f.write(f"visual_check run: {datetime.now().isoformat()}\n")
        f.write(f"git: {git_hash()}\n")
        f.write(f"file: {html_path}\n\n")
        for d in descriptions:
            f.write(d + "\n")

    print(f"\n📋 Manifest → {manifest_path}")
    print("=== done ===\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 scripts/visual_check.py <html_file> [out_label]")
        sys.exit(1)

    html_file = args[0]
    out_label = args[1] if len(args) > 1 else "latest"
    run(html_file, out_label)
