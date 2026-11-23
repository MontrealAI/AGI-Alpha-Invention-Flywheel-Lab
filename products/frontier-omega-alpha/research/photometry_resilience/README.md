# FRONTIER Ω ALPHA · Public ZTF broker resilience

## English

**Ordinary indexed fallback ties the constructed route. Keep the conventional method.** The second public broker recovered two independently checked g/r pairs when the primary response was withheld. The registered fresh cohort yielded no accepted pair. Archive-positive witnesses survived the tested fault, with no demonstrated productive cost advantage or S₁ admission.

[Prospective registration](registration.json) · [Signed confirmation receipt](evidence/confirmation.json) · [Retained failed attempt](evidence/failed-first-attempt.json)

### Consequential dependency

The [earlier #449 study](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/230409b54f4adf8f69bd8d029020bfde7acbcff0/products/frontier-omega-ignition/invention/next_week) spent 5.9898 seconds acquiring object history and about 0.0042 process seconds computing and checking the recorded evidence. The new mission asks whether a target has any independently supportable two-hour g/r positive-subtraction pair in a dated public window. Its explicit positive-witness decision is distinct from reconstructing the closest pair across a complete #449 snapshot. Research evidence comes from the public Fink and ALeRCE ZTF APIs. Both broker paths originate in ZTF, so this tests delivery dependence rather than independent survey measurements. [Fink API](https://doc.ztf.fink-broker.org/services/search/objectid/) · [ALeRCE schema](https://alerce.readthedocs.io/en/latest/models/detection.html) · [Survey schema](https://zwickytransientfacility.github.io/ztf-avro-alert/schema.html)

The constructor saw only the calibration summary for the six prior targets. The brokers agreed on 25 exact candidate IDs, bands and binary32 photometric values within the registered clock bound and produced no conflicting match. The constructor froze its source representation in a confined worker. The adjudicator then selected two distinct held-out series under the fixed dates, ranking and exclusion rule, acquired public records, and replayed the complete comparison without manual case selection. The earlier series admitted three of six requested targets after excluding development and first-confirmation objects.

| Confirmation series | Targets | Primary SQLite accepted | Ordinary ALeRCE fallback accepted | Candidate verified witness accepted |
| --- | ---: | ---: | ---: | ---: |
| Following week, November 17–23 UTC | 6 | 0 | 0 | 0 |
| Earlier nonoverlapping target series, November 1–8 UTC | 3 | 2 | 2 | 2 |

In the injected primary fragment, the primary-only arm had no complete pair. Both combined routes recovered the same two accepted cases. The public receipt retains one alternate proposed pair from the earlier series for which a matching exposure was unavailable in the held primary records, with a rejected-witness disposition. Its scientific output was withheld. The calibrated comparison uses evidence held by the evaluator. Continued independent validity of new, uncorroborated fallback rows during a future real outage remains unproven. The observed responses all returned HTTP 200. Missing source, conflict, malformed input, a false cutoff and both sides of the time-gap limit were exercised as controls.

Primary acquisitions used one batched, seven-column Fink query per series and took 4.09 s each. The six-call alternate query took 8.35 s in parallel. The three-call query took 4.14 s. The roster acquisition took 4.75 s and 4.00 s respectively and was available to all arms. The signed receipt records source status, timestamps, bytes, CPU, elapsed time and exact normalized per-exposure witnesses. The underlying API responses have source digests; future refetch may give a different response. The data projection and comparison reproduced offline. The CPU timings of the small unbatched scoring implementation are descriptive. Source availability, fee, loaded human effort, energy, maintenance and complete operating costs remain unmeasured. No telescope time, operational adoption or economic value was established. The prior negative result in #564, Endpoint abstention and indexed SQLite remain in force. S₂, constructor improvement and learning-rule improvement remain unproven.

### Reproduction

Run the signed receipt audit offline with standard Python, SQLite and OpenSSL. To run a fresh unattended acquisition, use the same exact registration and fetch the existing versioned #449 source first if it is unavailable in the local Git object store. The public runner keeps its configured authority and needs no paid credentials.

```sh
lab=products/frontier-omega-alpha/research/photometry_resilience
python3 -B "$lab/replay.py" audit "$lab/evidence/confirmation.json" \
  --key-sha256 066b78c0fd3f102c6dd07170ad5d912d4ae3e3ea349170e767f6b58215b7bf24
work=$(mktemp -d)
python3 -B "$lab/replay.py" run --state "$work/evaluator" --output "$work/public/receipt.json"
```

The `run` mode accepts a new private state for new acquisition and repeats an interrupted run with the same sealed inputs if its code is unchanged. The first run's Decimal boundary failure was corrected in a distinct source revision and new state. The exact acquisition failure record and old source revision are retained. Publishing this public scientific packet does not grant private case custody. [Standing evaluator authority](../autonomous_endpoint/CUSTODY.md)

## Français

**Le repli conventionnel par SQLite égale la méthode construite. SQLite indexé demeure le choix pratique.** Le courtier ALeRCE a permis de vérifier indépendamment deux paires g/r en retirant la réponse Fink de l’exécution. Le nouveau groupe de six cibles n’a fourni aucune paire acceptable. Dans le groupe historique de trois cibles admissibles, le repli SQLite et la nouvelle méthode ont tous deux accepté deux cas. Un troisième témoin n’a pas pu être corroboré. Les défauts de disponibilité ont été injectés dans les essais. Les réponses réelles des courtiers ont toutes porté le code HTTP 200.

La télémétrie précédente consacrait environ six secondes à l’acquisition et quatre millisecondes au calcul et à la vérification. Dans cet essai, chaque lot Fink a pris 4,09 s, contre 8,35 s et 4,14 s pour les lots ALeRCE. Il s’agit d’une mesure des appels sur ces échantillons. Les frais, la disponibilité soutenue, l’énergie, la révision, la maintenance et les coûts complets demeurent inconnus. Aucun gain productif ni admission de S₁ n’a été démontré. Les deux séries, les temps et les causes d’abstention sont vérifiables hors ligne. Le transfert vers S₂ et l’amélioration du constructeur ou de sa règle d’apprentissage restent à établir. [Reçu de confirmation signé](evidence/confirmation.json)
