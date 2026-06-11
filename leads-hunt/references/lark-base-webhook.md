# Lark Base webhook handler spec

This document defines the expected AIME-side behavior when the `Leads` table in the leads-hunt Lark Base flips `Draft Message` to `Yes`.

## Trigger contract

The Base automation should watch the `Leads` table and fire when:

- **Table:** `Leads`
- **Field:** `Draft Message`
- **Condition:** field value `is` `Yes`

The workflow should `POST` JSON to the configured AIME webhook endpoint.

### Expected request body

```json
{
  "event": "leads_hunt_draft_requested",
  "base_token": "<base_token>",
  "table_id": "<leads_table_id>",
  "table_name": "Leads",
  "record_id": "rec_xxx",
  "message_field": "Message Draft",
  "draft_toggle_field": "Draft Message"
}
```

### Endpoint configuration

- During setup, pass the webhook URL into `leads-hunt-setup/scripts/create_lark_base.py` with:
  - `--webhook-url <your-aime-webhook-endpoint>`
  - or environment variable `AIME_LEADS_HUNT_WEBHOOK_URL`
  - or environment variable `LEADS_HUNT_AIME_WEBHOOK_URL`
- The setup helper stores that URL in `<workspace>/leads-hunt/config.json` under `lark_base.webhook_url`.
- If no webhook URL is available yet, the Base can still be created first. In that case, leave the automation disabled and configure it later once the AIME endpoint exists.

## Handler behavior

When the webhook fires, AIME should do the following in order:

1. **Validate the payload**
   - Confirm `event == leads_hunt_draft_requested`
   - Confirm `record_id` is present
   - Confirm the request points to the `Leads` table

2. **Read the lead row from Lark Base**
   - Read the latest row by `record_id`
   - The minimum fields needed are:
     - `Company`
     - `Topic`
     - `Score`
     - `Sales Nav URL`
     - `LinkedIn URL`
     - `Summary`
     - `Draft Message`
     - `Message Draft`
     - `Date`
     - `Status`

   Suggested helper:

   ```bash
   python3 scripts/lark_base_sync.py get-lead --record-id rec_xxx
   ```

3. **Idempotency guard**
   - If `Draft Message` is already `Done` and `Message Draft` is non-empty, return success without generating a second draft.
   - If `Draft Message` is no longer `Yes`, return success without doing anything.

4. **Load AE voice and context**
   - Read `<workspace>/leads-hunt/style.md` fresh for every request.
   - Use the existing leads-hunt outreach behavior: the draft should reflect the AE's current voice, not a cached style snapshot.

5. **Generate the draft**
   - Draft a short outbound message for the company in the AE's voice.
   - Use the row fields as the prompt context.
   - Prioritize `Summary` as the outreach angle if present.
   - If `Summary` is empty, infer the angle from `Topic`, `Company`, and any URLs available on the row.

6. **Write the draft back to Base**
   - Write the generated text into `Message Draft`
   - Set `Draft Message` to `Done`

   Suggested helper:

   ```bash
   python3 scripts/lark_base_sync.py update-draft --record-id rec_xxx --draft-file /tmp/draft.txt
   ```

7. **Failure behavior**
   - Do **not** set `Draft Message` to `Done` if generation fails.
   - Leave the field at `Yes` so the AE can retry after the underlying issue is fixed.
   - Log the failure with the `record_id` and the reason.

## Response contract

AIME should return a 2xx JSON response on accepted requests.

Example:

```json
{
  "accepted": true,
  "record_id": "rec_xxx",
  "status": "draft_written"
}
```

If the event is invalid, return a non-2xx response with a short JSON error.

## Implementation notes

- Keep the Base row as the source of truth for the draft lifecycle.
- Always read `style.md` fresh so updates from `leads-hunt-voice` take effect immediately.
- Base workflow retries are possible, so the handler should remain idempotent.
- The webhook path itself is environment-specific; the setup helper stores the exact URL that was used when the workflow was created.
