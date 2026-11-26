# Activate research in Opportunity Capture

The operator path retains the original report locally, identifies exact source versions and runs a reviewed investigation when a registered match exists. The first pilot exercised three investigations. The public Atlas and the existing publisher continue on their established routes.

## Run a local cycle

From the repository root, use Python 3.11 or newer. The routing run also uses the existing HARNESS SQLite evaluator. The Game Theory replay uses SciPy and the existing exact reference.

```sh
# Import the published Atlas history from its live release.
python3 scripts/frontier_opportunity_capture.py --research atlas

# Save a copied report as UTF-8 text or Markdown and import it as received.
python3 scripts/frontier_opportunity_capture.py --research import report.md

# Inspect available investigations and run a reviewed match.
python3 scripts/frontier_opportunity_capture.py --research status
python3 scripts/frontier_opportunity_capture.py --research cycle routing-ceiling
python3 scripts/frontier_opportunity_capture.py --research cycle evaluation-sampling
python3 scripts/frontier_opportunity_capture.py --research cycle game-event-order
```

For standard input, use `--research import -`. For several reports in one file, use a structured `.json` export with `schema` set to `frontier/research-updates-v1` and an `updates` array. Each row contains `stream`, `observed_at` and `text`. Use `manual` for an ad hoc source and an empty time when the original time is unknown. The stream names are those in `frontier_public_watch.py`. Programmatic retrieval of private reports requires a supported account connector. Exported report text is sufficient for this path.

State defaults to `~/.local/state/frontier-omega/research`. To choose a different directory, pass `--research --store /path/to/private-state` before the command. Use a local owner-controlled directory outside Git. POSIX permissions protect the store from other local users within trusted parent directories. Windows requires a user-private ACL. Report bodies and lineage receipts belong in local storage. Public reporting should use independently sourced facts and aggregate counts.

## What the cycle establishes

- Atlas ingestion reads the two fixed live Pages endpoints and checks the ledger bytes against the release manifest. Historical observation dates and publisher commits come from the Atlas. Copied report timestamps and stream labels are reported observations.
- The import retains the report text and extracts explicitly versioned arXiv URLs. Other material remains available in the stored report for review. Atlas input also accommodates the existing supported exact software releases. Repeated arrivals can retain their provenance without recreating the same source-version identity.
- A registered source match identifies an investigation and its known bottleneck. A run requires explicit operator selection, independent exact-version metadata retrieval and a fixed reviewed runner. The registry covers the three cases above. Other leads remain `DISCOVERED` or `WATCH` at intake. Packet content supplies evidence only.
- A repeat request for the same selected runner and registration returns the historical receipt and separately lists any later sightings. For a fresh run, use a new private state directory or run the standalone reproduction for that investigation. A nonzero runner result stays recorded with a nonzero command exit. Receipt hashes identify selected study files, with frozen-input verification performed by the runners on actual execution.

## Capture a reported scout run

Use an authorized latest-result lookup or saved handoff to collect the report and its run metadata. For a run-aware export, use `frontier/research-scout-capture-v1` with an `observations` array. Each observation contains `stream`, `scout_id`, `observed_at`, `last_run` and `latest_result`. Use `null` for an unavailable run or result. When present, a run carries `run_id`, `scheduled_for`, `started_at`, `completed_at` and `recorded_status`. A result can supply `run_id`, `scheduled_for`, `completed_at`, `content_text`, `content_truncated`, `is_failure_message` and `requires_user_action`. Keep the exact ISO 8601 times and the unmodified report text. Save the export in a private location.

```sh
python3 scripts/frontier_opportunity_capture.py --research capture observations.json
python3 scripts/frontier_opportunity_capture.py --research status
```

The capture returns a status and, where applicable, a suggested retry time. Retry through the authorized lookup and capture the new observation with its own observation time. Replaying the same observation preserves one execution history. Revised content is retained with its run and source links. A stale or unavailable body remains a capture disposition. The importer accepts caller-supplied metadata and the timestamps retain that provenance.

Use `--research revoke-scout SCOUT_ID` to persist a local stop for that exact scope. After the revocation is recorded, further capture and new study dispatch through that scope are refused. An already reserved operator run can finish. The local command has no account credentials or schedule. A standing service requires the separate operating authority in the [qualification ledger](../GATES.md).

