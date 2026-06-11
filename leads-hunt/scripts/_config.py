"""Shared config loader for leads-hunt scripts.

Resolves `{SKILL_DIR}` and `{LEADS_HUNT_HOME}` placeholder paths to absolute paths.
Single source — every script imports `load_config()` from here.

Config layout:
  - Shared skill defaults live in `<skill>/scripts/config.json`
  - Per-AE mutable overrides live in `<LEADS_HUNT_HOME>/config.json`

This keeps runtime state like Lark Base IDs out of the installed shared skill while
still giving every script one merged config object.

Path resolution:
  LEADS_HUNT_HOME = $OPENCLAW_WORKSPACE/leads-hunt (default: ~/.openclaw/workspace/leads-hunt)
  Override via the --home CLI arg on each script (sets LEADS_HUNT_HOME env var
  before load_config() is called).

The home directory holds per-AE state:
  $LEADS_HUNT_HOME/
    kb.md                 — knowledge base (shipped leads, patterns)
    browser-profile/      — Chromium persistent context (Sales Nav SSO)
    data/candidates/      — Phase B output JSONs
    data/lead-gen/        — Phase C/D CSVs + run logs
    .env                  — LK_*, BD_*, LARK_* credentials
    config.json           — per-AE overrides (Lark Base IDs, workflow URL, etc.)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent  # leads-hunt/
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.json"
WORKSPACE_CONFIG_NAME = "config.json"


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


def _resolve_placeholders(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in mapping.items():
            value = value.replace(key, replacement)
        return value
    if isinstance(value, dict):
        return {k: _resolve_placeholders(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_placeholders(v, mapping) for v in value]
    return value


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    return override if override is not None else base


def _workspace_config_path(home: Path) -> Path:
    return home / WORKSPACE_CONFIG_NAME


def load_config() -> dict:
    home = resolve_home()
    mapping = {
        "{SKILL_DIR}": str(SKILL_DIR),
        "{LEADS_HUNT_HOME}": str(home),
    }

    cfg = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    cfg = _resolve_placeholders(cfg, mapping)

    workspace_cfg_path = _workspace_config_path(home)
    if workspace_cfg_path.exists():
        workspace_cfg = json.loads(workspace_cfg_path.read_text(encoding="utf-8"))
        workspace_cfg = _resolve_placeholders(workspace_cfg, mapping)
        cfg = _deep_merge(cfg, workspace_cfg)

    cfg["_leads_hunt_home"] = str(home)
    cfg["_workspace_config_path"] = str(workspace_cfg_path)
    return cfg
