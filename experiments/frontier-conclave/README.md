# THE FRONTIER CONCLAVE Ω.001
## Can intelligence change the game, then test the new possibility?

**Implemented, tested prepared experiment kit. Not a completed live frontier-model rehearsal, commercial qualification, or proof of general invention.**

Three hypothetical teams individually cannot fund a 450-unit project; combined caps are 500. The arrangement 90/140/220 makes a previously unaffordable project fundable, conditional on consent and individual caps. The experiment constructs an inspectable acceptance checker, challenges it, and reuses it on a fresh input. It does not prove the proposal will be accepted in a real market.

Open `START-HERE.html` for a no-network, prepared browser explainer with six challenge buttons. It is a separate illustrative view, not live candidate execution.

## Run now (Python 3.10+, no external packages or network)

Extract the entire ZIP, open a terminal inside this folder:

```
python3 RUN_WORKSHOP.py check
python3 RUN_WORKSHOP.py run inputs/funded.json
python3 RUN_WORKSHOP.py run inputs/consent-withdrawn.json
python3 RUN_WORKSHOP.py run inputs/beyond-capacity.json
python3 RUN_WORKSHOP.py run inputs/fresh-reopen.json
python3 -m unittest test_experiment -v
```

On Windows use `py` instead of `python3` if appropriate. Exit codes: 0 successful execution/check; 1 regression disagreement; 2 input error. A correctly rejected proposal still exits 0 and reports accepted:false. This is a local prepared runner, not the full HARNESS GUI or its authenticated connected-model workflow.

## Live construction with your ChatGPT Pro

1. Open your signed-in Pro account. Select its strongest currently available reasoning model, record displayed model name, date and mode. Availability is not established by this kit. No API or additional purchase is needed for manual transfer.
2. Give it only `missions/CHATGPT-PRO-BUILDER.txt` plus development cases. Keep challenge files outside the builder's context. Computer use, if supported in that mode, can save its JSON in this local folder; otherwise copy its response to `candidate-response.json`.
3. Freeze the response before testing. Run:
   `python3 IMPORT_CANDIDATE.py candidate-response.json > candidate.json`
4. Run `python3 RUN_WORKSHOP.py check --instrument candidate.json`. Preserve response, actual model label, result and failures. The supplied challenges are disclosed to this kit's implementer, so they are NOT independent hidden evidence for the prepared reference. They can be withheld from the live builder only if you enforce the separation.
5. Reveal failing cases only after initial qualification. Save repair as a new file, never overwrite the first attempt. Revealed cases become development cases; use new independent challenges for stronger successor claims.
6. If no construction result after six minutes, switch openly to the prepared reference. Say: “We are now using a prepared checker, not a live model-generated result.”

No authenticated ChatGPT Pro-to-HARNESS connector is implemented or claimed. Computer-use access and actual latest model availability require host verification. No API keys are requested or included.

## Input contract

Exact fields: cap_a/cap_b/cap_c, a/b/c, cost, contingency, consent_a/consent_b/consent_c. Amounts are integer fictional units in [-1,000,000,000,1,000,000,000]; negative inputs parse but invalidate acceptance. Use smallest whole monetary unit if adapting, not binary floating-point currency. Consent is a JSON boolean, never inferred from silence. All three parties' consent is mandatory even at zero contribution. Zero-cost/zero-contribution proposal with consent is accepted by the declared policy. Extra/missing fields, non-integers, boolean amounts and nonboolean consents fail closed. No real funds, contracts, agent outreach or account authority.

Funding capacity is only arithmetic, not willingness or allocation feasibility under additional constraints. `within_caps` reports upper limits separately; negative amounts fail `accepted` regardless. Output fields are declared in instrument.json. Native evaluation is bounded; the strict adapter is part of the acceptance boundary and must travel with it.

## What is tested

`evidence/TESTS.txt`: nine checks, including 2,000 seeded comparisons against a separate direct boolean oracle, invalid type/JSON rejection, sandbox constraints, fault detection including removal of the nonnegativity guard, ZIP extraction and execution on fresh-reopen input. This is testing, not universal proof. `REFERENCE.json`: ten authored scenarios. `LABELED-FAULT.json`: deliberate total-only mutation, clearly not a real model failure. `IMPORTED-REFERENCE.json`: manual-response conversion succeeds.

Prepared reference is authored in this implementation session using the unmodified released HARNESS evaluator. No local or external frontier inference was run during these tests, no operating-system GUI rehearsal is claimed, and tests were executed on this Linux workspace only. Initial integration mistake (accessing evaluator envelope as direct output) was corrected before final suite; raw artifact evidence does not claim a flawless development history.

## Reuse and provenance

`vendor/instruments.py` is byte-identical to release 9f469d129dae71cf939e1be8a7d30ab824906cb4. Exact customer ZIP SHA256 is in PROVENANCE.json. Apache-2.0 LICENSE/NOTICE are preserved in vendor. The run adapter, case suites, prompts and presenter script are new experiment materials. No release-wide commercial qualification is conferred. The released product remains a candidate.

Export: copy or ZIP this entire folder, extract elsewhere, run the fresh-reopen command above. The automated test performs exactly this in a clean temporary folder. Preserve hashes if comparing versions. Do not treat a digest as a signature or independent certification.

## Public revision Ω.001-r1

Review found the original negative challenge also exceeded a cap, allowing a candidate with no nonnegativity guard to pass 10/10. The revised challenge has a=-1, b=1, c=0 and zero cost/contingency; caps, funding and consent otherwise pass. A new mutation regression confirms the weakened candidate now fails (9/10), while the prepared reference passes 10/10. This repairs challenge coverage, not a defect in the reference formula. Nine unit tests pass. The finite suite remains disclosed, not exhaustive.
