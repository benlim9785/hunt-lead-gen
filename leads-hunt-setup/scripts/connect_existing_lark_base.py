#!/usr/bin/env python3
"""Bind an existing leads-hunt Lark Base to the local workspace and webhook.

Use this when the Base already exists and you want to:
- resolve the 4 expected table IDs
- create or update the draft-generation workflow
- enable that workflow
- persist the Base + webhook metadata to <workspace>/leads-hunt/config.json
- initialize <workspace>/leads-hunt/style.md if it is missing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from create_lark_base import (  # noqa: E402
    WORKFLOW_NAME,
    _build_workflow_body,
    _deep_merge,
    _extract_workflow_id,
    _load_existing_config,
    resolve_workspace,
)

TABLE_NAME_BY_KEY = {
    "leads": "Leads",
    "customers": "Customers",
    "skip_list": "Skip List",
    "discovery_patterns": "Discovery Patterns",
}
STYLE_SKELETON = (
    SCRIPT_DIR.parent.parent / "leads-hunt-voice" / "references" / "empty-skeleton.md"
)


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {}
    start = stdout.find("{")
    if start > 0:
        stdout = stdout[start:]
    return json.loads(stdout)


def _base_cli(*args: str) -> dict[str, Any]:
    return _run(["lark-cli", "base", *args])


def _leads_home(workspace: Path) -> Path:
    return workspace / "leads-hunt"


def _workspace_config_path(workspace: Path) -> Path:
    return _leads_home(workspace) / "config.json"


def _ensure_style_file(workspace: Path) -> Path:
    home = _leads_home(workspace)
    home.mkdir(parents=True, exist_ok=True)
    style_path = home / "style.md"
    if style_path.exists():
        return style_path
    style_path.write_text(STYLE_SKELETON.read_text(encoding="utf-8"), encoding="utf-8")
    return style_path


def _resolve_tables(base_token: str) -> dict[str, dict[str, str]]:
    listed = _base_cli("+table-list", "--base-token", base_token)
    tables = ((listed.get("data") or {}).get("tables") or [])
    by_name = {str(item.get("name") or ""): str(item.get("id") or "") for item in tables}
    resolved: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for key, name in TABLE_NAME_BY_KEY.items():
        table_id = by_name.get(name, "")
        if not table_id:
            missing.append(name)
            continue
        resolved[key] = {"id": table_id, "name": name}
    if missing:
        raise RuntimeError(f"Existing Base is missing required tables: {', '.join(missing)}")
    return resolved


def _find_workflow_id(base_token: str, workflow_name: str) -> str:
    payload = _base_cli("+workflow-list", "--base-token", base_token)
    items = ((payload.get("data") or {}).get("items") or [])
    for item in items:
        if str(item.get("title") or "") == workflow_name:
            return str(item.get("workflow_id") or "")
    return ""


def _ensure_workflow(base_token: str, leads_table_id: str, webhook_url: str) -> dict[str, Any]:
    workflow_body = _build_workflow_body(
        webhook_url=webhook_url,
        base_token=base_token,
        leads_table_id=leads_table_id,
    )
    existing_workflow_id = _find_workflow_id(base_token, WORKFLOW_NAME)
    if existing_workflow_id:
        update_body = {
            "title": workflow_body["title"],
            "steps": workflow_body["steps"],
        }
        _base_cli(
            "+workflow-update",
            "--base-token",
            base_token,
            "--workflow-id",
            existing_workflow_id,
            "--json",
            json.dumps(update_body, ensure_ascii=False),
        )
        workflow_id = existing_workflow_id
    else:
        created = _base_cli(
            "+workflow-create",
            "--base-token",
            base_token,
            "--json",
            json.dumps(workflow_body, ensure_ascii=False),
        )
        workflow_id = _extract_workflow_id(created)
        if not workflow_id:
            raise RuntimeError(f"Workflow create succeeded but no workflow id returned: {created}")

    enabled = _base_cli(
        "+workflow-enable",
        "--base-token",
        base_token,
        "--workflow-id",
        workflow_id,
    )
    status = str(((enabled.get("data") or {}).get("status") or "enabled"))
    return {
        "name": WORKFLOW_NAME,
        "id": workflow_id,
        "enabled": status == "enabled",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Override AIME_WORKSPACE_PATH")
    parser.add_argument("--base-token", required=True, help="Existing Lark Base token from the /base/<token> URL")
    parser.add_argument("--base-url", help="Optional exact Base URL to store in config.json")
    parser.add_argument("--webhook-url", required=True, help="Inbound webhook endpoint for Leads.Draft Message automation")
    args = parser.parse_args()

    workspace = resolve_workspace(args.workspace)
    home = _leads_home(workspace)
    home.mkdir(parents=True, exist_ok=True)
    style_path = _ensure_style_file(workspace)
    config_path = _workspace_config_path(workspace)
    existing = _load_existing_config(config_path)

    tables = _resolve_tables(args.base_token)
    workflow_meta = _ensure_workflow(args.base_token, tables["leads"]["id"], args.webhook_url)

    new_config = _deep_merge(
        existing,
        {
            "lark_base": {
                "base_token": args.base_token,
                "url": args.base_url or f"https://bytedance.my.larkoffice.com/base/{args.base_token}",
                "webhook_url": args.webhook_url,
                "tables": tables,
                "workflow": {
                    "draft_message_yes": workflow_meta,
                },
            }
        },
    )
    config_path.write_text(json.dumps(new_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "connected": True,
                "workspace": str(workspace),
                "workspace_config": str(config_path),
                "style_path": str(style_path),
                "lark_base": new_config["lark_base"],
                "updated_at_unix": int(time.time()),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
