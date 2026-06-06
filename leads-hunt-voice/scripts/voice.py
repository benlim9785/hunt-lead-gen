#!/usr/bin/env python3
"""voice.py — conversational style.md editor for the leads-hunt-voice skill.

Reads `<workspace>/leads-hunt/style.md`, where `<workspace>` is resolved from
the `LEADS_HUNT_HOME` env var (default `~/.openclaw/workspace/leads-hunt`).

The path resolution is intentionally identical to leads-hunt-outreach so both
skills agree on which file is "the voice file".

All write operations are atomic: write to <path>.tmp, fsync, os.replace.
Stdlib only.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# Allow running as a script ("python3 voice.py ...") from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_section  # noqa: E402


# ---------------------------------------------------------------------------
# Headings used by the schema. Keep these in sync with references/style-schema.md.
# ---------------------------------------------------------------------------
H_RHYTHM = "## Rhythm & cadence (used by drafting)"
H_VOCAB = "## Vocabulary do's and don'ts (used by drafting)"
H_DO = "### Do use"
H_DONT = "### Avoid"
H_SAMPLES = "## Real outreach samples (used by drafting)"
H_NOTES = "## Voice notes (NOT used by drafting; AE freeform notes)"

SKELETON_PATH = Path(__file__).resolve().parent.parent / "references" / "empty-skeleton.md"


# ---------------------------------------------------------------------------
# Path resolution + atomic IO
# ---------------------------------------------------------------------------

def workspace_root() -> Path:
    home = os.environ.get("LEADS_HUNT_HOME")
    if home:
        return Path(home).expanduser()
    return Path("~/.openclaw/workspace/leads-hunt").expanduser()


def style_path() -> Path:
    return workspace_root() / "style.md"


def atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically. Creates parents if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_skeleton() -> str:
    return SKELETON_PATH.read_text(encoding="utf-8")


def read_style_or_die() -> str:
    p = style_path()
    if not p.exists():
        sys.stderr.write(
            f"[voice] style.md not found at {p}. Run `voice.py init` first.\n"
        )
        sys.exit(2)
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_init(args) -> int:
    p = style_path()
    if p.exists() and not args.force:
        sys.stderr.write(f"[voice] {p} already exists. Pass --force to overwrite.\n")
        return 1
    atomic_write(p, read_skeleton())
    print(f"[voice] initialized {p}")
    return 0


def cmd_show(args) -> int:
    p = style_path()
    if not p.exists():
        sys.stderr.write(f"[voice] style.md not found at {p}. Run `voice.py init` first.\n")
        return 2
    sys.stdout.write(p.read_text(encoding="utf-8"))
    return 0


def _read_stdin_content(arg_value: str) -> str:
    if arg_value != "-":
        sys.stderr.write("[voice] --content must be '-' (read from stdin).\n")
        sys.exit(2)
    return sys.stdin.read()


def cmd_add_sample(args) -> int:
    body = _read_stdin_content(args.content).strip("\n")
    if not body:
        sys.stderr.write("[voice] empty sample, refusing.\n")
        return 1

    text = read_style_or_die()

    # Build the sample block.
    heading = f"### {args.date}"
    if args.annotation:
        heading += f" — {args.annotation}"
    block_lines = [heading, "", "```", body, "```", ""]
    block = "\n".join(block_lines)

    # Idempotency: skip if exact block already present in the samples section.
    samples_body = parse_section.read_section(text, H_SAMPLES)
    if samples_body is None:
        sys.stderr.write(f"[voice] heading not found: {H_SAMPLES}. Reset/init?\n")
        return 1
    if block.strip() in samples_body:
        print(f"[voice] sample already present (date {args.date}); skipped")
        return 0

    # If the section body is just the placeholder italic line, replace it.
    samples_stripped = samples_body.strip()
    placeholder = samples_stripped.startswith("_(") and samples_stripped.endswith(")_")
    if placeholder or samples_stripped == "":
        new_body = "\n" + block + "\n"
        new_text = parse_section.replace_section(text, H_SAMPLES, new_body)
    else:
        new_text = parse_section.append_under_heading(text, H_SAMPLES, block)

    # Round-trip check.
    if parse_section.read_section(new_text, H_SAMPLES) is None:
        sys.stderr.write("[voice] internal error: section parse broke after edit. aborting.\n")
        return 3

    atomic_write(style_path(), new_text)
    print(f"[voice] added sample dated {args.date}")
    return 0


def cmd_set_rhythm(args) -> int:
    body = _read_stdin_content(args.content).strip("\n")
    if not body:
        sys.stderr.write("[voice] empty rhythm body, refusing.\n")
        return 1

    text = read_style_or_die()
    if parse_section.read_section(text, H_RHYTHM) is None:
        sys.stderr.write(f"[voice] heading not found: {H_RHYTHM}. Reset/init?\n")
        return 1

    new_body = "\n" + body + "\n\n"
    new_text = parse_section.replace_section(text, H_RHYTHM, new_body)
    if parse_section.read_section(new_text, H_RHYTHM) is None:
        sys.stderr.write("[voice] internal error: section parse broke after edit. aborting.\n")
        return 3

    atomic_write(style_path(), new_text)
    print("[voice] rhythm updated")
    return 0


def _add_bullet(heading: str, phrase: str, label: str) -> int:
    phrase = phrase.strip()
    if not phrase:
        sys.stderr.write(f"[voice] empty {label}, refusing.\n")
        return 1

    text = read_style_or_die()
    body = parse_section.read_section(text, heading)
    if body is None:
        sys.stderr.write(f"[voice] heading not found: {heading}. Reset/init?\n")
        return 1

    bullet = f"- {phrase}"

    # Idempotency.
    for ln in body.splitlines():
        if ln.strip() == bullet:
            print(f'[voice] {label} already present: "{phrase}"; skipped')
            return 0

    # If body is just the placeholder italic, replace it with a fresh bullet list.
    body_stripped = body.strip()
    placeholder = body_stripped.startswith("_(") and body_stripped.endswith(")_")
    if placeholder or body_stripped == "":
        new_body = "\n" + bullet + "\n\n"
        new_text = parse_section.replace_section(text, heading, new_body)
    else:
        new_text = parse_section.append_under_heading(text, heading, bullet)

    if parse_section.read_section(new_text, heading) is None:
        sys.stderr.write("[voice] internal error: section parse broke after edit. aborting.\n")
        return 3

    atomic_write(style_path(), new_text)
    print(f'[voice] added {label}: "{phrase}"')
    return 0


def cmd_add_do(args) -> int:
    return _add_bullet(H_DO, args.text, "do")


def cmd_add_dont(args) -> int:
    return _add_bullet(H_DONT, args.text, "don't")


def cmd_reset(args) -> int:
    if not args.confirm_twice:
        sys.stderr.write(
            "[voice] reset refuses without --confirm-twice "
            "(the agent should ask the AE twice before invoking this).\n"
        )
        return 1
    p = style_path()
    if p.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup = p.with_name(f"{p.name}.bak-{ts}")
        backup.write_bytes(p.read_bytes())
        print(f"[voice] backed up existing style.md → {backup.name}")
    atomic_write(p, read_skeleton())
    print(f"[voice] reset {p} to empty skeleton")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voice.py",
        description="Edit the AE's leads-hunt style.md (writing voice file).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="Write empty skeleton if missing")
    s.add_argument("--force", action="store_true", help="Overwrite if exists")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("show", help="Print current style.md to stdout")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("add-sample", help="Append a real outreach sample")
    s.add_argument("--date", required=True, help="YYYY-MM-DD")
    s.add_argument("--annotation", default=None, help="optional context, e.g. 'replied in 4hrs'")
    s.add_argument("--content", required=True, help="must be '-' (reads from stdin)")
    s.set_defaults(func=cmd_add_sample)

    s = sub.add_parser("set-rhythm", help="Replace the Rhythm & cadence section body")
    s.add_argument("--content", required=True, help="must be '-' (reads from stdin)")
    s.set_defaults(func=cmd_set_rhythm)

    s = sub.add_parser("add-do", help="Append a bullet to Do use")
    s.add_argument("text", help="phrase to allow")
    s.set_defaults(func=cmd_add_do)

    s = sub.add_parser("add-dont", help="Append a bullet to Avoid")
    s.add_argument("text", help="phrase to ban")
    s.set_defaults(func=cmd_add_dont)

    s = sub.add_parser("reset", help="Overwrite with empty skeleton (backs up first)")
    s.add_argument("--confirm-twice", action="store_true", help="required")
    s.set_defaults(func=cmd_reset)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
