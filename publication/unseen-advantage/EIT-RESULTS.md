# What missing electrodes make unobservable / Ce que rendent inobservable les électrodes absentes

**ABSTAIN for physical or operational recovery.** MONTREAL.AI's interior-property research needs a genuinely informative measurement. On the 21 measured public Kuopio phantoms, the limited and full versions agree on all 26,217 retained voltages. The conventional reciprocal SVD found zero of the 23,259 omitted readings identifiable from the allowed measurements. The coordinate method supplied exact ambiguity witnesses for all 23,259. Keep the full direct source data where eligible. [Registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/7529e43338381b50d4ef5e852071756461d251c1/publication/unseen-advantage/EIT-REGISTRATION.md) · [Corrected receipt](evidence/eit-corrected.json)

| Level | phantoms | retained readings per phantom | omitted per phantom | SVD ranks | omissions with checked witnesses per phantom |
|---|---:|---:|---:|---:|---:|
| 1 | 3 | 2,356 | 0 | 360 | 0 |
| 2 | 3 | 1,624 | 732 | 315 | 732 |
| 3 | 3 | 1,404 | 952 | 273 | 952 |
| 4 | 3 | 1,200 | 1,156 | 234 | 1,156 |
| 5 | 3 | 1,012 | 1,344 | 198 | 1,344 |
| 6 | 3 | 630 | 1,726 | 165 | 1,726 |
| 7 | 3 | 513 | 1,843 | 135 | 1,843 |

Each certificate selects one symmetric transfer-operator entry invisible to every retained drive/read functional and visible to the omitted one. Let `E` be that symmetric coordinate matrix and `P` the orthogonal projection onto zero-sum electrode potentials. The two operators `P` and `P + PEP/2` are positive on that subspace and give the same retained linear functionals with different omitted values. The same perturbation argument applies around a strictly positive operator consistent with the retained data if one exists. The exact checker contracts drives and senses directly. These are structural ambiguity witnesses in the reciprocal linear response model. An actual material phantom is subject to additional geometry and measurement constraints and its conductivity inference is a separate question.

## Cost and scope

- Limited archive 426,229 bytes in 5.749 seconds and full archive 599,040 bytes in 5.773 seconds, acquired concurrently. All 49,476 direct source readings are available in the full archive. [Acquisition](evidence/eit-acquisition.json)
- On one Linux x86-64, single-BLAS-thread run, the shared coefficient construction took 73.44 ms for all cases. The usual reciprocal SVD took 1,961.96 ms. The proposed coordinate checks took 23.60 ms plus 380.89 ms for certificate verification. Total corrected process elapsed time was 2.888 seconds including startup and tests. These measurements do not price calibration, acquiring any new physical readings, operator time, repeatability or maintenance. The direct archive gives the real readings where eligible, and the methods restricted to reduced measurements recover zero. [Process timing](evidence/eit-time-corrected.txt)
- The frozen initial code rejected 18 source records because it expected zero at omitted positions. The publisher specifies NaN. The correction changes only omission parsing. Its replay covers all 21 cases and six controls. [Correction](EIT-DECODING-CORRECTION.md) · [Initial receipt](evidence/eit-original-decoding.json) · [Clean repeat](evidence/clean-repeat.json)

## Reproduce

Use Linux with Python 3.12 and the pinned NumPy and SciPy versions in `REQUIREMENTS.txt`. The runner validates the two archive sizes and publisher checksums, records SHA-256, and reads only the required phantom arrays. Its independently reproduced numeric outputs are retained without the raw archives.

```sh
git switch --detach 5eb5cac2cc4a96becf89f0eb775d8fc893e5016c
mkdir -p /tmp/frontier-eit-inputs
base=https://zenodo.org/records/10986692/files
curl -fLsS --max-time 30 "$base/EvaluationData.zip" -o /tmp/frontier-eit-inputs/EvaluationData.zip
curl -fLsS --max-time 30 "$base/EvaluationData_full.zip" -o /tmp/frontier-eit-inputs/EvaluationData_full.zip
OPENBLAS_NUM_THREADS=1 python publication/unseen-advantage/eit_boundary_probe.py --data-dir /tmp/frontier-eit-inputs
```

Data credit Mikko Räsänen, Petri Kuusela, Jyrki Jauhiainen, Muhammad Arif, Kenneth Scheel, Tuomo Savolainen and Aku Seppänen, University of Eastern Finland, [Kuopio Tomography Challenge 2023 dataset v3](https://doi.org/10.5281/zenodo.10986692), CC BY 4.0. Inferred imaging outputs have a separate specialist comparator, including the [official challenge winner](https://fips.fi/data-challenges/kuopio-tomography-challenge-2023/).

## Résultats en français

**ABSTAIN.** Les 21 fantômes physiques fournissent 26 217 tensions conservées identiques dans les deux versions du jeu de données. Aucune des 23 259 tensions omises n'est identifiable par la SVD réciproque conventionnelle. Un contrôle algébrique distinct a vérifié 23 259 témoins d'ambiguïté dans le modèle linéaire. Les données complètes du producteur restent la référence lorsqu'elles sont disponibles.

La première exécution a rejeté 18 dossiers parce que le décodeur attendait des zéros. L'éditeur emploie des NaN. Le protocole, les cas et les critères sont identiques dans l'exécution corrigée. Le calcul SVD a pris 1 961,96 ms. Les témoins et leur contrôle ont pris 404,49 ms, hors étapes communes. Ni le temps ni le coût d'une nouvelle mesure physique, l'acceptation en service ou le bénéfice économique n'ont été établis. Une autre observation doit fournir une information que les canaux conservés ne portent pas.
