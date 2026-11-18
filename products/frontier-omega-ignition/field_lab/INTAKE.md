# A service brief that keeps its meaning

A French request for a P95 delay and aggregate output rate previously became a per-user P90 contract in all four Qwen captures. The new local compiler ties each accepted value to its words in the original English or French brief. A recipient can inspect the exact character spans and obtain a typed result without running a model. An optional check can also withhold a model answer when the clauses do not support it.

## What the comparison found

The registered public CPU trial used twelve new authored briefs, with six valid contracts and six required deferrals. The field client sent each once at concurrency one. All twelve model streams completed on the first attempt.

| Route on the twelve briefs | Exact decisions | Unsafe ready among six required deferrals | Unnecessary defer among six valid contracts |
|---|---:|---:|---:|
| Existing conventional grammar | 6/12 | 4 | 2 |
| Qwen3-4B-Instruct-2507 Q4_K_M | 7/12 | 5 | 0 |
| Same model outputs checked against the whole brief | 12/12 | 0 | 0 |
| Direct new grammar, without model inference | 12/12 | 0 | 0 |

Qwen accepted two upper rate bounds as minimums. It also accepted an aggregate rate, a P95 target, and a complete-turn target as if they belonged to the supported contract. The model correctly deferred a separate case that named both P95 first output and P90 complete turn. The source-grounded check removed the five unsafe admissions. The direct compiler obtained the same twelve answers and supplied their source spans. The authored test supports use under its bounded grammar. [Frozen twelve requests](intake_workload.json) · [Measured outcomes](intake_recorded/result.json) · [Prespecified comparison](INTAKE_REGISTRATION.md)

An independent author committed a four-case challenge before seeing the compiler. The code was frozen before those briefs were revealed. The existing grammar scored **3/4** and admitted one unsafe complete-response requirement. The new compiler scored **2/4**, gave all four cases a deferral and lost both valid contracts. One French brief used an unfamiliar construction. An English brief mentioned observed fleet throughput before stating its separate, valid per-user requirement. The compiler could not establish which text was background. The unseen failure argues for showing unsupported wording to the operator. No model inference was performed on this four-case population. [Sealed challenge](intake_recorded/independent_challenge.json)

On the historical six briefs, each of the two original clients at both loads reproduced the original Qwen result of 5/6. The new check rejected all four former aggregate admissions. It also deferred all four copies of a valid legacy French brief because “sous 320 ms” can describe a strict upper bound and the recipient supports an inclusive limit. Its score stayed 5/6 in each group. The original direct grammar still scored 6/6 on that population. The four groups repeat the same six briefs. [Historical captures](../field_trials/recorded/) · [Per-arm adjudication](intake_recorded/result.json)

## What the operator can use

From `products/frontier-omega-ignition`, use Python 3.11 or later. The CLI can read a brief on standard input, which keeps its text out of command-line arguments.

```sh
python3 -B field_lab/intake.py 'P90 first visible output within 0.48 s and at least 76 tokens/s per user.'
python3 -B field_lab/intake.py 'P90 complete turn within 450 ms and at least 31 tokens/s per user.' \
  --candidate '{"status":"ready","p90_ms":450,"min_rate":31}'
python3 -B field_lab/intake_qualification.py --check
python3 -B -m unittest field_lab.test_intake -v
```

The first command returns 480 ms and 76 tokens/s/user with the two source spans. The second returns a deferral for the complete-turn request and the proposed model answer. Intervals are zero-based character offsets, including the start and excluding the end. To distribute the standalone compiler, keep `intake.py` and `protocol.py` together. Its input and output stay in the local process. Retain any private brief only within its authorized workspace.

The grammar requires a positive inclusive upper bound on P90 first visible output and a positive inclusive lower bound on output token rate per user. Each clause must match in full. It can read English or French decimals, seconds or milliseconds, reversed clauses, and explicitly supported unit spellings. Unsupported clauses, conflicting or repeated fields, precision that cannot be delivered faithfully, negations and different service metrics withhold the result. A rate still needs an operator-approved measurement protocol before it can be translated into a serving recommendation. The existing [private typed endpoint mission](../examples/endpoint.json) lets an operator state the full contract for a reviewable benchmark decision.

## What actually ran

| Observation | Recorded value |
|---|---|
| Serving identity | Qwen3-4B-Instruct-2507 Q4_K_M, pinned GGUF and llama.cpp b12242. Four CPU threads on an AMD EPYC 9V45, one serving slot. |
| Physical workload | Twelve authored public requests, once each, one concurrent user. No retries. |
| P90 first visible output | 1,412.659 ms from initial dispatch to a nonempty SSE text frame. |
| P90 complete turn | 23,300.579 ms from dispatch to the end of the complete stream. |
| P10 visible output delivery | 0.883 native visible tokens per complete-turn-second. The pinned tokenizer was independently called again on the joined text. |
| Transport, quality and performance | 12/12 complete at first attempt, 7/12 raw model outputs correct. Interactive performance failed the registered 500 ms, 2,500 ms and 5 tokens/turn-second contract. |
| Registered raw-model operation | 246.630 wall seconds including cache verification, startup, inference, two independent checks and shutdown. 709.122 CPU-seconds including child processes. 1,737 input and 245 completion tokens reported by the server. |
| Direct CLI delivery | A separate local observation started a fresh Python process per brief and reopened each output. P90 complete delivery was 48.719 ms, with 12/12 correct decisions. This clock measures cold CLI delivery. |
| Additional local checking | Median elapsed over thirty twelve-brief batches after one warmup was 0.158 ms for checking recorded model outputs, 0.131 ms for the new direct result with evidence and 0.044 ms for the original grammar. These are local computation and serialization measurements. Online guarded service latency was not observed. |

The previous shared model acquisition took 303.135 seconds of wall time. This run rechecked those cached bytes in 2.526 seconds, included in its operation total. Engineering, failure investigation, independent authorship, integration, electricity, complete hosting price, operator corrections, maintenance and support lack audited costs. Exact software/model identities and the bounded source snapshot are recorded in the observation. [Operation and content identities](intake_recorded/operation.json) · [Raw public wire receipt](intake_recorded/wire.json.gz) · [Observed local cost quantities](intake_recorded/route_costs.json)

The raw Qwen service verdict is **withhold**. A checked output can be used as an intake record within the tested controlled grammar. Production traffic, availability, resource costs, representative operator acceptance, the operating owner and the matching GPT-OSS 140/272 allocation remain unresolved. The next beneficiary test is blind intake against the operator's existing structured form, counting unsafe contracts, unnecessary deferrals, manual correction time and complete cost per accepted request. That test needs an approved beneficiary traffic sample. A new public measurement on an owned CPU with the pinned cache can run `field_trials/intake_observe.py --assets CACHE --work NEW_WORK --output NEW_OUTPUT`. Fresh timings have their own clock and identity.

## Résultat en français

Les douze réponses du modèle sont arrivées au complet. Sept respectaient la demande. Dans cinq cas, le modèle a accepté une exigence incompatible, par exemple un plafond de débit qu’il a transformé en minimum. La vérification du texte intégral a retrouvé les douze décisions attendues sur les cas rédigés pour l’essai. La grammaire seule a obtenu le même résultat.

Sur quatre demandes préparées indépendamment, la nouvelle grammaire s’est abstenue quatre fois. Elle a évité une acceptation dangereuse, mais a aussi écarté deux demandes valides. La latence P90 du modèle jusqu’au premier contenu visible a atteint 1,413 seconde. Le service demeure en attente de qualification pour un usage réel. Le fichier remis permet d’examiner les mots précis qui soutiennent chaque exigence acceptée.
