# GENESIS100 — immutable native-account registration binding

**Frozen before implementation / hosted qualification.** Source parent: GENESIS owner integration PR #229 commit `2fafbb01bb693d59de8f0bd0064eefd9470d16ff` (tree `6dec24e80e074a2c3c03461b036e25f5a0fa59e2`). Reviewer finding: PR #229 `discussion_r4474559033` (2026-11-04 23:16 UTC). Existing `audit_journal` checks native ledger against connected journal but is not evidence that account origin matches the GENESIS registration.

## Registered hypothesis and denominator

Exactly four native-account cases against the fixed `campaign/genesis-enterprise-002/PROTOCOL.json`, without changing this protocol, public-source manifests, original accounts, private signing material or costs.

- C0: normal unmodified canonical `BusinessAccount` creation and full operation must pass independent GENESIS audit.
- C1: construct a genuine *disposable* canonical account with native opening capital `p['opening'] + 100_000_000` microUSD while the protocol/registration remain unchanged. Independent GENESIS audit **must reject** `REGISTERED_NATIVE_ACCOUNT_CONFIGURATION_CHANGED`; native journal replay may itself be internally valid. No retrospective top-up or money mutation of an existing account.
- C2: create a genuine disposable account with `working=1_000_000` microUSD while registered working remains zero. GENESIS audit **must reject** the same discrepancy.
- C3: create a genuine disposable account using a different, nonempty native contract ID while the source-bound registration is unchanged. GENESIS audit **must reject**.

All four cases are mandatory. A case that cannot construct a valid native ledger is **inconclusive for the audit-boundary claim**, not a demonstrated GENESIS audit rejection. If test setup blocks the discrepancy, report the obstruction honestly. Do not replace arms, tune seeds, reset an existing business or reinterpret an unexpected pass as success.

The proposed gate independently checks exact native `ledger.config` opening/working/contract against the frozen protocol and `REGISTRATION.json` **after** the canonical `audit_journal` replay, without changing that replay, account identity, HMAC keys, earned funding, original obligations or the journal. Type-sensitive equality is required (boolean is not money). A forged or internally consistent journal must not serve as an alternate registration.

## Engineering scope and exit

This is a source-bound financial-integrity regression necessary for safe claims about seed-funded vs earned-funded capital. It is not P0 legacy-account migration, a new capital experiment, qualified public release, measured model billing, customer demand, paid revenue, a causal invention advantage or US$3 billion trailing-year profit. Implement in an isolated, reviewable branch stacked on owner PR #229; preserve historical failures, original active accounts, and other owner work. Source owner controls eventual integration. Qualify focused tests plus available exact-head hosted workflows. Do not merge into main or claim downloaded release before normal protected qualification.