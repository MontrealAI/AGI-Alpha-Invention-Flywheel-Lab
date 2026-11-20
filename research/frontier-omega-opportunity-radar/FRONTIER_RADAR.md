# FRONTIER Ω · Opportunity Radar

MONTREAL.AI research tooling for separating real capability changes from release noise and testing which new businesses the lab could own. This is a **shadow research release**. It makes no external deliveries, spends no funds, and does not change the existing Friday briefing or hourly alerts.

## Run it

From the folder containing `frontier_radar`, with Python 3.11+ and an IANA timezone database:

```sh
python -m unittest discover -s tests -p 'test_frontier_radar*.py' -v
python -m frontier_radar atlas
python -m frontier_radar --as-of 2026-11-20T22:00:00Z briefing
python -m frontier_radar --as-of 2026-11-20T22:00:00Z replay
python -m frontier_radar --db /path/to/operator-owned.sqlite3 shadow
python -m frontier_radar --db /path/to/operator-owned.sqlite3 health
python -m frontier_radar --db /path/to/operator-owned.sqlite3 leads
python -m frontier_radar --db /path/to/operator-owned.sqlite3 revisits
python -m frontier_radar --db /path/to/operator-owned.sqlite3 drafts
python -m frontier_radar --db /path/to/operator-owned.sqlite3 decisions
python -m frontier_radar alerts
```

Use the same SQLite path across polls. Store the file outside the checkout; it is local operating state, not a deployment artifact. A read-only HTTP GET of an allowlisted feed is the only external action. No model API, credentials, checkout, outreach, or auto-execution is required. Source responses are untrusted observations and cannot write decision records or change the allowlist. Review a source before treating it as evidence. No arbitrary URLs are fetched.

The collection path is deliberately narrow. A healthy run is **not** proof that the whole frontier was covered. `shadow` distinguishes missing or degraded collection from credible quiet, and does not create alert drafts during a degraded run. The standalone `alerts` command explicitly previews decision records and does not imply collection health. Limit the first recurring shadow run to an approved host. Space hourly jobs far enough apart that retries don't contend. Friday draft slot is Montréal Friday on or after 08:00 local, emitted once in SQLite even after a retry; scheduling at 08:00 and message transport are external responsibilities.

## What ships

- A July 1 to November 20, 2026 Frontier Atlas with a pre-July comparator, citations, domains, coverage gaps and dated dependencies. It is curated, not exhaustive.
- Economic tests with an actual enabling advance, a strong incumbent alternative, a buyer hypothesis, retained rights and stop/go thresholds. None is labeled a proven opportunity or urgent sale.
- A versioned source observation ledger, bounded GETs, source health, retry and duplicate tracking, decision gates, historical presentation, Friday research and alert renderers, and a durable shadow queue.
- An as-of replay using only records whose dated support is available by cutoff. Dates without times are treated with day-level precision. The atlas was researched retrospectively; archived contemporaneous decisions, independent gold labels, and true detection lead-time aren't inferred.

## Operator workflow

1. Read the original source for a lead; corroborate the claim and access where material. Check a matched earlier alternative; record gaps, counterexamples and rights.
2. Add or revise a reviewed record in `frontier_radar/data/opportunities.json`. Set capability and ownership gates only with specific support. A SELL recommendation additionally needs observed demand and verified delivery. Keyword-based revisit suggestions can route feed leads to registered theses, but no unreviewed lead qualifies. For urgency, cite what expires and include a timestamped deadline, a matching dated source URL, and certainty = fixed_deadline. Lower bounds and estimated dates cannot alert; a material change requires a fresh review.
3. Re-run tests and both previews. Existing schedules remain the only live paths until a named operator approves a long-running shadow trial, validates the results, tests failure and recovery, and connects verified delivery with one active route per output.
4. Preserve older evidence and decisions when correcting them. Do not equate a suggested test, benchmark, payment hypothesis, or narrative with earned revenue.

**Current gate:** GO for bounded shadow review. NO-GO for live alert cutover, comprehensive automated coverage, superiority to a news digest in true predictive performance, or hands-free opportunity qualification. Open issues: broader reviewed source subscriptions, production orchestration and transport, independent time-stamped replay labels, a sustained shadow run, and evidence-based adjudication of live leads.