## Observed pilot

The supported per-task lookup returned complete latest report bodies for five of the six enabled scouts. Action Alerts showed a completed run without a result body in that lookup. The publisher returned a publication receipt. The lookup exposed a latest run per scout. Total private history remains unknown. The pilot imported five reports, found 11 exact versioned references in them and combined them with 115 public source versions. Three overlapped, yielding 123 distinct versions and 126 sightings in the initial local cohort. These counts represent references, including comparators, as distinct from consequential findings.

The public inbox history contained 875 slots in 55 path snapshots, representing 116 distinct versions. The live Atlas at the start of the pilot retained 115 source versions within 122 records. Its opportunity projection contained 93 `WATCH` and 22 `DISCOVERED` observations plus seven separately reviewed cases. That projection did not identify a source-to-execution link. The pilot created three links with exact primary metadata checks, prior constraints, runner fingerprints and actual results. The routing lead came through the public Action Alerts projection. Sampling came from a substantive Radar report. The Game Theory lead was visible in both routes. [Public release baseline](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/atlas-release.json) · [Pinned inbox](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/0a9f9e0074194404eb98b02634d735fa4e4d0a4d/publication/frontier-watch-refs.json)

| Investigation | Decision and evidence |
| --- | --- |
| Routing quality | **PROVEN on four archived panels.** The perfect selector added zero accepted cases over the strongest fixed arm. A real HARNESS table run consumed 136 outcomes and matched an ordinary Python replay. Defer quality routing on these portfolios. Matched full-work costs remain unknown. [Registration](ROUTING-REGISTRATION.md) · [Results](ROUTING-RESULT.md) |
| Evaluation sampling | **FAIL at the registered advance thresholds.** On 18 published cases and 50 queries, the two tested metadata policies missed their performance-estimation and early-failure thresholds. Keep the stratified and complete controls. [Registration](sampling-registration.md) · [Result](sampling-results.json) |
| Decision-time game modeling | **PARTIAL.** Reviewed event-order inputs matched 768 exhaustive relations and nine published judgments. The exact control tied. Deliberately substituting physical delivery for effective access produced a false-known claim. Raw-language generalization and learned specialization remain open. [Registration](../game-theory/research-reactivation/REGISTRATION.md) · [Result](../game-theory/research-reactivation/RESULT.json) |

The work used published cohorts and a local operator-run process. The routing computation went through the existing HARNESS controller with an authored transport and zero model inference. The specialized and sampling computations ran as registered local experiments. Independent replay here shares administration with the constructors. Author-reported results on the three papers remain distinct from the local results. [Public pilot receipt](PILOT-RECEIPT.json) · [Current qualification and external gates](../GATES.md) · [Five opportunities](OPPORTUNITIES.md)

The subsequent Possible Now alert led to an actual CPU runtime and model-admission decision on two live documentation needs. [From alert to achievement](alert-achievement/REPORT.md)

## Mode d’emploi

À la racine du dépôt, avec Python 3.11 ou une version ultérieure, lancez les commandes suivantes.

```sh
python3 scripts/frontier_opportunity_capture.py --research atlas
python3 scripts/frontier_opportunity_capture.py --research status
python3 scripts/frontier_opportunity_capture.py --research cycle routing-ceiling
```

La première importe l’historique public et le vérifie à l’aide du manifeste de publication. La deuxième indique les études dont les sources sont présentes. La troisième lance l’étude d’aiguillage. Cette étude mesure le gain maximal possible à partir des réponses archivées. L’exploitation continue reste à qualifier.

Pour importer un rapport copié, utilisez `--research import rapport.md`. Avec cette version, vous pouvez aussi utiliser `--research capture observations.json` si vous disposez d’un export autorisé avec l’identité de la veille, les dates et le résultat de l’exécution. Les rapports, leurs révisions et les reçus restent dans le dossier privé local `~/.local/state/frontier-omega/research`, hors de Git. Ajoutez `--store /chemin/prive` entre `--research` et la sous-commande pour choisir un autre dossier. Un résultat absent ou périmé reçoit un statut de suivi. `--research revoke-scout SCOUT_ID` enregistre l’arrêt des nouvelles opérations dans la portée locale de cette veille.
