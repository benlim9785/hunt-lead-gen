---
name: leads-hunt-setup
description: "First-run onboarding wizard for a new AE installing leads-hunt-pack on OpenClaw. Walks through Lark binding check, LinkedIn login, BD Sales Nav SSO, kb.md init, topic scaffolding, cron registration."
version: 0.1.0
author: Ben Lim
license: MIT
---

# leads-hunt-setup

A conversational, Lark-driven onboarding wizard. Triggered when a new BytePlus AE says something like *"clawdia, set me up for leads hunt"*. Targets ~30 minutes end-to-end.

This skill is a **protocol the agent follows**, not a single script. The agent reads SKILL.md, drives an 8-step Q&A in Lark, and shells out to helper scripts in `scripts/` for the actual work.

## When to invoke

- First install of `leads-hunt-pack` on a fresh OpenClaw.
- Re-running specific steps after a partial failure (the wizard supports resuming).
- After an LLM provider rotation, BD-corp password change, or LinkedIn re-auth.

If the AE has already onboarded and just wants a single piece (e.g. re-login LinkedIn), the agent should skip ahead to that step instead of doing the full 8-step flow. The wizard is idempotent — re-running steps 1-3 is cheap.

## Prerequisites (check BEFORE step 1)

Run `python3 scripts/check_prereqs.py` first. It checks three things:

1. **OpenClaw onboard done** — `openclaw agents bindings` must include a `feishu:` binding. If not:
   > "First run `openclaw onboard` and bind your Lark app, then come back."
   > Do not proceed.
2. **Sibling skills installed** — `openclaw skills list` must show all four: `leads-hunt`, `leads-hunt-outreach`, `leads-hunt-add-target`, `leads-hunt-voice`. If any missing, tell the AE the exact `openclaw skills install ./<name>` command for each.
3. **Workspace writable** — `<workspace>/leads-hunt/` must be creatable (or already exist with a recoverable `kb.md`). If `kb.md` exists with content, refuse unless the AE passes `--force`; we do NOT clobber a populated KB.

If the OpenClaw CLI is not in PATH at all, print: *"OpenClaw not found in PATH; install OpenClaw first (see https://hermes-agent.nousresearch.com/docs)."* and abort.

Exit 0 → green light to start step 1. Exit 1 → repair and re-run.

## The 8-step wizard

### Step 1 — Detect workspace + create state dir

```bash
python3 scripts/init_state.py
```

Resolves `OPENCLAW_WORKSPACE` env (default `~/.openclaw/workspace`) and creates:
- `<workspace>/leads-hunt/data/`
- `<workspace>/leads-hunt/browser-profile/`
- `<workspace>/leads-hunt/kb.md` with the H2 skeleton:
  - `## Customers`
  - `## Shipped Leads`
  - `## Skip List`
  - `## Discovery Patterns Learned`

Idempotent: re-running on an existing dir is a no-op. `--force` overwrites kb.md (only do this on explicit AE confirmation in Lark).

**If AE refuses (says "I already did this manually")**: skip to step 2; the script's no-op behaviour means no harm done.

### Step 2 — Create blank-slate `style.md`

Copy `<skill-discovery>/leads-hunt-outreach/references/style.md` to `<workspace>/leads-hunt/style.md`. Use the path the agent resolved when locating the `leads-hunt-outreach` skill (sibling skill discovery — see Pitfalls below).

```bash
cp "<leads-hunt-outreach-skill>/references/style.md" "<workspace>/leads-hunt/style.md"
```

Do NOT pre-fill the voice file. It stays blank-slate; the AE fills it later via `leads-hunt-voice`.

### Step 3 — Collect Lark target chat

Already bound at the OpenClaw level (verified in prereqs). Ask:

> "Which Lark chat should leads digests deliver to? Default: your home channel from `openclaw agents bindings` (oc_xxxx). Reply with a chat ID, or 'default'."

Write to `.env`:

```bash
python3 scripts/write_env.py LARK_HUNT_CHANNEL=oc_xxx
```

The script merges into existing `.env` non-destructively (preserves other keys).

### Step 4 — Collect LLM provider key

Ask:

> "Which LLM provider should this skill use for scoring + outreach drafting? (openai / anthropic / bedrock)"

