---
name: leads-hunt-setup
description: "First-run onboarding wizard for a new AE setting up leads-hunt on AIME. Walks through workspace init, LinkedIn + Sales Navigator login, kb.md init, topic scaffolding, Lark Base setup, and recurring run setup."
author: Ben Lim
license: MIT
---

# leads-hunt-setup

A conversational, Lark-driven onboarding wizard. Triggered when a new BytePlus AE says something like *"clawdia, set me up for leads hunt"*. Targets ~30 minutes end-to-end.

This skill is a **protocol the agent follows**, not a single script. The agent reads SKILL.md, drives a 6-step Q&A in Lark, and shells out to helper scripts in `scripts/` for the actual work.

AIME provides the host agent runtime — do not ask the AE for any LLM provider keys. Any drafting, scoring, or per-topic research the pack needs is performed by the host agent inline.

## When to invoke

- First setup of `leads-hunt` for a new AE on AIME.
- Re-running specific steps after a partial failure (the wizard supports resuming).
- After a LinkedIn or Sales Navigator re-auth.
- When the AE needs the shared Lark Base re-created or re-wired.

If the AE has already onboarded and just wants a single piece (e.g. re-login LinkedIn), the agent should skip ahead to that step instead of doing the full 6-step flow. The wizard is idempotent — re-running steps 1-2 is cheap.

## Prerequisites (check BEFORE step 1)

Before starting, verify two things:

1. **Sibling skills are available** — the agent should be able to use all four companion skills: `leads-hunt`, `leads-hunt-outreach`, `leads-hunt-add-target`, and `leads-hunt-voice`.
2. **Workspace is writable** — `<workspace>/leads-hunt/` must be creatable (or already exist with a recoverable `kb.md`). If `kb.md` exists with content, refuse unless the AE passes `--force`; we do NOT clobber a populated KB.

If either prerequisite is not satisfied, stop and ask the AE to fix it before continuing.

## The 6-step wizard

### Step 1 — Detect workspace + create state dir

```bash
python3 scripts/init_state.py
```

Resolves the workspace root from the current AIME environment and creates:
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

### Step 3 — LinkedIn login (personal seat)

Use the `leads-hunt` skill's browser-based login helper, but **drive login through a cloud browser VNC session** instead of asking the AE to paste credentials into Lark.

High-level protocol:

1. **Spin up a cloud browser and share access details**
   - Start the hosted Chromium profile that writes cookies into `<workspace>/leads-hunt/browser-profile/`.
   - When the browser is ready, surface to the AE in Lark:
     - a **VNC URL** they can open in their local browser, and
     - a **VNC password** (or access token) needed to connect.
   - Make it explicit that all LinkedIn and Sales Navigator login happens **inside this VNC browser**, not in their local browser.

2. **Guide the AE to log into LinkedIn + Sales Navigator inside VNC**
   - Ask the AE to connect to the VNC URL and, inside the remote Chromium, do the following:
     1. Navigate to `https://www.linkedin.com/` and sign in with their personal LinkedIn account.
     2. Once the main LinkedIn feed loads, navigate to `https://www.linkedin.com/sales/` (Sales Navigator) and confirm Sales Nav opens without a login wall.
   - Handle any MFA/OTP/captcha entirely inside the VNC browser. Do **not** ask the AE to paste codes or passwords into Lark; they type them directly into the LinkedIn pages.
   - When they are done, have them reply in Lark: *"Done, I'm logged into LinkedIn + Sales Nav in the cloud browser."*

3. **Capture the actual VNC display to verify login state**
   - After the AE confirms, capture a screenshot directly from the live VNC display on `DISPLAY=:1`. Use `scrot` if available, or fall back to `xwd`, so the image reflects exactly what the user currently sees in the VNC window.
   - Example capture commands:

```bash
DISPLAY=:1 scrot /tmp/leads-hunt-vnc-verify-step3.png
```

   - Or, if `scrot` is unavailable:

```bash
DISPLAY=:1 xwd -root -silent -out /tmp/leads-hunt-vnc-verify-step3.xwd
```

   - Do **not** open a new managed browser session for verification. A fresh browser session will not reflect the authenticated state the user established inside VNC.
   - Inspect the captured VNC screenshot for a logged-in LinkedIn + Sales Nav state, ideally including clear Sales Nav indicators such as `linkedin.com/sales/home`, the Sales Navigator home UI, or other authenticated Sales Nav navigation elements.
   - If the captured VNC screenshot still shows a login form or error state, tell the AE what you see (for example *"I still see a LinkedIn sign-in form on the VNC display"*) and ask them to fix it in the same VNC browser, then capture the VNC display again.
   - Only when the VNC screenshot clearly shows a logged-in LinkedIn + Sales Nav session should the agent proceed to the session-persistence script.

