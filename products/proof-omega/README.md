# PROOF Ω — a bounded, independently replayable proof deliverable

**Give us a narrowly defined financial, security or operational rule. Get a replacement and a mechanically replayable certificate that the candidate agrees with the reference and maintains named invariants for EVERY admitted input in the supplied finite domain.**

The software is **runnable now** with Python 3.11+ and the standard library, with no APIs, accounts or paid services. It does **not** verify arbitrary application source, assembly, cryptography, Lean projects, smart contracts or unbounded software. The recent machine-code Signal proof breakthroughs are a *research motivation*, not a capability of this implementation.

## First command

```bash
python3 products/proof-omega/proof.py demo
python3 -m unittest discover -s products/proof-omega/tests -v

# Try an automatic, standard algebraic factorization:
python3 products/proof-omega/proof.py invent products/proof-omega/example.json \
  --output /tmp/proof-omega-proposal.json --report /tmp/proof-omega-report.json

# Independently recompute every input and compare the exact report:
python3 products/proof-omega/proof.py replay /tmp/proof-omega-proposal.json /tmp/proof-omega-report.json
```

Run the certificate verifier outside the proposing workflow, ideally under the buyer's control. It only declares `VERIFIED_BOUNDED` if the entire specified domain is enumerated, there is at least one admissible state, no execution is undefined, both candidate and reference outputs exactly agree, and all invariants hold on every such state. A witness shows the first counterexample otherwise. It refuses domains larger than 1,000,000 states instead of sampling them and mislabeling a sample a proof. Re-running `replay` recomputes the exact artifact and detects report tampering. The result is a *bounded exhaustive proof relative to the declared specification*, not a statement about real-world correctness of the chosen reference or invariants.

## Buyer-supplied contract

`example.json` defines:
- `schema: 1` and a human-readable `name`.
- `domain`: 1–4 named variables, each with finite inclusive **integer** minimum and maximum. This version admits at most one million states; quantities and money should be represented as integers (e.g. cents).
- `reference` and `candidate`: bounded, declarative, side-effect-free expressions in a limited AST language: integer addition, subtraction, multiplication, floor division, modulo, comparisons, boolean expressions and a conditional expression. **No Python execution, imports, function calls, attributes, network or file access.**
- `preconditions`: at most 12 boolean predicates defining admissible states. Empty admissible sets are rejected.
- `invariants`: 1–12 required boolean properties referring to `out` and inputs.

No code or real customer data is uploaded. The `invent` subcommand performs a **known algebraic factorization only**, and accepts it only after full verification and a lower *syntactic operator-cost proxy*. That proxy is **not** an observed runtime gain, scientific discovery, or evidence of legal compliance. For production-grade proof on general-purpose code, integrate a separately reviewed Lean/SMT/translation-validation workflow with pinned semantics and human-verifiable specifications; this package does not imply that integration already exists.

## Commercial delivery boundary

**Ideal paid pilot hypothesis:** a private payment processor, insurtech company or fintech wants a fast, lower-risk rule replacement for a finite integer state space. Obtain buyer-approved requirements and an *independent* expected interpretation; pre-register the scope, business acceptance and liability. Deliver the two JSON files, original specification hash, verified witness/proof replay, versioned verifier, and a clear exclusions list. Buyer-owned validation and regulatory/legal review are separate. No buyers, contracts, sale, net profit, or state-of-the-art proof have been obtained.

**Security:** read-only deterministic evaluator, strictly allowlisted AST, caps on domain and expression size, integer-size checks and independent replay. This is not a formally verified interpreter or hardened adversarial-hosting service; review and isolate the verifier before using untrusted contracts in shared production. For privacy, run inside the buyer's infrastructure.
