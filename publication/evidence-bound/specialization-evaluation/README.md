# Independent qualification of the antimeridian specialist

**GO for the tested historical catalog audit.** The frozen deterministic specialist matched **40/40** independently registered cases, with zero false inclusions. It verified the seam at physical ±180°, reconciled latest revisions, and quarantined conflicts before admitting an event. The independent exact Fraction implementation also scored 40/40. The ordinary SQLite comparison using binary `REAL` scored 38/40 and included five incorrect IDs. [Independent results](RESULT.json)

| Method | Exact case decisions | False included IDs | Median elapsed | Median child CPU |
| --- | ---: | ---: | ---: | ---: |
| Candidate, cold CLI | 40/40 | 0 | 35.92 ms | 27.64 ms |
| Independent Fraction audit, cold CLI | 40/40 | 0 | 32.51 ms | 27.97 ms |
| SQLite `REAL` and latest-revision window, in-process | 38/40 | 5 | 0.489 ms | Unmeasured |

The panel included six geographic boundary tests, one revision quarantine, one high-precision control, 24 previously unseen seeded cases, four invariance checks, and four filters over eight archived USGS observations. The source window was Alaska’s Aleutian Islands from June 20 through June 26, 2014, separate from the constructor’s July 2025 Fiji development data. All three methods agreed on the genuine observations: eight events in the complete window, five at magnitude 6 or higher, and none in the western lobe or before the exact first-event cutoff. Binary floating point rounded near-boundary coordinates and magnitude into eligibility and collapsed one conflicting revision. [Registered controls](REGISTRATION.json) · [USGS capture](USGS.geojson) · [USGS API](https://earthquake.usgs.gov/fdsnws/event/1/)

The evaluator independently selected the historical audit and authored the confirmation cases and exact oracle. The evaluator froze their hashes before receiving the candidate identity. The constructor received only the interface and evaluation registration hash before its candidate froze. The comparison ran two cold executable invocations per panel per exact method on one Linux host. SQLite timing used an in-process ordinary alternative and cannot be compared directly to CLI timing. Python and SQLite versions, timing distributions, and raw decisions are in the receipt. The evidence establishes a reusable deterministic supplied-record capability with a tied exact comparator. Production admission, external evaluator custody, new forecasting or warnings, and economic superiority remain outside the tested scope. The candidate required zero model inference and zero training.

## Reproduce

The input freezes to [CASES.jsonl](CASES.jsonl), with [ORACLE.json](ORACLE.json) and the disclosed [random seed](SEED.json). The harness checks the candidate SHA-256 `a02bc2e1065c67a492a9d9cb3ee4ee79035ebe51796671c9d72dc54ec01bf6b9` and registration SHA-256 `98700874dc394b0fcb8557d56ac28b220c4efe5697c7b8c2c11698e4cb00e213` before execution. This replay needs the in-repository data and Python 3.11 or newer on Linux.

```sh
python -B publication/evidence-bound/specialization-evaluation/grade.py \
  --candidate publication/evidence-bound/specialization/specialist.py \
  --out /tmp/frontier-seam-independent.json
```

## Français

**GO pour la vérification historique dans le périmètre testé.** Le moteur géospatial a réussi **40 cas indépendants sur 40**, sans admettre d’événement à tort. Il a reconnu les deux représentations du méridien ±180°, appliqué les révisions les plus récentes et isolé les révisions contradictoires. Le calcul exact en fractions a lui aussi réussi les 40 cas. Le comparateur SQLite en virgule flottante a réussi 38 cas et admis cinq identifiants à tort. Les trois méthodes concordent pour les quatre extractions relatives aux huit événements réels du catalogue USGS.

La comparaison valide les décisions pour des données fournies et un contrat précis. Les deux auteurs ont travaillé séparément dans le même environnement administratif. Aucun appel de modèle ni entraînement n’a été nécessaire. L’étude ne qualifie ni la prévision sismique ni le déploiement du moteur. [Résultats](RESULT.json)
