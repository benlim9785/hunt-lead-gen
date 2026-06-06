# "Why no new leads today?" — empty digest diagnostic

When the user asks "why no new leads today" / "today produced no leads at all" / "nothing in the digest," resolve this in ≤3 tool calls. Do NOT re-run the pipeline before diagnosing — the answer is almost always in the logs.

## Common causes, in observed frequency order

### 1. Total dedup drain (most common)
**Symptom**: cron healthy, all four phases ran, Phase D delivered an empty/skinny digest. Run-log shows Phase B yielded N candidates, Phase C dropped to 0–1.

**Root cause**: Brave search re-surfaced the same known names (Phot.AI, KreadoAI, Vizard, etc.) that yesterday's run already shipped. Layer 1 (skip-list) + Layer 2 (ClawMander leads) correctly filter them as duplicates. The pipeline did its job — discovery is just stale.

**Don't fix by re-running.** A second Brave query that hour returns the same SERP. The fix is broadening discovery channels (SimilarWeb, Crunchbase API, vertical-trade-press scraping), not retrying.

**Diagnose**:
```bash
# Today's run log — count per-phase yields
ls -la /root/.hermes/profiles/hunt/lead-gen/run-log-$(date +%Y-%m-%d).txt
grep -E '(candidates|filtered|shipped|net-new)' /root/.hermes/profiles/hunt/lead-gen/run-log-$(date +%Y-%m-%d).txt
# Today's candidates JSON — what Phase B actually found
cat /root/.hermes/profiles/hunt/lead-gen/candidates/*-$(date +%Y-%m-%d).json | jq '.[].company_name' | sort -u
# Compare to yesterday — overlap = stale-discovery signal
diff <(cat /root/.hermes/profiles/hunt/lead-gen/candidates/*-$(date +%Y-%m-%d).json | jq -r '.[].company_name' | sort -u) \
     <(cat /root/.hermes/profiles/hunt/lead-gen/candidates/*-$(date -d yesterday +%Y-%m-%d).json | jq -r '.[].company_name' | sort -u)
```

### 2. Saturated vertical for the day's rotation
Discovery rotation picked a vertical that's now in "Saturated verticals" list. Phase B yielded candidates but all were AI-prominent / AI-named / on the saturation list. Score floor (≥8) cut them.

**Diagnose**: same run-log grep; look at the candidate names against the SKILL.md "Saturated verticals" section.

### 3. Phase A SSO failure (cascades)
Sales Nav SSO expired → Phase A exit 3 → Phase B/C/D may run but Layer 4 silently no-ops, OR they're skipped entirely depending on cron wiring. Check Phase A first.

```bash
grep 'Phase A' /root/.hermes/profiles/hunt/lead-gen/run-log-$(date +%Y-%m-%d).txt
```

### 4. LinkedIn/Brave rate-limit or fingerprint detection
Phase B agent log shows tool errors (Brave 429, Sales Nav captcha, Playwright crash). Check `/root/.hermes/profiles/hunt/logs/agent.log` for errors during today's cron window.

```bash
awk -v d="$(date +%Y-%m-%d)" '$1==d && tolower($0) ~ /error|fail|429|captcha|timeout/' \
  /root/.hermes/profiles/hunt/logs/agent.log
```

### 5. Cron didn't fire
Rare. Verify with `cronjob list` or `hermes cron list` and `tick.lock` mtime ≥90s old.

## Response template (when answering the user)

Lead with the cause, not the diagnostic walkthrough. Two-line answer:
- "Cron ran fine. Phase B returned the same known names (Phot.AI, KreadoAI, etc.); dedup filtered them as already-shipped. Real fix is new discovery channels, not a re-run."
- Then offer the next concrete step (broaden Brave queries, wire SimilarWeb, etc.) only if the user asks.

## Anti-pattern: re-running the pipeline as a first response

The user asked this question on 2026-05-19. The agent burned 16+ tool calls re-running the entire pipeline (`/approve` × 2, agent runs of 118s + 620s + 163s + 739s) only to surface KreadoAI — which the same pipeline had already deduped earlier. Cost ≈$1 of Bedrock calls + 25min wall time for one marginal lead the user could have approved manually.

**Rule**: read the run-log first, re-run never. If the run-log shows total dedup drain, the answer is "discovery is stale, broaden channels," not "let me try again."
