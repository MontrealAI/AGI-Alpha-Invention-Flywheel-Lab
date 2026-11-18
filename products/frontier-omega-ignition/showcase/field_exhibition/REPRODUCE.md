# Reproduce the archive decision / Reproduire la décision d’archive

From the extracted directory, reopen the original Fink/ZTF survey data. The same nightly rule and first eligible later detection apply to each target and band. To check a selected decision, put the downloaded queue JSON next to `replay.py` and replace the example filename. Requests, exact acquisition times and response digests are in `invention/early_survey/sources/index.json`; the supplemental reference-image query is in `reference-index.json`.

Depuis le dossier décompressé, recalculez les décisions à partir des données publiques Fink/ZTF. Pour contrôler la décision d’une nuit, placez le JSON téléchargé à côté de `replay.py` et adaptez le nom du fichier dans la commande. Les archives incluent les requêtes datées, les empreintes des réponses et les identifiants de l’image de référence.

```sh
python3 -B replay.py
python3 -B replay.py --snapshot change-queue-early_warm-2026-10-26.json
python3 -B invention/early_survey/survey.py --as-of 2026-10-26T00:00:00Z --out first-notices.json
python3 -B invention/early_survey/survey.py --as-of 2026-10-29T00:00:00Z --csv follow-up.csv
python3 -B invention/evolution/alert.py --as-of 2026-11-13T00:00:00Z --out november.json
python3 -B evolution_trials/verify.py --as-of 2026-11-13T00:00:00Z --check november.json
python3 -B evolution_trials/early.py --as-of 2026-10-26T00:00:00Z --check first-notices.json
python3 -B invention/early_survey/exposures/verify.py --check
python3 -IB evolution_trials/broker_control.py --check
```

For a different target, copy `evolution_trials/broker_sources/alternate-notice.json` and supply its baseline and triggering detection IDs, filter and UTC window. The first command below prints the public archive queries offline. The guide in `evolution_trials/BROKER_REPLAY.md` shows how to check locally saved packets or request fresh public measurements using `--live`. The second command tests the separate equal-site comparison from pooled counts against exhaustive SQLite enumeration.

Pour une autre cible, copiez `evolution_trials/broker_sources/alternate-notice.json` et renseignez les identifiants des détections initiale et déclenchante, le filtre et la fenêtre UTC. La première commande affiche les requêtes sans connexion. Le guide `evolution_trials/BROKER_REPLAY.md` explique comment vérifier des paquets déjà téléchargés ou consulter les archives publiques avec `--live`. La seconde commande compare les bornes calculées à partir de totaux agrégés à une énumération exhaustive sous SQLite, en donnant le même poids à chaque site.

```sh
python3 -IB evolution_trials/broker_control.py --queries --notice evolution_trials/broker_sources/alternate-notice.json
python3 -IB discovery_field/decision_study/calibration_bounds.py --check
```

New output paths must be unused. Import the 19-digit detection IDs in CSV as text. The four October targets were selected by Fink's machine-generated “Early SN Ia candidate” tag. The original Fink record has a later coverage gap. Two public ZTF exposures recovered through ALeRCE independently meet the registered persistence rule. The downloadable case retains the Fink result and adds a source-labelled second-archive section when selected. Both brokers describe the same survey. Their prospective usefulness requires a new beneficiary study.

Choisissez des noms de sortie inutilisés. Dans un tableur, importez les identifiants de détection à 19 chiffres comme du texte. L’étiquette automatique « Early SN Ia candidate » a servi à sélectionner les quatre cibles d’octobre. Le dossier Fink initial présente une lacune de couverture. Deux poses ZTF retrouvées chez ALeRCE satisfont à la règle de persistance. Le cas téléchargé conserve le résultat de Fink et ajoute, lorsqu’elle est sélectionnée, la seconde source explicitement identifiée. Les deux courtiers exploitent le même relevé. Leur utilité pour un programme futur reste à mesurer.

## Supporting studies / Études associées

Use Python 3.12 on the extracted public files. The default command also replays the astronomy qualification, compares estimated target and Sun positions to the frozen Astropy ephemeris, checks the full schedule alternatives, independently recomputes the archive measurements in SQLite, checks the observed service-fixture receipts and audits the Earth-orientation queue against the original bulletin extracts.

Utilisez Python 3.12 sur les fichiers publics décompressés. La commande par défaut vérifie les coordonnées au moyen de l’éphéméride Astropy figée, les programmes à l’aide d’un solveur exact, la photométrie par SQLite, les résultats de l’essai d’inférence et la file de retraitement à partir des extraits de bulletins. Aucun accès réseau n’est requis pour cette reproduction.

```sh
python3 -B replay.py
python3 -B invention/next_week/replay.py
```

The second command rechecks the separate November 10–17 archive window, its two-hour and ten-minute deliveries, and the overlap with the earlier cohort. The frozen public alert and observation responses needed for this check are included in `invention/next_week/sources/`.

