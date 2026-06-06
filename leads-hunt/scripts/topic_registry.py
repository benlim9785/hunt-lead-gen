#!/usr/bin/env python3
"""
Topic registry for leads-hunt.

Topics are defined as markdown files at `references/topics/<slug>.md` with YAML
frontmatter. This module is the single source of truth for what topics exist
and their per-topic config.

Adding a new topic = drop one markdown file. No Python edits, no config edits.

Frontmatter schema (all fields except `slug` are optional):

    ---
    slug: aigc-visual
    display_name: Seedream + Seedance
    enabled: true
    ceiling: 5            # override global per_topic_ceiling
    score_floor: 8        # override global score_floor
    candidate_target: 18  # override global candidate_target_per_topic
    ---

Run as a script to print the resolved registry for sanity-checking:

    python3 topic_registry.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TOPICS_DIR = SKILL_DIR / "references" / "topics"

# Stdlib-only frontmatter parser. The format is trivial — three dashes,
# YAML-ish key:value lines, three dashes — and we don't need full YAML.
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*\n",
    re.DOTALL,
)


def _coerce(value: str):
    """Coerce a frontmatter string value to bool/int/str."""
    v = value.strip()
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    # Strip surrounding quotes if any
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v


def parse_frontmatter(text: str) -> dict:
    """Return a dict of frontmatter fields, or {} if no frontmatter block."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        # Strip inline comments after the value
        value = re.sub(r"\s+#.*$", "", value).strip()
        if not key:
            continue
        out[key] = _coerce(value)
    return out


def load_topics(cfg: dict | None = None, include_disabled: bool = False) -> list[dict]:
    """Walk references/topics/*.md and return resolved topic configs.

    Each returned dict has:
      slug, display_name, enabled, file_path, ceiling, score_floor, candidate_target

    Per-topic overrides from frontmatter take precedence; otherwise inherit from cfg.
    """
    if cfg is None:
        from _config import load_config
        cfg = load_config()

    defaults = {
        "ceiling": cfg.get("per_topic_ceiling", 5),
        "score_floor": cfg.get("score_floor", 8),
        "candidate_target": cfg.get("candidate_target_per_topic", 18),
    }

    out = []
    for path in sorted(TOPICS_DIR.glob("*.md")):
        text = path.read_text()
        fm = parse_frontmatter(text)
        # Files without a slug field are treated as legacy/unmigrated — skip
        # rather than guess from filename, so a typo in frontmatter fails loud.
        if "slug" not in fm:
            print(
                f"[topic_registry] WARN: {path.name} has no `slug` in frontmatter; skipping",
                file=sys.stderr,
            )
            continue
        slug = fm["slug"]
        # Filename should match slug — guard against drift
        expected_filename = f"{slug}.md"
        if path.name != expected_filename:
            print(
                f"[topic_registry] WARN: {path.name} declares slug={slug!r} (mismatch); skipping",
                file=sys.stderr,
            )
            continue

        enabled = bool(fm.get("enabled", True))
        if not enabled and not include_disabled:
            continue

        topic = {
            "slug": slug,
            "display_name": fm.get("display_name", slug),
            "enabled": enabled,
            "file_path": str(path),
            "ceiling": fm.get("ceiling", defaults["ceiling"]),
            "score_floor": fm.get("score_floor", defaults["score_floor"]),
            "candidate_target": fm.get("candidate_target", defaults["candidate_target"]),
        }
        out.append(topic)
    return out


def topic_slugs(cfg: dict | None = None) -> list[str]:
    """Convenience: just the enabled topic slugs."""
    return [t["slug"] for t in load_topics(cfg)]


def enabled_topics(cfg: dict | None = None) -> list[dict]:
    """Alias for load_topics(cfg) (only enabled topics by default)."""
    return load_topics(cfg)


def get_topic(slug: str, cfg: dict | None = None) -> dict | None:
    """Look up a single topic by slug. Returns None if not found or disabled."""
    for t in load_topics(cfg):
        if t["slug"] == slug:
            return t
    return None


def cfg_for_topic(cfg: dict, topic_slug: str) -> dict:
    """Return a config dict with per-topic overrides applied.

    The returned dict is a shallow copy of `cfg` with `score_floor`,
    `per_topic_ceiling`, and `candidate_target_per_topic` resolved to the
    topic-specific values. Use this in scripts that previously read globals
    directly so per-topic overrides Just Work.
    """
    t = get_topic(topic_slug, cfg)
    if t is None:
        return cfg
    merged = dict(cfg)
    merged["score_floor"] = t["score_floor"]
    merged["per_topic_ceiling"] = t["ceiling"]
    merged["candidate_target_per_topic"] = t["candidate_target"]
    return merged


def main() -> int:
    """Print the resolved registry as JSON for sanity-checking."""
    topics = load_topics(include_disabled=True)
    enabled = [t for t in topics if t["enabled"]]
    print(json.dumps({
        "topics_dir": str(TOPICS_DIR),
        "total": len(topics),
        "enabled": len(enabled),
        "registry": topics,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
