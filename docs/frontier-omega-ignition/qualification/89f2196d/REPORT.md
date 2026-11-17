# FRONTIER Ω IGNITION qualification at 89f2196d

**Disposition: working local product, independently executable recipient artifacts, open flagship qualification.** The decisive migration comparison favored direct construction with the same model. A commercial launch or historical frontier-crossing claim has no supporting measurement in this experiment.

The application under test is [draft PR #439](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/439), stacked on the research-edition draft #436. Its frozen implementation commit is [89f2196d552810bc56696a7f380ae66c55f8763a](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/89f2196d552810bc56696a7f380ae66c55f8763a/products/frontier-omega-ignition). This evidence record is kept separately so posting the results cannot move the tested product revision.

## Real model study

The public GitHub CPU runner loaded the SHA-256-verified Qwen3-4B-Instruct-2507 Q4_K_M weights and pinned llama.cpp runtime. All five actual model calls in this study completed. Four CPU threads were available to the model server. The same loaded model served the three arms in the predeclared order. Later arms may have benefited from the warm server. Wall time is measured elapsed time, not a complete economic price. [Machine-readable study](model-study.json) · [Original hosted artifact](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/artifacts/14362922436)

| Registered arm | Wall time | Input / output tokens | Actual outcome |
| --- | ---: | ---: | --- |
| Discovery, challenge and construction against the supplied public evidence | 597.08 s | 5,606 / 2,260 | Generated five candidates and deferred. No contract was frozen or artifact built. Construction qualification failed. |
| Direct construction of the identical frozen migration | 71.16 s | 1,784 / 174 | Produced a program, passed all nine checks, and ran the exported verifier and example with exit code 0. |
| Live-source investigation and construction | 949.24 s | 11,417 / 1,885 | Retrieved five observations, including an earlier/current llama.cpp pair. Generated five alternatives, cited none of the fresh observations as usable support, and stopped. The registered research and construction gates failed. |

The hosted model workflow consequently finished **FAIL**. The software correctly prevents a stop or deferral from producing an accepted artifact. The independently passing direct comparator is a usable outcome for the stated migration. [Model job](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/job/134294985506)

The public information was sufficient to reconstruct the [model's direct proposal](direct-proposal.json). Its canonical response digest, frozen contract digest, compiled artifact digest and example output digest matched the hosted receipt. The [recipient ZIP](Qwen_Direct_Migration.zip) is a fresh packaging of that recovered program on CPython 3.12.14; the hosted job used 3.12.16. The fresh package passed nine checks and processed the example after extraction. The original hosted ZIP’s exact timing bytes were not recovered.

```sh
python3 -I run.py verify
python3 -I run.py run < example-input.json
python3 -I run.py migrate-jsonl < source-rows.jsonl > migrated-rows.jsonl
```

Earlier registered attempts are part of the record. The first ran two genuine model turns and rejected a challenge objection outside the allowed vocabulary. A subsequent unconstrained trial rejected an invalid challenger, and its direct comparator also failed. The final study used the same structural constraints in the main and direct construction arms. Candidate, evidence and strategic judgments remained with the model. [First receipt](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44151148461/artifacts/14360935462) · [Second receipt](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44153934583/artifacts/14362616921)

## Product, recipients and sources

| Boundary | Result |
| --- | --- |
| Exact-source engineering | 60 Python tests. Three real Chromium suites exercised historical demos, the local workbench and the standalone offline preview. Coverage includes edited inputs, stale downloads, transfers, restart, refusal, downloaded artifacts, mobile layout and explicit replay. [Engineering job](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/job/134294986061) |
| Original assisted missions | The included Codex session supplied eight operator-assisted exchanges across three missions. File audit and migration each passed nine recipient checks. The physical mission deferred for lack of observations and apparatus. The operator knew the cases. [Original public evidence](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/89f2196d552810bc56696a7f380ae66c55f8763a/products/frontier-omega-ignition/evidence/recipient-checks.json) |
| Whole-directory release | Fifteen files, 239,857 bytes. A separately pinned receiver correctly identified a missing test, changed page and extra file, and identified both the modified README and rewritten incoming manifest. Independent sha256sum plus file inventory agreed on all three scenarios. This extension executed deterministically. [Observed handoff](release-handoff.json) · [Receiver and receipt download](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/artifacts/14361021738) |
| Conventional migration | Local jq 1.7 matched all four declared cases. Hosted jq 1.8.1 reproduced the result. Local GNU Coreutils 9.7 and hosted uutils sha256sum 0.10.0 furnished the respective conventional file-hash executables. [Recipient and conventional receipts](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/artifacts/14360453192) |
| Independent acquisition job | Twelve observations, nine releases and three earlier commits across Hugging Face Transformers, PyPA build and the explicitly supplied jq repository. No retrieval or integrity failure. This job measures access and provenance. [Source receipt](public-sources.json) · [Source job](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/job/134294986101) |
| Offline delivery | The 186,750-byte standalone HTML ran with network access disabled, opened three recorded missions and downloaded both original recipient ZIPs byte-for-byte. Its SHA-256 is `8855f5733f289807daec59f891833d6db05fcf8551d0e69a86a5bf876e534cee`. [Offline preview](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/artifacts/14359734492) · [Desktop and mobile screenshots](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44155490455/artifacts/14360463255) |

The remaining two public examples constitute a prospectively fixed unattended cohort on the same application source. Each has one registered outcome: verified artifact and actual recipient execution for the release-audit mission; explicit deferral or refusal with no artifact for the physical request. Their separate CI receipts leave the original registered migration failure intact.

## What the verdict permits

The operator can use a local model or an explicitly attributed assisted exchange, resume a private mission, inspect sources and challenger decisions, try the accepted record program, and download a verifiable package. A direct model call is a demonstrated productive route for the editorial migration. Selecting or inheriting a different mission still requires new authority and fresh acceptance.

Open requirements include a verified economic frontier crossing; evidence that research and challenge outperform the strongest complete alternative; and demonstrated demand, complete-cost margins, or successor improvement. The product covers two bounded execution families. It does not grant an open-ended model authority to run arbitrary software, deploy, spend or publish customer data. There is no production service, merge or release in this delivery.
