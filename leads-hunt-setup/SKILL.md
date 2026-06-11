---
name: leads-hunt-setup
description: "First-run onboarding wizard for a new AE installing leads-hunt-pack on OpenClaw. Walks through workspace init, LinkedIn login, BD Sales Nav SSO, kb.md init, topic scaffolding, cron registration."
author: Ben Lim
license: MIT
---

# leads-hunt-setup

A conversational, Lark-driven onboarding wizard. Triggered when a new BytePlus AE says something like *"clawdia, set me up for leads hunt"*. Targets ~30 minutes end-to-end.

This skill is a **protocol the agent follows**, not a single script. The agent reads SKILL.md, drives a 6-step Q&A in Lark, and shells out to helper scripts in `scripts/` for the actual work.

OpenClaw provides the LLM — we don't ask the AE for any LLM provider keys. Any drafting, scoring, or per-topic research the pack needs is performed by the host agent inline.

## When to invoke

- First install of `leads-hunt-pack` on a fresh OpenClaw.
- Re-running specific steps after a partial failure (the wizard supports resuming).
- After a BD-corp password change or LinkedIn re-auth.

If the AE has already onboarded and just wants a single piece (e.g. re-login LinkedIn), the agent should skip ahead to that step instead of doing the full 6-step flow. The wizard is idempotent — re-running steps 1-2 is cheap.

## Prerequisites (check BEFORE step 1)

Run the prereq check first:

```bash
python3 scripts/check_prereqs.py
```

It checks three things:

1. **OpenClaw onboard done** — `openclaw agents bindings` must include a `feishu:` binding. If not:
   > "First run `openclaw onboard` and bind your Lark app, then come back."
   > Do not proceed.
2. **Sibling skills installed** — `openclaw skills list` must show all four: `leads-hunt`, `leads-hunt-outreach`, `leads-hunt-add-target`, `leads-hunt-voice`. If any missing, tell the AE the exact `openclaw skills install ./<name>` command for each.
3. **Workspace writable** — `<workspace>/leads-hunt/` must be creatable (or already exist with a recoverable `kb.md`). If `kb.md` exists with content, refuse unless the AE passes `--force`; we do NOT clobber a populated KB.

If the OpenClaw CLI is not in PATH at all, print: *"OpenClaw not found in PATH; install OpenClaw first (see https://hermes-agent.nousresearch.com/docs)."* and abort.

Exit 0 → green light to start step 1. Exit 1 → repair and re-run.

## The 6-step wizard

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

3. **Capture a VNC screenshot to verify login state**
   - After the AE confirms, take a screenshot of the current VNC display and inspect it for:
     - a visible LinkedIn authenticated view (for example feed, profile, or top nav with their avatar), and
     - a Sales Navigator page that is past the login screen.
   - If the screenshot still shows a login form or error state, tell the AE what you see (for example *"I still see a LinkedIn sign-in form"*) and ask them to fix it in the VNC browser, then take another screenshot.
   - Only when the screenshot clearly shows a logged-in LinkedIn + Sales Nav session should the agent proceed to verification via script.

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

### Step 4 — BD-corporate Sales Nav SSO

Use the same cloud browser VNC pattern as step 3, but for the AE's BD-corporate Sales Nav seat.

High-level protocol:

1. **Reuse the active cloud browser if possible, otherwise spin up a new one**
   - If the VNC session from step 3 is still active and the browser profile is still attached to `<workspace>/leads-hunt/browser-profile/`, reuse it.
   - Otherwise, start a fresh cloud browser session that writes into the same browser profile directory.
   - In either case, surface to the AE in Lark:
     - the **VNC URL** to open, and
     - the **VNC password** (or access token) needed to connect.

2. **Guide the AE to log into the BD-corporate Sales Nav account inside VNC**
   - Ask the AE to connect to the VNC browser and open Sales Navigator using their BD-corporate account.
   - The goal for this step is a live BD-corporate Sales Nav seat inside the remote Chromium, not another credential exchange in Lark.
   - Handle any SSO, MFA, OTP, app-push, or captcha challenge entirely inside the VNC browser. Do **not** ask the AE to paste codes or passwords into Lark.
   - When they are done, have them reply in Lark: *"Done, I'm logged into my BD Sales Nav account in the cloud browser."*

3. **Capture a VNC screenshot to verify the BD seat login state**
   - After the AE confirms, take a screenshot of the current VNC display and inspect it for a Sales Navigator page that is clearly past the login wall.
   - If the screenshot still shows a sign-in page, SSO prompt, or error state, tell the AE what you see and ask them to finish the login in the VNC browser, then take another screenshot.
   - Only continue once the screenshot clearly shows an authenticated Sales Navigator session for the BD-corporate seat.

