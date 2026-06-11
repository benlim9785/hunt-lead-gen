# Lark Base webhook handler setup

This doc covers the live `Leads -> Draft Message -> webhook -> Message Draft` automation for leads-hunt.

## Current live endpoint

- **Webhook endpoint:** `https://8765-63695237a9154ca7b1d59be422f9fa1b-cube-kubestrato-online6.code-server.strato-https-proxy.bytedance.net/leads-hunt/draft`
- **Health check:** `https://8765-63695237a9154ca7b1d59be422f9fa1b-cube-kubestrato-online6.code-server.strato-https-proxy.bytedance.net/healthz`
- **Base URL:** `https://bytedance.my.larkoffice.com/base/GhaRbzKzKa99GbsUA3RmDpWqywd`
- **Leads table ID:** `tblbBRdDEIT3IQy2`
- **Workflow name:** `Generate outreach draft when Draft Message = Yes`

> The webhook URL is environment-specific. If the server is restarted on a different port or machine, update the Lark Base workflow and `<workspace>/leads-hunt/config.json` together.

## Trigger contract

The Base automation watches the `Leads` table and fires when:

- **Table:** `Leads`
- **Field:** `Draft Message`
- **Condition:** field value `is` `Yes`

The workflow sends a `POST` JSON request to the webhook URL.

### Expected request body

```json
{
  "event": "leads_hunt_draft_requested",
  "base_token": "GhaRbzKzKa99GbsUA3RmDpWqywd",
  "table_id": "tblbBRdDEIT3IQy2",
  "table_name": "Leads",
  "record_id": "rec_xxx",
  "message_field": "Message Draft",
  "draft_toggle_field": "Draft Message"
}
```

## Handler behavior

When the webhook fires, the server does the following:

1. Validates the payload (`event`, `record_id`, `table_name`, Base/table match)
2. Reads the current lead row from Lark Base by `record_id`
3. Returns success without rewriting if:
   - `Draft Message == Done` and `Message Draft` is already non-empty
   - or `Draft Message` is no longer `Yes`
4. Reads `<workspace>/leads-hunt/style.md` fresh on every request
5. Generates a short outbound draft from the row's `Company`, `Summary`, `Topic`, and the current voice hints in `style.md`
6. Writes the draft back to `Message Draft`
7. Sets `Draft Message` to `Done`

If generation fails, the handler returns a non-2xx response and leaves `Draft Message` at `Yes` so the AE can retry.

## Files involved

### Webhook server

```bash
python3 leads-hunt/scripts/draft_webhook_server.py --host 0.0.0.0 --port 8765
```

- Endpoint path: `/leads-hunt/draft`
- Health path: `/healthz`
- The public HTTPS URL comes from `aime ports` after the server starts listening.

### Existing-Base connector

Use this helper when the Base already exists and only the webhook + local config need to be wired:

```bash
python3 leads-hunt-setup/scripts/connect_existing_lark_base.py \
  --base-token GhaRbzKzKa99GbsUA3RmDpWqywd \
  --base-url "https://bytedance.my.larkoffice.com/base/GhaRbzKzKa99GbsUA3RmDpWqywd" \
  --webhook-url "https://8765-63695237a9154ca7b1d59be422f9fa1b-cube-kubestrato-online6.code-server.strato-https-proxy.bytedance.net/leads-hunt/draft"
```

What it does:

- resolves the 4 expected table IDs from the existing Base
- creates or updates the `Draft Message = Yes` workflow
- enables that workflow
- writes `<workspace>/leads-hunt/config.json`
- initializes `<workspace>/leads-hunt/style.md` from the empty voice skeleton if missing

## Workflow shape

The installed workflow uses:

- **Trigger:** `SetRecordTrigger`
  - table: `Leads`
  - field: `Draft Message`
  - condition: `is Yes`
- **Action:** `HTTPClientAction`
  - method: `POST`
  - content type: `application/json`
  - body: static JSON prefix + `$.step_trigger.recordId` + static suffix

## Manual test flow

1. Start the webhook server.
2. Run `aime ports` and copy the public HTTPS URL for port `8765`.
3. Connect the existing Base with `connect_existing_lark_base.py` using that URL.
4. In the `Leads` table, set one test row's `Draft Message` field to `Yes`.
5. Wait a few seconds.
6. Confirm that:
   - `Message Draft` is populated
   - `Draft Message` has moved to `Done`

> Note: `SetRecordTrigger` is a modification trigger. In practice, the clean human verification path is to flip the field inside the Lark Base UI. API-side updates were not observed to fire this trigger in my test run, so use a manual UI edit for final acceptance.

## Response contract

### Success

```json
{
  "accepted": true,
  "record_id": "rec_xxx",
  "status": "draft_written"
}
```

### Idempotent noop

```json
{
  "accepted": true,
  "record_id": "rec_xxx",
  "status": "already_done"
}
```

or

```json
{
  "accepted": true,
  "record_id": "rec_xxx",
  "status": "noop_draft_state"
}
```

### Invalid payload

```json
{
  "error": "invalid_event"
}
```

## Notes

- `style.md` is read on every request so later voice edits take effect immediately.
- The Base row is the source of truth for the draft lifecycle.
- The webhook server is intentionally stdlib-only and can run directly inside the AIME workspace.