4. **Persist the session via the existing helper script**
   - Once the screenshot check passes, run from the `leads-hunt` skill's scripts dir (NOT this skill — we don't duplicate playwright code):

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_session_setup.py
```

   - This script should pick up the cookies from `<workspace>/leads-hunt/browser-profile/` that were created by the cloud browser, and normalize them into the format used by the rest of the pack.

Verify with:

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_query.py BytePlus
```

Must return JSON. If it returns `needs-reauth`, the setup script lied — the heuristic is fragile. Re-run setup, including spinning up a fresh cloud browser session. Three strikes → escalate to `references/troubleshooting.md`.

### Step 4 — Topic file scaffolding

Ask:

> "Want to start with the example `aigc-visual` topic, or define your own now via `leads-hunt-add-target`?"

- **example**: copy `<leads-hunt-skill>/references/topics/aigc-visual.md` is already in place — just confirm it's enabled (frontmatter `enabled: true`). No copy needed; the file lives in the skill, not the workspace.
- **custom**: tell the AE to invoke `leads-hunt-add-target` after this wizard finishes:
  > *"After we wrap setup, message me 'add a leads-hunt target' and I'll walk you through your ICP."*

Either path is valid. Don't block.

### Step 5 — Auto-create the Lark Base + webhook automation

Create the AE's shared Lark Base after topic scaffolding, not before. This keeps the Base aligned with the AE's first real setup state.

Run:

```bash
python3 scripts/create_lark_base.py --webhook-url "<your-aime-webhook-endpoint>"
```

If the webhook URL is already present in the environment, the short form also works:

```bash
python3 scripts/create_lark_base.py
```

What this step must do:

1. Create a new Base named `leads-hunt`.
2. Create these tables:
   - `Leads`
   - `Customers`
   - `Skip List`
   - `Discovery Patterns`
3. Save the Base token, Base URL, table IDs, webhook URL, and workflow metadata to:
   - `<workspace>/leads-hunt/config.json`
4. If a webhook URL is supplied, also create + enable the Base automation that:
   - watches `Leads.Draft Message`
   - triggers when the value becomes `Yes`
   - `POST`s the lead row context to AIME's webhook endpoint

Schema requirements:

- **Leads** — `Company`, `Topic`, `Score`, `Sales Nav URL`, `LinkedIn URL`, `Summary`, `Draft Message`, `Message Draft`, `Date`, `Status`
- **Customers** — `Company`, `Status`, `Date Added`
- **Skip List** — `Domain/Company`, `Reason`, `Date Added`
- **Discovery Patterns** — `Date`, `Topic`, `Good`, `Bad`

Webhook configuration rules:

- Preferred input is `--webhook-url <your-aime-webhook-endpoint>`.
- Fallback environment keys are:
  - `AIME_LEADS_HUNT_WEBHOOK_URL`
  - `LEADS_HUNT_AIME_WEBHOOK_URL`
- The exact configured URL must be written into `<workspace>/leads-hunt/config.json` as `lark_base.webhook_url`.
- If the endpoint is **not** available yet, still create the Base now, but tell the AE the workflow remains unconfigured until the webhook URL is supplied later.

If this step succeeds, report back the Base URL and confirm whether the webhook workflow is enabled or still pending.

### Step 6 — Schedule recurring runs

Show the AE the 4 daily recurring runs from `leads-hunt`'s SKILL.md (Phase A 07:30, B 08:00, C 09:00, D 09:30). Ask:

> "Register them now? (y/n) — these are daily AIME native scheduled tasks in the workspace/server timezone."

If yes:

1. Run the helper to emit the canonical AIME scheduler specs:

```bash
python3 scripts/register_cron.py
```

2. Register the 4 recurring jobs through **AIME's native scheduler** using the `schedule` tool / AIME scheduler API (not system crontab).
3. Because these are cron tasks, set a stop time if the user did not provide one. Use the platform default policy if needed.
4. Verify that all 4 jobs appear in the scheduler after registration. If any are missing, tell the AE registration failed and they should not rely on automation yet.

