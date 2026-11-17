# FRONTIER Ω World Lab — preregistered cash conservation review

**Registered 2026-11-17 UTC, before source edits.** Exact original owner: PR #436, head `6d0cd4548a58557d97f483876d3e0f8842a029f3`. Independent dependent reviewer branch: `review/frontier-worldlab-nonrefundable-cash-20261117`. The original owner retains integration, release and commercial authority. No native account, private financial history, signing material, live demand, finance or production action is within scope.

## Falsifiable defect

The current *Invent the Economy* four-buyer World Lab reports +120 authored modeled contribution, while also demanding a **900-unit prefunding cash path** (600 fixed construction + four 75-unit adaptations). Its alleged independent event-ledger evaluator debits all four adaptations **before receipts**, then sets failed-world ending cash to `cash - 600`, silently recovering the 300 adaptation debit without a refund, resale, recovery entitlement, or supplier credit in the source assumptions. The formula also charges adaptation only on a successful buyer world. Neither unrecorded refunds nor future receipt funding are permitted. This is a conditional scenario-accounting inconsistency, not evidence of historical native-account fraud, actual lost cash, or current customer demand.

**Precommitted test:** For non-refundable, upfront committed adaptation (the documented 900 prefund interpretation), at four buyers, price 300, construction 600, adaptation 75 each, route 0, probability 0.8, starting cash 900: cash at decision 900, pre-receipt 0, success ending cash 1200, failure ending cash 0. Expected change = `0.8*1200 + 0.2*0 - 900 = 60`, not 120. At probability 0, expected change -900; at 0.75 it is exactly zero, so **not** positive-contribution qualified. At cash 899, it fails prefunding even when expected benefit is positive. No cash receipts exist before the 900 debit. The existing +120 is retained only as a historical **contingent-cost** source scenario if clearly separated and not shown as the complete nonrefundable upfront cash path.

## Frozen regression protocol

Add test-only assertions to existing `tests/test_frontier_omega_world_lab.cjs`; run the repository's actual `research-pages.yml` on unchanged owner economics and preserve its expected red result. Do not change these adversarial assertions after red. Subsequently correct only `marketFormula` and `marketIndependent`, plus candid source/guide explanations and existing previously passing tests whose *old fixture expectations* are explicitly invalidated by the new cost policy. Inspect actual hosted workflow logs, never infer result from a queued workflow. New prospective green must use exact head and retain the original red record.

## Binding boundaries

Only illustrative developer-authored, finite simulated market outcomes. Do not assert observed demand, consumer consent, actual revenue, third-party verification, a Nash optimum, novel financing, or permission to reach buyers. Compare strongest incumbent and no-deploy before any new commercial claim; this review adds no buyer, customer, funding or accepted service. Preserve all old economic history and source/ledger guards; publication and independent downloaded-audit are separate gates.
