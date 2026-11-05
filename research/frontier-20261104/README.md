# GENESIS Frontier 001 — Discover the next possible enterprise

**Research source cutoff:** 4 November 2026. **Execution evidence:** updated 5 November 2026. **Status:** exploratory, source-pinned execution in GitHub Actions; no achieved model-service attestation, breakthrough, production adoption, real revenue, or self-improved inventor.

## The first frontier event and the second-order hypothesis

[Anthropic's FlashProve release (2 November 2026)](https://www.anthropic.com/research/provable-inference) provides a research prototype for checking that output tokens came from weights committed by the provider. Its large-model example reports about 110 proof-tokens/second on one H100, about 19 MB of proof material per 1,024-token request and approximately 70–95 times ordinary model inference GPU time. The open-source [FlashProve repository](https://github.com/anthropics/FlashProve) includes a CPU verifier, Lean verifier/proofs and a small synthetic accepted example. The proof concerns *specified model inference*, not whether the response is true or useful. The published C++ verifier's behavior is tested; do not claim its source code is fully formally proved.

**Potential consequence:** independently checkable AI contracting, where a buyer receives both (1) independently authenticated model-origin evidence, and (2) mission-specific evidence that a useful deliverable meets its exact acceptance contract. Verifying identity is a possible additional trust instrument, never a substitute for testing a job result. A buyer could delegate computation without trusting the seller's claims about which model produced a reply. Whether this is economical depends on actual provers, trusted commitment distribution, network bandwidth, privacy, acceptance work, payment rules, and alternatives.

**Participation:** seller chooses to offer a price and proof, provider chooses to support the claimed model and compatible proof generation, independent verifier chooses whether to accept it, and buyer may refuse or use a competing complete service. None of these actors has agreed to participate. Provider availability for real service verification and customers' willingness to pay are unknown. The buyer retains a no-purchase option.

**Strong alternatives:** ordinary signed server receipts, hardware-attested execution where applicable, the best unproved frontier service with conventional audits, direct execution, and non-entry. Proof overhead can dominate expected value; do not assign imaginary premiums or assume monopoly. A qualified seller requires consent, real useful output, available authentic commitments, complete costs and cash settlement.

## Executable first-order experiment

This branch intentionally uses the *best existing released verifier*, rather than pretending to invent a new cryptosystem.

[Run the hosted study](../../actions/workflows/genesis-frontier-proof-20261104.yml) or invoke the local script research/frontier-20261104/probe_flashprove.sh with a **new absolute output directory**. It is designed for Linux, non-root execution, Git, g++ 13 or later, Bash, Python 3 and GNU sha256sum. The public GitHub Actions workflow uses read-only repository permissions and a standard Ubuntu runner, not GPU capacity, paid model APIs or model keys.

1. Clone and pin upstream FlashProve commit **9e2bdd8ff5bf9c62f18263d7dac189b0400b260c**.
2. Verify published checksums of the synthetic proof example.
3. Build the upstream C++ CPU verifier without modifying its code.
4. Verify the published synthetic example. Require process exit 0 and **the final line YES**.
5. Execute upstream's ten altered-proof negative controls. Require script exit 0 and **the final line 10 altered sets: all rejected**.
6. Export an inspectable RESULT.json, source SHA, log digests, exit codes and full stdout to the workflow artifact.

The synthetic example's commitment ID is packaged together with the proof. That is permitted for this self-test **only**. A real-world check requires the buyer to pin the trusted commitment from an independent channel *before* making the request and to bind the request/response bytes, token range and policy. Even a successful real model-origin proof would not establish the validity of a downstream physical or commercial claim.

The workflow is the evidence source: no success is assumed from upstream documentation before the hosted run completes. If the hosted job fails or does not run, state that the attempted reproduction remains unresolved.

## Verified result and exact audit sampling

[Hosted run 41938562815](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41938562815) passed on 5 November 2026 at source commit [`ba3e92e25ca042159f81756ae05292d8b9371103`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/ba3e92e25ca042159f81756ae05292d8b9371103): the synthetic example returned exit 0 and final line `YES`, all ten altered examples were rejected, and all five sampling tests passed. The [11-file evidence artifact](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41938562815/artifacts/13374777814) includes verifier logs and the generated sampling result; its recorded expiry is 5 December 2026, 00:06:33 UTC. This confirms the reported outcomes for that finite synthetic experiment, not a live provider, real request or production service. It does not certify later commits or all repository checks.

The standard finite-population model in [`audit_sampling.py`](audit_sampling.py) fixes `N` records with exactly `K` violations before choosing `q` uniformly random records without replacement. With `C(n,k)` denoting a binomial coefficient, for `0 <= q <= N-K`:

`P(at least one violation sampled) = 1 - C(N-q, K) / C(N, K)`.

For `K > 0` and `q > N-K`, the probability is 1; with `K = 0`, it is 0. Exact rational arithmetic gives the following minimum counts for `N = 10,000` and detection probability at least `99/100`:

| Fixed violations | Rate | Minimum audits |
| ---: | ---: | ---: |
| 1 | 0.01% | 9,900 |
| 10 | 0.1% | 3,689 |
| 100 | 1% | 448 |
| 500 | 5% | 90 |
| 1,000 | 10% | 44 |

The [tests](test_audit_sampling.py) compare the formula with exhaustive enumeration of all sample subsets for populations 1–8 and check minimum-count boundaries. These are mathematical checks, not live inference audits. Applying the probabilities to model substitution additionally requires a binding population and model commitment, sampling unpredictable to the provider until commitment, and reliable recognition of every sampled violation. Missing or refused proofs require a separate enforcement rule. Advance knowledge of the selection, mutable records or unrecognized violations invalidate the stated detection guarantee. This controls population-level sampling risk at the specified prevalence, not each job's integrity or outcome correctness.

Reproduce the mathematics from the repository root with Python 3.10 or newer and its standard library; choose a new output filename:

```sh
python3 -m unittest discover -s research/frontier-20261104 -p 'test_audit_sampling.py' -v
python3 -O -m unittest discover -s research/frontier-20261104 -p 'test_audit_sampling.py' -v
python3 research/frontier-20261104/audit_sampling.py --out NEW_AUDIT_RESULT.json
```

Audit fractions alone establish no commercial savings. Proof generation, transfer, verification, failures, enforcement and outcome acceptance must be costed and compared with signed receipts, hardware attestation, direct provider use and conventional quality assurance. A permissioned live-model pilot with independently authenticated commitments and separately accepted useful work remains the next test; no customer, payment, profit or superior invention procedure has been demonstrated.

## Materially different second-order opportunities

| Candidate | New frontier signal | Missing means and decisive next test | Strong complete alternative |
| --- | --- | --- | --- |
| **Proof-carrying AI services** (this first probe) | [FlashProve, 2 Nov](https://www.anthropic.com/research/provable-inference) | Use a genuinely independent model commitment and real supported model/prover; check a completed authorized job; compare cost and reliability | Signed response, hardware attestation, direct model use, ordinary artifact acceptance |
| **Remediation absorption at machine scale** | [OpenAI, 4 Nov](https://openai.com/index/a-thousand-fewer-paths-to-root/) reports 2,308 candidates, 1,724 reproduced vulnerabilities and 948 distinct Linux local-privilege-escalation patch cases in a large research campaign | Demonstrate fast, safe upstream patch *acceptance*, version/variant coverage, maintainers' consent and economic benefit; no exploitation run here | [Codex Security](https://help.openai.com/en/articles/20001107-codex-security), [GitHub agentic autofix](https://github.blog/changelog/2026-07-10-agentic-autofix-for-code-scanning-alerts-in-public-preview/), specialist engineers |
| **Programmable biological nanostructure research** | [Anthropic, 4 Nov](https://www.anthropic.com/research/investigating-vault-particles-with-claude) reports a prokaryotic vault structure and faster preparation | Obtain authorized source structures, experimental validation, a consequential new end use and a reliable wet-lab or production path | Established structural biology with domain experts and physical labs |

Two further high-upside tracks remain on the radar: [connected physical engineering](https://openai.com/index/accelerating-engineering-for-the-physical-world/) could produce qualified custom instruments once manufacturing and physical acceptance are solved (overlapping repository research is already underway in PR #239); [recent mathematical advances](https://openai.com/index/building-scientific-understanding-with-academic-communities/) could produce useful computational algorithms, but theoretical correctness does not imply competitive runtime, implementation or customer value. [Agentic cheminformatics](https://deepmind.google/blog/agentic-cheminformatics-with-google-antigravity/) is another explicit tool-assisted route, with access conditions and physical validation still required.

## Decision contract, costs and successor

**What first-order success means:** a pinned *public synthetic example* verifies and documented falsifying perturbations are rejected. This is a reproducible use of existing technology, not superior invention, model-service authenticity or proven commercial demand.

**What second-order success requires:** a buyer receives a useful independently accepted result, a legitimately authenticated model proof that is required for their use case, and a price window beating strong alternatives *after* prover compute, proof transfer/storage, checking, failures, maintenance, acquisition, support and all other costs. Simulated payments are not collected revenue.

**What third-order success requires:** freeze a verified proof-and-result receipt process, then compare fresh, different successor jobs using the retained process against capable controls free to build or procure FlashProve themselves; equalize models, available information and budgets and include all transfer and verification cost. Further compare *discovery procedures* at equal capability stock; routine reuse or provider progress alone is not improved invention.

**Tried →** use an origin-neutral upstream cryptographic verifier with reproducible positive/negative examples. **Outcome →** only actual workflow evidence can qualify these local checks. **Learning →** a result can be independently tested on an ordinary CPU but authentic model provenance in a live service is a separate, still-open integration challenge. **Next →** permissioned independent-commitment pilot and complete-cost control; stop or pivot when direct signed/attested alternatives dominate.

**Safety and authority:** no customer outreach, spending, security-exploit generation, live model access, contracts, cryptocurrency, protected data, repository main merge or physical actuation is authorized or performed by this study.