# PROOF Ω — a repair must earn its proof

**Experimental developer tool, not a general security certification service.** Give it a small pure Python integer function and an explicit contract. It returns a counterexample or a source-bound SMT obligation proving equivalence to that contract and output-range safety for **every integer input in the declared domain**. An optional authenticated Codex/ChatGPT repair loop proposes changes; the separate deterministic checker accepts or rejects them. No submitted Python is imported or executed by the checker.

## Try it now

Python 3.12 or newer, on your own machine:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r products/proof_omega/requirements.txt
python -m products.proof_omega check \
  --source products/proof_omega/examples/fee_bug.py \
  --contract products/proof_omega/examples/fee.contract.json --output /tmp/fee-counterexample
# Expected exit 2: a concrete counterexample, not a failed installation.
python -m products.proof_omega check \
  --source products/proof_omega/examples/fee_reference.py \
  --contract products/proof_omega/examples/fee.contract.json --output /tmp/fee-proof
python -m products.proof_omega verify /tmp/fee-proof
```

The fee reference is an explicitly **developer-written fixture**, not evidence of autonomous repair. A second example catches negative withdrawals that incorrectly increase balances. These are synthetic isolated kernels, not financial services or production banking code. Every output path must be new, preserving prior results.

### Real agent repair (explicit opt-in)

Install the official Codex CLI and sign in using your eligible ChatGPT plan. Then:

```sh
codex login
python -m products.proof_omega repair \
  --source products/proof_omega/examples/fee_bug.py \
  --contract products/proof_omega/examples/fee.contract.json \
  --output /tmp/fee-agent-repair --attempts 3 --authorize-model-sharing
```

`--model` selects an available model explicitly; otherwise the existing Codex configuration chooses it. This tool does not silently substitute a smaller model, create API keys, activate billing or fall back to paid APIs. ChatGPT-plan access is subject to account limits. `--authorize-model-sharing` authorizes sending the selected source and contract to that authenticated provider; do not use private/customer material without the appropriate consent. The agent runs in read-only sandbox mode and is instructed to return source only. Read-only is not no-read isolation: this adapter does not technically disable the CLI’s tools or prevent every host-file read. Run it in a dedicated account/workspace without unrelated sensitive data; prompt instructions are not a security boundary. The fixed contract is not changed by a proposal. Failed proposals receive actual counterexamples. Provider errors, deadlines and unknown solver results never become accepted repairs.

**Actual environment result:** the authenticated CLI was present, but app-server initialization failed with a read-only filesystem error before inference. Autonomous repair is implemented but **not demonstrated here**. No model capability, commercial scale, customers or profit is claimed. Run `repair` on a supported authenticated installation to qualify that path; do not bypass sandboxing.

## Supported semantics and trust boundary

- Exactly one function, positional parameters in contract order, exactly one return expression.
- Integer constants/names, addition, subtraction, multiplication, floor division/modulo by positive literal, integer comparisons, boolean conjunction/disjunction inside conditions and conditional expressions.
- **Python mathematical integers**, not C machine integers. No overflow claim about compiled code. No floats, loops, recursion, imports, calls, attributes, memory, I/O, exceptions, mutation, decorators, defaults or annotations. Unsupported code is rejected.
- The specification author must choose meaningful input ranges and the correct `expected` expression. Empty domains are rejected. Equality to a bad specification proves a bad specification faithfully; human domain review remains essential. Runtime/memory exhaustion, timing side channels, integration behavior, authentication and systems security are outside scope.
- Z3 4.15.4, Python's parser, this AST-to-SMT translation and the host are trusted. This is a **solver-checked universal obligation**, not a Lean proof or independently checked proof trace. `obligation.smt2` can be replayed by an SMT solver. `verify` reconstructs it from source/contract and re-solves rather than trusting the prior PASS. It is independent of the model proposer, **not an independent implementation of the translator or solver**.
- Bundle hashes establish consistency, not signer authenticity. Pin the approved contract/source hashes outside the bundle; an attacker replacing the entire contract and source can create a different valid theorem.
- Default solver timeout is 30 seconds; UNKNOWN is a rejected qualification, not a theorem. Expression-size and literal bounds are computational-input safeguards, not universal commercial scale claims.

## Why build it now, and what has not been earned

[AlphaProof Code (Google DeepMind, November 10, 2026)](https://deepmind.google/documents/36/Formal_Verification_of_Signal_4.pdf) is evidence for the direction of AI-assisted code verification, not a system this package reproduces or depends on. Automated verification and synthesis predate this fortnight. This initial product combines established SMT methods with a current model proposal interface; it does **not** establish that its supported scope was impossible two weeks earlier.

The consequential prospective use is reducing the work needed to repair and qualify security-sensitive numeric decision kernels. Existing Z3 workflows, specialist formal-methods tools and expert-plus-AI engineering are strong alternatives. The simplest exact-contract implementation often wins without AI. This tool does not force a model call when a known solution is available.

Commercial gate: a consenting customer supplies an eligible, valuable kernel and independently accepts its contract and integration. Compare full delivery cost and latency with that customer's strongest alternative, including specification work, failed attempts, verification, support, maintenance and inference/compute. Pricing and willingness to pay are unmeasured. No paid outreach, production deployment or financial transaction occurs. Profit, market size and autonomous scaling remain hypotheses.

## Test

```sh
python -m unittest discover -s products/proof_omega/tests -v
```

Local and hosted qualification cover the scoped parser/solver/product path, not a safety certification. New frontier claims need a genuinely new result against current alternatives, not the fixture demonstrations.
