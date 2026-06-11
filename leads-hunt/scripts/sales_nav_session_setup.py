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
import os
import sys
import time
from pathlib import Path

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
from _linkedin_session import ensure_session_profile  # noqa: E402

CFG = load_config()
PROFILE_DIR = CFG["paths"]["browser_profile"]
STATUS_FILE = Path("/tmp/sales-nav-status.txt")


def status(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with STATUS_FILE.open("a") as f:
        f.write(line + "\n")


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
    status("✅ SESSION VERIFIED. Profile persisted at " + PROFILE_DIR)
    status("DONE")


if __name__ == "__main__":
    main()
