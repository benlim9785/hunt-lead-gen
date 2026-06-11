#!/usr/bin/env python3
"""Register the 4 leads-hunt recurring jobs using the local system crontab.

Adds the canonical Phase A/B/C/D jobs from leads-hunt's SKILL.md.
Idempotent — checks the current crontab first and skips any job whose marker
already exists.

Use --dry-run to write the would-be commands to <workspace>/leads-hunt/
cron-suggestions.txt instead of modifying crontab.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

JOBS = [
    {
        "name": "leads-hunt Phase A (sso-check)",
        "schedule": "30 7 * * *",
        "message": "Run leads-hunt Phase A: python3 scripts/run_topic.py --phase sso-check. Lark me on exit 3.",
    },
    {
        "name": "leads-hunt Phase B (discover-all)",
        "schedule": "0 8 * * *",
        "message": "Run leads-hunt Phase B: glob references/topics/*.md and discover for each enabled topic. Skill: leads-hunt.",
    },
    {
        "name": "leads-hunt Phase C (dedup-all)",
        "schedule": "0 9 * * *",
        "message": "Run leads-hunt Phase C: python3 scripts/run_topic.py --phase dedup-all",
    },
    {
        "name": "leads-hunt Phase D (deliver)",
        "schedule": "30 9 * * *",
        "message": "Run leads-hunt Phase D: python3 scripts/run_topic.py --phase deliver",
    },
]


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("AIME_WORKSPACE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "aime-workspace").resolve()


def crontab_available() -> bool:
    return shutil.which("crontab") is not None


def list_existing() -> str:
    if not crontab_available():
        return ""
    try:
        p = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return ""
    if p.returncode != 0:
        return ""
    return p.stdout or ""


def marker(job: dict) -> str:
    return f"# leads-hunt::{job['name']}"


def cron_line(job: dict) -> str:
    escaped = job["message"].replace('"', '\\"')
    return f"{job['schedule']} cd {resolve_workspace(None) / 'leads-hunt'} && {escaped}"


def already_registered(existing: str, job: dict) -> bool:
    return marker(job) in existing


def install_crontab(contents: str) -> tuple[bool, str]:
    try:
        p = subprocess.run(["crontab", "-"], input=contents, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        return False, "crontab not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "crontab install timed out"
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or f"rc={p.returncode}").strip()
    return True, "installed"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", help="Override AIME_WORKSPACE_PATH")
    ap.add_argument("--dry-run", action="store_true", help="Write commands to cron-suggestions.txt instead of registering")
    args = ap.parse_args()

    workspace = resolve_workspace(args.workspace)

    if args.dry_run:
        path = workspace / "leads-hunt" / "cron-suggestions.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for j in JOBS:
            lines.append(f"{marker(j)}\n{cron_line(j)}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote dry-run commands to {path}")
        return 0

    if not crontab_available():
        print("❌ crontab not found in PATH; cannot register recurring jobs automatically.", file=sys.stderr)
        return 1

    existing = list_existing()
    chunks = [existing.rstrip()] if existing.strip() else []
    added = 0
    for j in JOBS:
        if already_registered(existing, j):
            print(f"= {j['name']}: already registered, skipping")
            continue
        chunks.append(marker(j))
        chunks.append(cron_line(j))
        added += 1

    if added == 0:
        print("All jobs already registered")
        return 0

    new_body = "\n".join(chunks).strip() + "\n"
    ok, msg = install_crontab(new_body)
    if not ok:
        print(f"❌ failed to install crontab: {msg}", file=sys.stderr)
        return 1

    print(f"✅ registered {added} leads-hunt recurring job(s)")
    print("\nVerify with: crontab -l")
    return 0


if __name__ == "__main__":
    sys.exit(main())
