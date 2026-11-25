# Allocation under disagreeing forecasts

An included-Codex assisted mission constructed a portable read-only HARNESS instrument after an independently selected general ambition about sharing a rehearsal hall. The original ambition and French wording are recorded in the registration. Real forecasts, contractual minima and the group's preferences were unavailable. The allocation below uses published synthetic inputs. [Registration](REGISTRATION.json) · [Public example](EXAMPLE.json)

The instrument identifies an allocation with the smallest worst-case decline in total service relative to what could be achieved with perfect knowledge of each specified scenario. Minimax regret is a standard method for finite scenario sets. The instrument enumerates feasible bounded assignments, computes each scenario's best attainable service, and reports the distribution of loss against one deterministic scenario optimum. Its secondary ordering maximizes equal-weight total service, then chooses the lexicographically first allocation. The ordering makes outcomes reproducible. Community adoption requires agreement on floors, demand units and preferences for sharing the losses. [Minimax regret survey](https://doi.org/10.1016/j.ejor.2008.09.012) · [SQL artifact](allocation.sql)

## What the instrument delivered

The example assigns two slots to choir, two to dance and three to theatre. Its worst-case loss is two attendance-equivalent slots. A positive signed loss identifies a group that would receive more service under the identified scenario's best allocation. A negative value identifies a group that receives more under the robust choice. In addition, the tool reports each group's unmet demand under the chosen allocation.

| Scenario | Total loss | Choir | Dance | Theatre |
| --- | ---: | ---: | ---: | ---: |
| Choir demand | 2 | 2 | 0 | 0 |
| Mixed demand | 1 | −1 | 2 | 0 |
| Theatre demand | 2 | 0 | 0 | 2 |

A separate agent authored the ordinary direct included-Codex program from the registered problem and schema. A third agent independently supplied two acceptance fixtures before seeing the SQL. All **46/46** case outputs matched the direct program, including unchanged portable replay. On the independently authored complete fixture, the allocation was 1, 2, 2 across its three groups and worst-case loss was one. All three missing forecasts for an independently declared scenario were reported individually, and the tool withheld allocation. Additional controls checked infeasible minima, null and duplicate records, out-of-scope values, capacity boundaries, forecast order and loss conservation. All data and code were under shared administration. [Assessor](assess.py) · [Independently authored inputs](INDEPENDENT-INPUTS.json) · [Ordinary program](ordinary.py) · [Results](RESULT.json)

The first query used an implicit table record in `COUNT(*)` and the unchanged evaluator's read-only authorizer refused it. Explicit approved columns corrected that failure before the held inputs were opened. HARNESS constructed and executed the unchanged artifact in its separate SQLite worker and reproduced all 46 verdicts when run from the extracted, hash-pinned 1.2 package. The compact SQLite instrument's SHA-256 is `006666c263b61367c16bb2d479a25c8fc661552a95cdbe24c2a9692180c125f3`. [Operation](operate.py) · [Exact archive replay](ARCHIVE-REPLAY.json)

**GO** for bounded assisted construction and use on the supplied public fixtures. **NO-GO** for unattended execution, real hall scheduling or a measured operating advantage. Typical local time was about 39 ms per isolated HARNESS operation and 0.065 ms for the direct Python calculation in-process. The latter returned the same exact output. Authoring slices, runtime requests and hosted inference costs are recorded separately. These timings capture unequal process-isolation overhead. [Cost observations](RESULT.json)

## Reproduce

Use Python 3.11 or later with SQLite 3.37 or later. Execute from this directory in the source checkout. Every command writes to a new output location. Use `--harness` with the directory of a separately verified extracted executor to repeat against the distributed evaluator. The example remains a development fixture.

```sh
run=$(mktemp -d)
python -B operate.py EXAMPLE.json --output "$run/example"
python -B assess.py --output "$run/assessment.json"
```

Each successful result row contains the following fields, in order.

| Field | Meaning |
| --- | --- |
| Disposition | `OK`, `MISSING_FORECAST`, `INVALID_INPUT` or `INFEASIBLE_MINIMA` |
| Scenario ID, group ID | Declared source row identities |
| Assigned slots, demand, served, unmet | The robust assignment and its outcome under this scenario |
| Oracle slots, oracle served, signed loss | A scenario-optimal assignment and the group's opportunity loss relative to it |
| Scenario regret, worst-case regret, aggregate service | Total opportunity loss here, largest scenario loss and unweighted sum of service across scenarios |

## Game Theory follow-up

The exact owner ambition **Build frontier AI LLM for Game Theory.** motivated a fresh bilingual investigation of the learned formalizer's known timing failure. An independently authored panel supplied four new textual decision conditions. Included Codex produced a cited event-order, visibility and revision graph before opening the held reference. The existing graph closure and total-order enumeration produced the same proof for each case before a game was admitted. The assisted route matched all four independent whole-case dispositions. Direct included-Codex judgment also matched all four. The earlier narrow phrase checker matched one. [Fixed inputs](STRATEGIC-INPUTS.json) · [Registration](STRATEGIC-REGISTRATION.json) · [Executed results](STRATEGIC-RESULT.json)

The compatible case asks whether to buy a private reading with a locked state and a precommitted conditional policy. The old numerical envelope first declined its `60` and `−60` entries. The follow-up kept the same source numbers, divided every payoff and the fee by the exact common unit of six, then rescaled both certificate bounds. A separate exact reference computed the same **387/13 net minutes saved** for buying and **0** for skipping directly in the original units. It confirmed that the positive change of units preserved the decision. The other three graphs identified respectively a late reading, state revision after seeing the action paired with incompatible units, and missing structural and numerical information. The private solver was withheld for those cases. [Cited graphs](STRATEGIC-PROPOSALS.json) · [Adaptation and first refusal](STRATEGIC-ADAPTATION.json) · [Independent reference](STRATEGIC-REFERENCE.json)

**GO** for the scoped assisted graph replay and exact conversion. **NO-GO** for deploying a learned specialist or inferring strength above direct included Codex. This follow-up did not perform parameter updates and does not change the earlier Model Card's qualification. [Strategic assessor](strategic_assay.py) · [Earlier learned model card](../../outcome-driven/strategic/MODEL-CARD.md)

```sh
python -B strategic_assay.py --output "$run/strategic.json"
```

## Français

Un instrument HARNESS construit avec Codex répartit les créneaux et mesure la perte de fréquentation lorsque les prévisions divergent. L'exemple attribue deux créneaux à la chorale, deux au groupe de danse et trois au théâtre. La perte totale maximale est de deux créneaux équivalents. Les 46 cas concordent avec un programme Python rédigé séparément. Une prévision manquante suspend l'allocation et le résultat nomme le groupe et le scénario concernés. Les données sont synthétiques et le travail est assisté. Avant une utilisation réelle, les groupes doivent confirmer les prévisions, leurs engagements et la règle de partage. [Résultats](RESULT.json) · [Vérification à partir de l'archive publiée](ARCHIVE-REPLAY.json)

Dans quatre nouveaux cas stratégiques, les graphes produits avec Codex ont distingué le signal privé utilisable, le signal tardif, la révision adverse et les faits insuffisants. Les quatre diagnostics concordent avec l'analyse directe. Le calcul exact d'un cas compatible établit un gain net garanti de 387/13 minutes après une conversion d'unité exacte vérifiée séparément. Le déploiement d'un modèle spécialisé reste non qualifié. [Résultats stratégiques](STRATEGIC-RESULT.json)
