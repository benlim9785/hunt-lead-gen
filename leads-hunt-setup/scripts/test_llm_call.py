#!/usr/bin/env python3
"""Validate the configured LLM provider key with a minimal "respond with: ok" call.

Reads <workspace>/leads-hunt/.env, looks for LLM_PROVIDER (one of: openai,
anthropic, bedrock) and the corresponding key(s). Makes one tiny call.

Exit 0 on success, 1 on auth/transport failure, 2 on misconfig.

Stdlib + `urllib` only — no third-party SDK assumed. For bedrock, falls back
to `boto3` if available; otherwise prints a clear "install boto3" hint.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_env(path: Path) -> dict[str, str]:
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


def _post_json(url: str, headers: dict, body: dict, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace") if e.fp else str(e)
    except (urllib.error.URLError, OSError) as e:
        return 0, f"transport-error: {e}"


def test_openai(env: dict[str, str]) -> int:
    key = env.get("OPENAI_API_KEY")
    if not key:
        print("❌ OPENAI_API_KEY missing from .env", file=sys.stderr)
        return 2
    code, body = _post_json(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {
            "model": env.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": "respond with: ok"}],
            "max_tokens": 5,
        },
    )
    return _verdict("openai", code, body)


def test_anthropic(env: dict[str, str]) -> int:
    key = env.get("ANTHROPIC_API_KEY")
    if not key:
        print("❌ ANTHROPIC_API_KEY missing from .env", file=sys.stderr)
        return 2
    code, body = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {
            "model": env.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "respond with: ok"}],
        },
    )
    return _verdict("anthropic", code, body)


def test_bedrock(env: dict[str, str]) -> int:
    if not env.get("AWS_ACCESS_KEY_ID") or not env.get("AWS_SECRET_ACCESS_KEY"):
        print("❌ AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY missing from .env", file=sys.stderr)
        return 2
    try:
        import boto3  # type: ignore
    except ImportError:
        print("❌ bedrock test requires `pip install boto3` (or use a different provider)", file=sys.stderr)
        return 2
    region = env.get("AWS_REGION", "us-east-1")
    model = env.get("BEDROCK_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0")
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        )
        resp = client.converse(
            modelId=model,
            messages=[{"role": "user", "content": [{"text": "respond with: ok"}]}],
            inferenceConfig={"maxTokens": 8},
        )
        text = resp.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
        print(f"✅ bedrock OK (model={model}, region={region}): {text!r}")
        return 0
    except Exception as e:
        print(f"❌ bedrock failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def _verdict(provider: str, code: int, body: str) -> int:
    if 200 <= code < 300:
        print(f"✅ {provider} OK ({code})")
        return 0
    snippet = body[:200].replace("\n", " ")
    print(f"❌ {provider} failed (HTTP {code}): {snippet}", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", help="Override OPENCLAW_WORKSPACE")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser() if args.workspace else Path(
        os.environ.get("OPENCLAW_WORKSPACE") or Path.home() / ".openclaw" / "workspace"
    )
    env_path = (workspace / "leads-hunt" / ".env").resolve()
    env = _load_env(env_path)
    if not env:
        print(f"❌ {env_path} not found or empty — run write_env.py first", file=sys.stderr)
        return 2

    provider = (env.get("LLM_PROVIDER") or "").lower().strip()
    if not provider:
        # Infer from which key is present.
        if "OPENAI_API_KEY" in env:
            provider = "openai"
        elif "ANTHROPIC_API_KEY" in env:
            provider = "anthropic"
        elif "AWS_ACCESS_KEY_ID" in env:
            provider = "bedrock"
        else:
            print("❌ no LLM_PROVIDER set and no recognizable key in .env", file=sys.stderr)
            return 2

    if provider == "openai":
        return test_openai(env)
    if provider == "anthropic":
        return test_anthropic(env)
    if provider == "bedrock":
        return test_bedrock(env)
    print(f"❌ unsupported LLM_PROVIDER={provider!r} (want: openai|anthropic|bedrock)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
