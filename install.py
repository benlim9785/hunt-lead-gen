#!/usr/bin/env python3
"""
leads-hunt-pack installer.

One-shot installer that registers all 5 leads-hunt-pack skills with the
local OpenClaw skill registry. Run ONCE after cloning this repo onto a
machine that already has OpenClaw installed and an agent bound to Lark.

Usage:
    python3 install.py                # normal install
    python3 install.py --dry-run      # show what would happen, change nothing
    python3 install.py --verbose      # print full subprocess output
    python3 install.py --help

After this script succeeds, open your Lark DM with your agent and say:
    "set me up for leads hunt"
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# OpenClaw CLI surface for installing skills. If OpenClaw renames this
# (e.g. `openclaw skill add` or `openclaw install`), change it here.
OPENCLAW_INSTALL_CMD = ["openclaw", "skills", "install"]
OPENCLAW_LIST_CMD = ["openclaw", "skills", "list"]

# Install order: leaf skills first, the "setup" wizard last (its prereq
# check probably looks for the others to be registered).
SKILL_ORDER = [
    "leads-hunt-voice",
    "leads-hunt-add-target",
    "leads-hunt",
    "leads-hunt-outreach",
    "leads-hunt-setup",
]

OPENCLAW_DOCS_URL = "https://openclaw.dev/install"  # placeholder
MIN_PY = (3, 10)

REPO_ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Pretty output helpers (TTY-aware)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def green(t: str) -> str: return _c("32", t)
def red(t: str) -> str: return _c("31", t)
def yellow(t: str) -> str: return _c("33", t)
def bold(t: str) -> str: return _c("1", t)


PASS, FAIL, WARN = green("✓"), red("✗"), yellow("!")


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------


def run(cmd: list[str], verbose: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess capturing output. Never raises on non-zero exit."""
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        cp = subprocess.CompletedProcess(cmd, returncode=127, stdout="", stderr=str(e))
    if verbose:
        if cp.stdout:
            print(f"  [stdout] {cp.stdout.rstrip()}")
        if cp.stderr:
            print(f"  [stderr] {cp.stderr.rstrip()}")
    return cp


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def banner() -> None:
    print(bold("leads-hunt-pack installer"))
    print("---------------------------")
    print("This will register the following 5 skills with your local OpenClaw:")
    for s in SKILL_ORDER:
        print(f"  • {s}")
    print()
    print("Once installed, open Lark and say to your agent:")
    print(f'  {bold("set me up for leads hunt")}')
    print()


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL
)
_NAME_RE = re.compile(r"^\s*name\s*:\s*(\S+)\s*$", re.MULTILINE)


def check_skill_dir(skill: str) -> tuple[bool, str]:
    d = REPO_ROOT / skill
    if not d.is_dir():
        return False, f"missing directory: {d}"
    sk = d / "SKILL.md"
    if not sk.is_file():
        return False, f"missing SKILL.md: {sk}"
    text = sk.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return False, f"no YAML frontmatter in {sk}"
    if not _NAME_RE.search(m.group("body")):
        return False, f"no `name:` field in frontmatter of {sk}"
    return True, "ok"


