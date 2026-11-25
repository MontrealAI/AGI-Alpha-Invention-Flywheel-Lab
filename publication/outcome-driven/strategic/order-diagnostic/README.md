# Proving the timing of a strategic observation

The learned strategic formalizer marked all 16 prose briefs as private and pre-action. This diagnostic tests whether checked records of event order, access and revision rights can distinguish strategic situations. It uses fresh synthetic structured inputs. [Learned formalizer results](../README.md)

## What the witness establishes

Each input declares the actors, the actor responsible for each event, and which events play five roles: announcing the purchase, committing the policy, fixing the state, receiving the signal and binding the action. Events may have arbitrary names. The witness uses strict precedence pairs and checkpoint access claims. An access entry has the form `[outcome_event, actor, checkpoint_event, boolean]`. A positive entry establishes access to that event's outcome by the checkpoint. A negative entry denies access through that checkpoint. Unstated access stays unknown unless it follows from the event order or another access claim. The revision roster declares whether its coverage is complete.

The checker derives precedence from both explicit order and access claims. Access can begin only after the outcome exists, and established access persists within the model. The checker rejects contradictory constraints and derives facts from every admissible event order. A private verdict requires the opponent to have the purchase and policy at fixation, fixation before the signal, the signal before the binding action, and access for the payer alone among declared actors by binding. The complete revision roster must place all possible revisions before fixation. An explicit opportunity to respond after seeing the signal or binding action proves adaptation. An action before the signal proves lateness. The receipt preserves both facts when both apply.

## Executed diagnostic

The checker and separate reference agreed on **all 136 complete proof records**. All 16 named controls produced their expected verdicts. The other 120 inputs cross six order patterns, five visibility patterns and four revision patterns. The reference enumerates every total ordering with up to seven events and checks every feasible first-access interval against the supplied facts. It uses a separate algorithm within the same research workstream.

| Verdict | Cases |
| --- | ---: |
| Private | 9 |
| Late | 13 |
| Adaptive | 23 |
| Unknown | 49 |
| Contradictory | 42 |

The checker had zero spurious and zero missed private findings against the reference. The unordered-binding control kept the payer's access and both order directions unresolved. The late-and-adaptive control retained both the delay and the named opportunity to react to the binding action. [Fixed plan](PRE-REGISTRATION.json) · [Execution receipt](RESULT.json)

This result establishes the checker on structured evidence in the tested scope. Extracting truthful event and access claims from prose, verifying their provenance and evaluating product admission remain separate tasks. Production qualification of the learned formalizer remains NO-GO.

## Reproduce

Run from this directory with Python 3.10 or later. The assay and checker use the standard library. Use a new receipt path for each replay.

```sh
python -B assay.py --output /path/to/new-receipt.json
python -B assay.py --example transitive-private > /path/to/witness.json
python -B witness.py /path/to/witness.json
```

The input and proof hashes should match the recorded run. The receipt also records local elapsed times, which vary by run.

## Français

Le vérificateur utilise des événements ordonnés partiellement, des déclarations d'accès à l'information et une liste des possibilités de révision. Il distingue un signal privé reçu avant l'action, un signal tardif, une adaptation adverse, des faits insuffisants et des contraintes contradictoires. Les 136 preuves concordent avec la référence qui énumère les ordres possibles. L'extraction fiable de ces faits à partir de texte libre reste à établir. [Résultat](RESULT.json)
