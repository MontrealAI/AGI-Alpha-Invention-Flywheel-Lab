# Frontier monitoring / Veille de la frontière

The local connector can periodically observe authorized public sources and reopen related questions in Ω GENESIS NEXT. It records exact source URL, retrieval time and SHA-256. A changed page is a reason to investigate, not proof of a new model capability or a removed bottleneck.

## Configure an observation

Authorize each public hostname through the connector's `source_hosts` configuration. Local-only mode refuses external observation. Sources must use HTTPS, the configured exact hostname and the standard port, with no credentials or URL fragment. The shared source transport rejects private addresses, redirects and oversized responses.

Register an exact URL, a descriptive title, related capability IDs and a polling interval. Confirm permission for that source and choose whether monitoring may resume after a connector restart. Registration records consent but starts paused. Use **Poll** for one observation or **Start** for periodic observation. **Stop** prevents further scheduled work and discards any late result that no longer has current authority. Removing a job removes its schedule.

Polling runs only while the local connector is running. This is not a hosted monitoring subscription or an operating-system background service. Without explicit restart consent, an enabled job pauses when the connector reopens. A prior interrupted request is recorded as interrupted, not silently called successful.

## Interpret the result

| Observation | Meaning |
|---|---|
| Initial observation | First successful source snapshot for this job. |
| Unchanged | The observed source bytes match the previous snapshot. |
| Changed | The source byte hash differs. Relevance and technical significance still require assessment. |
| Failed | Retrieval failed; prior successful evidence remains historical and unchanged. |
| Discarded | Permission, local-only mode or job state changed while a request was in flight. No new replay is accepted. |

A new observed hash invokes a reported-evidence replay against the job's related capability IDs. This may mark matching vault opportunities for reconsideration. It does not set them to unlocked, label the source independently reproduced, authorize an experiment or promote an upgrade. A repeated unchanged observation normally creates no new replay. The replay and monitor receipt are two authenticated stores: a crash between those writes can cause the same reported event to be delivered again. Delivery is at least once across that boundary, not exactly once; duplicates never promote evidence.

Recent status history is bounded and records how many older entries were omitted. Preserve important exported evidence separately. Retrieval time is not publication time. Hashes identify observed bytes; they do not certify author identity or factual truth.

## Expert API

Use an authenticated loopback connector session. Register with `POST /api/frontier-monitor/add`, supplying `url`, `title`, `capability_ids`, `interval_seconds`, `authorize: true` and optional `resume_after_restart`. Inspect `GET /api/frontier-monitor/status`. The `poll`, `start`, `stop` and `remove` POST routes accept a `job_id`; follow their explicit consent requirements. No endpoint performs model inference, payments or publication.

## Français

Le connecteur peut observer périodiquement des sources publiques autorisées et rouvrir les questions associées dans Ω GENESIS NEXT. Chaque observation garde l'URL exacte, l'heure de récupération et l'empreinte SHA-256. Un changement de page n'est pas une capacité reproduite ni la preuve qu'un obstacle a disparu.

Autorisez d'abord le nom d'hôte exact dans `source_hosts`, puis enregistrez l'URL HTTPS, son titre, les identifiants de capacités et l'intervalle. Le mode strictement local refuse cette transmission. L'enregistrement garde le consentement sans démarrer la veille. Demandez une observation ou démarrez la surveillance périodique. L'arrêt retire l'autorité des résultats tardifs; la suppression retire la tâche.

La veille fonctionne pendant l'exécution du connecteur. Elle ne constitue ni abonnement de surveillance hébergé ni service système. Sans consentement explicite de reprise, elle se remet en pause après redémarrage. Une interruption ou une récupération échouée demeure enregistrée comme telle.

Une nouvelle empreinte peut déclencher le réexamen d'une possibilité, mais aucune promotion ni expérience n'est automatiquement autorisée. Les vérifications indépendantes, les coûts et les résultats requis restent distincts. Un arrêt entre la sauvegarde du réexamen et celle du reçu peut produire un événement signalé en double; ce doublon ne promeut jamais une preuve. Les horodatages de récupération ne sont pas des dates de publication; les empreintes ne certifient pas la vérité du contenu.
