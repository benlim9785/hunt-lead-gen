#!/usr/bin/env python3
"""Register the 4 leads-hunt cron jobs with OpenClaw.

Wraps `openclaw cron add` for each of the canonical Phase A/B/C/D jobs from
leads-hunt's SKILL.md. Idempotent — checks `openclaw cron list` first and
skips any job whose schedule + message-substring already exists.

Use --dry-run to write the would-be commands to <workspace>/leads-hunt/
cron-suggestions.txt instead of executing them.
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
        "extra": [],
    },
    {
        "name": "leads-hunt Phase B (discover-all)",
        "schedule": "0 8 * * *",
        "message": "Run leads-hunt Phase B: glob references/topics/*.md and discover for each enabled topic. Skill: leads-hunt.",
        "extra": ["--skills", "leads-hunt", "--enabled-toolsets", "terminal,web,file"],
    },
    {
        "name": "leads-hunt Phase C (dedup-all)",
        "schedule": "0 9 * * *",
        "message": "Run leads-hunt Phase C: python3 scripts/run_topic.py --phase dedup-all",
        "extra": [],
    },
    {
        "name": "leads-hunt Phase D (deliver)",
        "schedule": "30 9 * * *",
        "message": "Run leads-hunt Phase D: python3 scripts/run_topic.py --phase deliver",
        "extra": [],
    },
]


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("OPENCLAW_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".openclaw" / "workspace").resolve()


def list_existing() -> str:
    if shutil.which("openclaw") is None:
        return ""
    try:
        p = subprocess.run(
            ["openclaw", "cron", "list"], capture_output=True, text=True, timeout=15
        )
        return (p.stdout or "") + "\n" + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return ""


def already_registered(existing: str, schedule: str, message: str) -> bool:
    # Lenient: a job is "the same" if both its schedule and a 40-char prefix
    # of its message appear in the same line of `cron list` output.
    needle = message[:40]
    for line in existing.splitlines():
        if schedule in line and needle in line:
            return True
    return False


def add_job(job: dict) -> tuple[bool, str]:
    cmd = [
        "openclaw", "cron", "add",
        "--schedule", job["schedule"],
        "--message", job["message"],
        *job["extra"],
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        return False, "openclaw not in PATH"
    except subprocess.TimeoutExpired:
        return False, "openclaw cron add timed out"
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or f"rc={p.returncode}").strip()
    out = (p.stdout or "").strip()
    return True, out or "(registered)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", help="Override OPENCLAW_WORKSPACE")
    ap.add_argument("--dry-run", action="store_true", help="Write commands to cron-suggestions.txt instead of registering")
    args = ap.parse_args()

    if args.dry_run:
        path = resolve_workspace(args.workspace) / "leads-hunt" / "cron-suggestions.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for j in JOBS:
            extra = " ".join(f'"{x}"' if " " in x else x for x in j["extra"])
            cmd = f'openclaw cron add --schedule "{j["schedule"]}" --message "{j["message"]}"'
            if extra:
                cmd += " " + extra
            lines.append(f"# {j['name']}\n{cmd}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote dry-run commands to {path}")
        return 0

    if shutil.which("openclaw") is None:
        print("❌ openclaw not found in PATH; install OpenClaw first.", file=sys.stderr)
        return 1

    existing = list_existing()
    failures = 0
    for j in JOBS:
        if already_registered(existing, j["schedule"], j["message"]):
            print(f"= {j['name']}: already registered, skipping")
            continue
        ok, msg = add_job(j)
        if ok:
            print(f"✅ {j['name']}: {msg}")
        else:
            print(f"❌ {j['name']}: {msg}", file=sys.stderr)
            failures += 1

    if failures:
        return 1
    print("\nVerify with: openclaw cron list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
