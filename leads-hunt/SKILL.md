---
name: leads-hunt
description: "Daily lead-gen pipeline for BytePlus AEs: SSO check → topic-rotation discovery → 3-layer dedup → Lark digest. Runs on OpenClaw via cron. AE-portable; per-AE state in workspace; LinkedIn Sales Nav + BD-corp creds per AE."
version: 0.1.0
author: Ben Lim
license: MIT
---

# leads-hunt

Daily lead generation for BytePlus AIGC products (and any other product line the AE configures), with Sales Navigator CRM dedup. Surfaces up to 5 net-new companies per topic that are NOT already in BytePlus's Salesforce.

## Prerequisites

Before this skill works on a fresh OpenClaw install:

1. **`openclaw onboard`** completed — Lark channel bound (`openclaw agents bindings | grep feishu` shows a binding).
2. **`leads-hunt-setup`** run once — wizard creates `kb.md`, browser-profile, `.env` at `<workspace>/leads-hunt/`. Walks the AE through their own LinkedIn login + BD-corp Sales Nav SSO + LLM provider key.
3. **`leads-hunt-voice`** used at least once (or `style.md` edited directly) — empty voice file works but produces flat outreach drafts.

If the wizard hasn't run, scripts in this skill fail with a clear "run leads-hunt-setup first" error.

## Foundational filter — read before discovery

> **Sell to companies whose *product* uses AI, not companies whose *operations* use AI.**

Good leads are **AI producers** — companies whose own product exposes AI to end users (image generators, AR configurators, video editors, 3D viewers). Bad leads are **AI consumers** — companies that use AI internally for ops.

**Litmus test**: does the lead's customer see AI output, or only their employees? Customer-facing AI → producer (good lead). Employee-facing AI only → consumer (skip).

This filter runs **before** scoring (it is "Filter 0"). Full doctrine: [references/lead-philosophy.md](references/lead-philosophy.md).

## Quick start

```bash
# Phase A: SSO health check (must pass before B-D fire)
python3 scripts/run_topic.py --phase sso-check

# Phase B: discovery, fan-out over all enabled topics
python3 scripts/run_topic.py --phase discover-all

# Phase C: dedup, fan-out over all enabled topics
python3 scripts/run_topic.py --phase dedup-all

# Phase D: aggregate + Lark deliver
python3 scripts/run_topic.py --phase deliver

# Single-topic invocation — debugging / manual runs only:
python3 scripts/run_topic.py --topic aigc-visual --phase discover
python3 scripts/run_topic.py --topic aigc-visual --phase dedup
```

All scripts resolve `LEADS_HUNT_HOME` at startup as `$OPENCLAW_WORKSPACE/leads-hunt` (default `~/.openclaw/workspace/leads-hunt`). Override with `--home <path>` for testing.

## Topics (default — AE replaces with their own)

The pack ships with two example topic files in `references/topics/`. The AE replaces or augments these via the `leads-hunt-add-target` skill.

- **`aigc-visual`** — Image + video gen ICP example (marketing SaaS, agencies, e-commerce, media).
- **`seed3d`** — 3D asset gen ICP example (indie game dev, AR/VR tools, e-commerce 3D viewers).

To add a new topic, invoke `leads-hunt-add-target` skill via Lark — it runs interactive Q&A, drafts the topic file, writes to `references/topics/<slug>.md`. Tomorrow's `discover-all` cron picks it up automatically.

## Workflow per topic

```
discover (browser-driven)  →  score (1-10 rubric)  →  dedup (3-layer stack)  →  CSV
                              ↓                         ↓
                        ship if score ≥ 8       Layer 3 = Sales Nav CRM check
                                                (the truth signal)
```

## Rules (non-negotiable)

1. **Per-topic ceiling**: ≤5 leads NOT in CRM, score ≥8.
2. **Auto-skip**: company website mentions BytePlus product names (Seedream/Seedance/ByteDance/VolcEngine/Doubao/Jimeng) → SKIP and add to skip-list.
3. **Cite sources**: every lead has a verified website URL + LinkedIn URL.
4. **Voice**: outreach angle uses the AE's voice from `<workspace>/leads-hunt/style.md`. Manage via `leads-hunt-voice` skill or edit directly.
5. **No tasking systems**: leads ship as CSV + Lark digest only.

## 3-layer dedup stack

