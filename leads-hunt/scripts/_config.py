"""Shared config loader for leads-hunt scripts.

Resolves `{SKILL_DIR}` and `{LEADS_HUNT_HOME}` placeholder paths to absolute paths.
Single source — every script imports `load_config()` from here.

Path resolution:
  LEADS_HUNT_HOME = $OPENCLAW_WORKSPACE/leads-hunt (default: ~/.openclaw/workspace/leads-hunt)
  Override via the --home CLI arg on each script (sets LEADS_HUNT_HOME env var
  before load_config() is called).

The home directory holds per-AE state:
  $LEADS_HUNT_HOME/
    kb.md                 — knowledge base (shipped leads, patterns)  [Phase 2]
    browser-profile/      — Chromium persistent context (Sales Nav SSO)
    data/candidates/      — Phase B output JSONs
    data/lead-gen/        — Phase C/D CSVs + run logs
    .env                  — LK_*, BD_*, LARK_* credentials
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent  # leads-hunt/
CONFIG_PATH = SCRIPT_DIR / "config.json"


def resolve_home() -> Path:
    """Resolve LEADS_HUNT_HOME from environment, with OpenClaw workspace default.

    Resolution order:
      1. $LEADS_HUNT_HOME (explicit override; set by --home CLI arg or shell)
      2. $OPENCLAW_WORKSPACE/leads-hunt
      3. ~/.openclaw/workspace/leads-hunt
    """
    explicit = os.environ.get("LEADS_HUNT_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    workspace = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
    return (Path(workspace) / "leads-hunt").resolve()


def _resolve_placeholders(value, mapping):
    if isinstance(value, str):
        for k, v in mapping.items():
            value = value.replace(k, v)
        return value
    if isinstance(value, dict):
        return {k: _resolve_placeholders(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_placeholders(v, mapping) for v in value]
    return value


def load_config() -> dict:
    cfg = json.loads(CONFIG_PATH.read_text())
    home = resolve_home()
    cfg = _resolve_placeholders(cfg, {
        "{SKILL_DIR}": str(SKILL_DIR),
        "{LEADS_HUNT_HOME}": str(home),
    })
    cfg["_leads_hunt_home"] = str(home)
    return cfg
