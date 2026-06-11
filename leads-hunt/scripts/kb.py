"""Base-backed knowledge helper for leads-hunt (stdlib-only).

Public API (called from dedup_pipeline.py, deliver_lark.py, discover.py):
    - already_seen(name, cfg) -> bool
    - append_shipped(rows, today, cfg) -> int
    - read_recent_patterns(topic, days, cfg) -> dict | None

`kb.py` keeps the existing fuzzy company-name matching logic, but the source of
truth now lives in the configured Lark Base tables instead of the local
`<LEADS_HUNT_HOME>/kb.md` markdown file:

    - `already_seen()` reads **Customers** + **Leads** from Base
    - `append_shipped()` writes to **Leads** in Base
    - `read_recent_patterns()` reads **Discovery Patterns** from Base

CLI (manual debugging):
    python3 kb.py init
    python3 kb.py check "Foobar AI Inc"
    python3 kb.py recent aigc-visual 14
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _config import load_config  # noqa: E402

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


# Cache: (base_token, customers_table_id, leads_table_id) -> frozenset[str]
_SEEN_CACHE: dict[tuple[str, str, str], frozenset[str]] = {}


def _normalise(name: str) -> str:
    """Lowercase, strip punctuation+hyphens, drop legal/AI suffixes, collapse ws.

    Hyphens and underscores are treated as word separators so the slug
    ``foobar-ai`` and the human form ``Foobar AI Inc`` both collapse to
    ``foobar``.
    """
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[-_]+", " ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    prev = None
    while prev != s:
        prev = s
        s = _SUFFIX_RE.sub("", s).strip()
    return s


def _base_sync():
    try:
        import lark_base_sync  # type: ignore
        return lark_base_sync
    except ImportError:
        return None


def _cache_key(cfg: dict) -> tuple[str, str, str]:
    section = (cfg or {}).get("lark_base") or {}
    tables = section.get("tables") or {}
    return (
        str(section.get("base_token") or ""),
        str(((tables.get("customers") or {}).get("id") or "")),
        str(((tables.get("leads") or {}).get("id") or "")),
    )


# ---------------------------------------------------------------------------
# already_seen — Base-backed with per-process cache
# ---------------------------------------------------------------------------


def _load_seen(cfg: dict) -> set[str]:
    base_sync = _base_sync()
    if base_sync is None:
        return set()
    try:
        if not base_sync.is_configured(cfg):
            return set()
    except Exception:
        return set()

    key = _cache_key(cfg)
    cached = _SEEN_CACHE.get(key)
    if cached is not None:
        return set(cached)

    names: set[str] = set()
    for raw_name in base_sync.read_customer_names(cfg):
        norm = _normalise(raw_name)
        if norm:
            names.add(norm)
    for raw_name in base_sync.read_lead_names(cfg):
        norm = _normalise(raw_name)
        if norm:
            names.add(norm)

    _SEEN_CACHE[key] = frozenset(names)
    return names


def _invalidate_cache(cfg: dict) -> None:
    _SEEN_CACHE.pop(_cache_key(cfg), None)


def already_seen(name: str, cfg: dict) -> bool:
    """True if `name` fuzzy-matches an existing Base Customer or shipped Lead."""
    norm = _normalise(name)
    if not norm:
        return False
    return norm in _load_seen(cfg)


# ---------------------------------------------------------------------------
# Write shipped leads
# ---------------------------------------------------------------------------


def _first_present(d: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = d.get(key)
        if value not in (None, "", []):
            return value
    return default


def _lead_rows_for_base(rows: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    payload_rows: list[dict[str, Any]] = []
    for row in rows:
        company = str(_first_present(row, "company", "Company")).strip()
        if not company:
            continue
        payload_rows.append(
            {
                "company": company,
                "topic": str(_first_present(row, "topic", "Topic", "_topic")).strip(),
                "score": _first_present(row, "score", "Score", default=""),
                "sales_nav_url": _first_present(row, "sales_nav_url", "Sales Nav URL", "SalesNavURL", default=""),
                "linkedin_url": _first_present(row, "linkedin_url", "LinkedIn URL", "LinkedInURL", default=""),
                "summary": _first_present(row, "summary", "Summary", "OutreachAngle", default=""),
                "message_draft": _first_present(row, "message_draft", "Message Draft", default=""),
                "date": _first_present(row, "date", "Date", default=today),
                "status": _first_present(row, "status", "Status", default="New"),
                "draft_message": _first_present(row, "draft_message", "Draft Message", default="No"),
            }
        )
    return payload_rows


def append_shipped(rows: list[dict[str, Any]], today: str, cfg: dict) -> int:
    """Write shipped leads into the Base Leads table.

    Returns the number of newly created lead rows. Existing same-day rows are
    updated in place by `lark_base_sync.upsert_leads()`.
    """
    if not rows:
        return 0
    base_sync = _base_sync()
    if base_sync is None or not base_sync.is_configured(cfg):
        return 0
    result = base_sync.upsert_leads(cfg, _lead_rows_for_base(rows, today))
    _invalidate_cache(cfg)
    return int(result.get("created", 0))


# ---------------------------------------------------------------------------
# Discovery patterns
# ---------------------------------------------------------------------------


def read_recent_patterns(topic: str, days: int, cfg: dict) -> dict | None:
    """Read recent Discovery Patterns rows from Lark Base for a topic."""
    base_sync = _base_sync()
    if base_sync is None or not base_sync.is_configured(cfg):
        return None
    return base_sync.read_discovery_patterns(cfg, topic, days)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: kb.py {init|check <name>|recent <topic> <days>}", file=sys.stderr)
        return 2
    cfg = load_config()
    cmd = argv[1]
    if cmd == "init":
        print("kb.py no longer initializes a local kb.md; Lark Base is the source of truth.")
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
