# Evidence-bound mission claims / Affirmations liées aux preuves

## Historical mixture replay

The prior runtime recorded a concentration of `138461.54 mg/L` in generated prose, followed by a SQLite sum of `2` over a model-generated example. The replay submits the two original proposals to the mission service and runs the same fixture query. The output matches the prior SQLite receipt byte for byte. No bound concentration, mass, or volume is displayed in either step.

The third step runs an explicitly authored SQLite correction using the original approved rows. A separate Python `Fraction` calculation normalizes units and reconciles solute mass. All three values agree exactly.

| Quantity | Executed and verified value |
| --- | --- |
| Final concentration | `16600/13 mg/L` |
| Total solute mass | `3320 mg` |
| Total volume | `13/5 L` |

The mission enters `needs_review`. Its overall qualification stays `UNVERIFIED`. The replay uses recorded proposals and an authored third step. It makes no live model requests. Independent evaluator custody and production admission require separate evidence.

- [Captured proposals, input rows and original digests](./HISTORICAL-M06.json)
- [Execution receipt and exact source hashes](./REPLAY-RECEIPT.json)
- [Published historical production follow-up](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/e39f5b7cf965c5838ba1e1a6c85c59c73bb34e0a/publication/mission-executor/production/HELD-MIXTURE-FOLLOWUP.json)

## Runtime contract

An operator registers the dataset digest, admissible origin, version, scope facts and required fields. Each claim specifies an operation, a result location, units and dimension. A candidate can run a bounded SQLite query or the arithmetic instrument with a registered dataset. A failed precondition keeps the numerical value out of the claim report. The durable receipt ties the executed operation and output to the mission revision, frozen input and artifact digests. Reloading the saved mission checks those identities again.

| Status | Meaning |
| --- | --- |
| `UNVERIFIED` | The mission has no evidence contract or its claim dispositions are mixed and incomplete. |
| `ABSTAIN` | The claim lacks approved data, a required field or a qualifying execution. |
| `REJECTED` | The proposed binding, result, comparison or recorded provenance is invalid. |
| `SOURCE_BOUND` | The value comes from the authorized execution and awaits an independent reference. |
| `VERIFIED` | The source-bound numerical value agrees with a frozen reference within its declared tolerance. |

The constructor receives the authorized input and claim contract. The frozen reference stays outside its prompts and tool feedback. Generated prose is displayed as a proposal. The contract covers finite numerical scalars. An authorized external-source label records operator attestation, and a derived-data receipt checks parent identities and digests. Scientific validation of a source or external transformation still requires an appropriate independent assessment.

From the repository root, run the replay and focused control suite.

```sh
python publication/evidence-bound/claim-binding/replay.py
python -m unittest discover -s products/alpha-genesis-harness/tests -p test_mission_evidence.py
```

## Rejeu du calcul de mélange

Le rejeu exécute les deux propositions d’origine. Le texte généré annonçait `138461.54 mg/L`. Le calcul SQLite exécuté ensuite renvoyait `2` à partir d’un exemple généré par le modèle. Le moteur s’abstient de présenter ces nombres comme les résultats du mélange.

Une troisième étape, rédigée pour la correction, exécute un calcul SQLite sur les données autorisées d’origine. Un calcul séparé en fractions exactes confirme la concentration de `16600/13 mg/L`, la masse totale de `3320 mg` et le volume total de `13/5 L`. La mission attend une révision. Sa qualification globale demeure `UNVERIFIED`. Le rejeu n’appelle aucun modèle en direct.

Le contrat rattache chaque valeur publiée à la version de la mission, à la provenance des données, à l’opération exécutée et à l’emplacement du résultat. Le moteur vérifie ces éléments lors d’une reprise. Une valeur liée à sa source obtient le statut `VERIFIED` lorsqu’elle concorde avec la référence numérique préétablie. Les validations scientifique et opérationnelle demeurent distinctes.
