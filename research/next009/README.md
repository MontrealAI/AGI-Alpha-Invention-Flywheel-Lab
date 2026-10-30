# Campaign 009: reconstruct and replay the executed evidence

`reproduce.py` reruns the native EPA model simulations, generated observation plans, strong controls, independent numerical checks, exposed diagnostic cases, commercial simulation and research-funded successor. It requires the source files and public evidence archives in the extracted package. It does not use Git history, inherited working directories, network calls, model-provider APIs or live payments.

This is **exposed reproduction**, with zero new protected cases. A completed replay establishes that these package bytes reproduce their declared outputs on the specified platform. It does not add field validation, scientific novelty, grounded buyer participation, measured complete costs, qualified unrestricted earnings or earned-funded successor construction.

## Environment and installation

The qualified environment is CPython 3.12 on Linux x86_64. The package contains the pinned native EPANET library and the exact EPA network inputs; an unqualified platform is refused rather than silently substituted. The numerical and exchange dependencies are pinned in `requirements.txt`:

```text
numpy==2.3.5
scipy==1.17.0
cryptography==50.0.2
```

From the root of a freshly downloaded and extracted release, create an isolated environment. Dependency installation is a separate download operation; the replay itself works offline after installation.

```bash
python3.12 -m venv /tmp/agi-alpha-next009-venv
/tmp/agi-alpha-next009-venv/bin/python -m pip install -r research/next009/requirements.txt
```

No `git clone`, editable package installation or repository history is needed. Invoke commands from the extraction root. `--require-clean` refuses an extraction containing a `.git` directory. The driver fixes subprocess import paths to the current extraction and verifies that the project modules resolve there.

## Full reconstruction command

The output directory must be new. Reusing a previous output is refused so that a failed run remains inspectable.

```bash
/tmp/agi-alpha-next009-venv/bin/python -m research.next009.reproduce \
  --require-clean \
  --output /tmp/agi-alpha-next009-replay-001
```

Allocate an explicit CPU, wall-time, memory and storage envelope before execution. The above command is the replay entry point, not a grant of resource authority. During the original campaign it must run under the unchanged `experiments.resource006_v3` supervisor and the existing campaign ledger, with an integration-owner-approved additional reservation. Do not replace the ledger, reset previous charges, or infer a new allowance from this README. A future independent reproducer must declare its own allocation and distinguish it from original campaign expenditure.

Every stage prints a concise start/completion line. Full subprocess commands, stdout, stderr, exit codes and measured driver/waited-child CPU are written beneath the output's `logs` directory. The external supervisor remains the authoritative budget and interruption monitor. The driver does not translate CPU seconds into monetary costs.

To check package dependencies, restore archived evidence and validate source bindings without executing the experiments:

```bash
/tmp/agi-alpha-next009-venv/bin/python -m research.next009.reproduce \
  --require-clean --preflight \
  --output /tmp/agi-alpha-next009-preflight-001
```

Preflight reports `PREFLIGHT_PASSED_NO_EXECUTION_CLAIM`. It is not a substitute for the full replay. If successor evidence has not yet been published, `--through commerce` explicitly stops at that boundary and reports `PARTIAL_REPRODUCTION_THROUGH_COMMERCE_PASSED`; the default requires all successor inputs and refuses to silently skip them.

## What is actually reexecuted

| Stage | Executed work and comparison | Preserved limit |
| --- | --- | --- |
| Archive restoration | `restore_evidence.restore` checks archive identity, every member identity and safe paths, then restores all public archive members. Existing differing files are refused. | Restoration supplies reproducible public bytes; it does not itself qualify an experiment. |
| Net1 and raw Net3 | The frozen `inventions.measurement009.run` reruns native EPANET, all four compiler/control arms, full builder-visible source/erasure diagnostic replays, and full ambiguity witnesses. Reconstructed corpus bytes must match the published originals exactly. | These are authored finite numerical models, with simulated observations and no field calibration. |
| Net1 independent exposed replay | The frozen verifier and actual candidate runtime execute the original 72 cases using the published seed through `--development-seed`. Every source-pair/outage obligation and the exact conventional minimum are recomputed. | `--confirm` is never passed. Protected-case counts remain zero in the new run. |
| Raw Net3 failure | The original source-bound driver is executed and must fail with exactly `TRACE_PERCENT_RANGE`. Every one of the original 1,211 out-of-range coordinate witnesses is reconstructed over the full 203,136-coordinate denominator. | Raw Net3 remains unqualified under the frozen input contract. No clipping, altered checker, dropped coordinates or favorable relabeling is allowed. |
| Net3 numerical edition | The uniform half-even 12-place adapter processes every coordinate and recompiles all three calibrated arms. The separately authored numerical checker verifies the entire transformation; the derivative driver checks all 4,186 pairs and 26 outage states. | This is a separate numerical edition. Its 25-sensor global minimum remains solver-reported, and its pass does not qualify the original raw corpus. |
| Source-bound commerce | The existing Alpha protected exchange is executed with the exact original accepted plan and receipt. All six conditional CAD scenarios are recomputed. A separate Decimal auditor checks the newly produced report using a byte-bound input view. | Participation and cost assumptions remain modeled; qualified unrestricted earnings and earned-funded investment remain zero. There are no real transactions. |
| Net2 successor | The root's frozen-source construction driver resimulates Net2, applies the prospective uniform numerical edition, executes actual retention/retrieval, and constructs all 15 drift/arm plans plus the old plan. The separate verifier reruns every drift level and actual runtime case using `--replay-seed`. | This is exposed replay of a research-funded successor, not another untouched confirmation or evidence of discovery superiority. |

