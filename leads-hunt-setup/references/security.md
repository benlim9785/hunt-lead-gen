# Security — what credentials this skill handles

The `leads-hunt-setup` wizard handles several sensitive inputs during onboarding. This document is the contract: what gets collected, where it's stored, and what the AE is responsible for.

This skill does **not** collect or store any LLM provider API keys. The host agent runtime is provided by AIME; nothing in this pack talks directly to OpenAI / Anthropic / Bedrock.

## Credentials collected

### 1. LinkedIn personal login

- **Used by**: `<leads-hunt>/scripts/sales_nav_session_setup.py` together with the cloud-browser/VNC login flow.
- **Stored as**: HTTP cookies inside `<workspace>/leads-hunt/browser-profile/` (Chromium persistent context). Plaintext credentials are **not written to disk** by this setup skill.
- **Lifetime**: cookies persist until LinkedIn invalidates them. Re-run the LinkedIn login step of the wizard when `sales_nav_query.py` returns `needs-reauth`.
- **Never logged**: credentials are entered by the AE directly into the VNC browser session, not echoed back into Lark.

### 2. LinkedIn / Sales Nav verification challenges

- **Handled in-browser**: MFA, OTP, app-push, or captcha challenges are completed by the AE directly inside the cloud browser session.
- **Stored**: challenge data is not intentionally persisted by this skill outside the browser session and resulting cookies.

### 3. BD-corporate Sales Nav login

- **Same treatment as #1 and #2**, against the same `browser-profile/` directory but a separate authenticated seat.
- **Note**: BD-corporate auth is still subject to BD's own security policy. If BD requires MFA on every login, expect the AE to re-do the BD-SSO step frequently.

### 4. Lark / messaging tokens

- **NOT handled by this skill directly**. AIME and the surrounding messaging integrations own any required messaging credentials.
- The skill does persist non-secret Base wiring metadata — Base token, Base URL, table IDs, webhook URL, and workflow metadata — into `<workspace>/leads-hunt/config.json`.
- If the AE asks to rotate a messaging token or rebind an integration, handle that through the relevant AIME integration flow rather than this skill.

## File-system layout (after setup)

```text
<workspace>/leads-hunt/
├── .env                    # mode 0600. Non-secret config only.
├── config.json             # NOT secret. Base token/URL, table IDs, webhook URL, workflow metadata.
├── kb.md                   # Legacy compatibility notes file only; not the runtime source of truth.
├── style.md                # NOT secret. AE's outreach voice.
├── browser-profile/        # CONTAINS LinkedIn + BD session cookies.
│   ├── Default/Cookies     # SQLite — readable by anyone with FS access.
│   └── ...
├── data/                   # Cached lead candidates, run logs, generated CSVs.
└── cron-suggestions.json   # Canonical scheduler specs if step 6 was declined.
```

## What the AE is responsible for

1. **Do NOT commit `.env` or `browser-profile/` to git.** The pack ships a `.gitignore` that excludes both, but if the AE creates their own repo on top, double-check.

   ```gitignore
   # leads-hunt-pack/.gitignore (recommended)
   **/.env
   **/browser-profile/
   **/data/
   **/style.md
   ```

   `kb.md` is no longer sensitive runtime state, but it is still safer not to commit per-AE notes unless intentionally shared.

2. **Workstation hygiene**. Anyone with read access to the AE's home dir can read `.env` and impersonate the LinkedIn session via `browser-profile/`. The wizard cannot fix this — full-disk encryption + screen lock are the AE's problem.

3. **Rotate after exposure**. If the AE has any suspicion that their LinkedIn or BD-corp session was compromised, wipe `browser-profile/` (`rm -rf browser-profile/`) and re-run the LinkedIn / BD-SSO steps. For BD-corp password compromise, follow BD IT's standard rotation procedure first, then re-run the BD-SSO step.

4. **No sharing across AEs**. Each AE's workspace is per-AE state. Sharing `browser-profile/` between AEs will cause LinkedIn to flag both seats. Sharing `.env` is just bad credential hygiene.

## What this skill explicitly does NOT do

- Does not collect or store LLM provider API keys. The host agent runtime is AIME's responsibility.
- Does not transmit credentials to Nous Research or any third party — credentials only go to the provider they belong to (LinkedIn → linkedin.com, BD-corp SSO → BD's IdP, etc.).
- Does not write credentials to any central platform state on behalf of the AE. All workspace secrets are workspace-local.
- Does not encrypt `.env` at rest. Mode 0600 is the only protection. AEs who want stronger guarantees should run inside an encrypted home dir or equivalent.

## Audit trail

If the AE wants to verify what a script does with their credentials, every script in `scripts/` is plain Python in this repo. There are no compiled binaries, no obfuscated calls. `grep -r "password\|secret" scripts/` will find every reference.