def prereq_checks(openclaw_bin: str, verbose: bool) -> bool:
    print(bold("Prerequisite checks"))
    ok = True

    # Python version
    if sys.version_info >= MIN_PY:
        print(f"  {PASS} python3 {sys.version.split()[0]} (>= 3.10)")
    else:
        print(f"  {FAIL} python3 {sys.version.split()[0]} — need >= 3.10")
        ok = False

    # OpenClaw on PATH
    found = shutil.which(openclaw_bin) if openclaw_bin == "openclaw" else (
        openclaw_bin if Path(openclaw_bin).is_file() else None
    )
    if not found:
        print(f"  {FAIL} OpenClaw CLI not found ({openclaw_bin})")
        print(
            f"     OpenClaw CLI not found. Install OpenClaw first: {OPENCLAW_DOCS_URL} "
            f"then re-run install.py."
        )
        ok = False
    else:
        print(f"  {PASS} openclaw on PATH ({found})")

        # openclaw --version
        cp = run([openclaw_bin, "--version"], verbose=verbose)
        if cp.returncode == 0:
            ver = (cp.stdout or cp.stderr).strip().splitlines()[0] if (cp.stdout or cp.stderr) else "?"
            print(f"  {PASS} openclaw --version → {ver}")
        else:
            print(f"  {FAIL} `openclaw --version` failed (exit {cp.returncode})")
            if cp.stderr.strip():
                print(f"     {cp.stderr.strip()}")
            ok = False

        # openclaw agents bindings (need at least one feishu binding)
        cp = run([openclaw_bin, "agents", "bindings"], verbose=verbose)
        if cp.returncode != 0:
            print(f"  {FAIL} `openclaw agents bindings` failed (exit {cp.returncode})")
            print("     Run `openclaw onboard` to bind a Lark/Feishu agent first.")
            ok = False
        elif "feishu" in cp.stdout.lower() or "lark" in cp.stdout.lower():
            print(f"  {PASS} at least one Feishu/Lark agent binding present")
        else:
            print(f"  {FAIL} no feishu/lark binding found in `openclaw agents bindings`")
            print("     Run `openclaw onboard` to bind your Lark app first.")
            ok = False

    # Skill directories
    for skill in SKILL_ORDER:
        good, msg = check_skill_dir(skill)
        if good:
            print(f"  {PASS} skill dir present: {skill}")
        else:
            print(f"  {FAIL} skill dir invalid: {skill} — {msg}")
            ok = False

    print()
    return ok


# ---------------------------------------------------------------------------
# Install / verify
# ---------------------------------------------------------------------------


def already_installed(skill: str, listing: str) -> bool:
    """Return True if `skill` appears as a token on its own line of `listing`."""
    for line in listing.splitlines():
        # match the skill name as a whole token on the line
        if re.search(rf"(?<![\w-]){re.escape(skill)}(?![\w-])", line):
            return True
    return False


def get_installed_listing(openclaw_bin: str, verbose: bool) -> str:
    cmd = [openclaw_bin] + OPENCLAW_LIST_CMD[1:]
    cp = run(cmd, verbose=verbose)
    if cp.returncode != 0:
        return ""
    return cp.stdout or ""


def install_skill(
    skill: str,
    openclaw_bin: str,
    dry_run: bool,
    verbose: bool,
    already: bool,
) -> bool:
    skill_path = str(REPO_ROOT / skill)
    base_cmd = [openclaw_bin] + OPENCLAW_INSTALL_CMD[1:]

    if already:
        # Best-effort upgrade; if --upgrade is unsupported, fall back to plain install.
        upgrade_cmd = base_cmd + ["--upgrade", skill_path]
        plain_cmd = base_cmd + [skill_path]
        if dry_run:
            print(f"  {WARN} [dry-run] {skill} already installed; would run: {' '.join(upgrade_cmd)}")
            return True
        cp = run(upgrade_cmd, verbose=verbose)
        if cp.returncode == 0:
            print(f"  {PASS} {skill} re-installed (--upgrade)")
            return True
        # Detect "unknown flag" style errors and retry without --upgrade.
        combined = (cp.stdout + "\n" + cp.stderr).lower()
        if any(s in combined for s in ("unknown", "unrecognized", "no such option", "invalid")):
            cp = run(plain_cmd, verbose=verbose)
            if cp.returncode == 0:
                print(f"  {PASS} {skill} re-installed (no --upgrade flag; plain install)")
                return True
        print(f"  {FAIL} {skill} re-install failed (exit {cp.returncode})")
        if cp.stderr.strip():
            print(f"     {cp.stderr.strip()}")
        return False

    cmd = base_cmd + [skill_path]
    if dry_run:
        print(f"  {WARN} [dry-run] would run: {' '.join(cmd)}")
        return True
    cp = run(cmd, verbose=verbose)
    if cp.returncode == 0:
        print(f"  {PASS} {skill} installed")
        return True
    print(f"  {FAIL} {skill} install failed (exit {cp.returncode})")
    if cp.stdout.strip():
        print(f"     stdout: {cp.stdout.strip()}")
    if cp.stderr.strip():
        print(f"     stderr: {cp.stderr.strip()}")
    return False


