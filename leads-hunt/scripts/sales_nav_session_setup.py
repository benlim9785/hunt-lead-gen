"""
Sales Nav session bootstrap / verifier for the VNC-based login flow.

This script does not launch a second verification browser anymore. Instead, it
reads Chromium's Cookies SQLite DB directly, checks for valid LinkedIn auth
cookies, and syncs them into the leads-hunt profile when the live VNC browser
is writing to a different Chromium profile path.

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
from _linkedin_session import cleanup_temp_profile, ensure_session_profile, prepare_temp_linkedin_profile  # noqa: E402

CFG = load_config()
PROFILE_DIR = CFG["paths"]["browser_profile"]
STATUS_FILE = Path("/tmp/sales-nav-status.txt")
SSO_HOST = os.environ.get("SSO_HOST", "sso.")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def status(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with STATUS_FILE.open("a") as f:
        f.write(line + "\n")


async def verify_sales_nav_session() -> bool:
    session = prepare_temp_linkedin_profile(PROFILE_DIR, status=status)
    if not session.get("ok"):
        return False

    temp_root = session.get("temp_root")
    temp_profile_dir = session.get("temp_profile_dir")
    try:
        status(f"Check 2: launch Playwright against temp profile {temp_profile_dir}")
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=temp_profile_dir,
                headless=True,
                user_agent=UA,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="Asia/Kuala_Lumpur",
                args=["--disable-blink-features=AutomationControlled"],
            )
            await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            linkedin_cookies = [
                cookie
                for cookie in await ctx.cookies(["https://www.linkedin.com", "https://www.linkedin.com/sales/"])
                if "linkedin.com" in cookie.get("domain", "")
            ]
            if linkedin_cookies:
                status(f"Injected {len(linkedin_cookies)} LinkedIn cookies into Playwright context")
                await ctx.add_cookies(linkedin_cookies)
            else:
                status("No LinkedIn cookies were available after cloning the temp profile")

            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto("https://www.linkedin.com/sales/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            lower_url = page.url.lower()
            title = await page.title()
            body = await page.evaluate("document.body.innerText")
            lower_title = (title or "").lower()
            lower_body = (body or "").lower()

            logged_out = (
                SSO_HOST in lower_url
                or "/login" in lower_url
                or "/checkpoint" in lower_url
                or "/authwall" in lower_url
            )
            sales_nav_ui_detected = (
                "linkedin.com/sales/" in lower_url
                or "sales navigator" in lower_title
                or "account lists" in lower_body
                or "lead lists" in lower_body
                or "saved searches" in lower_body
            )
            await ctx.close()
            return bool(linkedin_cookies) and (not logged_out) and sales_nav_ui_detected
    finally:
        cleanup_temp_profile(temp_root)


def main():
    STATUS_FILE.unlink(missing_ok=True)
    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

    status("Check 1: inspect LinkedIn auth cookies from Chromium profile(s)")
    result = ensure_session_profile(PROFILE_DIR, status=status)
    if not result["ok"]:
        status(
            "needs-reauth: no valid LinkedIn auth cookies detected. "
            "Have the AE log in via the live VNC Chromium browser, then rerun this script"
        )
        sys.exit(3)

    details = result.get("details", {})
    cookies = details.get("auth_cookies", [])
    cookie_names = ", ".join(sorted({cookie["name"] for cookie in cookies})) or "none"
    if result.get("synced"):
        status(f"Synced cookies from live Chromium profile: {result['source']}")
    status(f"LinkedIn auth cookies OK ({cookie_names})")

    if not asyncio.run(verify_sales_nav_session()):
        status("needs-reauth: Playwright could not verify the cloned Sales Nav session")
        sys.exit(3)

    status("✅ SESSION VERIFIED. Profile persisted at " + PROFILE_DIR)
    status("DONE")


if __name__ == "__main__":
    main()