For source-bound Net3 drivers, the fresh native and transformed corpus bytes must first match the originals. The independent drivers then receive the original published plan bytes, because their frozen plan identities include historical construction timings. Separately, the replay compares each newly generated plan against the published plan after removing **only** construction wall/CPU timing fields. Sensors, objectives, solver status, generated expressions, all pair certificates, assumptions and all other plan content must match.

The primary diagnostic replay also uses the original plan and seed. Its checker/runtime outputs are compared to the original evidence after explicitly relabeling confirmation counts as exposed-development counts and excluding measured wall/CPU times. This preserves the original case denominator and does not manufacture new protected cases.

Successor plans are freshly generated and independently tested. Their byte hashes legitimately differ because they contain fresh timing measurements. The driver compares the complete remaining plan semantics, the simulation-receipt content excluding timing, actual retrieval records, every old-plan failure, all three matched arms, every prespecified drift level, conventional controls and actual diagnosis outcomes. It removes only the corresponding timing-derived plan/receipt hashes and explicit replay labels from the final report comparison. No global rule ignores arbitrary hash fields or adverse outcomes.

## Successor input manifest

The integration owner publishes `research/next009/REPLAY_INPUTS.json` after the original successor run. The driver requires schema `agi-alpha/next009-successor-replay-inputs/v1`, the frozen successor identity `18fcf172156ea18ccb5c343844e160779884b3d44f8a04cfd1dae7ce7b99cb30`, and pinned Net2 Git blob `6645947b161a90a18f312539d4ff5ac3aee12c4a`.

Its `paths` object has exactly these keys, each relative to the extraction root:

| Key | Contents |
| --- | --- |
| `network` | Exact acquired `Net2.inp` |
| `raw_corpus` | Original native Net2 corpus JSON |
| `corpus` | Derived uniform numerical-edition corpus JSON |
| `numeric_receipt` | Complete all-coordinate representation receipt |
| `simulation_receipt` | Original source-pinned native simulation receipt |
| `plans` | Directory containing the old plan and all 15 drift/arm plans |
| `comparison` | Original `SUCCESSOR.json` from that plans directory |
| `acceptance` | Original separately executed successor acceptance report |
| `exposed_case_truths` | Original exposed seed and all independently generated case truths |

The manifest's `files` object maps each referenced file, all 16 plan files and `RETRIEVAL.json` to its SHA256. `network_git_blob_sha1` and `freeze_sha256` are separate fields. All listed files must be present after archive restoration and match their recorded bytes. The driver also checks every dependency bound by the successor freeze. An alternate manifest can be supplied with `--successor-manifest`, but it cannot change the frozen successor, network identity, complete cohort or evidence requirements.

## Reading the result

The authoritative new output is `REPRODUCTION.json`. A full pass is labeled `COMPLETE_EXPOSED_REPRODUCTION_PASSED`; preflight, a partial run, a mismatch and an interrupted/incomplete run are separate states. Every numerical comparison has its own recorded semantic hashes and an explicit list of excluded timing/replay fields. A mismatch writes both values to `disagreements/` and stops dependent work. No failure is silently repaired or overwritten.

All source identities are checked again at completion. Outputs and logs remain available on failure. If an external supervisor terminates the run before the final report can be written, use that supervisor's interruption receipt and the retained stage logs; absence of `REPRODUCTION.json` is not a pass.

The economic and scientific interpretation remains the one supported by the original evidence: useful finite-model measurement planning, technical parity with strong known controls, modeled commercial scenarios with unresolved demand and complete-cost inputs, and a separately tested research-funded successor where the original confirmation supports it. A reproducible package is a durability result, not mission completion.
