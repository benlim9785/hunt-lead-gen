# Troubleshooting — leads-hunt-setup

Common failure modes encountered during the 7-step wizard, with fix recipes. Cross-reference [security.md](security.md) for credential-handling questions.

---

## Prereq failures

### `openclaw: command not found`

**Cause**: OpenClaw CLI is not installed or not in `PATH`.

**Fix**: Install OpenClaw first. This skill will not function without it. If installed but not in PATH, add the install dir to `~/.bashrc` (or shell equivalent) and `source` it.

### `openclaw agents bindings` shows no `feishu:` line

**Cause**: The AE has not run `openclaw onboard`, or onboarding completed but Lark binding was skipped.

**Fix**:
```bash
openclaw onboard
```
Follow the prompts; bind a Lark app. Then re-run `python3 scripts/check_prereqs.py`.

### Sibling skill missing

**Cause**: One of `leads-hunt`, `leads-hunt-outreach`, `leads-hunt-add-target`, `leads-hunt-voice` not installed in the active OpenClaw skills registry.

**Fix**: From the pack repo root:
```bash
openclaw skills install ./leads-hunt
openclaw skills install ./leads-hunt-outreach
openclaw skills install ./leads-hunt-add-target
openclaw skills install ./leads-hunt-voice
```

### Workspace already exists with kb.md

**Cause**: A prior run of `leads-hunt-setup` populated `<workspace>/leads-hunt/kb.md`, or the AE has been using the pipeline for a while.

**Fix**:
- If the AE wants to **resume setup** (e.g. just re-do steps 4/5 after an OTP timeout), do NOT pass `--force`. The wizard's resume logic skips already-done steps.
- If the AE genuinely wants to **start over**, back up `kb.md` first (it contains shipped leads + customer tracking that's painful to lose), then re-run with `--force`:
  ```bash
  cp <workspace>/leads-hunt/kb.md /tmp/kb.md.backup
  python3 scripts/init_state.py --force
  ```

---

## LinkedIn login (step 4)

### `Wrong email or password`

**Cause**: Typo, password rotated, or wrong account.

**Fix**: Re-prompt the AE in Lark. After 3 failures, suggest password reset and abort the wizard — don't burn LinkedIn's risk-engine budget on bad creds.

### `Check your LinkedIn app`

**Cause**: LinkedIn pushed an app-approval challenge to the AE's mobile LinkedIn app.

**Fix**: Tell the AE to open LinkedIn mobile and approve the prompt. The setup script polls; once approved, login proceeds.

### `Let's do a quick security check` (captcha / risk challenge)

**Cause**: LinkedIn's risk engine flagged the headless browser. Common in fresh `browser-profile/` directories with no cookie history.

**Fix** — manual seasoning (counterintuitive but reliable):

1. Tell the AE to install Chromium on the same machine if not already (`apt install chromium`).
2. Have them launch Chromium pointed at the same profile dir:
   ```bash
   chromium --user-data-dir=<workspace>/leads-hunt/browser-profile
   ```
3. Manually log in to https://www.linkedin.com/ in that Chromium window. Solve any captcha by hand.
4. Close Chromium.
5. Re-run step 4 — the headless script now inherits a "warm" profile.

### `verification code` (email OTP)

**Cause**: Expected fallback path. LinkedIn emailed a 6-digit code.

**Fix**: The setup script writes a status marker and waits up to 60s for `/tmp/lk_otp.txt`. Agent should:
1. Prompt AE in Lark: *"LinkedIn emailed an OTP. Paste it here within 60 seconds."*
2. On AE reply, write the value to `/tmp/lk_otp.txt`.
3. Script reads, deletes the file, continues.

If the AE misses the 60s window, the script aborts. Restart step 4.

### `sales_nav_query.py BytePlus` returns `needs-reauth` after setup claimed success

**Cause**: The setup script's success heuristic is fragile (see leads-hunt SKILL.md). It logged a "looks good" but actually didn't establish a full session.

**Fix**: Re-run step 4 from scratch. If it lies again twice in a row, fall back to manual seasoning (see captcha case above).

---

## BD-corporate Sales Nav SSO (step 5)

### `crmStatus` missing in the response payload

**Cause**: The AE's BD-corporate Sales Nav seat does not have Salesforce sync enabled. This is a BD IT thing, not a wizard thing.

**Fix**: Tell the AE to open a ticket with BD IT:
> "Please enable Sales Navigator ↔ Salesforce sync for my seat (email: <ae-bd-email>). Without it, our deal-dedup pipeline can't see which companies are already in our Salesforce instance."

The wizard can complete without this — just warn the AE that Layer 3 dedup will be degraded until IT acts.

### BD email login redirects to corporate SSO (Okta / Azure AD)

**Cause**: BD has SSO in front of LinkedIn. The setup script handles this if the SSO portal is plain username/password, but mileage varies.

**Fix**: If the script fails on the SSO redirect, fall back to manual seasoning (see LinkedIn captcha case). The AE logs into the BD corporate Sales Nav via Chromium against the same `browser-profile/` once, then headless re-uses the cookies.

---

## Cron registration (step 7)

### `openclaw cron add` succeeds but jobs never fire

**Cause**: OpenClaw cron daemon is not running. The CLI happily writes to SQLite even when the dispatcher is down.

**Fix**:
```bash
openclaw cron list   # confirm jobs are listed
openclaw doctor --fix
```
The `doctor --fix` should restart the daemon if it's stopped. If it can't, the AE's OpenClaw install is broken — escalate beyond this skill.

### Schedule string malformed

**Cause**: AE manually edited cron commands and broke the cron expression.

**Fix**: Standard cron format: `minute hour day-of-month month day-of-week`. Use https://crontab.guru/ to debug. The 4 default schedules are known-good.

### Job already registered (idempotency triggered unexpectedly)

**Cause**: A previous run of `register_cron.py` succeeded, then the AE re-ran the wizard.

**Fix**: This is correct behaviour — `register_cron.py` skips matching jobs. To force re-register, manually delete via `openclaw cron remove <id>` first.

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

**Cause**: `write_env.py` always chmods 600. If a previous run was as root and the wizard now runs as the AE's user (or vice versa), permissions clash.

**Fix**: `chown` the workspace dir to the user that runs OpenClaw:
```bash
sudo chown -R $USER <workspace>/leads-hunt
```

---

## When all else fails

Capture the failing command + full output, then drop into Lark with the AE and walk it manually. The wizard is a convenience; every step it does, the AE can do by hand.
