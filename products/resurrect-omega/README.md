# RESURRECT Ω — authorized black-box replacement with independent acceptance

**One input:** a binary executable with a finite documented JSONL request domain, whose owner has lawful reimplementation rights. **One deliverable:** a self-contained Python replacement generated solely from its observed behavior, plus a fresh oracle-comparison verdict.

This prototype **really reconstructs the behavior of a limited, declared input domain**, rather than presenting a mock UI or promising a general clone. It does **not** recover the author's original source code or prove equivalence outside the frozen domain. It does not clone Slack, Finder, third-party licensed software or any customer's private code.

## One-command reproducible demonstration

```bash
# Requires Python 3.10+, a C compiler, and Docker for isolated execution.
python3 products/resurrect-omega/resurrect.py demo --out /tmp/resurrect-omega-demo
python3 -m unittest discover -s products/resurrect-omega/tests -v

# On a system without Docker, ONLY for the checked-in synthetic demo code:
python3 products/resurrect-omega/resurrect.py demo --unsafe-local --out /tmp/resurrect-omega-trusted-demo
```

The demonstration compiles `examples/legacy_pricing.c` into a native executable, reveals **only the executable and its outputs** to the synthesis path, and rebuilds its bounded JSONL behavior as a readable standalone `replacement.py` with an exact lookup representation. It covers all 3 regions × 2 tiers × 4 seat counts = **24 combinations**. Verification **re-runs the binary**, in reversed order, and checks every canonical JSON response against the generated program. The bundled C source exists only for transparent reproducibility of the *synthetic* example and is not read by the synthesizer. Finite-domain exhaustive comparison is not proof of general program reconstruction.

## For an authorized real executable

Prepare a JSON manifest:

```json
{
  "schema": "resurrect-omega.jsonl.v1",
  "name": "my_owned_contract_engine",
  "authorization": "I_OWN_OR_AM_AUTHORIZED_TO_REIMPLEMENT",
  "binary": "/absolute/path/to/authorized-jsonl-binary",
  "axes": {"region": ["NA", "EU"], "tier": ["BASIC", "PRO"], "seats": [1, 2, 3]}
}
```

The native executable reads one JSON request per line on stdin, emits exactly one JSON result per line on stdout, writes no stderr, exits 0 and has no side effects. These are **explicit adapter assumptions**, not universal executable behavior. An owner can write a rights-cleared JSONL adapter to bridge its system. Docker is mandatory by default, with no network, read-only filesystem, dropped Linux capabilities, nonroot user, CPU/memory/PID limits and a read-only mount of **only one executable**. It is not a production-strength hostile binary sandbox; use dedicated isolated infrastructure for actual customer binaries. The supplied command will fail closed without Docker.

```bash
python3 products/resurrect-omega/resurrect.py capture my_manifest.json --out /tmp/observations.json
python3 products/resurrect-omega/resurrect.py synthesize my_manifest.json /tmp/observations.json --out /tmp/replacement.py
python3 products/resurrect-omega/resurrect.py verify my_manifest.json /tmp/replacement.py --out /tmp/REPLAY.json
```

### Optional frontier-agent reconstruction

The deterministic code generator above is useful for narrow contract migration but **is not the 2026 frontier leap by itself**. There is now an optional 'agent' path that invokes the user's **already installed, independently authenticated Codex CLI**, with explicit permission to transmit selected behavior examples to the model provider. The agent receives a deliberately limited subset of observations and no binary or binary path, attempts to create a more general maintainable 'solution.py', and receives up to three mismatch examples if its independent Docker replay fails. Only a candidate that passes the complete fresh declared-domain replay is returned; otherwise the result is HOLD. This feature is implemented but its live provider execution remains untested here because this environment has no Codex CLI login. Do not confuse a ChatGPT Pro plan with authorization to use separately billable APIs.

```bash
python3 products/resurrect-omega/resurrect.py agent my_manifest.json /tmp/observations.json \
  --out /tmp/agent_replacement.py --rounds 2 --authorize-disclosure
```

**Security:** Codex's 'workspace-write' sandbox is not a high-assurance confidentiality boundary; only use authorized nonsecret examples in a dedicated environment. Agent-generated programs are **never** executed directly on the host by this workflow. The Docker evaluator is constrained but not a fully audited malicious-code containment solution.

A complete manifest domain of at most 25,000 combinations is captured and compared. Axes that are provably irrelevant over this finite domain are removed before generating the lookup implementation. Domain misses produce `HOLD`; they never silently extrapolate. `capture`, `synthesize` and `verify` bind manifest and binary hashes. Any binary change, license-right change or expanded request domain requires recapture and requalification. No LLM or paid API is required for the deterministic bounded path. The optional Codex agent path is **not** automatically run, qualified or billed by this repository; it requires explicit operator consent and an existing authenticated local Codex session. Additional fresh customer-held-out cases remain required beyond the finite-domain replay.

### Commercial acceptance

- **Buyer:** owner of a discontinued pricing engine, inherited internal data transform, legacy business rules, or end-of-support enterprise utility.
- **Value:** restoration of a supported, auditable replacement for a *bounded business-critical interface*, potentially avoiding specialist rewriting or vendor dependency. Value depends on actual operating obligations and licensing rights.
- **Strongest alternatives:** supported vendor upgrade, decompilers and static binary translation, hand-written replacement, off-the-shelf migration partners, competent human-plus-AI rebuild, no migration.
- **Required buyer gate:** legal rights attestation, actual nontrivial undocumented program, separate unexposed regression/holdout cases, performance and failure-behavior checks, 30-day maintenance estimate, security review, deployment acceptance and measured avoided cost. Finite lookup reconstruction alone is rarely commercially defensible where ordinary manual enumeration already suffices.
- **Suggested business model (unvalidated):** fixed-price technical qualification, then a negotiated higher-value migration contract conditional on actual successful replacement. Pricing, customer demand, supplier permission and profits are **unknown**, not booked.

### Frontier link (primary sources)

Intezer/Kodem, **November 10, 2026**, *When Everything Becomes Open-Source*, published AI-agent reconstruction experiments using Slack's shipped client, Apple's Finder and a malware sample. The authors explicitly note incomplete coverage and legal/engineering limitations. The 2026 Meta ProgramBench study establishes that general full-software reconstruction remains highly challenging; it was originally published **May 5**, not November.

- https://research.intezer.com/blog/2026/11/when-everything-becomes-open-source/
- https://arxiv.org/abs/2605.03546

**Status:** BOUNDED RECONSTRUCTION PROTOTYPE. No real legacy customer binary, accepted migration, original-source recovery, general semantic equivalence, secure hostile-code evaluation, agent-driven source reconstruction, commercial sale or verified profit.
