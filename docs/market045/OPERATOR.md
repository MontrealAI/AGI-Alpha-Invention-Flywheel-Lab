# AGI ALPHA — Invention of a viable market, not merely a cheaper worker

**Edition 045 / opt-in stacked on PR #78.** Exact finite, source-grounded contract-composition research. It changes no native business, account, default operating controller, signing key, buyer budget, real payment, live contract, or authority. It is a construction instrument, not a deployed automatic marketplace.

## The binding constraint

A buyer requires four things *together*: actual useful reconciliation output, independent proof, a portable source trace, and distribution. The incumbent direct specialist combined with an external checker is too expensive to supply the complete accepted package under the proposed $599 fixed price. A single builder, checker, bridge or distributor cannot meet all requirements separately.

AGI ALPHA enumerates **sets of suppliers**, not isolated cheap bids. It identifies coverage, required interfaces, independently separated checking, supplier and buyer participation, current declared available cash, refundable/protected exposure, noncollection guarantees, expiry and rights. It chooses the feasible set with maximum retained provider contribution; a stronger direct option can win, and no-bid is valid. This is an **exact optimization over an explicitly small bid universe**, not equilibrium or truthful elicitation under private information.

The 4-way constructed design is:

| Supplier role | Declared settled cost | Minimum supplier gain | Activation cost |
|---|---:|---:|---:|
| Useful delivery | $160 | $40 | $25 |
| Source-to-claim portable trace bridge | $42 | $10 | $6 |
| Independent verifier | $65 | $15 | $5 |
| Distribution partner | $88 | $22 | $15 |
| **Sum** | **$355** | **$87** | **$51** |

All amounts are **author-provided synthetic quotes**, not actual partner offers. At the proof package's fixed $599 price, the hypothetical enterprise retains **$106**, the buyer declares **$151 benefit above their outside surplus**, and each supplier meets its declared gain. The jointly modeled total noncollection exposure is **$141**, backed in the quoted $1,000 cash and $300 protection scenario. The direct specialist plus independent checker would require at least **$725** including margin and activation, exceeding the same fixed price; hence no feasible direct trade in this constructed instance.

The portable trace is not an invented scientific breakthrough: it is a real executable adapter from the existing `commercial.portable_offer` proof system. The *economic arrangement*, rather than its underlying code, is what this finite solver constructs. The solver calls `commercial.portable_offer.verify` and independently checks the actual synthetic reconciliation bytes before producing a contract proposal. Any mutation invalidates the proposal.

## Participation and legal/economic boundaries

- **Buyer:** posted price must not exceed the declared budget; declared value net of price must beat the declared outside option. No actual willingness to pay or buyer authorization is observed.
- **Suppliers:** each fee is its own complete settled-delivery cost plus declared minimum gain. Fees are *contingent proposals*, not earned or payable entitlements. Seller funds activation, stated failure guarantees and protected liquidity before the proposed work. Existing principals, refunds and tax duties remain unknown until real contracts are validated.
- **Independent checking:** no identical provider can be both delivery and verifier in a selected group. Supplier labels and declared rights do **not** authenticate ownership or actual institutional independence.
- **Authority:** `funding_authority:false`, `current_proof:null` for the proposed *business contract*, `authority:[]`. The completed synthetic service has separately rechecked source-bound proof; the contract has no signatures, accepted buyers, or actual collection.
- **Optimality:** enumeration of at most 12 supplier proposals and at most 12 participants, with exact integer-cent arithmetic, contingent minimum-fee offers and noncollection constraints. It is not dominant-strategy truthfulness, Bayesian incentive compatibility, real ex-post budget balance for all unknown contingencies, general market equilibrium, or automatic legal enforceability.

The Myerson–Satterthwaite impossibility theorem warns against promising universally efficient, subsidy-free, incentive-compatible private-information trade. Contract theory highlights why uncontractible effort, incomplete terms and decision rights matter. Established market and commerce primitives can be used without inventing them again. Sources: https://www.sciencedirect.com/science/article/pii/0022053183900480/pdf , https://www.nobelprize.org/prizes/economic-sciences/2016/press-release/ , https://developers.openai.com/commerce .

## Reproduction, independent verifier and failure branches

On the stacked PR #78 checkout, with the existing `commercial/portable_offer.py` and `commercial/partner_offer.py`:

```bash
python -m pip install -r requirements-commercial010.txt
python -m unittest discover -s tests -p 'test_outcome_market045.py' -v
python -m unittest discover -s tests -p 'test_partner_offer043.py' -v
python -m commercial.outcome_market045 demo --output /absolute/NEW/market045
python -m commercial.outcome_market045 verify --path /absolute/NEW/market045
```

`market045/proof/` is generated by the real existing producer and checker, and `market045/market/COALITION.json` contains the contract inputs and reproducible solver certificate. A separate verifier recomputes both the actual proof and the exact coalition optimum; an external independently pinned SHA-256 can detect later replacement of agreed quote bytes, but a hash is not a signature. The CLI never contacts customers or moves money.

Negative tests include low budget, dominant outside provider, missing distribution, missing connector, unaffordable cash/protection, excessive noncollection losses, expired/unlicensed inputs, forged self-verification, changed source bytes, misreported retained surplus and a cheaper direct specialist that correctly wins. Failure logs are not accumulated; retain concise lessons and executable regressions.

## What would complete the transformative flywheel

1. Replace declared customer value and supplier costs with **consented, rights-cleared, genuinely available quotes** and independently verified buyer acceptance. Measure the rate at which coalitions make previously unreachable work feasible.
2. Implement conditional obligations and actual accepted/collected fees in the **existing `JournalAccount`**, with guarded current liquidity, refunds, taxes, controls, verification and audited settlement. The output of this module must never be used as financial authority.
3. Prove **incremental complete-cost benefit against the strongest conventional specialist**, including partner onboarding, risk, maintenance, work correction and lost sales. The synthetic positive case is not empirical demand or profit.
4. Turn a successful, transferable source-to-claim capability into an applicability-bound asset, revalidate on a different fresh service, and evaluate retained generic method versus equal-content ordinary reuse. Prefer simpler ordinary methods when they win.
5. Reinvest legitimately earned available surplus in the next more valuable outcome, perhaps financial reconciliations → cross-vendor audit assurance → collaborative procurement compliance. These are future opportunities, not completed transfers.

**Novel strategic target:** construct new *feasible production-and-contract networks*, not simply optimize one organization's fixed production function. This could eventually be a platform for market creation, but no economic, scientific or industrial breakthrough is asserted by this constructed synthetic exercise alone.
