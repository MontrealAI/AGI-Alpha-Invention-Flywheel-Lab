# The first follow-up decision for an early supernova candidate

On the archived October 25–November 1 observing week, the four candidates selected by Fink's early-supernova classifier supplied nine public survey detections. Retaining 28 eligible measurements from the preceding seven days changed the October 26 review queue. The same issue rule produced two notices on ZTF26acbezdh. Starting with an empty history produced none. Both routes had the same four targets, nine in-week measurements and permission to use the archive. The cold/warm choice governs the baseline only. [Registration](REGISTRATION.md) · [Whole source-bound decision](RESULT.json) · [Action queue](worklist.csv)

| Band | Starting detection (UTC) | First qualifying detection (UTC) | Difference-magnitude change | Change per day | Fink's reported rate at that detection | ZTF reference ID shared by the pair |
| --- | --- | --- | ---: | ---: | ---: | --- |
| g | Oct 20 09:24:53.000 | Oct 25 08:33:14.999 | −0.836744 ± 0.056113 mag | −0.168558 mag/day | −0.162397 mag/day | 505120158 |
| r | Oct 21 06:27:08.000 | Oct 25 09:11:13.004 | −0.557955 ± 0.052787 mag | −0.135625 mag/day | −0.132321 mag/day | 505120258 |

A negative magnitude change means the positive difference signal brightened. The quoted uncertainties combine catalog PSF-fit errors in quadrature. Shared reference images, calibration and systematic errors can correlate the measurements. The catalog reference identifiers were independently fetched and joined to each detection by its original 64-bit candidate ID. The reported broker rate is an incumbent measurement with its own algorithm. Fink has published rates since December 2023. [ZTF alert schema](https://zwickytransientfacility.github.io/ztf-avro-alert/schema.html) · [Fink rate definitions](https://doc.ztf.fink-broker.org/broker/science_modules/)

The review was due by October 29 at 00:00 UTC. The frozen Fink response has no qualifying same-band observation of this target before that deadline. That gap is preserved in its decision. A separately registered recovery experiment asks which other publicly accessible records can answer the same question. The comparison uses exposure times. Broker arrival and publication times at the historical desk were not observed. [Recovered October 28 witnesses and independent reductions](exposures/README.md) · [Recovery registration](exposures/REGISTRATION.md)

## Reproduce or change the mission

From `products/frontier-omega-ignition`, use Python 3.12 and a new destination for a dated delivery.

```sh
python3 -B invention/early_survey/survey.py --check
python3 -B evolution_trials/early.py --check invention/early_survey/RESULT.json
python3 -B invention/early_survey/survey.py --as-of 2026-10-26T00:00:00Z --out /tmp/october-26-queue.json
python3 -B invention/early_survey/survey.py --as-of 2026-10-29T00:00:00Z --csv /tmp/october-29-queue.csv
```

The first program checks each result against the separately written SQLite implementation. The second also reconstructs the broker values and the reference-image joins independently from the original responses. Both read the recorded data without network access. For a new public observation of the mutable archive, run `python3 -B invention/early_survey/acquire.py /path/to/a/new-directory`. New results have their own timestamps and hashes. [Acquisition receipts](sources/index.json) · [Reference lookup](sources/reference-index.json) · [Conventional comparison, costs and controls](../../evolution_trials/README.md)

The issuer is the Fink broker using survey data from the Zwicky Transient Facility. ZTF and its partners acquired the exposures. The Fink class selects proposals for research, with independent confirmation needed for a physical classification. Scope is ZTF public-program detections and attributed, reproducible research calculations. A new observing allocation, product adoption, willingness to pay and a commercial data licence each require separate evidence. [Fink class search](https://doc.ztf.fink-broker.org/services/search/classsearch/) · [ZTF data access and public releases](https://www.ztf.caltech.edu/ztf-public-releases.html)

## En français

Le 26 octobre à 00 h UTC, les mesures des sept jours précédents permettaient de signaler un changement dans deux bandes pour ZTF26acbezdh. Avec les seules données de la semaine en cours, aucune mesure ne franchissait les trois seuils. Le signal différentiel s’était éclairci de 0,836744 mag en g et de 0,557955 mag en r. Dans chaque bande, les deux mesures se rapportent à la même image de référence. Le fichier Fink ne contenait aucune mesure de suivi admissible avant le 29 octobre. La recherche dans un second fonds public conserve cette première décision et fait l’objet d’une vérification distincte.
