# Verified outcomes as a commercial mechanism

**An executable public-synthetic proof package, not a real customer contract or payment rail.**

The AGI ALPHA strategy is to make digital outcomes contractible: a buyer should be able to inspect a task definition, reproduce independent acceptance, see disclosed exceptions, and evaluate the service offer **before trusting the provider's sales claims**. The present instrument packages the existing bounded receivables-reconciliation producer and separate checker; it does not replace either. Its output is tamper-evident against fixed source and manifest bytes, but is **not digitally signed or externally certified**. A malicious provider that changes the source and advertises a new source hash can still create a self-consistent bundle; customers must trust/pin the public verifier version and independently execute it.

## Execute the working mechanism

```bash
python3 -m commercial.portable_offer build \
  --input examples/portable_offer/sample_order.json \
  --output /tmp/agi-alpha-proof-NEW \
  --price-cents 4999
python3 -m commercial.portable_offer verify --path /tmp/agi-alpha-proof-NEW
python3 -m unittest discover -s tests -p test_portable_offer.py -v
```

The bundle contains `ORDER.json`, `OFFER.json`, `VERDICT.json`, `DELIVERY/reconciliation.json`, `DELIVERY/exceptions.csv`, and `MANIFEST.json`. A different process can verify the bundle using only the source-pinned independent checker. The producer’s `accepted` flag is never sufficient evidence by itself. Required complete delivery fails acceptance when unmatched records remain; when incompleteness is expressly permitted, exceptions are disclosed, not hidden. Source identity and every included file are hashed; output reuse and symlinked files are refused.

The price is **a hypothetical quote only**. Every input here is synthetic/public. The tool has no access to wallets, bank accounts, customers, distribution channels or payment providers, and cannot settle an invoice. Actual willingness to pay, human comparator, provider insurance terms and complete agent economics are **not measured** by this deliverable.

## The game-theoretic hypothesis

A low-marginal-cost frontier-AI production advantage invites imitation and price pressure. An independent portable acceptance package may make an otherwise difficult-to-purchase outcome easier to trust, compare and contract for. **That is a hypothesis about buyer behavior, not a free utility bonus granted by the simulator.**

A future buyer-permitted experiment should compare the *same* production and verification outcome in two arrangements: (A) standard delivery with its existing independent acceptance and (B) the same delivery with the portable buyer-side evidence package. Charge (B)'s packaging and support costs, account for buyer attention, privacy, warranty/recourse and timing, and compare voluntary conversion, accepted delivery, dispute rate, collection delay, complete-cost profit and repeated purchase. Introduce an equally capable rival offering portable proof, and a low-price self-service alternative. Do not infer conversion from a synthetic choice equation; actual real-market promotion requires separately authorized outreach and payment terms.

The commercial flywheel may already profit with unchanged capabilities. The capability-compounding flywheel contributes only if a verified instrument expands the range of *fresh* acceptable work, reduces complete costs or improves useful discovery/production relative to strong reuse controls. For example, generalizing the portable verification interface to a new independently accepted service must be built and fresh-tested; copying the same demonstration to another folder is not evidence of transferable invention.

The strongest joint strategy is **earn through independently verifiable work, learn which part of the customer transaction actually limits adoption, then buy, partner, adapt or invent the instrument that changes that constraint**. The decision is conditional on rival responses and total costs. The optimal arrangement could be the existing simpler service. No mandatory R&D allocation, fabricated earnings, human staffing or unrestricted market size appears in the tool.

## Source and qualification boundaries

- This demonstration imports the current repository's existing `commercial.service` and separately implemented `commercial.service_verifier`; both are source-hash bound and remain unmodified.
- It is a narrow synthetic reconciliation proof, not a general financial audit, bank reconciliation, legal assurance, live merchant facility, third-party certification, protocol standard, or claim of customer demand.
- The bundle fails on altered receipts, totals, source, hash manifest, exceptions, quotes or extra files. A rehashed malicious report still fails independent semantic recomputation.
- Source metadata and a generated hash are *not signatures*. Do not pass untrusted private data to a public artifact, treat synthetic orders as transactions or claim zero operating costs.
- No new API spend, outreach, customer contact, deployment, real cash movement or release authority is introduced. The canonical connected enterprise and its frozen commercial evidence are unchanged.

Once the buyer-side acceptance mechanism actually changes a qualified economic outcome in a source-bound comparison, its value can be supplied as evidence to the canonical joint commercial/capability investment controller. Until then it is an **enabling instrument**, not claimed earned revenue, real demand or a verified profit advantage.