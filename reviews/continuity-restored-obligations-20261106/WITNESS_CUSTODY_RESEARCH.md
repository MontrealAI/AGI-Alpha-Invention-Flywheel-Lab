# CONTINUITY Ω — synthetic cross-custodian fulfillment witness

**Independent research only. Not an operating release, migration, customer contract or financial authority.**

## Original obstruction and constructed means

A restored ERP may report gross outstanding units while forgetting the units already shipped. The existing v2 reference oracle (review PR #286) independently replays partial fulfillment, but two caller-held SHA256 hashes do not independently establish ownership or custody of the source. The v1 owner implementation (PR #279) and proposed fail-closed repair (PR #287) remain unchanged.

This additional experiment is a **synthetic multi-role attestation chain**. Each original event is hash-linked and signed by a locally simulated ERP custodian; each FULFILL event also needs a distinct simulated fulfillment custodian's Ed25519 signature. A simulated independent auditor signs the final receipt, restored v2 snapshot hash, source hash and monotonic counter. The read-only verifier needs separately pinned public keys, the latest anchor hash and a minimum event counter **from outside the received bundle**, then runs the independently authored v2 source replay. There is no private key in any bundle or report; local tests create keys ephemerally in memory.

This constructs and tests a concrete missing evidence channel: partially fulfilled work can be compared to witnessed prior fulfillment, rather than mistaking the original gross order for its undelivered remainder. It is **not** proof that a real ERP, supplier or recipient signed anything, that independent real people hold keys, or that any delivery occurred. The same dishonest entity could control several physical signers. Real-world authorization, hardware custody, signed buyer acceptance, rights to data, freshness, public transparency and third-party certification are absent.

## Reproduce

Install only a public open-source dependency (cryptography==46.0.4; no paid services) and run:

    python3 -m pip install --only-binary=:all: cryptography==46.0.4
    python3 -m unittest discover -s tests -p 'test_continuity_witness_custody_review.py' -v

Twenty-two synthetic adversarial cases require the two independent event signers, correct case identity, distinct pinned keys, signed external anchor and monotonicity, and refuse missing/reordered receipts, forged data, recovered fulfillment counter resets, fully re-signed forks when the original anchor is retained externally, v1 gross-only snapshots, invalid source replay, strict canonical integer typing even for correctly signed boolean/float counters, and unsupported real-world claims. A correctly reconstructed source with 100 previously fulfilled units and an absent canceled order is accepted **only as simulated custody**.

The dedicated GitHub Actions job uses ubuntu-latest, the standard six-hour job window, an execution-start receipt, and a pinned checkout action. Treat any failed hosted run as failed. Independent hosted qualification, owner adoption, main merge and downloaded release proof remain separate stages.

## Why the evidence does not yet support sales or funding

The strongest alternatives are (1) an existing ERP/backups with a competent systems integrator; (2) human-led continuity work with conventional software, normal ERP recovery and shipment/counterparty reconciliation; (3) a consented, third-party-attested obligation handoff with independently confirmed fallback capacity; and (4) **NO DEPLOY**. No fair measured comparison shows the new service beating the first two. No willing customer, supplier agreement, genuinely witnessed source, fee, paid contract, actual model/host bill, delivery cost or real payment has been established. The supported commercial decision remains **NO DEPLOY**.

A complete comparison must include failed acquisition and quotes, setup, rights, integration, production, independent acceptance, repair, support, maintenance, refunds, taxes, operational loss, provider costs, capacity, time, capital costs and invention expenses. Synthetic signatures are not paid revenue and no forecast utility is booked.

## Boundary and acceptance matrix

- **Implemented in additive research:** an optional independent witness/verifier helper, signature/counter/chain checks and twenty synthetic regressions. Do not equate local test success with independently checked hosted success.
- **Preserved:** original PR #286 red source findings, PR #287 fail-closed v1 repair, owner PR #279, protected main, old allocation failures, original journal, liabilities and queues.
- **Unqualified:** authenticated real custodians, external latest-anchor persistence, lawful consent, actual shipments, independent acceptance, paid buyers, competitively superior complete service, recursive-discovery advantage.
- **P0 blocked:** latest signed native-capital checkpoint, exclusive writer transfer and tested nonempty operating-queue migration. These research signatures are NOT a replacement for canonical JournalAccount, HMAC authority, immutable events, source-version authorization or write-ahead recovery. Do not reset accounts or weaken a transition guard.
- **Operating milestone:** US$3 billion trailing-365-day complete-cost profit remains unachieved. This work contributes no modeled or real profit.

**Next decision:** preserve this research and show the owner a possible versioned acceptance protocol, but do not merge the stacked branch into main or deploy the service. Seek separate source/witness custody and complete matched incumbent economics before any proposed operational v2 use. If the conventional route wins, retain it.
