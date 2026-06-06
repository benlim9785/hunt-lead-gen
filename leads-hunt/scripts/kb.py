"""Markdown KB helper for leads-hunt (stdlib-only).

Replaces the legacy ClawMander HTTP-backed leads/customers DB with a plain
markdown file at ``<LEADS_HUNT_HOME>/kb.md``.

Public API (called from dedup_pipeline.py, deliver_lark.py, discover.py):
    - already_seen(name, cfg) -> bool
    - append_shipped(rows, today, cfg) -> int
    - read_recent_patterns(topic, days, cfg) -> dict | None

The kb.md sections we touch::

    ## Customers           # one bullet per active/churned customer
    ## Shipped Leads       # append-only, one bullet per shipped lead
    ## Skip List           # freeform AE notes (NOT parsed by dedup)
    ## Discovery Patterns Learned
        ### YYYY-MM-DD <topic>
        - good: <bullet>
        - bad:  <bullet>

CLI (manual debugging):
    python3 kb.py init
    python3 kb.py check "Foobar AI Inc"
    python3 kb.py recent aigc-visual 14
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

# Strip these legal/biz suffix tokens (matched as whole trailing words after
# punctuation has already been stripped). Order matters: longer first.
_SUFFIX_RE = re.compile(
    r"\s+(?:incorporated|inc|corporation|corp|company|co|llc|ltd|limited|ai)$",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s-]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _normalise(name: str) -> str:
    """Lowercase, strip punctuation+hyphens, drop legal/AI suffixes, collapse ws.

    Hyphens and underscores are treated as word separators so the on-disk slug
    ``foobar-ai`` and the human form ``Foobar AI Inc`` both collapse to
    ``foobar`` — round-trip safe.

    Examples:
        'Foobar AI Inc.'  -> 'foobar'
        'foobar-ai'       -> 'foobar'
        'Acme-Corp, LLC'  -> 'acme corp'
        'Globex Co.'      -> 'globex'
    """
    if not name:
        return ""
    s = name.strip().lower()
    # Hyphens / underscores -> spaces so suffix stripping sees them as words.
    s = re.sub(r"[-_]+", " ", s)
    # Replace remaining punctuation with space (keeps ASCII + unicode letters).
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    # Strip trailing suffixes repeatedly (handles e.g. 'foo ai inc' -> 'foo').
    prev = None
    while prev != s:
        prev = s
        s = _SUFFIX_RE.sub("", s).strip()
    return s


def _slug(name: str) -> str:
    """Slugify a normalised name for use in markdown bullets (spaces -> '-')."""
    return _normalise(name).replace(" ", "-")


# ---------------------------------------------------------------------------
# Path / file helpers
# ---------------------------------------------------------------------------

def _kb_path(cfg: dict) -> Path:
    """Resolve <LEADS_HUNT_HOME>/kb.md from cfg (or env var fallback)."""
    home = None
    paths = cfg.get("paths") if isinstance(cfg, dict) else None
    if isinstance(paths, dict):
        home = paths.get("leads_hunt_home")
    if not home and isinstance(cfg, dict):
        home = cfg.get("_leads_hunt_home")
    if not home:
        home = os.environ.get(
            "LEADS_HUNT_HOME",
            os.path.expanduser("~/.openclaw/workspace/leads-hunt"),
        )
    return Path(home) / "kb.md"


_SKELETON = """\
# leads-hunt knowledge base

This file is the source of truth for dedup (Layer 2) and Phase B's pattern-learning brief.
Do NOT delete sections; the dedup pipeline depends on them. Edit freely otherwise.

## Customers

## Shipped Leads

## Skip List