def install_all(openclaw_bin: str, dry_run: bool, verbose: bool) -> bool:
    print(bold("Installing skills"))
    listing = "" if dry_run else get_installed_listing(openclaw_bin, verbose)
    for skill in SKILL_ORDER:
        already = already_installed(skill, listing)
        if not install_skill(skill, openclaw_bin, dry_run, verbose, already):
            print()
            print(red("Aborting: skill install failed. Fix the error above and re-run."))
            return False
    print()
    return True


def verify_installed(openclaw_bin: str, verbose: bool) -> bool:
    print(bold("Verifying install"))
    listing = get_installed_listing(openclaw_bin, verbose)
    if not listing:
        print(f"  {FAIL} `openclaw skills list` returned no output or failed.")
        return False
    missing = [s for s in SKILL_ORDER if not already_installed(s, listing)]
    if missing:
        print(f"  {FAIL} missing from registry: {', '.join(missing)}")
        return False
    for s in SKILL_ORDER:
        print(f"  {PASS} registered: {s}")
    print()
    return True


# ---------------------------------------------------------------------------
# Final message
# ---------------------------------------------------------------------------


def print_next_steps() -> None:
    print(green(bold("✅ leads-hunt-pack installed.")))
    print()
    print("Next steps (do these in your Lark DM with your agent):")
    print('  1. Say: "set me up for leads hunt"')
    print(
        "     → leads-hunt-setup wizard runs (~30 min, walks through LinkedIn login, "
        "BD SSO, topic config, cron jobs)"
    )
    print("  2. Once setup completes, your daily Lark digest fires at 09:30 (server tz).")
    print(
        '  3. To teach the agent your outreach voice, say: '
        '"add this to my voice: <paste a real message>"'
    )
    print('  4. To add a new lead-gen target, say: "add a new target topic"')
    print()
    print("For troubleshooting see leads-hunt-setup/references/troubleshooting.md.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="install.py",
        description="One-shot installer for the leads-hunt-pack OpenClaw skills.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "After success, open Lark and tell your agent: "
            '"set me up for leads hunt".'
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run prereq checks and print install commands but do not register skills.",
    )
    p.add_argument(
        "--skip-prereq-check",
        action="store_true",
        help="Skip prerequisite checks. Development only — your install may fail later.",
    )
    p.add_argument(
        "--openclaw-bin",
        default="openclaw",
        metavar="PATH",
        help="Override the openclaw binary location (default: PATH lookup).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print full subprocess stdout/stderr for each step.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    banner()

    if args.skip_prereq_check:
        print(yellow("⚠ --skip-prereq-check enabled (development only)"))
        print()
    else:
        if not prereq_checks(args.openclaw_bin, args.verbose):
            print(red("Prerequisite checks failed. Resolve the items above and re-run."))
            print(
                "Re-run with --skip-prereq-check to bypass (development only), "
                "or --dry-run to preview the install commands."
            )
            return 1

    if not install_all(args.openclaw_bin, args.dry_run, args.verbose):
        return 1

    if args.dry_run:
        print(yellow("Dry run complete. No skills were registered."))
        return 0

    if not verify_installed(args.openclaw_bin, args.verbose):
        print(red("Verification failed. Some skills did not register."))
        print("Try re-running install.py, or pass --verbose for more detail.")
        return 1

    print_next_steps()
    return 0


if __name__ == "__main__":
    sys.exit(main())
