"""
Sales Nav session bootstrap / verifier for the VNC-based login flow.

This script no longer performs credential-based authentication. The AE logs into
LinkedIn and Sales Navigator manually inside the shared VNC browser session.
This helper simply reuses the persistent browser profile, verifies that the
session is live, and writes progress to /tmp/sales-nav-status.txt.

CLI:
  --home <path>     Override LEADS_HUNT_HOME (per-AE workspace root).

Outputs:
  - $LEADS_HUNT_HOME/browser-profile/sales-nav/  (Chromium profile dir)
  - /tmp/sales-nav-status.txt                     (progress log)

Exit codes:
  0 = session verified / usable
  2 = bad invocation or local setup problem
  3 = session expired or not authenticated; user must log in via VNC first
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def _parse_args():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    return ap.parse_args()


_args = _parse_args()
if _args.home:
    os.environ["LEADS_HUNT_HOME"] = _args.home

from _config import load_config  # noqa: E402

CFG = load_config()
PROFILE_DIR = CFG["paths"]["browser_profile"]
STATUS_FILE = Path("/tmp/sales-nav-status.txt")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with STATUS_FILE.open("a") as f:
        f.write(line + "\n")


async def verify_profile_session(page):
    status("Check 1: inspect LinkedIn session from persistent browser profile")
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    if "/login" in page.url or "/checkpoint" in page.url or "/authwall" in page.url:
        status(f"LinkedIn session is not authenticated ({page.url})")
        return False
    status(f"LinkedIn session OK ({page.url})")

    status("Check 2: inspect Sales Navigator session from persistent browser profile")
    await page.goto("https://www.linkedin.com/sales/home", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(5000)
    title = await page.title()
    body = await page.evaluate("document.body.innerText")
    lower_body = (body or "").lower()
    lower_url = page.url.lower()
    lower_title = (title or "").lower()

    sales_nav_indicators = (
        "linkedin.com/sales/home" in lower_url
        or "sales navigator" in lower_title
        or "account lists" in lower_body
        or "lead lists" in lower_body
        or "saved searches" in lower_body
    )
    logged_out = any(marker in lower_url for marker in ("/login", "/checkpoint", "/authwall"))

    if logged_out or not sales_nav_indicators:
        status(f"Sales Navigator session is not ready (url={page.url!r}, title={title!r})")
        return False

    status(f"Sales Navigator session OK ({page.url})")
    return True


async def main():
    STATUS_FILE.unlink(missing_ok=True)
    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            user_agent=UA,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="Asia/Kuala_Lumpur",
            args=["--disable-blink-features=AutomationControlled"],
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
            "Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});"
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        ok = await verify_profile_session(page)
        if not ok:
            status("needs-reauth: have the AE log in via the VNC browser using the same browser profile, then rerun this script")
            await ctx.close()
            sys.exit(3)

        status("✅ SESSION VERIFIED. Profile persisted at " + PROFILE_DIR)
        await ctx.close()
        status("DONE")


asyncio.run(main())
