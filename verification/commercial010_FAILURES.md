# Adversarial findings, commercial cycle 010

These are development findings, not confirmation evidence. Builder and verifier
use separate implementations and roles on one host and model family.

## Forged acceptance receipt (reproduced before repair)

The initial `commercial.ledger.load_jobs` accepted an arbitrary JSON artifact
`{"invented":"not a reconciliation"}` when accompanied by a locally authored
receipt with `accepted: true` and its byte hash. Recomputed manifest hashes were
enough. `TapeExchange` initialized and exposed the forged job without reading an
order or running the reconciliation checker.

The reproduced result was `{"forged_service_cohort_accepted":true,
"jobs":["forged"]}`. No transaction was executed or reported as commercial
success. The required repair is source-bound order inputs and fresh independent
acceptance during loading and release, rather than reliance on stored receipt
summaries. Regression tests retain this attack.

## Producer/checker input contract mismatch (found before freeze)

The initial separate checker admitted empty tables and wider table bounds and
did not reject unknown invoice references or referenced-customer mismatch in its
input parser. The producer rejected those orders. The verifier author aligned
the independently implemented input contract and added mutation tests before
any frozen campaign result. This repair changes validation, not historical
service receipts.

## Self-consistency versus authority

A hash and deterministic ledger replay establish content identity and arithmetic
consistency. A caller that changes cost actions and recomputes every derived
field can define a different internally consistent scenario. Full campaign
qualification must additionally bind a separately frozen policy, whole source
cohort and seed/scenario set; replay against those inputs is required. A digest
stored beside mutable events is not external authority.

## Rejected-attempt cost field mismatch (found before confirmation)

The initial market draft counted `attempt.accepted == false`, while actual
attempt records use `outcome: REJECTED`. This omitted the additional supplied
unsafe-first-match attempt from the modeled cost-unit count. The whole cohort
has 19 jobs and 20 attempts; the cost model must charge all 20, including the
three rejected jobs and the extra failed development attempt.

## Tax provision base (found before confirmation)

The initial market draft calculated additional tax provisions from profit
already reduced by prior tax provisions. A repeated marginal-profit sequence
would therefore under-provision the declared modeled tax rate. The repair uses
cumulative profit before the previously recognized modeled tax expenses, then
charges the incremental provision once. This is a conditional tax scenario,
not observed tax advice or a source-exact liability.

## Inconsistent verdict input (reproduced before repair)

The initial verdict helper accepted `simulated_go=true` with either zero
accepted service jobs or `positive_service=false`. The actual market caller
derived consistent values, but the public verdict API did not enforce its
necessary preconditions. Independent regression tests reproduced all three
inconsistent combinations; the repaired helper rejects them. Fixed-capability
commercial success remains independent of invention and live-commerce claims.
