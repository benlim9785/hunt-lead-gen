#!/usr/bin/env python3
"""
Wrap the Sales Nav query script with a 24-hour cache.

Public functions:
  smoke_test(cfg) -> int
      Phase A: tests SSO with a known query. Returns 0 if SSO OK, 3 if expired.
      On 3, prints a Lark-ready alert message to stdout (cron picks up stdout).

  check(company_name, cfg) -> dict
      Phase C: lookup with cache. Returns {"in_crm": bool, ...} or
      {"error": "sso-expired"} if exit code 3.

Cache file: {lead_gen_root}/sales-nav-cache.jsonl
Cache key: lowercase company name.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _cache_path(cfg) -> Path:
    return Path(cfg["paths"]["lead_gen_root"]) / cfg["paths"]["sales_nav_cache"]


def _read_cache(cfg) -> dict[str, dict]:
    p = _cache_path(cfg)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        key = entry.get("company", "").lower().strip()
        if key:
            out[key] = entry
    return out


def _append_cache(cfg, entry: dict) -> None:
    p = _cache_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _is_fresh(entry: dict, ttl_hours: int) -> bool:
    ts = entry.get("checked_at")
    if not ts:
        return False
    try:
        when = datetime.datetime.fromisoformat(ts)
    except Exception:
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - when.astimezone(datetime.timezone.utc)
    return age.total_seconds() < ttl_hours * 3600


def _run_query(name: str, cfg) -> tuple[int, str]:
    script = cfg["external"]["sales_nav_query_script"]
    try:
        proc = subprocess.run(
            ["python3", script, name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        return 1, "{}"
    except Exception as e:
        print(f"[sales_nav_check] subprocess error: {e}", file=sys.stderr)
        return 1, "{}"


def check(company_name: str, cfg) -> dict[str, Any]:
    """Look up company in CRM. Returns dict with keys at least:
        in_crm: bool (or absent if error/not-found)
        error: str (if error)
        cached: bool
    """
    key = company_name.lower().strip()
    cache = _read_cache(cfg)
    ttl = cfg.get("salesforce_cache_ttl_hours", 24)
    if key in cache and _is_fresh(cache[key], ttl):
        out = dict(cache[key])
        out["cached"] = True
        return out

    rc, stdout = _run_query(company_name, cfg)
    if rc == 3:
        return {"error": "sso-expired", "cached": False}
    if rc == 1:
        return {"error": "not-found", "cached": False, "found": False}
    if rc != 0:
        return {"error": f"exit-code-{rc}", "cached": False}

    try:
        result = json.loads(stdout)
    except Exception:
        return {"error": "bad-json", "cached": False, "raw": stdout[:200]}

    entry = {
        "company": company_name,
        "in_crm": bool(result.get("in_crm")),
        "found": bool(result.get("found")),
        "match_name": result.get("match_name"),
        "salesforce_url": result.get("salesforce_url"),
        "salesforce_id": result.get("salesforce_id"),
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _append_cache(cfg, entry)
    out = dict(entry)
    out["cached"] = False
    return out


def smoke_test(cfg) -> int:
    """Phase A: ping Sales Nav with a known query to verify SSO.

    Returns exit code. Stays silent on success (no spammy Lark messages).
    On SSO failure, prints alert message (caller delivers it to the AE).
    """
    test_query = cfg.get("smoke_test_query", "Microsoft")
    rc, stdout = _run_query(test_query, cfg)
    if rc == 0:
        # Silent success; only stderr gets a confirmation, not stdout.
        print(f"[Phase A] SSO OK ({test_query} query returned 0)", file=sys.stderr)
        return 0
    if rc == 3:
        # Print alert message; caller's delivery hook posts to Lark.
        print(_sso_alert_message(cfg))
        return 3
    print(f"[Phase A] WARN: query exit {rc}", file=sys.stderr)
    print(stdout[:500], file=sys.stderr)
    return 1


def _sso_alert_message(cfg) -> str:
    setup_script = cfg.get("external", {}).get("sales_nav_setup_script",
                                               "scripts/sales_nav_session_setup.py")
    return (
        "leads-hunt: Sales Nav session expired\n\n"
        "Cannot verify CRM today. Run:\n"
        f"  python3 {setup_script}\n\n"
        "Use the leads-hunt-setup VNC login flow to refresh the shared browser "
        "profile for LinkedIn / Sales Navigator.\n"
        "Complete any SSO, MFA, OTP, or captcha directly inside the VNC browser, "
        "then retry the check. Will retry tomorrow if not refreshed today."
    )


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Sales Nav CRM check (cached).")
    ap.add_argument("company", nargs="?", help="Company name to look up")
    ap.add_argument("--smoke-test", action="store_true")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    from _config import load_config
    cfg = load_config()
    if args.smoke_test:
        sys.exit(smoke_test(cfg))
    if not args.company:
        print("usage: sales_nav_check.py <company>  OR  --smoke-test", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(check(args.company, cfg), indent=2))