## Discovery Patterns Learned
"""


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically (tmp + fsync + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kb-", suffix=".tmp", dir=str(path.parent))
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


def _ensure_skeleton(path: Path) -> str:
    """Create kb.md with the H2 skeleton if missing. Returns current text."""
    if not path.exists():
        _atomic_write(path, _SKELETON)
        return _SKELETON
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*-\s+(.*)$")


def _split_sections(text: str) -> dict:
    """Split markdown into a dict of H2 title -> list of body lines (verbatim).

    Header lines themselves are NOT included in the body lists.
    """
    sections: dict = {}
    current = None
    body: list = []
    for line in text.splitlines():
        m = _H2_RE.match(line)
        if m:
            if current is not None:
                sections[current] = body
            current = m.group(1).strip()
            body = []
        else:
            if current is not None:
                body.append(line)
    if current is not None:
        sections[current] = body
    return sections


def _bullet_first_token(line: str) -> str:
    """Extract the first ' · '-separated token from a bullet line (the name slug).

    Returns '' if the line isn't a recognisable bullet.
    """
    m = _BULLET_RE.match(line)
    if not m:
        return ""
    body = m.group(1)
    # Lines look like:  acme-corp · 2025-12-01 · status=active
    head = body.split("·", 1)[0].strip()
    return head


def _names_from_section(lines: list) -> set:
    """Return a set of normalised names from bullets in a section."""
    out = set()
    for line in lines:
        head = _bullet_first_token(line)
        if not head:
            continue
        out.add(_normalise(head))
    return out


# ---------------------------------------------------------------------------
# already_seen — with per-process mtime cache
# ---------------------------------------------------------------------------

# Cache: (str(path), mtime_ns) -> frozenset[str]
_SEEN_CACHE: dict = {}


def _load_seen(path: Path) -> set:
    """Load the union of normalised names from ## Customers + ## Shipped Leads.

    Cached by (path, mtime_ns). Returns an empty set if the file doesn't exist.
    """
    if not path.exists():
        return set()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return set()
    key = (str(path), mtime)
    cached = _SEEN_CACHE.get(key)
    if cached is not None:
        return set(cached)
    text = path.read_text(encoding="utf-8")
    sections = _split_sections(text)
    names = set()
    names |= _names_from_section(sections.get("Customers", []))
    names |= _names_from_section(sections.get("Shipped Leads", []))
    _SEEN_CACHE[key] = frozenset(names)
    return names


def _invalidate_cache(path: Path) -> None:
    """Drop any cached entries for this path (called after writes)."""
    p = str(path)
    for k in [k for k in _SEEN_CACHE if k[0] == p]:
        _SEEN_CACHE.pop(k, None)


def already_seen(name: str, cfg: dict) -> bool:
    """True if ``name`` (normalised) appears in ## Customers or ## Shipped Leads.

    Reads ``<LEADS_HUNT_HOME>/kb.md``. If the file is missing returns False
    (this is not an error — fresh AE setup is a valid state).
    """
    norm = _normalise(name)
    if not norm:
        return False
    path = _kb_path(cfg)
    return norm in _load_seen(path)


# ---------------------------------------------------------------------------
# append_shipped
# ---------------------------------------------------------------------------

def append_shipped(rows: list, today: str, cfg: dict) -> int:
    """Append shipped leads to ## Shipped Leads. Idempotent on normalised name.

    Each row is a dict with at least: company, topic, score.
    Returns the count of NEW rows appended (skips already-present names).
    """
    if not rows:
        return 0
    path = _kb_path(cfg)
    text = _ensure_skeleton(path)
    sections = _split_sections(text)
    existing_in_shipped = _names_from_section(sections.get("Shipped Leads", []))

    new_lines = []
    seen_in_batch = set()
    for row in rows:
        company = (row.get("company") or "").strip()
        if not company:
            continue
        norm = _normalise(company)
        if not norm or norm in existing_in_shipped or norm in seen_in_batch:
            continue
        seen_in_batch.add(norm)
        topic = (row.get("topic") or "").strip()
        score = row.get("score", "")
        bullet = f"- {_slug(company)} · {today} · topic={topic} · score={score}"
        new_lines.append(bullet)

    if not new_lines:
        return 0

    updated = _insert_under_section(text, "Shipped Leads", new_lines)
    _atomic_write(path, updated)
    _invalidate_cache(path)
    return len(new_lines)


def _insert_under_section(text: str, section: str, new_lines: list) -> str:
    """Insert `new_lines` at the end of the named H2 section (before next H2/EOF).

    If the section doesn't exist, append it (with header) at end of file.
    Preserves trailing blank line conventions.
    """
    out = text.splitlines(keepends=False)
    target = f"## {section}"
    # Find section header.
    start = -1
    for i, line in enumerate(out):
        if line.strip() == target:
            start = i
            break
    if start == -1:
        # Append the section.
        if out and out[-1].strip() != "":
            out.append("")
        out.append(target)
        out.append("")
        out.extend(new_lines)
        out.append("")
        return "\n".join(out) + ("\n" if not text.endswith("\n") or True else "")
    # Find end of section: next H2 or EOF.
    end = len(out)
    for j in range(start + 1, len(out)):
        if _H2_RE.match(out[j]):
            end = j
            break
    # Find last non-blank line within the section body.
    insert_at = end
    while insert_at > start + 1 and out[insert_at - 1].strip() == "":
        insert_at -= 1
    new_block = list(new_lines)
    # If body is empty (insert_at == start+1), drop a leading blank for tidiness.
    if insert_at == start + 1:
        # Section was empty: place a blank line then the bullets.
        new_block = [""] + new_block
    out[insert_at:insert_at] = new_block
    # Ensure a blank line separates from the next H2 (if any).
    rebuilt = "\n".join(out)
    if not rebuilt.endswith("\n"):
        rebuilt += "\n"
    return rebuilt


# ---------------------------------------------------------------------------
# read_recent_patterns
# ---------------------------------------------------------------------------

def read_recent_patterns(topic: str, days: int, cfg: dict) -> dict | None:
    """Pull dated H3 entries under ## Discovery Patterns Learned.

    Match rule:
      - H3 line is ``### YYYY-MM-DD <topic>`` with ``<topic>`` matching exactly
      - the date is within the last ``days`` days from today (inclusive)

    Returns None if kb.md missing or the section is empty/absent. Otherwise:
        {
          'window_days': int,
          'topic': str,
          'good': [...],   # dedup'd, most-recent-first
          'bad':  [...],
          'entry_count': int,
        }
    """
    path = _kb_path(cfg)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    sections = _split_sections(text)
    body = sections.get("Discovery Patterns Learned")
    if body is None or not any(line.strip() for line in body):
        return None

    cutoff = date.today() - timedelta(days=max(0, int(days)))

    # Walk H3 sub-blocks; each entry is (date, lines-of-body).
    entries: list = []  # list of (date_obj, [body_lines])
    cur_date = None
    cur_topic = None
    cur_body: list = []
    for line in body:
        m = _H3_RE.match(line)
        if m:
            if cur_date is not None and cur_topic == topic:
                entries.append((cur_date, cur_body))
            cur_body = []
            try:
                cur_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                cur_date = None
            cur_topic = m.group(2).strip()
        else:
            if cur_date is not None:
                cur_body.append(line)
    # Flush the last entry.
    if cur_date is not None and cur_topic == topic:
        entries.append((cur_date, cur_body))

    # Filter by age and sort most-recent-first.
    entries = [(d, b) for (d, b) in entries if d >= cutoff]
    entries.sort(key=lambda x: x[0], reverse=True)

    good: list = []
    bad: list = []
    seen_good: set = set()
    seen_bad: set = set()
    for _d, body_lines in entries:
        for line in body_lines:
            m = _BULLET_RE.match(line)
            if not m:
                continue
            text_after = m.group(1).strip()
            low = text_after.lower()
            if low.startswith("good:"):
                v = text_after[5:].strip()
                if v and v not in seen_good:
                    seen_good.add(v)
                    good.append(v)
            elif low.startswith("bad:"):
                v = text_after[4:].strip()
                if v and v not in seen_bad:
                    seen_bad.add(v)
                    bad.append(v)
            # else: silently ignore non-good/bad bullets

    return {
        "window_days": int(days),
        "topic": topic,
        "good": good,
        "bad": bad,
        "entry_count": len(entries),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv: list) -> int:
    if len(argv) < 2:
        print("usage: kb.py {init|check <name>|recent <topic> <days>}", file=sys.stderr)
        return 2
    # Build a minimal cfg that defers to env var / default via _kb_path.
    cfg: dict = {}
    cmd = argv[1]
    if cmd == "init":
        path = _kb_path(cfg)
        created = not path.exists()
        _ensure_skeleton(path)
        print(f"{'created' if created else 'exists'}: {path}")
        return 0
    if cmd == "check":
        if len(argv) < 3:
            print("usage: kb.py check <name>", file=sys.stderr)
            return 2
        print(already_seen(argv[2], cfg))
        return 0
    if cmd == "recent":
        if len(argv) < 4:
            print("usage: kb.py recent <topic> <days>", file=sys.stderr)
            return 2
        try:
            days = int(argv[3])
        except ValueError:
            print("days must be an integer", file=sys.stderr)
            return 2
        out = read_recent_patterns(argv[2], days, cfg)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