The pack uses a 3-layer dedup stack against the AE's local `kb.md` knowledge base + skip-list + live Sales Nav CRM check:

1. **Layer 1 — `skip-list.txt`** (cheapest): manual + auto-appended hard-skips.
2. **Layer 2 — `kb.md`** (the AE's source of truth): markdown KB of every shipped lead and tracked customer. Replaces what was a server-backed leads/customers DB in Ben's setup.
3. **Layer 3 — Sales Nav CRM check** (the truth signal): live query via `sales_nav_check.py`, 24hr-cached.

Full protocol + cache format + SSO failure handling: [references/dedup-process.md](references/dedup-process.md).

## Reference docs (load on demand)

- [references/dedup-process.md](references/dedup-process.md) — 3-layer dedup stack + Sales Nav protocol + BD SSO expiry handling
- [references/scoring-rubric.md](references/scoring-rubric.md) — 1-10 scoring + skip rules
- [references/output-format.md](references/output-format.md) — 11-column CSV schema + Lark digest template
- [references/discovery-rotation.md](references/discovery-rotation.md) — day-of-week → discovery method
- [references/lead-philosophy.md](references/lead-philosophy.md) — producer-vs-consumer doctrine
- [references/warm-signals.md](references/warm-signals.md) — outreach signal taxonomy
- [references/scoring-rubric.md](references/scoring-rubric.md) — score rubric
- [references/empty-digest-diagnostic.md](references/empty-digest-diagnostic.md) — when no leads ship today, read this BEFORE re-running
- [references/layer4-vs-linked-api.md](references/layer4-vs-linked-api.md) — why Sales Nav can't be replaced with a SaaS LinkedIn API
- [assets/byteplus-products-cheatsheet.md](assets/byteplus-products-cheatsheet.md) — product positioning quick-ref

## Outputs (under `<workspace>/leads-hunt/data/`)

| File | Written by | Notes |
|---|---|---|
| `candidates/<topic>-YYYY-MM-DD.json` | Phase B | 14-day TTL |
| `leads-<topic>-YYYY-MM-DD.csv` | Phase C | permanent, 11 cols |
| `leads-aggregate-YYYY-MM-DD.csv` | Phase D | permanent merged |
| `sales-nav-cache.jsonl` | Phase C | rolling 24hr |
| `run-log-YYYY-MM-DD.txt` | all phases | 30-day TTL |

## Side-effects (external systems)

Phase D appends each shipped lead to `<workspace>/leads-hunt/kb.md` under `## Shipped Leads` so future runs see it via Layer 2 dedup. Idempotent — re-running Phase D the same day skips duplicates by name.

## Cron scheduling (OpenClaw)

OpenClaw cron (Gateway-level scheduler, persists in SQLite, delivers to bound Lark channel). 4 jobs total, regardless of how many topics the AE has enabled:

```bash
# Phase A — SSO canary at 07:30
openclaw cron add --schedule "30 7 * * *" \
  --message "Run leads-hunt Phase A: python3 scripts/run_topic.py --phase sso-check. Lark me on exit 3."

# Phase B — agent-mode discovery at 08:00
openclaw cron add --schedule "0 8 * * *" \
  --message "Run leads-hunt Phase B: glob references/topics/*.md and discover for each enabled topic. Skill: leads-hunt." \
  --skills leads-hunt --enabled-toolsets terminal,web,file

# Phase C — dedup at 09:00
openclaw cron add --schedule "0 9 * * *" \
  --message "Run leads-hunt Phase C: python3 scripts/run_topic.py --phase dedup-all"

# Phase D — Lark digest at 09:30
openclaw cron add --schedule "30 9 * * *" \
  --message "Run leads-hunt Phase D: python3 scripts/run_topic.py --phase deliver"
```

Server timezone matters — run `timedatectl` to confirm before scheduling. Adjust the times to MYT (or AE's local) by reading the server's tz offset.

The `leads-hunt-setup` wizard offers to register these for the AE.

## Topic registry & cron topology

**Default to a fan-out topology, NOT per-topic cron registrations.** 4 cron jobs regardless of topic count. The dispatcher (`run_topic.py`) handles per-topic stagger internally.

| Time | Phase | Behaviour |
|---|---|---|
| 07:30 | A — sso-check | single-shot SSO canary |
| 08:00 | B — discover-all | loops over enabled topics, sleeps ≥5min between |
| 09:00 | C — dedup-all | loops over enabled topics, sleeps ≥15min between |
| 09:30 | D — deliver | aggregate + Lark digest |

**Topic registry comes from the filesystem, not a hardcoded list.** Each topic is a single file at `references/topics/<slug>.md` with YAML frontmatter:

```yaml
---
slug: aigc-visual
display_name: "Image + Video Gen"
enabled: true
# Optional overrides:
# ceiling: 5
# score_floor: 8
---
(ICP body)
```

`run_topic.py` discovers enabled topics by globbing `references/topics/*.md` and reading frontmatter via `topic_registry.py` (stdlib-only parser, no PyYAML dep). Adding a new topic = drop one file, no Python edits, no cron edits. Pausing = `enabled: false` in frontmatter.

Sanity-check: `python3 scripts/topic_registry.py` prints the resolved registry. Filename must match `slug` field — typos fail loud.

The general pattern (filesystem-as-registry, fan-out-over-enum, slug-filename invariants) is captured in skill `filesystem-as-registry` if available in the AE's installation.

## Failure modes

- **BD SSO expired** (Phase A exit 3) → Lark AE "BD SSO expired, run setup script". Halt the day.
- **LinkedIn fingerprint detection** → Halt + Lark AE.
- **Discovery method fails** → Try next day's method.
- **Zero leads from a topic** → Ship empty CSV; note in the Lark digest.
- **AE asks "why no new leads today?"** → Read the run-log first, do NOT re-run the pipeline. Diagnostic recipe + response template: [references/empty-digest-diagnostic.md](references/empty-digest-diagnostic.md). Most common cause is total dedup drain.
- **Playwright `Executable doesn't exist at .../chromium_headless_shell-NNNN/...`** → Playwright Python and the cached Chromium got out of sync. Fix: `playwright install chromium` from the python venv that runs this skill.

### Sales Nav setup script can lie about success

The `sales_nav_session_setup.py` heuristic is fragile. Treat its exit/log as a hint, not the truth — always re-probe with `python3 scripts/sales_nav_query.py BytePlus` after running setup. If the probe still returns `needs-reauth`, setup did NOT actually log in.

Common body-text signatures and meanings:
- `"Wrong email or password"` — bad creds.
- `"Check your LinkedIn app"` — app-push challenge; script falls back to email OTP. Write OTP to `/tmp/lk_otp.txt`.
- `"Let's do a quick security check"` / captcha — LinkedIn risk engine flagged the headless browser. AE must log in manually from a non-headless context first to season the profile.
- `"verification code"` — email OTP path, write code to `/tmp/lk_otp.txt`.

If LinkedIn redesigns its login DOM again, run `scripts/lk_dom_probe.py` to dump every `<input>` on the login page before guessing selectors.

## Layer 3 (Sales Nav CRM dedup) — what the signal actually is

`sales_nav_check.py` → `sales_nav_query.py` does **not** scrape Sales Nav search results in the obvious sense. It intercepts the `salesApiAccountSearch` XHR response and reads the `crmStatus` object that LinkedIn injects **only when the authenticated seat has Salesforce sync enabled** (the AE's BD-corporate Sales Nav seat must be wired to BD's Salesforce tenant).

Key fields read off `crmStatus`:
- `imported` (bool) → `in_crm`
- `externalCrmUrl` → `salesforce_url`
- `idInSourceDomain` → `salesforce_id`

This is a **server-side join Sales Nav performs between LinkedIn's company entity and the connected Salesforce tenant**. Tenant-private; not visible to any third-party LinkedIn automation tool. See `references/layer4-vs-linked-api.md` for the full vendor-evaluation note.

**Implication for refactors**: any proposal to replace the Playwright-driven Sales Nav stack with a SaaS LinkedIn automation API will lose Layer 3 entirely.

## Discovery patterns (seed; AE refines via `kb.md`)

The AE's `kb.md` accrues a `## Discovery Patterns Learned` section over time as Phase B agent runs surface saturated/high-yield verticals. Phase B's brief reads recent entries from `kb.md` (`kb.read_recent_patterns()`) and feeds them into the next morning's prompt.

The seed patterns Ben observed are documented in [references/discovery-rotation.md](references/discovery-rotation.md). Treat them as a starting point — your accumulated `kb.md` will diverge based on your own region, ICP, and outreach feedback.
