# "Why no new leads today?" — empty digest diagnostic

When the user asks "why no new leads today" / "today produced no leads at all" / "nothing in the digest," resolve this by inspecting the existing outputs first. Do **not** re-run the pipeline before diagnosing — the answer is usually in the logs.

## Check these artifacts first

- `<workspace>/leads-hunt/data/lead-gen/run-log-YYYY-MM-DD.txt`
- `<workspace>/leads-hunt/data/lead-gen/leads-aggregate-YYYY-MM-DD.csv`
- the per-topic CSVs for the same date

## Common causes, in observed frequency order

### 1. Total dedup drain (most common)
**Symptom**: Phase B produced candidates, but Phase C filtered almost all of them.

**Root cause**: Discovery resurfaced companies already covered by:
- Base `Skip List`
- Base `Customers`
- Base `Leads`
- Sales Nav CRM sync

**What to say**: The pipeline likely worked correctly; the discovery inputs were stale or saturated.

### 2. Score-floor drain
**Symptom**: Plenty of candidates discovered, few or none made it into the CSV.

**Root cause**: Most candidates scored below the configured threshold.

**What to say**: Discovery found names, but they were weak fits against the current rubric.

### 3. Sales Nav session problem
**Symptom**: Run-log shows `needs-reauth`, `sso-expired`, or many rows marked for manual review.

**Root cause**: The LinkedIn / Sales Nav session drifted after Phase A or was never fully healthy.

**What to say**: The CRM verification layer was unhealthy, so today's output may be empty or only partially verified. Refresh the VNC/browser session before trusting the next run.

### 4. Topic was genuinely dry
**Symptom**: Phase B itself found very few credible AI producers.

**Root cause**: The day's discovery method or target segment was low-yield.

**What to say**: Today looked like a low-signal discovery day for that topic. Try the next day's method or refresh the topic thesis.

## Minimal response template

> I checked the existing leads-hunt outputs instead of re-running the pipeline. Today's empty/skinny digest looks caused by **[dedup drain / score-floor drain / Sales Nav session issue / dry topic]**. The key evidence is in `<workspace>/leads-hunt/data/lead-gen/run-log-YYYY-MM-DD.txt`, where **[brief evidence]** shows why the candidates did not ship.

## Important rule

If the user asks "why no leads," **diagnose first**. Re-running without reading the existing run-log usually wastes time and can muddy the evidence.