Then:
- **openai** → ask for `OPENAI_API_KEY`. Format hint: `sk-...`.
- **anthropic** → ask for `ANTHROPIC_API_KEY`. Format hint: `sk-ant-...`.
- **bedrock** → ask for `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional `AWS_REGION` (default `us-east-1`). Format: 20-char + 40-char + region.

Write each via `write_env.py`. Then validate:

```bash
python3 scripts/test_llm_call.py
```

Reads provider+key from `.env`, makes a one-shot "respond with: ok" call. Exit 0 → green. Exit 1 → bad key. On failure, re-prompt the AE for the key (most common cause: typo or wrong provider). Three strikes → tell them to fix manually, point at `references/troubleshooting.md`.

### Step 5 — LinkedIn login (personal seat)

Run from the `leads-hunt` skill's scripts dir (NOT this skill — we don't duplicate playwright code):

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_session_setup.py
```

Q&A flow over Lark:
1. Agent asks: *"Paste your personal LinkedIn email."* → AE pastes → agent forwards to script's stdin.
2. Agent asks: *"Paste your password."* → never log this.
3. If LinkedIn challenges with email OTP, the script writes a status file and waits up to 60s for `/tmp/lk_otp.txt`. Agent prompts the AE: *"LinkedIn sent an OTP to your email. Paste it here within 60 seconds."*. When AE replies, agent writes the value to `/tmp/lk_otp.txt`. The setup script picks it up and continues.
4. If `Wrong email or password` appears in the script output → re-prompt creds.
5. If `Check your LinkedIn app` appears → app-push challenge. Tell the AE to approve from their LinkedIn mobile app, then continue.
6. If `Let's do a quick security check` (captcha) appears → fall back to **manual seasoning**: tell the AE to open Chromium on the same machine, log in to LinkedIn manually once via `<workspace>/leads-hunt/browser-profile/`, then re-run step 5. See `references/troubleshooting.md`.

Verify with:

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_query.py BytePlus
```

Must return JSON. If it returns `needs-reauth`, the setup script lied — the heuristic is fragile. Re-run setup. Three strikes → escalate to troubleshooting doc.

**OTP timeout**: if the AE doesn't paste OTP within 60s, the script aborts. Keep the Lark conversation alive and re-prompt; restart step 5.

### Step 6 — BD-corporate Sales Nav SSO

Same script, different seat. Ask:

> "Now your BD-corporate Sales Nav login. Paste your BD email."

Same OTP fallback flow as step 5. After login, verify Salesforce sync:

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_query.py BytePlus
```

Look for `crmStatus` in the response payload. If absent, the AE's seat does NOT have Salesforce sync enabled — Layer 3 dedup will be dead. Tell the AE:

> "Your BD seat is logged in, but Salesforce sync is not active on this seat. This is an IT thing — open a ticket asking BD IT to enable Sales Nav ↔ Salesforce sync for your seat. The pipeline will run without it but you'll get false positives in dedup."

