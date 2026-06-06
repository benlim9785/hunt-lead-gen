# Security — what credentials this skill handles

The `leads-hunt-setup` wizard collects several secrets during onboarding. This document is the contract: what gets collected, where it's stored, and what the AE is responsible for.

## Credentials collected

### 1. LinkedIn personal email + password

- **Used by**: `<leads-hunt>/scripts/sales_nav_session_setup.py` (Playwright login flow).
- **Stored as**: HTTP cookies inside `<workspace>/leads-hunt/browser-profile/` (Chromium persistent context). The plaintext password is **never written to disk**.
- **Lifetime**: cookies persist until LinkedIn invalidates them (typically weeks-to-months of low risk activity, less under captcha pressure). Re-run step 5 of the wizard when `sales_nav_query.py` returns `needs-reauth`.
- **Never logged**: The setup script reads the password from stdin and passes it directly to the Playwright `page.fill(...)` call. It is not echoed, written to log files, or sent to Lark.

### 2. LinkedIn email-OTP code

- **Collected via**: Lark message from the AE, written to `/tmp/lk_otp.txt`.
- **Stored**: in `/tmp/lk_otp.txt` for at most ~60 seconds — the setup script reads, uses, and deletes the file.
- **Cleanup**: if the script aborts (timeout, exception), `/tmp/lk_otp.txt` may persist. Wizard should clean up: `rm -f /tmp/lk_otp.txt`. The OTP is single-use anyway, so leakage risk is bounded by LinkedIn's TTL (typically 5 minutes).

### 3. BD-corporate email + password + OTP

- **Same treatment as #1 and #2**, against the same `browser-profile/` directory but a separate cookie set for the corporate seat.
- **Note**: BD-corporate creds are subject to BD's own security policy. If BD requires MFA on every login (as opposed to a remembered device), expect the AE to re-do step 6 frequently.

### 4. LLM provider API key

- **Collected for**: OpenAI (`OPENAI_API_KEY`), Anthropic (`ANTHROPIC_API_KEY`), or AWS Bedrock (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + optional `AWS_REGION`).
- **Stored as**: plain text in `<workspace>/leads-hunt/.env`, mode `0600` (owner read/write only). Atomic write via temp-file rename, so partial writes never expose the key.
- **Read by**: scripts in this pack at runtime via `os.environ` (after `dotenv` load) or direct `.env` parsing.
- **Never logged**: `test_llm_call.py` redacts to last-4-chars in summaries. Other scripts should follow the same convention; if you find an unredacted key in a log, file it as a bug.

### 5. Lark target chat ID (`LARK_HUNT_CHANNEL`)

- **Not strictly secret**, but stored alongside the LLM key in `.env` for convenience.
- The chat ID alone doesn't grant access — Lark posting requires the bound bot's token, which is managed by OpenClaw Gateway, not this skill.

### 6. Lark bot tokens

- **NOT handled by this skill at all**. OpenClaw Gateway owns Lark API tokens. The wizard only verifies that a feishu binding exists — it never reads or relays the token.
- If the AE asks to rotate the Lark token, the answer is "rerun `openclaw onboard`", not "rerun `leads-hunt-setup`".

## File-system layout (after setup)

```
<workspace>/leads-hunt/
├── .env                    # mode 0600. LLM key + LARK_HUNT_CHANNEL.
├── kb.md                   # NOT secret, but per-AE business intel.
├── style.md                # NOT secret. AE's outreach voice.
├── browser-profile/        # CONTAINS LinkedIn + BD session cookies.
│   ├── Default/Cookies     # SQLite — readable by anyone with FS access.
│   └── ...
├── data/                   # Cached lead candidates, run logs.
└── cron-suggestions.txt    # Plain text cron commands (only if step 8 declined).
```

## What the AE is responsible for

1. **Do NOT commit `.env` or `browser-profile/` to git.** The pack ships a `.gitignore` that excludes both, but if the AE creates their own repo on top, double-check.

   ```
   # leads-hunt-pack/.gitignore (already in place)
   **/.env
   **/browser-profile/
   **/data/
   **/kb.md
   **/style.md
   ```

2. **Workstation hygiene**. Anyone with read access to the AE's home dir can read `.env` and impersonate the LinkedIn session via `browser-profile/`. The wizard cannot fix this — full-disk encryption + screen lock are the AE's problem.

3. **Rotate after exposure**. If the AE accidentally pastes the LLM key into a public Slack / Lark / GitHub, treat it as compromised: revoke at the provider, generate a new one, re-run wizard step 4. Cookies in `browser-profile/` should also be wiped (`rm -rf browser-profile/` then re-run step 5) if there's any suspicion the workstation was compromised.

4. **No sharing across AEs**. Each AE's workspace is per-AE state. Sharing `browser-profile/` between AEs will cause LinkedIn to flag both seats. Sharing `.env` is just bad credential hygiene.

## What this skill explicitly does NOT do

- Does not transmit credentials to Nous Research, Anthropic, or any third party — credentials only go to the provider they belong to (LinkedIn → linkedin.com, OpenAI key → api.openai.com, etc.).
- Does not write credentials to OpenClaw's central state (Gateway, SQLite). All secrets are workspace-local.
- Does not encrypt `.env` at rest. Mode 0600 is the only protection. AEs who want stronger guarantees should run inside a LUKS-encrypted home dir or equivalent.

## Audit trail

If the AE wants to verify what a script does with their credentials, every script in `scripts/` is plain Python in this repo. There are no compiled binaries, no obfuscated calls. `grep -r "password\|api_key\|secret" scripts/` will find every reference.
