# FRONTIER Ω ALPHA · Autonomous Endpoint Field Lab

## English

**ABSTAIN FOR OPERATIONAL ADOPTION.** Indexed SQLite remains the default for this archive decision. The recorded Qwen CPU pilot had no qualifying load. The separate FA01 loopback fixture met its registered requirements at load 3 for both clients. Both clients abstained on the adverse fixture.

[Confirmation receipt](evidence/confirmation.json) · [Detached evidence capsule](evidence/capsule.json) · [Earlier development run](evidence/development-recovery.json) · [Frozen protocol and requirement provenance](registration.json)

### Evidence accepted on 23 November 2026

| Archive comparison | Oracle agreement | Total time for 64 warm queries | P90 warm query | Materialized size |
| --- | ---: | ---: | ---: | ---: |
| Indexed SQLite | 64/64 | 1.75 ms | 52.34 µs | 77,824 bytes (database) |
| Fixed #554 instrument | 64/64 | 31.17 ms | 627.42 µs | 34,651 bytes (serialized projection) |
| Detached capsule | 64/64 | 0.62 ms | 13.74 µs | 9,018 bytes (capsule) |

The adjudicator found 31 decisions with a measured load and 33 abstentions. The new means is a signed, exact-scope projection of the dated evidence. It answers after the original feed and normalized archive are removed from the serving path. The SQL incumbent can also pre-acquire and operate offline. Dominance eliminated none of the 37 development points. The constructor selected projection, and the adjudicator independently checked all 82 retained confirmation points across eight exact configurations. Ties preserve every witness. A different system, submission, workload, publication cutoff or unauthenticated revision requires revalidation.

For this campaign, the measured wall time for capsule materialization, coverage verification, reopen and 64 queries was **122.01 ms** versus **3.01 ms** for SQL materialization, opening and 64 queries. The capsule constructor added 94.24 ms separately. Both arms used the same authenticated public source. Its local acquisition and admission took 4.76 ms after one injected failed read. The receipt includes separate CPU and wall costs, stored bytes, failed acquisition, verification, retry and pilot resource use. Warm-query timings came from this small campaign on one CPU host. Upstream fees, energy, total engineering, loaded reviewer labor, sustained availability, support and maintenance remain unmeasured. No economic advantage or S₁ admission was established. S₂ transfer, constructor improvement and learning-rule improvement remain unproven. The frozen #554 learning and conventional-baseline findings remain part of the record.

| FA01 workload | Field HTTP client | Conventional curl client | Adjudicated limit |
| --- | --- | --- | --- |
| Nominal loopback, load 3 | 6/6 accepted, P90 first visible 14.84 ms, P90 turn 17.30 ms, P10 1,211.47 fixture tokens/s | 6/6, 47.78 ms, 49.16 ms, 551.17 fixture tokens/s | 3, highest tested |
| Adverse loopback, loads 1 and 3 | 2/6 accepted, seven attempts at each load | 2/6, seven attempts at each load | ABSTAIN |
| Archived Qwen CPU inference, loads 1 and 3 | 5/6 accepted at each load, P90 first visible 4.459 s and 10.048 s | 5/6 at each load, 3.736 s and 11.760 s | ABSTAIN |