Allow them to proceed (it's not blocking, just degraded).

### Step 7 — Topic file scaffolding

Ask:

> "Want to start with the example `aigc-visual` topic, or define your own now via `leads-hunt-add-target`?"

- **example**: copy `<leads-hunt-skill>/references/topics/aigc-visual.md` is already in place — just confirm it's enabled (frontmatter `enabled: true`). No copy needed; the file lives in the skill, not the workspace.
- **custom**: tell the AE to invoke `leads-hunt-add-target` after this wizard finishes:
  > *"After we wrap setup, message me 'add a leads-hunt target' and I'll walk you through your ICP."*

Either path is valid. Don't block.

### Step 8 — Schedule cron jobs

Show the AE the 4 cron commands from `leads-hunt`'s SKILL.md (Phase A 07:30, B 08:00, C 09:00, D 09:30). Ask:

> "Register them now? (y/n) — server timezone is `<run timedatectl>`. Times are server-local."

If yes:

```bash
python3 scripts/register_cron.py
```

This wraps `openclaw cron add` for each of the 4 jobs. Idempotent — skips if a job with matching `--schedule` and `--message` substring already exists. Prints the registered job IDs.

After registration, verify with `openclaw cron list` — confirm all 4 jobs appear. If any missing, the OpenClaw cron daemon may not be running. Point at `openclaw doctor --fix`.

If the AE says no, save commands to `<workspace>/leads-hunt/cron-suggestions.txt` for later (the script accepts `--dry-run`).

## Final message

When all 8 steps pass, send to Lark:

> "All set. Voice file at `<workspace>/leads-hunt/style.md` is empty. Chat with me anytime to teach me your style — try *'add this to my outreach voice: [paste a real message]'* or *'set my voice rhythm to: [describe how you write]'*. You can do this now, later, or iteratively."

## Pitfalls (encoded — read before driving the wizard)

1. **LinkedIn captcha season**. If headless setup hits a captcha (`Let's do a quick security check`), the AE MUST log in manually from a non-headless Chromium against the same `<workspace>/leads-hunt/browser-profile/` directory ONCE to season the profile. Then retry step 5. Document this clearly when the failure occurs; AEs find it counterintuitive.

2. **OTP timeout (60s)**. If the AE is slow pasting OTP, the script aborts. The agent's job is to keep the Lark conversation responsive — prompt explicitly with a deadline ("paste OTP in the next minute or I'll restart"). On abort, re-run step 5 from scratch. Don't try to resume mid-OTP-flow.

3. **OpenClaw cron daemon not running**. `openclaw cron add` returns success even if the daemon is dead. After step 8, ALWAYS run `openclaw cron list` and confirm the 4 jobs are listed AND the daemon column shows `running`. If not, point at `openclaw doctor --fix`.

4. **Sibling skill discovery**. If `leads-hunt` is installed `--global` and `leads-hunt-setup` is workspace-local (or vice versa), path resolution between them can fail. Every script that needs to reach into a sibling skill accepts a `--leads-hunt-skill <path>` override. The agent should resolve the path from `openclaw skills list --paths` and pass it explicitly.

5. **Empty style.md is fine**. Step 2 creates a blank-slate `style.md`. Do NOT pre-fill it with examples or guess at the AE's voice. The wizard's final message tells the AE how to fill it later. Resist the temptation to be helpful here — a wrong voice is worse than no voice.

6. **Credentials never logged**. LinkedIn email/password, BD creds, OTP, LLM keys — none of these get echoed to Lark, written to logs, or persisted outside their canonical location (`browser-profile/` for cookies, `.env` for keys). The agent must never repeat back a credential to confirm it; ask the AE to re-paste if unsure.

## Error recovery — quick pointers

| Symptom | Fix recipe |
|---|---|
| `openclaw: command not found` | Install OpenClaw first; this skill assumes the CLI is in PATH. |
| `feishu binding not found` | Run `openclaw onboard`. |
| Sibling skill missing | `openclaw skills install ./leads-hunt-<name>` from the pack repo. |
| LinkedIn `Wrong email or password` | Re-prompt the AE; common is typo'd password. |
| LinkedIn captcha | Manual seasoning (see Pitfall #1). |
| LLM key validation 401 | Wrong key or wrong provider. Re-prompt. |
| `crmStatus` missing in Sales Nav response | BD seat lacks Salesforce sync; escalate to BD IT. |
| Cron job didn't fire next morning | `openclaw cron list` → check daemon status; `openclaw doctor --fix`. |

Full failure-mode catalog: [references/troubleshooting.md](references/troubleshooting.md).
Credential handling + AE responsibilities: [references/security.md](references/security.md).

## Resume semantics

The wizard is step-addressable. If the AE drops mid-flow and comes back, the agent should:

1. Re-run `check_prereqs.py`.
2. Inspect `<workspace>/leads-hunt/` for what already exists:
   - `kb.md` exists → skip step 1.
   - `style.md` exists → skip step 2.
   - `.env` has `LARK_HUNT_CHANNEL` → skip step 3.
   - `.env` has the LLM key for the chosen provider → skip step 4 (still re-validate with `test_llm_call.py`).
   - `browser-profile/` has cookies AND `sales_nav_query.py BytePlus` returns JSON → skip steps 5/6.
   - At least one enabled topic file → skip step 7.
   - `openclaw cron list` shows 4 leads-hunt jobs → skip step 8.
3. Resume from the first unfinished step.

Ask the AE before skipping a step: *"Looks like step 4 is already done — your LLM key validates. Skip it?"* — give them an out in case they want to re-do it (e.g. provider rotation).
