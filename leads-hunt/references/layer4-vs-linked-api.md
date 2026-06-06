# Layer 4 (CRM dedup) vs third-party LinkedIn automation APIs

This note exists so future refactor proposals don't waste a session re-discovering why the Playwright-driven Sales Nav stack can't be cleanly replaced by a SaaS LinkedIn API. It also documents the verification process so the conclusion can be re-run if a vendor adds CRM-sync support later.

## The signal Layer 4 reads

`scripts/sales_nav_query.py` launches Chromium with a persistent profile authenticated as Ben's **BD-corporate Sales Nav seat**, navigates to `https://www.linkedin.com/sales/search/company?keywords=...`, and intercepts the `salesApiAccountSearch` XHR response. Each result element contains a `crmStatus` object that is **only present because LinkedIn's server-side has joined the company entity to the Salesforce tenant connected to the seat**:

```json
"crmStatus": {
  "imported": true,
  "externalCrmUrl": "https://bytedance.lightning.force.com/lightning/r/Account/...",
  "idInSourceDomain": "001..."
}
```

`imported: true` is the canonical "this company is already a BD Salesforce Account" signal. The other fields exist for outbound linking back into Salesforce.

This is tenant-private metadata. No public-LinkedIn automation tool can see it.

## What `linkedin-cli` / Linked API offers (and doesn't)

**Tool**: `@linkedapi/linkedin-cli` (npm), wrapping `linkedapi.io`. Pricing: $49/seat/mo Core, $74/seat/mo Plus (Sales Navigator actions gated behind Plus). Architecture: dedicated cloud browser per connected LinkedIn account, residential IP, behavioural mimicry.

**CLI surface** (verified against v1.0.10):
- `account` / `admin` — multi-account + subscription management
- `person fetch|search` / `company fetch|search` — public LinkedIn data
- `connection list|send|status|...` — connection graph operations
- `message send|get` / `navigator message send|get` — DM and InMail
- `navigator company fetch|search` / `navigator person fetch|search` — Sales Nav driving (better filters: revenue, decision-makers)
- `post` / `stats` / `workflow` — posting, SSI/perf analytics, custom multi-action workflows

**Action catalog** (`linkedapi.io/docs/actions-overview`): full enumeration of `st.*` (Standard) and `nv.*` (Navigator) actions. Searched the entire catalog for: `crmStatus`, `salesforce`, `crm`, `imported`, `account` (in the Salesforce sense). **No matches.** The Navigator actions cover Sales Nav UI driving (search, employees, decision-makers) but do not surface CRM-sync metadata.

**Verdict**: Linked API operates on public LinkedIn surface area. It cannot read tenant-private Salesforce-sync state. Therefore it cannot replace Layer 4.

## Re-verifying when a vendor claims CRM support

If a future vendor (Linked API or otherwise) advertises Salesforce integration, the precise question to put to support is:

> Given a connected LinkedIn account whose Sales Navigator seat has Salesforce sync enabled with a specific Salesforce tenant, can your API return whether a company is currently an Account in that connected Salesforce tenant — i.e. expose the `crmStatus.imported` field that LinkedIn renders inside the Sales Nav UI for that seat?

If the answer is "we integrate with Salesforce" but the fine print is "you give us a Salesforce token and we query Salesforce directly" — that's a different mechanism. It works only if Ben has an API user in BD's Salesforce, which is a much larger ask than reusing his SSO seat.

If the answer is yes to the LinkedIn-mediated `crmStatus` field specifically, the vendor is offering something LinkedIn does not officially document for third parties; treat that claim with appropriate skepticism and ask for a recorded demo against a test account.

## Architectural options on the table

| Option | Layer 4 alive? | SSO setup needed? | Cost | When it makes sense |
|---|---|---|---|---|
| **Status quo** (Playwright + BD SSO) | yes | yes (fragile) | $0 + ops | default; works |
| **A: Full migrate to linkedin-cli, drop Layer 4** | no | no | $49–74/mo | when the saturated-vertical heuristics + ClawMander leads table demonstrably catch enough of what Layer 4 used to catch |
| **B: linkedin-cli for enrichment, keep Playwright for Layer 4** | yes | yes | $49–74/mo + ops | only if decision-maker discovery / employee filtering becomes a top need |
| **C: Hybrid — Playwright only for the `crmStatus` check, linkedin-cli for everything else** | yes | yes (smaller surface) | $49–74/mo + reduced ops | rare; mostly worse than A or B |

