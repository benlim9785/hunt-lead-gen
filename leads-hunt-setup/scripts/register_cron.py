#!/usr/bin/env python3
"""Emit the canonical AIME scheduler specs for the 4 leads-hunt recurring jobs.

This helper no longer touches system crontab. The leads-hunt-setup skill should
register recurring runs through AIME's native scheduler (`schedule` tool / AIME
scheduler API).

Default behavior prints the canonical job specs as JSON so the host agent can
create or verify the native scheduled tasks. Use --dry-run to also save the same
specs to <workspace>/leads-hunt/cron-suggestions.json for later inspection.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

JOBS = [
    {
        "name": "leads-hunt Phase A (sso-check)",
        "cron_expression": "0 30 7 * * *",
        "message": "Run leads-hunt Phase A: python3 scripts/run_topic.py --phase sso-check. Lark me on exit 3.",
    },
    {
        "name": "leads-hunt Phase B (discover-all)",
        "cron_expression": "0 0 8 * * *",
        "message": "Run leads-hunt Phase B: glob references/topics/*.md and discover for each enabled topic. Skill: leads-hunt.",
    },
    {
        "name": "leads-hunt Phase C (dedup-all)",
        "cron_expression": "0 0 9 * * *",
        "message": "Run leads-hunt Phase C: python3 scripts/run_topic.py --phase dedup-all",
    },
    {
        "name": "leads-hunt Phase D (deliver)",
        "cron_expression": "0 30 9 * * *",
        "message": "Run leads-hunt Phase D: python3 scripts/run_topic.py --phase deliver",
    },
]


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("AIME_WORKSPACE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd().resolve()


def materialize_specs() -> list[dict]:
    return [
        {
            "mode": "cron",
            "name": job["name"],
            "cron_expression": job["cron_expression"],
            "message": job["message"],
            "target": "main",
        }
        for job in JOBS
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", help="Override AIME_WORKSPACE_PATH")
    ap.add_argument("--dry-run", action="store_true", help="Write specs to cron-suggestions.json in the workspace")
    args = ap.parse_args()

    specs = materialize_specs()
    if args.dry_run:
        workspace = resolve_workspace(args.workspace)
        path = workspace / "leads-hunt" / "cron-suggestions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(specs, indent=2) + "\n", encoding="utf-8")
        print(f"wrote AIME schedule specs to {path}")
        return 0

    json.dump(specs, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
