# Dedup Process (3-layer stack)

For every candidate, walk these layers in order. First decisive signal wins. Cheapest layers go first.

## Why Lark Base is the source of truth

The runtime system of record now lives in the configured Lark Base, not in a local markdown file:

- `Leads` drives historical shipped-lead dedup and draft state.
- `Customers` drives customer suppression.
- `Skip List` drives hard-skips.
- `Discovery Patterns` feeds Phase B learning loops.

Local CSVs (`leads-{topic}-YYYY-MM-DD.csv`, `leads-aggregate-YYYY-MM-DD.csv`) are outputs only. They can be deleted and regenerated without changing future dedup behavior.

`<workspace>/leads-hunt/kb.md` may still exist as a compatibility/notes file, but it is **not** consulted by the runtime dedup pipeline anymore.

## Layer 1 — Base `Skip List`

Fastest filter. If the candidate's domain or normalized company name matches a record in the `Skip List` table, drop it immediately.

Typical sources of skip entries:
- manual AE hard-skips
- auto-skips when a company website mentions BytePlus/ByteDance/VolcEngine/Doubao/Jimeng/Seedream/Seedance
- known irrelevant or saturated names the AE never wants to see again

## Layer 2 — Base `Customers` + Base `Leads`

`kb.already_seen()` fuzzy-matches the candidate company name against both tables:

- `Customers` = already a BytePlus customer / active account
- `Leads` = already shipped by this system before

This gives cross-day memory without depending on local files.

Operational implications:
- Cross-day shipment dedup comes from the Base `Leads` table.
- Manual AE additions should go into the relevant Base table, not `kb.md`.
- Phase D upserts shipped leads into Base so tomorrow's run sees them automatically.

## Layer 3 — Sales Nav CRM check (truth signal)

If the candidate survives Layers 1-2, run the live Sales Navigator CRM check via `sales_nav_check.py`.

Possible outcomes:

1. **`in_crm = true`**
   - Candidate is already present in the synced Salesforce tenant.
   - Drop it.

2. **`in_crm = false` with a normal JSON response**
   - Candidate is not currently in CRM.
   - Keep it (subject to score ceiling / per-topic ceiling).

3. **`needs-reauth` / `sso-expired`**
   - Phase A should usually catch this before Phase C starts.
   - If it still happens mid-run, treat it as a session-health problem and refresh the VNC/browser session before trusting future runs.
   - The current pipeline may still mark such rows for manual review rather than hard-dropping them, so read the run-log before deciding whether a digest is fully verified.

4. **Sales Nav company not found**
   - The current pipeline may still ship the row with `SalesNavNotFound=true` so the AE can manually review it.
   - This is a weaker signal than a clean `in_crm = false` result.

## Cache behavior

Layer 3 uses a rolling JSONL cache at `data/lead-gen/sales-nav-cache.jsonl`.

- Cache key: normalized lowercase company name
- TTL: 24 hours
- Purpose: avoid repeated Playwright lookups for the same company in one day

The cache accelerates repeated checks, but the live Sales Nav result remains the real truth signal.

## Failure-handling guidance

- **Phase A fails (`exit 3`)**: stop relying on Layer 3 until the session is refreshed.
- **Empty digest**: do not immediately re-run the pipeline; inspect the run-log first.
- **Unexpected drops in shipped count**: compare candidate count vs kept count in the run-log to see whether Layers 1-2 or Layer 3 did most of the filtering.

## Related docs

- [output-format.md](output-format.md)
- [empty-digest-diagnostic.md](empty-digest-diagnostic.md)
- [layer4-vs-linked-api.md](layer4-vs-linked-api.md)
