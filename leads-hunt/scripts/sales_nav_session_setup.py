"""
Sales Nav session bootstrap — populates the persistent browser profile with
LinkedIn personal auth, plus an OPTIONAL corporate SSO step for AEs whose
employer requires SSO to access Sales Navigator (e.g. ByteDance/BytePlus).

Run this script ONCE (or whenever sessions drop). Future leads-hunt queries
reuse the profile without re-authentication until the upstream session expires.

Env vars:
  Required:
    LK_EMAIL, LK_PASSWORD               LinkedIn personal credentials
  Optional (corporate SSO; gated by ENABLE_CORPORATE_SSO=1):
    SSO_EMAIL, SSO_PASSWORD             Corporate-account credentials
    SSO_HOST                            Hostname substring used to detect SSO
                                        redirect (e.g. 'sso.bytedance.com').
                                        Default: 'sso.' (any sso.* host).

CLI:
  --home <path>     Override LEADS_HUNT_HOME (per-AE workspace root).

OTP flow:
  - When LinkedIn (or the SSO IdP) prompts for an email OTP, this script polls
    /tmp/lk_otp.txt every 2 seconds for the code.
  - Send the code by writing it to that file (e.g. via a Lark webhook handler,
    or manually for now).

Outputs:
  - $LEADS_HUNT_HOME/browser-profile/sales-nav/  (Chromium profile dir)
  - /tmp/sales-nav-status.txt                     (progress log)
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


# ---- CLI / env bootstrap ----
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
OTP_FILE = Path("/tmp/lk_otp.txt")
STATUS_FILE = Path("/tmp/sales-nav-status.txt")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# LinkedIn personal credentials (always required)
LK_EMAIL = os.environ.get("LK_EMAIL")
LK_PASSWORD = os.environ.get("LK_PASSWORD")

# Optional corporate SSO (gated)
ENABLE_CORPORATE_SSO = os.environ.get("ENABLE_CORPORATE_SSO", "0") == "1"
SSO_EMAIL = os.environ.get("SSO_EMAIL")
SSO_PASSWORD = os.environ.get("SSO_PASSWORD")
SSO_HOST = os.environ.get("SSO_HOST", "sso.")

if not all([LK_EMAIL, LK_PASSWORD]):
    print("ERROR: LK_EMAIL and LK_PASSWORD env vars required", file=sys.stderr)
    sys.exit(2)

if ENABLE_CORPORATE_SSO and not all([SSO_EMAIL, SSO_PASSWORD]):
    print("ERROR: ENABLE_CORPORATE_SSO=1 requires SSO_EMAIL and SSO_PASSWORD", file=sys.stderr)
    sys.exit(2)


def status(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with STATUS_FILE.open("a") as f:
        f.write(line + "\n")


async def wait_for_otp(timeout=600):
    if OTP_FILE.exists():
        OTP_FILE.unlink()
    start = time.time()
    while time.time() - start < timeout:
        if OTP_FILE.exists():
            txt = OTP_FILE.read_text().strip()
            if txt:
                return txt
        await asyncio.sleep(2)
    return None


async def linkedin_login(page):
    status("LinkedIn step 1: navigate to /login")
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
    # 2026 redesign: inputs no longer use name='session_key'/'session_password'.
    # They expose autocomplete='username webauthn' + 'current-password' instead,
    # with a duplicate hidden pair earlier in the DOM. We target by attribute
    # and pick the LAST password field to dodge the decoy.
    await page.wait_for_selector("input[type='password']", state="visible", timeout=20000)
    await page.wait_for_timeout(2000)

    status("LinkedIn step 2: fill creds + tick 'Keep me signed in'")
    email_input = page.locator("input[autocomplete='username webauthn']").first
    if await email_input.count() == 0:
        email_input = page.locator("input[autocomplete='username']").first
    await email_input.fill(LK_EMAIL)
    pwds = await page.query_selector_all("input[type='password']")
    if not pwds:
        raise RuntimeError("LinkedIn login: no password input found")
    await pwds[-1].fill(LK_PASSWORD)
    cb = page.locator("input[type='checkbox']").last
    try:
        if await cb.count() and not await cb.is_checked():
            await cb.check(timeout=2000)
    except Exception:
        pass
    await page.wait_for_timeout(500)
    submits = await page.query_selector_all("button[type='submit']")
    if not submits:
        raise RuntimeError("LinkedIn login: no submit button found")
    await submits[-1].click()
    await page.wait_for_timeout(8000)

    body = await page.evaluate("document.body.innerText")
    if "Wrong email or password" in body:
        raise RuntimeError("LinkedIn rejected credentials: wrong email or password")
    if "Check your LinkedIn app" in body or "challengesV2" in page.url:
        status("LinkedIn step 3: app-push challenge, switching to email OTP")
        rd = page.locator("#recognizedDevice")
        if await rd.count() and not await rd.is_checked():
            await rd.check()
        clicked = False
        for sel in ["text=have access to this device", "*:has-text('have access to this device')"]:
            loc = page.locator(sel)
            if await loc.count():
                await loc.last.click()
                clicked = True
                break
        if not clicked:
            raise RuntimeError("Could not click 'I don't have access to this device'")

        await page.wait_for_timeout(8000)
        try:
            await page.wait_for_selector("input[name='pin']", timeout=20000)
            pin_sel = "input[name='pin']"
        except Exception:
            await page.wait_for_selector("input[autocomplete='one-time-code']", timeout=20000)
            pin_sel = "input[autocomplete='one-time-code']"
        status("LinkedIn step 4: WAITING FOR LinkedIn OTP. Write to /tmp/lk_otp.txt")
        otp = await wait_for_otp(timeout=600)
        if not otp:
            raise RuntimeError("LinkedIn OTP timeout")
        await page.fill(pin_sel, otp)
        await page.click("button[type='submit']")
        await page.wait_for_timeout(10000)

    final = page.url
    logged_out_markers = ("/login", "/checkpoint", "/uas/login", "/authwall")
    if any(m in final for m in logged_out_markers):
        body = await page.evaluate("document.body.innerText")
        snippet = body[:300].replace("\n", " | ")
        raise RuntimeError(f"LinkedIn login did not reach signed-in state. URL={final} body[:300]={snippet!r}")
    status(f"LinkedIn LOGIN OK at {final}")


async def corporate_sso_login(page):
    """Optional corporate SSO step.

    Only runs when ENABLE_CORPORATE_SSO=1. Detects an SSO IdP redirect by
    looking for SSO_HOST (default: 'sso.') in the URL after navigating to
    /sales/home. Tuned for a generic IAM IdP flow:
      step 1: enter email prefix (everything before @)
      step 2: click Next/Continue
      step 3: enter password
      step 4: click Login
      step 5: optional 2FA OTP via /tmp/lk_otp.txt
    AEs whose IdP differs significantly may need to fork this.
    """
    status("SSO step 1: navigate /sales/home, expect possible SSO redirect")
    await page.goto("https://www.linkedin.com/sales/home", wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(8000)
    status(f"  URL: {page.url}")
    if SSO_HOST not in page.url:
        if "linkedin.com/sales" in page.url:
            status("  SSO already valid (or not required), no re-auth needed")
            return True
        return False

    email_prefix = SSO_EMAIL.split("@")[0]
    status(f"SSO step 2: fill email prefix {email_prefix}")
    email_input = None
    for sel in ["input[placeholder*='Email prefix' i]", "input[placeholder*='email' i]", "input[type='text']"]:
        loc = page.locator(sel)
        if await loc.count():
            for i in range(await loc.count()):
                if await loc.nth(i).is_visible():
                    email_input = loc.nth(i)
                    break
            if email_input:
                break
    if not email_input:
        raise RuntimeError("SSO email input not found")
    await email_input.fill(email_prefix)
    await page.wait_for_timeout(800)

    next_btn = None
    for sel in ["button:has-text('Next step')", "button:has-text('Next')", "button:has-text('Continue')", ".iam-btn--username"]:
        loc = page.locator(sel)
        if await loc.count():
            next_btn = loc.first
            break
    if not next_btn:
        raise RuntimeError("SSO Next/Continue button not found")
    for _ in range(20):
        if await next_btn.is_enabled():
            break
        await page.wait_for_timeout(500)
    await next_btn.click()
    await page.wait_for_timeout(8000)

    status("SSO step 3: fill password")
    pw_input = None
    for sel in ["input[type='password']", "input[name='password']"]:
        loc = page.locator(sel)
        if await loc.count():
            for i in range(await loc.count()):
                if await loc.nth(i).is_visible():
                    pw_input = loc.nth(i)
                    break
            if pw_input:
                break
    if not pw_input:
        raise RuntimeError("SSO password input not found")
    await pw_input.fill(SSO_PASSWORD)
    await page.wait_for_timeout(500)

    for sel in ["button:has-text('Login')", "button:has-text('Log in')", "button:has-text('Sign in')", "button.iam-theme-button"]:
        loc = page.locator(sel)
        if await loc.count() and await loc.last.is_enabled():
            await loc.last.click()
            break
    await page.wait_for_timeout(15000)

    body = await page.evaluate("document.body.innerText")
    if "Two-step verification" in body or "verification code" in body.lower():
        status("SSO step 4: 2FA, click 'Send verification code'")
        for sel in ["button:has-text('Send verification code')", "button:has-text('Send code')", "button.iam-theme-button"]:
            loc = page.locator(sel)
            if await loc.count() and await loc.first.is_enabled():
                await loc.first.click()
                break
        await page.wait_for_timeout(5000)

        otp_input = None
        for sel in ["input[placeholder*='code' i]", "input[type='text'][maxlength]", "input[name='code']"]:
            loc = page.locator(sel)
            if await loc.count():
                for i in range(await loc.count()):
                    if await loc.nth(i).is_visible():
                        otp_input = loc.nth(i)
                        break
                if otp_input:
                    break
        if not otp_input:
            raise RuntimeError("SSO OTP input not found")

        status("SSO step 5: WAITING FOR SSO OTP. Write to /tmp/lk_otp.txt")
        sso_otp = await wait_for_otp(timeout=600)
        if not sso_otp:
            raise RuntimeError("SSO OTP timeout")
        await otp_input.fill(sso_otp)
        await page.wait_for_timeout(800)
        for sel in ["button:has-text('Confirm')", "button:has-text('Verify')", "button:has-text('Submit')", "button:has-text('Login')", "button.iam-theme-button"]:
            loc = page.locator(sel)
            if await loc.count() and await loc.last.is_enabled():
                await loc.last.click()
                break
        await page.wait_for_timeout(15000)

    status(f"SSO post-OTP URL: {page.url}")
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

        # Test if LinkedIn session is still valid
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        if "/login" in page.url or "/checkpoint" in page.url:
            status("LinkedIn session needs re-auth")
            await linkedin_login(page)
        else:
            status(f"LinkedIn session OK ({page.url})")

        if ENABLE_CORPORATE_SSO:
            sso_ok = await corporate_sso_login(page)
            if not sso_ok:
                status("ERROR: Corporate SSO failed")
                await ctx.close()
                return
        else:
            status("Corporate SSO disabled (ENABLE_CORPORATE_SSO != 1); skipping")

        # Verify Sales Nav loads
        await page.goto("https://www.linkedin.com/sales/home", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(8000)
        status(f"Final Sales Nav URL: {page.url}")
        title = await page.title()
        status(f"Final title: {title}")

        if "linkedin.com/sales" in page.url and "Sales Navigator" in title:
            status("✅ SESSION ESTABLISHED. Profile persisted at " + PROFILE_DIR)
        else:
            status(f"⚠ Final state unexpected: {page.url}")

        await ctx.close()
        status("DONE")


asyncio.run(main())
