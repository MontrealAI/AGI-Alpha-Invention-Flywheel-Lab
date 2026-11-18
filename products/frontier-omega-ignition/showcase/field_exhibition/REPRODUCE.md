# Observing-night recipient · Dossier d’observation

Use Python 3.12 on the extracted public files. The default command replays the astronomy qualification, compares estimated target and Sun positions to the frozen Astropy ephemeris, checks the full schedule alternatives, independently recomputes the archive measurements in SQLite, checks the observed service-fixture receipts and audits the Earth-orientation queue against the original bulletin extracts.

Utilisez Python 3.12 sur les fichiers publics décompressés. La commande par défaut vérifie les coordonnées au moyen de l’éphéméride Astropy figée, les programmes à l’aide d’un solveur exact, la photométrie par SQLite, les résultats de l’essai d’inférence et la file de retraitement à partir des extraits de bulletins. Aucun accès réseau n’est requis pour cette reproduction.

```sh
python3 -B replay.py
```

To check the case you selected in the Forge, place the downloaded JSON beside `replay.py` and substitute its filename below. To construct the registered primary worklist or regenerate the scientific CSV, use fresh output paths. The CSV contains 19-digit observation identifiers. Import these columns as text in spreadsheet software.

Pour vérifier le cas choisi dans la Forge, placez le JSON téléchargé à côté de `replay.py` et utilisez son nom ci-dessous. Pour construire le programme principal ou régénérer le CSV scientifique, utilisez de nouveaux chemins de sortie. Dans un tableur, importez les identifiants d’observation à 19 chiffres comme du texte.

```sh
python3 -B replay.py --case b6-v2.json
python3 -B invention/plan.py --out my-worklist
python3 -B invention/verify.py my-worklist/worklist.json
python3 -B invention/photometry.py --max-gap-minutes 10 --out my-photometry.csv
python3 -B successor_field/triage.py --route direct --output my-queue.csv
python3 -B successor_field/audit.py my-queue.csv
```

Use `--mission` with a copy of `invention/mission.json` to change budget or cadence. A new site, sky position or time window depends on a new independent ephemeris. `invention/reference.py` regenerates it using the Astropy version identified in the catalog. A fresh HTTP loopback fixture experiment needs Python and curl. Its captured timings depend on the host.

L’option `--mission` accepte une copie de `invention/mission.json` avec un budget ou une cadence modifiés. Un changement de site, de position ou de fenêtre dépend d’une nouvelle éphéméride indépendante. `invention/reference.py` permet de la calculer avec la version d’Astropy indiquée dans le catalogue. Un nouvel essai HTTP en boucle locale nécessite Python et curl. Les temps mesurés dépendent de la machine.

```sh
python3 -B field_lab/verify.py --public field_lab/PUBLIC.json
python3 -B field_lab/field.py fixture --output my-service-fixture
```

The local Qwen pilot's observed results are included in `field_trials/recorded/summary.json`. To recheck this separate model run from its compressed public service captures, run `python3 -B products/frontier-omega-ignition/field_trials/replay_cpu.py` from the matching repository revision. Both clients completed all six streams at each load and accepted five outputs per arm. Production access and all-in operating cost remain unresolved.

Les mesures de l’essai Qwen local figurent dans `field_trials/recorded/summary.json`. La commande `python3 -B products/frontier-omega-ignition/field_trials/replay_cpu.py` régénère ces résultats à partir des flux publics compressés dans la révision correspondante du dépôt. Chaque client a reçu six flux complets à chaque charge. Cinq réponses sur six ont satisfait le critère de qualité. L’accès en production et le coût d’exploitation complet restent à établir.

The catalog and holdout use public Fink/Zwicky Transient Facility data. URLs, acquisition periods and content identities appear in `invention/catalog.json` and `invention/sources/holdout-source.json`. `successor_field/SOURCES.json` identifies the IERS bulletins. `discovery_field/catalog.json` attributes the five research possibilities. Each study’s registered scope and control appear alongside its code. `SHA256SUMS` records the bytes included in this recipient.

Le catalogue et les observations ultérieures proviennent des données publiques Fink/Zwicky Transient Facility. Les adresses, périodes d’acquisition et empreintes sont indiquées dans `invention/catalog.json` et `invention/sources/holdout-source.json`. `successor_field/SOURCES.json` identifie les bulletins de l’IERS. `discovery_field/catalog.json` attribue les cinq pistes de recherche. Le périmètre et le témoin de chaque essai figurent à côté de son code. `SHA256SUMS` recense les empreintes du dossier.