If the AE says no, save the canonical scheduler specs for later:

```bash
python3 scripts/register_cron.py --dry-run
```

This writes `<workspace>/leads-hunt/cron-suggestions.json` for later inspection.

## Final message

When all 6 steps pass, send to Lark:

> "All set. Voice file at `<workspace>/leads-hunt/style.md` is empty. Your shared Base is ready too. Chat with me anytime to teach me your style — try *'add this to my outreach voice: [paste a real message]'* or *'set my voice rhythm to: [describe how you write]'*. You can do this now, later, or iteratively."

## Pitfalls (encoded — read before driving the wizard)

1. **LinkedIn captcha season**. If headless setup hits a captcha (`Let's do a quick security check`), the AE MUST log in manually from a non-headless Chromium against the same `<workspace>/leads-hunt/browser-profile/` directory ONCE to season the profile. Then retry step 3. Document this clearly when the failure occurs; AEs find it counterintuitive.

2. **OTP timeout (60s)**. If the AE is slow pasting OTP, the script aborts. The agent's job is to keep the Lark conversation responsive — prompt explicitly with a deadline ("paste OTP in the next minute or I'll restart"). On abort, re-run step 3 from scratch. Don't try to resume mid-OTP-flow.

3. **Scheduler registration can silently fail**. After step 6, always verify the recurring jobs are actually present before telling the AE automation is set up.

4. **Sibling skill discovery**. If the agent resolves `leads-hunt` and `leads-hunt-setup` from different installation contexts, path resolution between them can fail. Every script that needs to reach into a sibling skill accepts a `--leads-hunt-skill <path>` override. The agent should resolve the path explicitly before invoking sibling scripts.

5. **Empty style.md is fine**. Step 2 creates a blank-slate `style.md`. Do NOT pre-fill it with examples or guess at the AE's voice. The wizard's final message tells the AE how to fill it later. Resist the temptation to be helpful here — a wrong voice is worse than no voice.

6. **Credentials never logged**. LinkedIn credentials or one-time codes should never be echoed to Lark, written to logs, or persisted outside their canonical location (`browser-profile/` for cookies, `.env` for non-secret config). The agent must never repeat back a credential to confirm it; ask the AE to re-paste if unsure.

7. **Base IDs are per AE, not shared skill config**. Always write the Base token/table IDs to `<workspace>/leads-hunt/config.json`, not the installed skill's shared `scripts/config.json`. Shared skill config is for defaults only.

8. **No webhook URL means no live draft automation yet**. The Base can exist before the webhook exists. In that case, be explicit: the schema is ready, but `Draft Message = Yes` will not call AIME until the webhook URL is configured.

## Error recovery — quick pointers

| Symptom | Fix recipe |
|---|---|
| Missing companion skill | Make sure `leads-hunt`, `leads-hunt-outreach`, `leads-hunt-add-target`, and `leads-hunt-voice` are all available to the agent. |
| Workspace init fails | Confirm the current workspace is writable and retry step 1. |
| LinkedIn `Wrong email or password` | Re-prompt the AE; common is typo'd password. |
| LinkedIn captcha | Manual seasoning (see Pitfall #1). |
| Base created but workflow missing | Re-run step 5 with `--webhook-url <your-aime-webhook-endpoint>`. |
| Recurring job didn't fire next morning | Re-check scheduler registration and confirm the expected jobs were actually created. |

Full failure-mode catalog: [references/troubleshooting.md](references/troubleshooting.md).
Credential handling + AE responsibilities: [references/security.md](references/security.md).

## Resume semantics

The wizard is step-addressable. If the AE drops mid-flow and comes back, the agent should:

1. Re-check which prerequisites are already satisfied.
2. Inspect `<workspace>/leads-hunt/` for what already exists:
   - `kb.md` exists → skip step 1.
   - `style.md` exists → skip step 2.
   - `browser-profile/` has cookies AND `sales_nav_query.py BytePlus` returns JSON → skip step 3.
   - At least one enabled topic file → skip step 4.
   - `config.json` contains `lark_base.base_token` and the 4 expected table IDs → skip step 5.
   - The scheduler already shows 4 leads-hunt jobs → skip step 6.
3. Resume from the first unfinished step.

Ask the AE before skipping a step: *"Looks like step 5 is already done — your Base is configured. Skip it?"* — give them an out in case they want to re-do it.
