# Troubleshooting — leads-hunt-setup

Common failure modes encountered during the 6-step wizard, with fix recipes. Cross-reference [security.md](security.md) for credential-handling questions.

---

## Prereq failures

### Companion skill missing

**Cause**: One of `leads-hunt`, `leads-hunt-outreach`, `leads-hunt-add-target`, or `leads-hunt-voice` is not available in the current AIME workspace.

**Fix**: Make sure all companion skills are installed/enabled for the current AIME workspace before re-running setup.

### Workspace already exists with kb.md

**Cause**: A prior run of `leads-hunt-setup` populated `<workspace>/leads-hunt/kb.md`, or the AE has been using the pipeline for a while.

**Fix**:
- If the AE wants to **resume setup** (for example just re-do steps 4/5 after a partial failure), do NOT pass `--force`. The wizard's resume logic skips already-done steps.
- If the AE genuinely wants to **start over**, back up `kb.md` first (it contains shipped leads + customer tracking that's painful to lose), then re-run with `--force`:
  ```bash
  cp <workspace>/leads-hunt/kb.md /tmp/kb.md.backup
  python3 scripts/init_state.py --force
  ```

---

## LinkedIn login (step 3)

### `Wrong email or password`

**Cause**: Typo, password rotated, or wrong account.

**Fix**: Re-prompt the AE and have them try again inside the cloud browser. After repeated failures, suggest password reset and abort the wizard — don't burn LinkedIn's risk-engine budget on bad creds.

### `Check your LinkedIn app`

**Cause**: LinkedIn pushed an app-approval challenge to the AE's mobile LinkedIn app.

**Fix**: Tell the AE to open LinkedIn mobile and approve the prompt, then continue in the VNC session.

### `Let's do a quick security check` (captcha / risk challenge)

**Cause**: LinkedIn's risk engine flagged the login flow. Common in fresh `browser-profile/` directories with no cookie history.

**Fix** — manual seasoning inside the cloud browser flow:

1. Keep the AE in the same browser profile used by setup.
2. Have them complete the LinkedIn login manually in the VNC browser, including any captcha.
3. Once the browser is clearly authenticated, re-run the verification step.

### Verification challenge during login

**Cause**: Expected fallback path. LinkedIn or Sales Navigator requested an OTP, MFA prompt, or similar check.

**Fix**: Have the AE complete the challenge directly in the cloud browser session. If the session expires or the browser gets stuck on login, restart step 3 with a fresh VNC session.

### `sales_nav_query.py BytePlus` returns `needs-reauth` after setup claimed success

**Cause**: The setup script's success heuristic is fragile. It reported a healthy login, but the browser cookies were not sufficient for a full session.

**Fix**: Re-run step 3 from scratch. If it still fails repeatedly, restart from a fresh cloud-browser session and verify the authenticated state with another screenshot before proceeding.

---

## BD-corporate Sales Nav SSO (step 4)

### `crmStatus` missing in the response payload

**Cause**: The AE's BD-corporate Sales Nav seat does not have Salesforce sync enabled. This is a BD IT thing, not a wizard thing.

**Fix**: Tell the AE to open a ticket with BD IT:
> "Please enable Sales Navigator ↔ Salesforce sync for my seat (email: <ae-bd-email>). Without it, our deal-dedup pipeline can't see which companies are already in our Salesforce instance."

The wizard can complete without this — just warn the AE that Layer 3 dedup will be degraded until IT acts.

### BD login redirects to corporate SSO (Okta / Azure AD)

**Cause**: BD has SSO in front of LinkedIn. The browser session can still work, but the exact redirect flow varies.

**Fix**: Have the AE complete the SSO flow directly in the VNC browser. Once Sales Navigator is visibly logged in, take a fresh screenshot and continue.

---

## Scheduler setup (step 6)

### Recurring jobs were supposedly registered but never fired

**Cause**: The local scheduler entry was not actually installed, the environment differs under cron, or the host machine's scheduler is disabled.

**Fix**:
```bash
crontab -l
```
Confirm the leads-hunt entries are present. If they are missing, run `python3 scripts/register_cron.py` again or use the generated `cron-suggestions.txt` and install the jobs manually.

### Schedule string malformed

**Cause**: Someone manually edited the schedule and broke the cron expression.

**Fix**: Standard cron format: `minute hour day-of-month month day-of-week`. Use https://crontab.guru/ to debug. The 4 default schedules are known-good.

### Job already registered (idempotency triggered unexpectedly)

**Cause**: A previous run of `register_cron.py` succeeded, then the AE re-ran the wizard.

**Fix**: This is correct behaviour — `register_cron.py` skips matching jobs. To force re-register, remove the corresponding leads-hunt entries from `crontab -l`, then run the script again.

---

## Workspace + state

### `--force` semantics

`init_state.py --force` rewrites `kb.md` to the empty H2 skeleton. **It does not delete `data/`, `browser-profile/`, or `.env`.** Those are preserved across re-inits. Only the KB resets.

If the AE wants a true full reset, do it manually:
```bash
rm -rf <workspace>/leads-hunt
python3 scripts/init_state.py
```

### Permission denied on `<workspace>/leads-hunt/.env`

**Cause**: `write_env.py` always chmods 600. If a previous run was under a different user account, permissions can clash.

**Fix**: Make sure the workspace dir is owned by the same user account that runs the setup flow:
```bash
sudo chown -R $USER <workspace>/leads-hunt
```

---

## When all else fails

Capture the failing command + full output, then walk the step manually with the AE. The wizard is a convenience; every step it does, the AE can do by hand.
