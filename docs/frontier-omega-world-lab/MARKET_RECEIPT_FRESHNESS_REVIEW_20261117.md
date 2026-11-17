# FRONTIER Ω World Lab — source-bound market receipt freshness review (2026-11-17)

**Pre-implementation registration.** This follow-up is confined to the existing independent cash-conservation reviewer PR #438 (source head `4a7e1077a02638ef2e6aac17237e1e92b0982265`). The original integration owner is PR #436. No financial signer, journal, public customer, cash authority, or released runtime is in scope.

## Falsifiable issue

The existing offline World Lab `runMarket()` stores a report in `S.market`. Market input `input` handlers refresh only the visible slider captions, while the `download-market` handler recomputes the report **only when `S.market` is falsy**. If the visitor first evaluates one scenario, then changes a slider and clicks Download without pressing Evaluate again, the exported JSON can report a **previous scenario's inputs, decision and economics**. The file can appear contemporaneous despite having been invalidated by the user's current controls.

## Frozen acceptance protocol (before repair)

- **F1**: Compute an authored scenario with n=4, k=600, p=80%, starting cash=900, then change probability to 55% without pressing Evaluate. Download must reflect the current 55%, not stale 80%, and its arithmetic must reconcile with the independently computed cash path.
- **F2**: After that download, change two *other* controls (buyer count to 5 and starting cash to 1500) without pressing Evaluate. Download must use the latest values (n=5, cash=1500), with expected delta equal to the event path on precisely those inputs.
- **Positive control**: Without changing any inputs, the existing computed/downloaded model report remains identical. The change must not turn any hypothetical values into real buyers, externally collected receipts, or actual enterprise profit.

Implement the tests against the **actual embedded JavaScript extracted from `docs/research/frontier-omega-world-lab.html`** by invoking its real market functions and event handlers inside an isolated Node VM with stubbed DOM and save. Preserve the test-first Actions outcome even when it fails. Do not cherry-pick or change these frozen conditions after seeing results. Correct the producer/export-input binding prospectively, with clear invalidation of previously displayed results. Re-run the exact tests and repository CI. Stop at owner review, never force a merge or production publication.

## Accounting and claims

The already-qualified PR #438 head stays immutable as the historical cash-conservation qualification (16/16 successful source-matched workflows). Its four preregistered cash assertions and earlier genuine red test-first run remain unchanged. This freshness review is a separate increment; any new prospective head must earn its own source-matched qualification. The source model remains fictional and nonrefundable, with no actual buyer data or funded action.