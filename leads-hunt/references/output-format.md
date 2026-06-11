# Output Format

## Per-topic CSV

Path: `<workspace>/leads-hunt/data/lead-gen/leads-<topic>-YYYY-MM-DD.csv`

13 columns:

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
| 9 | SalesforceURL | (empty if `InCRM=false`) |
| 10 | OutreachAngle | "Saw their ABM AI agent. Seedance could power their multi-channel video ads." |
| 11 | DiscoveredVia | YC F2025 batch sweep |
| 12 | ProducerEvidence | "Their pricing page exposes AI-generated ad video output to paying users." |
| 13 | SalesNavNotFound | false |

Notes:
- `SalesNavNotFound=true` means the row was not cleanly confirmed by the normal Sales Nav company lookup path and may need manual review.
- The per-topic CSV is Phase C output.

## Aggregate CSV

Path: `<workspace>/leads-hunt/data/lead-gen/leads-aggregate-YYYY-MM-DD.csv`

This is the merged Phase D output across all enabled topics. It uses the **same 13-column schema** as the per-topic CSVs and is sorted by `Score` descending.

## Lark digest shape

Phase D prints a markdown digest to stdout for the invoking agent to post into Lark. The digest includes:

- one headline line with the date
- total shipped count
- top leads summary grouped from the aggregate CSV
- a reference to the aggregate CSV path
- per-topic notes when a topic was dry or heavily deduped

Typical successful delivery includes only rows that survived:
- Filter 0 (AI producer vs consumer)
- score floor
- Layer 1 Base `Skip List`
- Layer 2 Base `Customers` + `Leads`
- Layer 3 Sales Nav CRM check

## When BD SSO expires

Phase A sends a different message (no verified leads):

```text
⚠️ *ClawHunt: BD SSO expired*

Cannot verify CRM today. Run:
python3 <leads-hunt-skill>/scripts/sales_nav_session_setup.py

Use the leads-hunt-setup VNC login flow to refresh the shared browser profile for LinkedIn / Sales Navigator.
Complete any OTP / MFA / captcha directly inside the VNC browser, then retry the check.
```

## Important distinction

- **Source of truth**: Lark Base (`Leads`, `Customers`, `Skip List`, `Discovery Patterns`)
- **Generated artifacts**: per-topic CSVs, aggregate CSV, run logs, candidate JSONs

Deleting CSVs changes reporting history, but it does **not** erase dedup memory. Dedup memory lives in Lark Base.
