# Output Format

## Per-topic CSV

Path: `lead-gen/leads-<topic>-YYYY-MM-DD.csv`

12 columns:

| # | Column | Example |
|---|---|---|
| 1 | Company | Abmatic AI |
| 2 | Domain | abmatic.com |
| 3 | Topic | aigc-visual |
| 4 | Score | 9 |
| 5 | Industry | Marketing & Advertising |
| 6 | Region | US |
| 7 | EmployeeCount | 5 |
| 8 | InCRM | false |
| 9 | SalesforceURL | (empty if InCRM=false) |
| 10 | OutreachAngle | "Saw their ABM AI agent. Seedance could power their multi-channel video ads. Volume tier + Asia low-latency might fit." |
| 11 | DiscoveredVia | YC F2025 batch sweep |
| 12 | ProducerEvidence | "Their /pricing page shows an 'AI ad video generation' feature exposed to subscribers — customer-facing AI output" |

Column 12 (`ProducerEvidence`) is **mandatory** — it's the explicit citation that the candidate passed [Filter 0](./lead-philosophy.md). One short sentence pointing at the user-visible AI feature (URL fragment, product page screenshot caption, app-store listing, etc.). If you cannot fill this cell with concrete evidence, the candidate fails Filter 0 and must be skipped, not shipped. Audit-friendly format: agents reviewing past leads can verify the producer claim by visiting the URL hint.

Header row present (Phase D writes it from `assets/csv-template.csv`).

## Aggregate CSV

Path: `lead-gen/leads-aggregate-YYYY-MM-DD.csv`

Same 11-column schema. Rows from both per-topic CSVs concatenated, sorted by `Score` descending.

## Lark digest

Single message at ~9:30AM MYT to `+601139987039` via existing announce mode. Top 5 across both topics.

### Template

```
🎯 *AIGC Lead Report — YYYY-MM-DD*

✅ All leads verified against BytePlus Salesforce via Sales Nav (none in CRM).

━━━━━━━━━━━━━━━━━━━━

*Top 5 by score:*

1. ⭐ {score}/10 *{company}* ({region}) — {topic}
🌐 {domain}
💡 {one-line outreach hook}

2. ⭐ {score}/10 *{company}* ({region}) — {topic}
...

━━━━━━━━━━━━━━━━━━━━

📊 {N_aigc_visual} aigc-visual + {N_seed3d} seed3d = {total} net-new today
🔍 Methods: {aigc_visual_method}, {seed3d_method}
⚠️ {N_skipped_in_crm} skipped (in CRM), {N_below_score} skipped (score <8)

📁 Full CSVs:
~/.openclaw/workspace-clawhunt/lead-gen/leads-aggregate-YYYY-MM-DD.csv
```

### Rules

- **No em-dash (—) or en-dash (–)** anywhere in the message. Use period, comma, colon, or parenthesis.
- **Light emoji only**: ⭐ 🌐 💡 📊 🔍 ⚠️ 📁 ✅. Never gratuitous.
- **Keep total under 1500 characters** to avoid Lark split.
- **Topic name** is the slug, not a translation: `aigc-visual` and `seed3d`.

## When zero leads ship

If a topic produces 0 leads (rare but possible on bad days):

```
🎯 *AIGC Lead Report — YYYY-MM-DD*

⚠️ {topic} ran dry today: 0 net-new after dedup.
{other_topic}: {N} leads (see CSV).

📁 ~/.openclaw/workspace-clawhunt/lead-gen/leads-aggregate-YYYY-MM-DD.csv
```

Reflection paragraph for the dry topic should explain what verticals were tried + what to try tomorrow.

## When BD SSO expires

Phase A sends a different message (no leads):

```
⚠️ *ClawHunt: BD SSO expired*

Cannot verify CRM today. Run:
LK_EMAIL=... BD_EMAIL=... python3 /root/.openclaw/workspace-clawhunt/scripts/sales-nav-session-setup.py

Reply with OTP via Lark when prompted. Will retry tomorrow.
```
