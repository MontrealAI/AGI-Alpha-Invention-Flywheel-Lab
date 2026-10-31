# 🌌♾️ AGI ALPHA — Proof-led partner commerce

**New product instrument, not another market simulator.** This promotes the already tested source-bound reconciliation proof from [PR #31](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/31) into a current-main additive contribution, then constructs a bilateral distributor/provider quote bound to the verified proof.

## One useful, independently checkable demonstration

The customer/agency sees the same exact synthetic inputs, reconciliation output, exception schedule, independent acceptance check and pinned implementation that produced it. The seller's success flag is not trusted. Buyers can reproduce the checker themselves. The demonstration is public synthetic work, **not** a real customer, contract, result guarantee or financial receipt.

## One incentive-compatible commercial arrangement

The distributor has a predeclared minimum distribution cost and required surplus. The producer has a full settled-delivery cost, required surplus, activation cost, loss-on-noncollection cost and protected liquidity. For the **fixed hypothetical quote** the mechanism chooses the smallest distributor share satisfying the stated minimum and refuses the proposal if neither a funded nor mutually viable split exists. It does **not** claim universal game-theoretic optimality, partner acceptance or a calibrated price.

Three cases remain distinct: no sale (activation costs are lost), delivery without collection (acquisition and fulfillment losses), and independently accepted/collected delivery (net after partner share, activation and complete operating costs). Partner share is payable only if actually collected under a subsequently authorized native contract. No advance, deposit or future collections are treated as earned funds.

## Run the complete proof-to-partner vertical slice

From the repository root in Python 3.12:

```bash
python3 -m commercial.portable_offer build \
  --input examples/portable_offer/sample_order.json \
  --output /tmp/alpha-proof-unique \
  --price-cents 59900

python3 -m commercial.portable_offer verify --path /tmp/alpha-proof-unique

python3 -m commercial.partner_offer build \
  --proof-dir /tmp/alpha-proof-unique \
  --output /tmp/alpha-partner-unique \
  --distributor-cost 12000 \
  --distributor-min-gain 5000 \
  --provider-complete-cost 10000 \
  --provider-min-gain 15000 \
  --activation-cost 1000 \
  --provider-loss-cost 6500 \
  --protected-cash 30000 \
  --opening-cash 100000
```

The returned `proposal_sha256` is the shareable contract-content pin. Ask a second process to verify *that exact pin*:

```bash
python3 -m commercial.partner_offer verify \
  --proof-dir /tmp/alpha-proof-unique \
  --package /tmp/alpha-partner-unique \
  --expected-sha256 <the-exact-sha256-from-build>
```

The illustrative $599 sale would leave a $170 minimum declared distributor share, a $50 net distributor surplus over its stated costs, and a $319 provider contribution after its declared $100 delivery cost and $10 activation expense. Both are **hypothetical**; $319 is not earned, collected or booked. No-bid remains the correct result if the partner or provider cannot participate.

**Security:** Hash binding is tamper detection given a trusted/pinned source and external contract digest. It is not a digital signature, independent source of truth or substitute for identity, legal terms, buyer authorization and payment reconciliation. A verifier run without the external hash can confirm the arithmetic but cannot authenticate the originally agreed contract terms.

## A decision-relevant experiment, not imagined billion-scale success

A paid native commercial cohort, if authorized later, should compare two otherwise identical offers: (A) standard accepted outcome and (B) portable evidence with partner distribution. Track voluntary buyer choices, purchase/collection delays, customer and partner acceptance, full inference/verification/packaging costs, refunds, channel expenditures and repeat business. Contingent partner payouts must be represented as explicit native-account commitments before money is spendable or distributable. **Do not implement commissions as free synthetic buyer utility or reserve transfers as enterprise profit.**

Retain B only if it outperforms the strong direct specialist and evidence-less channel after full costs. A qualified proof could help distribute a service; it does not guarantee new customers, $15,000/month contracts, the 60-month $1B target or actual autonomous profit.

## Why this is the practical Transformational Intelligence move

Do not merely make an existing AI worker cheaper. **Remove a buyer's reason to distrust an opaque service, then invent a mutually acceptable distribution mechanism tied to a checkable outcome.** Use a small, demonstrable product to investigate willingness to pay before increasing capital, capacity or assumed customer populations.

This contribution does not replace the canonical `connected_enterprise` ledger, operate private accounts, publish real invoices or contact customers. Source-matched CI and normal release integration remain required.
