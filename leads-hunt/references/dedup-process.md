# Dedup Process (3-layer stack)

For every candidate, walk these layers in order. First hit wins (skip the candidate, log to run-log). Cheapest layers first.

## Why `kb.md` is the source of truth

Phase D's `deliver_lark.py` appends every shipped lead to `<workspace>/leads-hunt/kb.md` under `## Shipped Leads` at the end of every run. Layer 2 reads from that file. Local CSVs (`leads-{topic}-YYYY-MM-DD.csv`) are **pure outputs**, not state — they can be deleted/regenerated without affecting future dedup correctness.

Operational implications:
- Cross-day shipment dedup is driven entirely by `kb.md`'s Shipped Leads section. Old companies never fall off the list as long as their entry remains.
- The AE can manually add to `kb.md` (e.g. customers tracked elsewhere, leads marked dead, false positives) and Layer 2 picks them up on the next run.
- `kb.md` is the **portable** state — git-versioned if the AE chooses, Obsidian-compatible, grep-friendly.
- Format is line-oriented: `- <slug> · <date> · key=value`. Helper `kb.py` provides `already_seen(name)`, `append_shipped(rows, date)`, `read_recent_patterns(topic, days)`.

## Layer 1 — `skip-list.txt`

`<workspace>/leads-hunt/data/skip-list.txt`. Format: one bare domain or company name per line, with `#` comments for cohorts. Match by lowercased company name OR domain.

Hit reasons:
- `manual-skip` — entry was added by AE directly
- `auto-skip-from-cohort-YYYY-MM-DD` — entry was appended by a previous run (e.g. saturated vertical detected)
- `confirmed-customer` — AE annotated this manually
- `byteplus-mention` — website mentioned a BytePlus product

## Layer 2 — `kb.md` (the source-of-truth layer)

Reads `<workspace>/leads-hunt/kb.md`. Two H2 sections matter for dedup:

```markdown
## Customers
- acme-corp · 2025-12-01 · status=active
- globex · 2026-01-15 · status=churned

## Shipped Leads
- foobar-ai · 2026-05-20 · topic=aigc-visual · score=9
- bazquux · 2026-05-22 · topic=seed3d · score=8
```

Names from both sections are normalized (lowercase, strip punctuation, strip "AI"/"Inc"/"Corp" suffixes) and merged into a single set. Match on **normalized company name**.

Hit reasons:
- `tracked-customer` — match against `## Customers`
- `previously-shipped-lead` — match against `## Shipped Leads`

The AE can use `kb.md` for any other note-taking (the `## Discovery Patterns Learned` section is read by Phase B's brief; the `## Skip List` section is a freeform area for AE notes that doesn't affect dedup directly — that's `skip-list.txt`'s job).

## Layer 3 — Sales Nav CRM check (the truth signal)

Use `scripts/sales_nav_check.py` which wraps `scripts/sales_nav_query.py`.

Checks BytePlus's actual Salesforce via LinkedIn Sales Navigator's CRM Sync badge. Returns one of:
- `in_crm: true` → SKIP, append to skip-list with `auto-skip-sales-nav-YYYY-MM-DD`
- `in_crm: false` → SHIP (assuming layer 1-2 also clean and score ≥8)
- `found: false` → company not on LinkedIn at all (rare, often hallucination); SKIP and log
- exit code 3 → BD SSO expired; HALT the day, Lark AE

### Cache layer (24hr)

`<workspace>/leads-hunt/data/sales-nav-cache.jsonl` stores verdicts to avoid redundant API calls. CRM Sync refreshes every 12hr per LinkedIn docs, so 24hr cache returns no stale data. Cache key is the lowercased company name.

```jsonl
{"company": "Hypotenuse AI", "in_crm": true, "checked_at": "2026-04-25T17:43:00+08:00", "salesforce_url": "https://byteplus.my.salesforce.com/001RC00001DeCAYYA3"}
{"company": "Abmatic AI", "in_crm": false, "checked_at": "2026-04-25T17:43:00+08:00"}
```

### When BD SSO expires (Phase A)

Phase A runs `sales_nav_query.py "BytePlus"` as a smoke test before Phase B. If exit code 3:
1. Send Lark via deliver script: "BD SSO expired. Run `python3 scripts/sales_nav_session_setup.py` and reply with OTP via Lark when prompted. leads-hunt will retry tomorrow."
2. Halt all subsequent phases for the day.
3. The next morning, Phase A retries. If AE refreshed SSO during the day, normal run resumes.

**Never degrade to "no Sales Nav layer" mode.** The whole point of the design is the CRM signal. Skipping Layer 3 means shipping unverified leads, which defeats the purpose.

## Order of execution within Phase C

```python
for candidate in candidates_json:
    # Layer 1
    if candidate.domain in skip_list: skip("manual-skip"); continue
    # Layer 2 — kb.md (source of truth)
    if kb.already_seen(candidate.name): skip("kb-tracked-or-shipped"); continue
    # Layer 3 (cache first, then live API)
    if cached := sales_nav_cache.get(candidate.name):
        if cached.in_crm: skip("sales-nav-cached"); continue
    else:
        result = sales_nav_query(candidate.name)
        cache.write(result)
        if result.exit_code == 3: halt_day(); break
        if result.in_crm: skip("sales-nav-live"); continue
    # Survived all 3 layers → ship if score ≥ 8
    ship_to_csv(candidate)
```

Phase D then calls `kb.append_shipped(rows, today)` to write the surviving leads back into `kb.md`'s `## Shipped Leads` section, closing the loop for tomorrow's Layer 2.

## Performance

- Layer 1: ~5ms per candidate (in-memory set lookup)
- Layer 2: ~10ms total per Phase C run (read kb.md once, build name set, cached for the run)
- Layer 3 cache hit: ~5ms (jsonl scan)
- Layer 3 cache miss (live Sales Nav): ~10s per candidate (browser + page load)

Worst case: 30 candidates with 0% cache hit = 5 minutes Sales Nav latency. Acceptable for once-a-day batch.
