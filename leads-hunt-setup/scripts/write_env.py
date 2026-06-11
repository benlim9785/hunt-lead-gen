#!/usr/bin/env python3
"""Write key=value pairs to <workspace>/leads-hunt/.env atomically.

Usage:
    python3 write_env.py KEY1=val1 KEY2=val2 ...

Behaviour:
  - Merges into existing .env (preserves keys not mentioned in argv).
  - Atomic: writes .env.tmp then renames over .env.
  - chmod 600 (owner read/write only).
  - Idempotent: keys already matching argv values are unchanged.
  - Prints a redacted summary (last 4 chars of each value, prefixed with `***`).

No LLM keys needed — AIME provides the host runtime. Expected keys for this
pack are LARK_*, LINKEDIN_*, BYTEDANCE_CORP_*, and any scheduler-related config.

Workspace resolves from $AIME_WORKSPACE_PATH when available.
Override with --workspace <path>.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("AIME_WORKSPACE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "aime-workspace").resolve()


def parse_existing(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def redact(v: str) -> str:
    if len(v) <= 4:
        return "***"
    return f"***{v[-4:]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", help="Override AIME_WORKSPACE_PATH")
    ap.add_argument("pairs", nargs="+", help="KEY=VALUE pairs (one or more)")
    args = ap.parse_args()

    updates: dict[str, str] = {}
    for pair in args.pairs:
        if "=" not in pair:
            print(f"error: '{pair}' is not KEY=VALUE", file=sys.stderr)
            return 2
        k, _, v = pair.partition("=")
        k = k.strip()
        if not k:
            print(f"error: empty key in '{pair}'", file=sys.stderr)
            return 2
        updates[k] = v

    root = resolve_workspace(args.workspace) / "leads-hunt"
    root.mkdir(parents=True, exist_ok=True)
    env_path = root / ".env"
    existing = parse_existing(env_path)

    merged = dict(existing)
    changed: list[str] = []
    for k, v in updates.items():
        if existing.get(k) != v:
            changed.append(k)
        merged[k] = v

    lines = [f"{k}={merged[k]}" for k in sorted(merged)]
    body = "\n".join(lines) + "\n"

    tmp = env_path.with_suffix(".env.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(tmp, env_path)
    os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)

    print(f"wrote {env_path} (mode 600, {len(merged)} keys)")
    if changed:
        for k in changed:
            print(f"  ~ {k}={redact(merged[k])}")
    else:
        print("  (no changes — all keys already matched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