La seconde commande revérifie la fenêtre d’archives distincte du 10 au 17 novembre (borne de fin exclue), les résultats à deux heures et à dix minutes, ainsi que les cibles communes à la première cohorte. Les réponses publiques nécessaires figurent dans `invention/next_week/sources/`.

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
python3 -B field_lab/verify.py --workload field_lab/intake_workload.json --receipt field_lab/hosted_repeat/wire.json
python3 -B field_lab/field.py fixture --output my-service-fixture
```

The new bilingual intake compiler can be called with `python3 -B field_lab/intake.py` and a brief on standard input. The registered workload, row-level model scores and separate four-brief challenge are under `field_lab/`. Reproduce the new service run scoring from its wire records in a matching repository checkout with `python3 -B field_lab/intake_qualification.py --check`.

L’analyseur bilingue accepte une fiche sur l’entrée standard de `python3 -B field_lab/intake.py`. Les résultats par fiche et les quatre cas additionnels sont dans `field_lab/`. Dans la révision correspondante du dépôt, `python3 -B field_lab/intake_qualification.py --check` vérifie la nouvelle session à partir des flux enregistrés.

The local Qwen pilot's observed results are included in `field_trials/recorded/summary.json`. To recheck this separate model run from its compressed public service captures, run `python3 -B products/frontier-omega-ignition/field_trials/replay_cpu.py` from the matching repository revision. Both clients completed all six streams at each load and accepted five outputs per arm. Production access and all-in operating cost remain unresolved.

Les mesures de l’essai Qwen local figurent dans `field_trials/recorded/summary.json`. La commande `python3 -B products/frontier-omega-ignition/field_trials/replay_cpu.py` régénère ces résultats à partir des flux publics compressés dans la révision correspondante du dépôt. Chaque client a reçu six flux complets à chaque charge. Cinq réponses sur six ont satisfait le critère de qualité. L’accès en production et le coût d’exploitation complet restent à établir.

The catalog and holdout use public Fink/Zwicky Transient Facility data. URLs, acquisition periods and content identities appear in `invention/catalog.json` and `invention/sources/holdout-source.json`. `successor_field/SOURCES.json` identifies the IERS bulletins. `action_study/opportunities/sources.json` identifies the primary evidence for the current five choices. The earlier discovery study retains its own records under `discovery_field/decision_study/`. Each study’s registered scope and control appear alongside its code. `SHA256SUMS` records the bytes included in this recipient.

Le catalogue et les observations ultérieures proviennent des données publiques Fink/Zwicky Transient Facility. Les adresses, périodes d’acquisition et empreintes sont indiquées dans `invention/catalog.json` et `invention/sources/holdout-source.json`. `successor_field/SOURCES.json` identifie les bulletins de l’IERS. `action_study/opportunities/sources.json` identifie les sources primaires des cinq pistes actuelles. L’étude antérieure conserve ses propres sources dans `discovery_field/decision_study/`. Le périmètre et le témoin de chaque essai figurent à côté de son code. `SHA256SUMS` recense les empreintes du dossier.

## Evidence to action / De la preuve à la décision

Save the decision from the purpose selector as `decision.json` inside the extracted instrument. The receipt records its mission, sources, cutoff, evidence, action and fingerprints. Verify it, generate a new engineering mission, change its repository budget, then compute a fresh result. Each command runs offline with the Python standard library. The source-scoped verifier rejects an altered receipt. The remaining commands reconstruct both reference-stream controls, compare issue-time decisions with SQLite, repeat the engineering census and check the shadow rehearsal.

Dans le dossier décompressé, enregistrez sous `decision.json` la décision choisie dans le sélecteur d’objectif. Le reçu conserve la mission, les sources, l’échéance, les observations, la décision et leurs empreintes. Vérifiez-le, générez une mission d’évaluation technique, modifiez son nombre maximal de dépôts et calculez un nouveau résultat. Ces commandes s’exécutent hors ligne avec la bibliothèque standard de Python. Les dernières commandes reconstruisent les deux contrôles de référence ZTF, comparent les décisions à l’émission avec SQLite, répètent le recensement des dépôts et vérifient la répétition du suivi.

```sh
python3 -IB action_study/desk.py verify decision.json
python3 -IB action_study/desk.py example engineering-qualification > mission.json
python3 -IB action_study/desk.py decide mission.json > fresh.json
python3 -IB action_study/desk.py verify fresh.json --mission mission.json
python3 -IB action_cases.py
python3 -IB action_study/observing/desk.py --check
python3 -IB action_study/qualification_choice/verify.py
python3 -IB action_study/shadow/shadow.py check
```

The public five-minute guide is in `PRESENT.md`. A publication timestamp, an observer’s receipt and an actual telescope instruction are distinct records. Use the human-review registration before any participant study. The downloaded instrument evaluates public evidence offline.

Le guide public de cinq minutes figure dans `PRESENT.md`. L’heure d’émission, la réception par une équipe et la commande d’un télescope constituent des traces distinctes. Le protocole d’évaluation humaine précède toute étude avec des participants. L’instrument téléchargé examine les sources publiques hors ligne.
