# CONTINUITY Ω — independent restoration reference, NOT a deployed engine

**Current owner:** PR #279 retains implementation and integration authority. This
review extends PR #286 without changing the owner code, the separate native
financial account, the restored-order production interface, any historical
failure, or protected main. It must **not** be merged wholesale as a release.

## The concrete missing means

A continuity service must distinguish work **not yet fulfilled** from previously
fulfilled or canceled work when a damaged ERP snapshot is reconstructed. A
gross-only row cannot prove that a previously shipped quantity will not be
sent twice. Treating an absent canceled order as missing may create unnecessary
work. The exact original source-level counterexamples are still red on the
pinned owner implementation; see this review's existing README and hosted
failure receipts.

The new reference_oracle.py is an independently written **non-operating
research reference**: it replays source ACCEPT, AMEND, FULFILL, CANCEL events,
requires an explicit v2 recovered-active schema with gross, fulfilled and
source-event sequences, and checks which active obligations survive. It
explicitly refuses gross-only snapshots, missing provenance, canceled and
fully-fulfilled resurrections, changed source versions, bad counters and
duplicate IDs. An external caller-held pin for *both* the event list and
restored view is necessary for a conditional reconciliation result.

Those source/snapshot hashes alone **do not establish independent custodians,
consent, actual delivery, uniqueness of real shipments, legal evidence or
third-party certification**. Even a passing v2 synthetic comparison cannot
authorize an order or replace separate signed financial source guards. Actual
shipment evidence may require its own authenticated receipt identity and
real-world source-observation protocol before any deployment decision.

## Exact conditional protocol

Python 3, no paid calls, no external dependencies:

    python3 -m unittest discover -s tests -p 'test_continuity_reference_oracle_review.py' -v

Call reconcile(events, snapshot, expected_source_sha256=...,
expected_restored_sha256=...) with hashes **held outside the case being
examined**. The snapshot shape is:

    {
      "schema": "continuity-omega/restored-active-v2",
      "source_events_sha256": "<SHA256 of original canonical event JSON>",
      "records": [
        {"order_id":"A-100", "gross_quantity":1100, "fulfilled_quantity":100,
         "source_event_sequences":[1,4,5]}
      ]
    }

Rows contain outstanding *active* orders only. Fully fulfilled/canceled orders
are absent; completed quantity and all source event sequence IDs must match.
There is no supported reinstatement transition. A v1 gross-only row is
INVALID; absent external reference pins make the result UNVERIFIABLE.
RECONCILED_SYNTHETIC means only that source replay and the declared v2
snapshot agree *given the supplied two pins*. Source custody remains unproved.

The dedicated .github/workflows/continuity-reference-review.yml tests this
reference without rewriting or suppressing the separately retained **red**
owner-source acceptance tests. A green reference run does **not** make PR #279
green, and must not turn its historically failed workflow runs into passes.

## Three complete business alternatives and the hold decision

| Arrangement | Complete product and capable alternative | Present acceptance/commercial evidence |
|---|---|---|
| Existing ERP recovery plus integrator/consultant | Recover order state, reconcile shipped quantities and independently verify inside existing ERP, backup and accounting controls | Strong incumbent; total price and error-rate for the target case unknown |
| Managed consultant-led continuity planning and exercises | Human + conventional software restore a bounded customer promise and document cross-system exceptions and corrective work | Real category, but no relevant willing buyer, measured pricing or comparative delivery here |
| Narrow independent interparty obligation handoff | Two independently controlled evidence sources, supplier permissions and a verifiable customer-accepted residual order across an outage | This research reference only tests *synthetic internal consistency*, not the complete service or advantage |
| **NO DEPLOY** | Spend/commit no new funds; retain existing services and obligations | **Supported by current evidence** |

Before changing that decision, independently qualify a real cross-provider case
with consent, separately held reference evidence and a competent ERP / human
comparison under **the same scope, deadlines and permissions**. Measure sourcing
and failed quotes, customer acquisition, onboarding, restoration, any supplier
reservation, checking, corrections, support, taxes, maintenance, claims,
recovery times and complete actual human/model/host costs. Require voluntary
buyer acceptance and legally collected funds before any native earnings or
earned-funded successor reservation. This reference has **zero collected
revenue and no native accounting effect**; demand and the $3B trailing-365-day
complete-cost profit objective remain unqualified.

## Acceptance ledger (not a publication claim)

- **Achieved in code:** a read-only independent reference schema, source replay,
  fail-closed invalid inputs and 22 preregistered synthetic tests; hosted outcome
  must be checked separately.
- **Expected historical red:** two original owner-source restoration
  counterexamples, with immutable failed workflow receipts.
- **Partial:** conditional simulation comparator; no external source custody.
- **Blocked:** owner integration of a versioned recovery contract, independently
  authenticated real recovered evidence, the separate native financial writer
  handoff, real supplier/buyer acceptance and complete-cost profitable delivery.
- **No claims:** general cyber resilience, unqualified external authority,
  new customers, recouped costs, paid commerce, invention superiority,
  successor advantage, or US$3 billion profit.

**Tried → finding → next:** gross-only restoration loses fulfillment
observability and treats canceled absence incorrectly → build a stricter
explicit schema and independent reference replay → confirm hosted tests and
have the original owner decide whether a compatible versioned repair can
pass both the old baseline and the independent red cases. Preserve any
failures. If capable ERP integration already provides the same complete
accepted outcome more cheaply, retain the incumbent and do not deploy.
