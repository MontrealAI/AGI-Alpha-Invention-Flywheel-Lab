# PROOF Ω — an auditable, executable assurance product

**One input:** a bounded payment, escrow or authorization policy. **One deliverable:** a passing, independently replayable proof certificate and a runtime that executes only certified transitions, or a shortest counterexample and a HOLD.

This is a real, usable *finite-state* assurance kernel with an additional compiled-executable conformance gate. It is **not** Google DeepMind's AlphaProof Code; it does not verify third-party compiled code or solve arbitrary cryptographic security properties. The November 10, 2026 publication creates a compelling frontier opportunity to pursue progressively stronger agent-assisted specification/proof, not an earned claim that this implementation has comparable breadth.

## Run in a minute (Python 3.10+, a C compiler, and Docker; no paid API)

```bash
python3 products/proof-omega/proof_omega.py demo --out /tmp/proof-omega-demo
# Without Docker: only for the public trusted synthetic fixture:
python3 products/proof-omega/proof_omega.py demo --unsafe-local --out /tmp/proof-omega-trusted-demo
python3 products/proof-omega/proof_omega.py prove products/proof-omega/examples/escrow.json --out /tmp/escrow-proof.json
python3 products/proof-omega/proof_omega.py audit products/proof-omega/examples/escrow.json /tmp/escrow-proof.json
python3 products/proof-omega/proof_omega.py apply products/proof-omega/examples/escrow.json /tmp/escrow-proof.json reserve '{"buyer":2,"escrow":0,"seller":0,"settled":0,"refunded":0}'
python3 -m unittest discover -s products/proof-omega/tests -v
```

The compiled C executable is also run against every certified reachable state × action pair (12 requests); the good binary matches exactly, and a deliberately altered compiled binary produces a concrete divergent witness. On real customer binaries Docker isolation is mandatory by default; the '--unsafe-local' switch is for the checked-in fixture only, NEVER customer code. This is a full finite-contract comparison, not a proof about all binary inputs.

The safe sample provably conserves funds (in its **specified integer, atomic, finite-state semantics**) and forbids both refund and settlement; an intentionally defective variant violates conservation after `reserve → settle`, producing a reproducible counterexample. `prove` enumerates *all reachable states* and outgoing transitions under declared bounds, not just finite random test cases. If it exceeds `--max-states`, fails validation or finds a violation, it never emits a passing certificate. `audit` independently reconstructs reachability using separate transition semantics and detects omitted states, altered edges and stale policies. `apply` executes only an edge from that certified graph and refuses an unproven action/state.

### Customer contract

- **Buyer:** payment processor, marketplace, enterprise wallet, or software vendor using financial entitlements.
- **First deliverable:** an executable, narrowly scoped payment or authorization policy, approved invariants, certificate, and an independent customer replay report.
- **Acceptance:** contract freezes exact business rules, rounding/precision, initial state assumptions, supported amounts, error behavior and risk controls *before* constructing a proof. Customer independently audits an isolated artifact and verifies it enforces that same policy in its real integration.
- **Strongest comparator:** in-house formal methods, model checkers, TLA+/Apalache, professional security review, AI-assisted engineering, existing vendor features, and doing nothing. Do not claim an advantage until matched benchmarks prove it.
- **Pricing thesis, not a quote:** fixed-fee technical assurance pilot with a larger success-based production engagement if independently accepted. Neither willing buyers nor positive margins have been established.
- **Key limiting factor:** proving this executable state machine **does not prove a surrounding API, a database's transaction isolation, a smart contract, arbitrary compiled code, concurrent distributed workflows, or the correctness/completeness of the business specification**. Separate integration proofs and threat models are necessary. Human review of trusted specification remains required for high-stakes deployment.

### Interface and semantics

JSON policy `proof-omega.finite-policy.v1` declares bounded integer variables, one initial state, named guarded atomic transitions and named safety invariants. Expressions use only integers, booleans, declared variables and whitelisted `add/sub/mul/eq/ne/lt/le/gt/ge/and/or/not` operators. They are interpreted without `eval` or network access; arithmetic is exact mathematical integers, never machine overflow. State and action names are sanitized. A guard returning something other than Boolean is not accepted by the independent audit.

The separate `bind-binary` command checks an owned/authorized deterministic JSONL executable against every certified state-action result. The preconditions exclude I/O side effects, undeclared environment inputs and concurrency; the binary SHA-256 and case count are recorded in its verdict. This reviewed implementation runs the domain under canonical, reversed and repeated/rotated orderings, recording the total executed requests and rejecting order-dependent transcript impostors. These **three public finite probes cannot prove arbitrary executable determinism or resistance to an adaptive, schedule-aware binary**; a customer must supply a separately supported threat model, sandbox and stronger formal/refinement proof for higher claims. It is a bounded executable conformance check, not a machine-code formal proof.

The certified artifact stores every reachable state and edge, allowing a client to check and run the proofed finite-state behavior. The certificate is SHA-256-bound to canonical policy JSON. The SHA is for source identity, **not a cryptographic proof of correctness by itself**. No third-party data or credentials are required or transmitted.

### Frontier link (primary source)

Google DeepMind, **November 10, 2026**, *Introducing AlphaProof Code* and its machine-code-level `libsignal` proof. Google describes ~6.5M lines of Lean and human-reviewed specifications, produced in four weeks. Their result concerns named security properties under formal assumptions; ours is a distinct, far narrower executable policy verifier.

- https://deepmind.google/blog/introducing-alphaproof-code/
- https://google-deepmind.github.io/code-verification/

**Status:** BOUNDED LOCAL PRODUCT PROTOTYPE. Real customer integration, economically significant acceptance, source-level/machine-code refinement, production hardening, willingness-to-pay and independently accepted frontier advantage remain **UNQUALIFIED**.
