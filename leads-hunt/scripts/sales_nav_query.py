"""
Sales Nav company search using the persistent browser profile.

Reuses $LEADS_HUNT_HOME/browser-profile/sales-nav/ — no credentials needed.
Before launching Playwright, this script inspects Chromium's Cookies SQLite DB
for LinkedIn auth cookies. If the live VNC browser is using a different
Chromium profile path, the script will sync the cookie DB into the leads-hunt
profile first. If no valid auth cookies can be found, exits with code 3 and
prints "needs-reauth" so the caller can ask the AE to log in via VNC again and
rerun sales_nav_session_setup.py to verify the refreshed profile.

Usage:
  python3 sales_nav_query.py "Acme Corp"
  python3 sales_nav_query.py "Acme Corp" --home /tmp/test-home

Exit codes:
  0 = success, JSON result printed to stdout
  1 = company not found
  2 = bad invocation
  3 = session expired, run sales_nav_session_setup.py first
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("company", nargs="?")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    return ap.parse_args()


_args = _parse_args()
if _args.home:
    os.environ["LEADS_HUNT_HOME"] = _args.home

from _config import load_config  # noqa: E402
from _linkedin_session import cleanup_temp_profile, prepare_temp_linkedin_profile  # noqa: E402

CFG = load_config()
PROFILE_DIR = CFG["paths"]["browser_profile"]
SSO_HOST = os.environ.get("SSO_HOST", "sso.")  # match session_setup default
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

if not _args.company:
    print("Usage: sales_nav_query.py <company name> [--home <path>]", file=sys.stderr)
    sys.exit(2)

QUERY = _args.company


async def main():
    session = prepare_temp_linkedin_profile(PROFILE_DIR)
    if not session["ok"]:
        print("needs-reauth", file=sys.stderr)
        sys.exit(3)

    found_response = None
    temp_root = session.get("temp_root")
    temp_profile_dir = session.get("temp_profile_dir")
    try:
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
                await ctx.add_cookies(linkedin_cookies)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            async def on_response(resp):
                nonlocal found_response
                if "salesApiAccountSearch" in resp.url and resp.status == 200:
                    try:
                        found_response = await resp.text()
                    except Exception:
                        pass

            page.on("response", on_response)

            target = f"https://www.linkedin.com/sales/search/company?keywords={QUERY.replace(' ', '%20')}"
            await page.goto(target, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(10000)

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

            if logged_out or not sales_nav_ui_detected:
                print("needs-reauth", file=sys.stderr)
                await ctx.close()
                sys.exit(3)

            await ctx.close()
    finally:
        cleanup_temp_profile(temp_root)

    if not found_response:
        print("no-search-response-captured", file=sys.stderr)
        sys.exit(1)

    data = json.loads(found_response)
    elements = data.get("elements", [])
    if not elements:
        print(json.dumps({"query": QUERY, "found": False, "in_crm": None}))
        sys.exit(1)

    import re

    def tokenize(s: str) -> set:
        s = (s or "").lower().strip()
        for suf in (".ai", ".com", ".io", ".co", ".net", ".org", ".dev", ".tech"):
            if s.endswith(suf):
                s = s[: -len(suf)]
        return {t for t in re.split(r"[^a-z0-9]+", s) if len(t) >= 3}

    query_tokens = tokenize(QUERY)
    if not query_tokens:
        query_tokens = {QUERY.strip().lower()}

    def name_overlaps(el: dict) -> bool:
        return bool(query_tokens & tokenize(el.get("companyName", "")))

    in_crm_token_match = next(
        (
            el for el in elements
            if name_overlaps(el) and el.get("crmStatus", {}).get("imported")
        ),
        None,
    )
    name_match = next((el for el in elements if name_overlaps(el)), None)
    chosen = in_crm_token_match or name_match or elements[0]

    crm_status = chosen.get("crmStatus", {})
    in_crm = bool(crm_status.get("imported", False))
    out = {
        "query": QUERY,
        "found": True,
        "match_name": chosen.get("companyName"),
        "entity_urn": chosen.get("entityUrn"),
        "industry": chosen.get("industry"),
        "employee_count": chosen.get("employeeDisplayCount"),
        "in_crm": in_crm,
        "saved_to_my_list": chosen.get("saved", False),
        "salesforce_url": crm_status.get("externalCrmUrl"),
        "salesforce_id": crm_status.get("idInSourceDomain"),
        "total_results": data.get("metadata", {}).get("totalDisplayCount"),
        "match_strategy": (
            "token-match-in-crm" if in_crm_token_match else
            "token-match" if name_match else
            "first-result-fallback"
        ),
    }
    print(json.dumps(out, indent=2))


asyncio.run(main())