## Decision input: measure Layer 4's marginal value before retiring it

Before adopting Option A, count how often Layer 4 actually catches something the earlier layers missed. The question to answer with the data:

> Of candidates that survive Layer 0 (foundational filter), Layer 1 (skip-list), and Layer 2 (ClawMander leads table), what fraction get rejected by Layer 4's `in_crm: true`?

A high fraction (e.g. >20%) means Layer 4 is genuinely catching mid-tier surprises that the heuristics don't see, and dropping it has real cost. A low fraction means the saturated-vertical patterns in this skill have already absorbed most of Layer 4's job.

Source data: `lead-gen/sales-nav-cache.jsonl` — each line is a `{company, in_crm, found, ...}` cache entry. Cross-reference against the per-day `candidates/<topic>-<date>.json` to compute "passed L0–L2, then `in_crm=true` at L4" rate.

**Empirical measurement (n=252, May 2026 cache):** 77 `in_crm=True` vs 175 `in_crm=False` → **30.6% rejection rate at Layer 4**. That's the difference between shipping ~10 quality leads/day vs shipping ~14 leads/day with ~30% already in pipeline. Real value, not droppable. Treat this as the working number until re-measured.

## Why "just query BD's Salesforce directly" is NOT an option for this user

A plausible-sounding alternative is to skip the LinkedIn-mediated `crmStatus` join and query BD's Salesforce directly via `sf` CLI (`sf org login web → sf data query -q "SELECT Id, Name, Website FROM Account"`). This is architecturally cleaner: authoritative source, ~90-day refresh tokens, loud 401 failures instead of silent CAPTCHA, no Playwright fragility.

**It does not apply here.** Ben (the user) is a Solutions Architect at Byteplus with a Sales Nav seat wired to BD's Salesforce, but he does NOT have direct Salesforce API/login access. The `crmStatus.imported` field surfaced inside Sales Nav is the **only legitimate window BD has chosen to leave open** for him to read CRM state — they've configured the Salesforce↔LinkedIn sync and given him a Sales Nav seat, but not Salesforce credentials. Closing that window would mean revoking his seat or disconnecting the sync.

So:
- Don't propose the `sf` CLI path for this user. It's eliminated by org access policy, not technology.
- Layer 4's brittleness is the price of the only legal access path. Mitigation is making failures loud (exit code 3 → re-auth alert), not finding a replacement.
- If a future user *does* have direct Salesforce access (different role, different org), the `sf` CLI path becomes strictly better and Layer 4 should be replaced. Keep this distinction in mind when re-reading this doc later.

## Full elimination tree for Layer 4 replacements

For posterity and so future sessions don't re-walk this:

| Path | Why eliminated |
|---|---|
| Direct Salesforce API (`sf` CLI, REST, SOQL) | No BD Salesforce access for this user (org policy) |
| Salesforce-connected enrichment (Clay, Crossbeam, RevenueHero) | All require Salesforce API creds → same blocker |
| Surfe / Lusha / Apollo browser-extension sidebars | Show CRM status only via *your own* OAuth-connected CRM → same blocker; also UI-for-humans, not batch-programmatic |
| Surfe / Apollo API tier | Queries vendor's contact DB, NOT your tenant's `crmStatus` |
| Linked API / linkedin-cli | Action catalog confirmed: no `crmStatus` exposure (verified v1.0.10) |
| Public LinkedIn scraping (logged-out) | `crmStatus` gated behind authenticated Sales Nav seat |
| Asking BD IT for read-only Salesforce API role | Possible but org-political, weeks of process, may be denied. Worth filing if Layer 4 outage extends; not a near-term plan. |
| Authenticated Sales Nav scraping (Playwright + BD SSO) | ✅ The current implementation. Only legal path. |

## Pitfalls observed

- **Don't recommend a SaaS replacement for the whole Sales Nav stack on architectural grounds alone.** The user explicitly asked "verify before you do it first" — vendor capability claims need to be probed against the actual integration point (`crmStatus.imported` here) before a recommendation lands. CLI help text + action catalog are the cheapest verification surface.
- **Don't conflate "Sales Navigator actions" with "Salesforce integration".** The former means driving the LinkedIn Sales Nav UI; the latter means reading the customer's CRM. Most vendors offer the former and call it "Sales Nav support".