The archived model arm independently replays the retained wire, using its recorded native tokenizer results. The original run measured 547.47 wall seconds, 3,251.15 CPU seconds and 303.14 seconds for resource acquisition. No fresh inference or live retokenization took place. FA01 was a six-task public engineering pilot with its own exact criteria and hardware scope. See the [FA01 registration at #449](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/230409b54f4adf8f69bd8d029020bfde7acbcff0/products/frontier-omega-ignition/field_lab/REGISTRATION.md) and [archived model captures](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/230409b54f4adf8f69bd8d029020bfde7acbcff0/products/frontier-omega-ignition/field_trials/recorded).

### Custody and unattended execution

Acceptance, source, resource limits and evaluator code identity are fixed before the confined constructor sees 37 development rows. The evaluator creates the random confirmation selection after the artifact freeze. The frozen materializer receives only the public evidence rows needed to apply its plan. It receives neither the selected tasks nor their expected answers. The evaluator keeps the nonce, cases, answers and signing key in a private directory. Linux seccomp probes denied reads and writes of an evaluator canary, socket creation, process creation and program execution. The parent launched a separate trusted evaluator process. On this host it was killed after case selection and restarted unattended with the same artifact and case commitment. A separate audit regenerated all 64 tasks in custody. Thirteen controls passed, including malformed and missing data, contradictory and stale data, a changed witness, cutoff and tied-witness cases, overload, source fallback and interruption recovery. The overload fixture returned empty 503 responses and both clients recovered after the slot was released. The two actual trial receipts are preserved.

The trust boundary is the approved public runner, OS and launcher. The signing key is local to that evaluator state. A public key pinned independently of the receipt supplies identity trust. This experiment uses public underlying evidence and evaluator-held selection. A real confidential trial requires a separately administered evaluator identity and store. Keep the [#550 authority and release gates](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550). The current ledger lacks a cleared representative request distribution, beneficiary-approved latency, sustained throughput, concurrency, acceptance and availability criteria, matched resource entitlement and complete costs. Review of the [ALPHA-1 correction](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/563), [observing worklist](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/449), and [governance candidate](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/259) found public historical evidence and proposal fixtures. An authorized fresh operational series with independent criteria and provenance was unavailable for those routes.

The existing read-only Observatory workflow runs the public cycle on eligible PRs and dispatches, and on the existing daily schedule when the two research opt-ins apply. It exports only the two public files. The capsule and receipt can cross that path unattended because they originate on the research runner. The ChatGPT intake bridge still requires a reviewed capsule and exact-head review confirmation ([#546](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/546)). No standing unattended write authority for conversation material was established. A future authorized contract gets a new registration and replay against its own requirements.

### Reproduce and audit

Use Linux with Python 3.10+, libseccomp, Git, curl and OpenSSL with Ed25519 support. Run from the repository root. The exact public FA01 commit is fetched if it is absent locally. Reuse the same private state to resume or to re-export byte-identical results. Use a new state for fresh confirmation. The recovery exercise consumes ordinary local CPU and a loopback socket.

```sh
lab=products/frontier-omega-alpha/research/autonomous_endpoint
work=$(mktemp -d)
python3 -B "$lab/cycle.py" run --state "$work/evaluator" --output "$work/public" --exercise-recovery
python3 -B "$lab/cycle.py" verify "$work/public/receipt.json"
python3 -B "$lab/cycle.py" audit --state "$work/evaluator" --key-sha256 "$trusted_key_sha256"
```

Set `trusted_key_sha256` from your evaluator's independently known fingerprint for an identity-bound check. The fingerprint for the retained confirmation receipt is `5d4faad25c30a0efc970ebf6e16fa9b66c398bef1afd8cd4ed94f0e06691b0d2`. `audit` runs in custody and publishes no cases. To use the signed capsule offline, invoke `cycle.py decide --capsule CAPSULE --receipt RECEIPT --query QUERY --key-sha256 FINGERPRINT`. The query is a JSON object with `scope` in the exact order of `comparison.scope_keys` in the registration, `as_of` as an ISO day, `floor` as a decimal throughput string and `ceiling` as a decimal P90 first-token-millisecond string. The output gives all IDs at the highest qualifying measured load. An unsupported scope, future cutoff or empty qualifying set returns `ABSTAIN`. An altered signature or capsule is rejected. A separate detached test returned a measured load of 768 for one public scope without the original archive and rejected a later cutoff, modified receipt and modified capsule.

### One standing authorization for confidential operation

Authorize a dedicated non-production evaluator service identity under independent administration on an approved host. Give it read-only access to the cleared workload and exclusive control of the evaluator code version, private case store and signing key. Pin the public key outside the runner and keep deployment, spending, external contact and constructor credentials outside this grant. With a versioned real contract, this permits autonomous selection, execution and publication of redacted signed aggregates. Revoke by disabling the identity, removing its data access and revoking the pinned key. The real contract, records and matched resource entitlement are still missing.

## Français

**ABSTENTION POUR L’ADOPTION OPÉRATIONNELLE.** SQLite indexé demeure la référence pratique pour cette décision d’archive. Aucune charge du pilote Qwen sur CPU n’a satisfait aux critères. Dans le test FA01 sur boucle locale, les deux clients ont satisfait aux critères à la charge 3 en situation nominale et se sont abstenus dans le scénario dégradé.

[Reçu de confirmation signé](evidence/confirmation.json) · [Capsule de preuves](evidence/capsule.json) · [Essai de développement](evidence/development-recovery.json) · [Protocole et provenance](registration.json)

| Méthode | Accord avec le vérificateur | Temps total des 64 requêtes avec données déjà chargées | Taille matérialisée |
| --- | ---: | ---: | ---: |
| SQLite indexé | 64/64 | 1,75 ms | 77 824 octets |
| Instrument figé de la PR #554 | 64/64 | 31,17 ms | 34 651 octets |
| Capsule de preuves autonome | 64/64 | 0,62 ms | 9 018 octets |

Le vérificateur a confirmé 31 décisions fondées sur une charge réellement mesurée et 33 abstentions. Aucun des 37 points de développement ne pouvait être supprimé par dominance. La capsule projette les mesures utiles et préserve tous les témoins à égalité. Le vérificateur a confirmé la couverture des 82 points de confirmation dans huit configurations. Une fois la projection authentifiée, une requête peut être résolue sans consulter l’archive initiale. Le cache de SQLite fonctionne aussi hors ligne. Sur ce cycle, matérialiser, vérifier, rouvrir et interroger la capsule a pris **122,01 ms**, contre **3,01 ms** pour préparer et interroger SQLite. S’ajoutent 94,24 ms pour la construction de la capsule. Les frais de source, l’énergie, le coût complet d’ingénierie et de révision, le soutien et la maintenance n’ont pas été mesurés. L’admission de S₁, le transfert vers S₂ et l’amélioration du constructeur et de sa règle d’apprentissage restent à établir.

Le processus d’évaluation a sélectionné les 64 cas après le gel de l’artefact. Linux a refusé au constructeur les accès aux fichiers de l’évaluateur, au réseau et à la création de processus. L’évaluateur a repris automatiquement après une interruption injectée en conservant l’artefact et l’engagement cryptographique des cas. Les treize contrôles ont réussi. En surcharge simulée sur la boucle locale, les deux clients ont reçu une réponse 503 vide, puis ont réussi après libération de la capacité. Le rejeu des captures Qwen historiques a reproduit 5 réponses acceptées sur 6 aux charges 1 et 3 pour chaque client. L’inférence n’a pas été relancée.

Pour reproduire le cycle, utilisez les commandes ci-dessus. L’état de l’évaluateur reste privé. Le reçu et la capsule sont les seuls fichiers publiés par le flux de recherche. Un nouvel état produit une nouvelle confirmation. Le contrôle par un tiers des cas et des réponses s’exécute dans l’environnement de l’évaluateur. La signature locale peut être vérifiée avec l’empreinte connue de sa clé publique.

**Autorisation permanente demandée pour un essai confidentiel.** Créer une identité de service d’évaluation hors production sur un hôte approuvé sous administration indépendante. Lui donner la lecture des données autorisées et le contrôle exclusif de la version de l’évaluateur, du dépôt privé des cas et de sa clé. Fixer la clé de confiance à l’extérieur du moteur de construction. Cette identité pourra exécuter les évaluations et publier des agrégats expurgés et signés lorsque les exigences et les droits seront documentés. Pour révoquer l’accès, désactiver l’identité, retirer la lecture et révoquer la clé. La charge réelle représentative, les exigences actuelles, l’accès aux ressources correspondantes et les coûts complets restent à établir. [Exigences de sécurité et d’autorisation #550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550)