4. **Persist the session via the existing helper script**
   - Once the screenshot check passes, run from the `leads-hunt` skill's scripts dir (NOT this skill — we don't duplicate playwright code):

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_session_setup.py
```

   - This script should pick up the cookies from `<workspace>/leads-hunt/browser-profile/` that were created or refreshed by the cloud browser, and normalize them into the format used by the rest of the pack.

After login, verify Salesforce sync:

```bash
python3 <leads-hunt-skill>/scripts/sales_nav_query.py BytePlus
```

Look for `crmStatus` in the response payload. If absent, the AE's seat does NOT have Salesforce sync enabled — Layer 3 dedup will be dead. Tell the AE:

> "Your BD seat is logged in, but Salesforce sync is not active on this seat. This is an IT thing — open a ticket asking BD IT to enable Sales Nav ↔ Salesforce sync for your seat. The pipeline will run without it but you'll get false positives in dedup."

Allow them to proceed (it's not blocking, just degraded).

### Step 5 — Topic file scaffolding

Ask:

> "Want to start with the example `aigc-visual` topic, or define your own now via `leads-hunt-add-target`?"

- **example**: copy `<leads-hunt-skill>/references/topics/aigc-visual.md` is already in place — just confirm it's enabled (frontmatter `enabled: true`). No copy needed; the file lives in the skill, not the workspace.
- **custom**: tell the AE to invoke `leads-hunt-add-target` after this wizard finishes:
  > *"After we wrap setup, message me 'add a leads-hunt target' and I'll walk you through your ICP."*

Either path is valid. Don't block.

### Step 6 — Schedule cron jobs

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

When all 6 steps pass, send to Lark:

> "All set. Voice file at `<workspace>/leads-hunt/style.md` is empty. Chat with me anytime to teach me your style — try *'add this to my outreach voice: [paste a real message]'* or *'set my voice rhythm to: [describe how you write]'*. You can do this now, later, or iteratively."

## Pitfalls (encoded — read before driving the wizard)

1. **LinkedIn captcha season**. If headless setup hits a captcha (`Let's do a quick security check`), the AE MUST log in manually from a non-headless Chromium against the same `<workspace>/leads-hunt/browser-profile/` directory ONCE to season the profile. Then retry step 3. Document this clearly when the failure occurs; AEs find it counterintuitive.

2. **OTP timeout (60s)**. If the AE is slow pasting OTP, the script aborts. The agent's job is to keep the Lark conversation responsive — prompt explicitly with a deadline ("paste OTP in the next minute or I'll restart"). On abort, re-run step 3 from scratch. Don't try to resume mid-OTP-flow.

3. **OpenClaw cron daemon not running**. `openclaw cron add` returns success even if the daemon is dead. After step 6, ALWAYS run `openclaw cron list` and confirm the 4 jobs are listed AND the daemon column shows `running`. If not, point at `openclaw doctor --fix`.

4. **Sibling skill discovery**. If `leads-hunt` is installed `--global` and `leads-hunt-setup` is workspace-local (or vice versa), path resolution between them can fail. Every script that needs to reach into a sibling skill accepts a `--leads-hunt-skill <path>` override. The agent should resolve the path from `openclaw skills list --paths` and pass it explicitly.

5. **Empty style.md is fine**. Step 2 creates a blank-slate `style.md`. Do NOT pre-fill it with examples or guess at the AE's voice. The wizard's final message tells the AE how to fill it later. Resist the temptation to be helpful here — a wrong voice is worse than no voice.

6. **Credentials never logged**. LinkedIn email/password, BD creds, OTP — none of these get echoed to Lark, written to logs, or persisted outside their canonical location (`browser-profile/` for cookies, `.env` for non-secret config). The agent must never repeat back a credential to confirm it; ask the AE to re-paste if unsure.

## Error recovery — quick pointers

| Symptom | Fix recipe |
|---|---|
| `openclaw: command not found` | Install OpenClaw first; this skill assumes the CLI is in PATH. |
| `feishu binding not found` | Run `openclaw onboard`. |
| Sibling skill missing | `openclaw skills install ./leads-hunt-<name>` from the pack repo. |
| LinkedIn `Wrong email or password` | Re-prompt the AE; common is typo'd password. |
| LinkedIn captcha | Manual seasoning (see Pitfall #1). |
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
   - `browser-profile/` has cookies AND `sales_nav_query.py BytePlus` returns JSON → skip steps 3/4.
   - At least one enabled topic file → skip step 5.
   - `openclaw cron list` shows 4 leads-hunt jobs → skip step 6.
3. Resume from the first unfinished step.

Ask the AE before skipping a step: *"Looks like step 3 is already done — your LinkedIn session is live. Skip it?"* — give them an out in case they want to re-do it (e.g. cookie rotation).
