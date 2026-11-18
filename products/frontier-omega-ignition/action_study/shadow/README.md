# When should an observer close a pending notice?

On 28 October 2026 at 07:00 UTC, one of two pending archival notices could be answered. The g-band measurement had occurred at 05:58:39.000 UTC. The r-band measurement would occur at 09:21:10.995 UTC. The decision depends on the clock and reference image as well as the object. Both detections belong to the Zwicky Transient Facility. The target ZTF26acbezdh was already known.

The six-slot rehearsal asks when to deliver a source-qualified measurement of positive difference-image light. It uses the two known notices at three frozen cutoffs. A delivery at two cutoffs can refer to the same exposure. Broker ingestion and operator receipt at the historical cutoffs are unknown. The prospective observer queue has zero enrolled participants and zero observed downstream uses.

## Reproduce the public rehearsal

From the product directory with Python 3.10 or later and its standard library, run the following commands. Each output path must be new.

```sh
python -B action_study/shadow/shadow.py check
python -B -m unittest discover -s action_study/shadow -v
python -B -m unittest invention.early_survey.exposures.test_exposures -v
python -B action_study/shadow/shadow.py rehearse --out /tmp/ztf-shadow-study
python -B action_study/shadow/shadow.py direct-inputs --out /tmp/ztf-direct-inputs
python -B action_study/shadow/shadow.py portable --out /tmp/ztf-shadow.zip
```

Extract the ZIP into a new directory and run the same commands there. The ZIP is built from named public files and contains all required inputs. The local rehearsal creates a private study store and randomized tickets. The only checked-in study observations are the compact public result and any independently returned public worker records. The exact cutoffs, arms and missing-access dispositions were registered before execution. [Registration](REGISTRATION.md) · [Recorded public result](PUBLIC_RESULT.json)

| Event cutoff, exclusive UTC | g-band shadow action | r-band shadow action |
|---|---|---|
| 27 Oct 00:00 | Keep open | Keep open |
| 28 Oct 07:00 | Deliver g measurement | Keep open |
| 29 Oct 00:00 | Deliver g measurement | Deliver r measurement |

| Route | Submitted / frozen slots | Accepted | Qualified deliveries |
|---|---:|---:|---:|
| A · Actual fully human incumbent | 0 / 6 | Unmeasured | Unmeasured |
| B · Conventional broker lookup | 6 / 6 | 6 | 3 |
| C · Integrated evidence-to-action receiver | 6 / 6 | 6 | 3 |
| D · Included direct AI using local conventional tools | 6 / 6 | 6 | 3 |
| E · Keep every notice open | 6 / 6 | 3 | 0 |

A fresh-context direct worker constructed its own temporal selector from the same public case, using the conventional routines. The worker returned all six responses before seeing the independent key. Its output reproduced byte for byte on a newly built direct-input folder. Its recorded interval was 176.081 seconds from its first timed inventory to delivery and 211.078 seconds through its own verification. Briefing before that clock, inference tokens, server costs and historical observer availability remain unmeasured. The public result records separate local clocks for conventional and integrated execution, independent SQL and delivery. The three methods tied on technical acceptance. Incremental beneficiary benefit and complete economic advantage remain open. [Direct receipt](direct/receipt.json) · [Returned working script](direct/review.py)

The independent SQL reference reads six original Avro records and selects by time, program, sign, filter, detector and reference. It computes the witness-minus-baseline PSF magnitude and quadrature formal error from original packet values. Full precision and original hashes accompany each scored delivery. The conventional receiver uses a separate Avro projection and adjudication. SQL and the integrated receiver share a low-level full-record decoder. SQL and the conventional route share the TAP parser. All three use the same survey measurements. The physical uncertainties exclude unmeasured calibration systematics.

The previously registered synthetic controls exercise an earlier different-reference projection and an earlier same-reference projection with no original packet. The first preserves the two qualified results. The second withholds the claim. Neither projection is an independently observed earlier event. See the upstream review for its historical failed runs and exact original source. [First-witness review](../../invention/early_survey/exposures/STREAM_FIRST_REVIEW.md)

## Use the field kit with a willing team

The primary comparison is A, a competent fully human operator using the beneficiary's actual conventional tools, against C, the instrument used by the appropriate agent or operator. B is a capable conventional archive workflow. D is direct frontier AI or an explicitly identified hybrid. E keeps the notice open without a search. Supply every arm with the same allowable source packets, deadline and resource rights. Record the actual operator, methods and access in the private protocol. Use distinct operators for the same object across arms. Mark unstaffed arms with null.

1. Agree on the actionable question, source interval, duty and cost horizon with the team. Freeze a roster of consecutive eligible queue entries and the end rule. For a rolling queue, use successive predeclared blocks as their evidence cutoffs arrive and retain all blocks. Keep the authority and consent references privately with the operator. The team controls participation, access, retention and withdrawal. Record any excluded or withdrawn cases and their timing under the agreed protocol; preserve aggregate recruitment/attrition counts as permitted.
2. Capture the authorized source packet at its cutoff. The manifest command hashes only files explicitly selected. Include a source-provenance record with actual acquisition, observation and publication times when each is known. A recorded acquisition can support a local availability clock. An exposure time alone cannot. Supply investigators only the permitted prefix for their current case. Where a source becomes available later, freeze a new source manifest and decision assignment.
3. Supply `prepare` with a JSON plan and an array of cases. Use the plan and cases written by `rehearse` as schema examples. For a real field block set `mode` to `field` and supply real `authority_receipt`, `consent_receipt`, distinct private `operator_assignments` for A–E and two or more registered independent `reviewers`. The required plan fields cover the objective, population, end and grading rules, deadline policy, available sources and permissions, staffing budget, cost horizon and currency. Every field case requires a stable `case_id`, `cluster`, `question`, `cutoff_utc`, `decision_due_utc`, `source_manifest` and its `source_set_sha256`. Add `available_utc` only with a dated local `availability_proof_sha256`.
4. The independent evidence adjudicator seals one expected result for every case, including unsettled references, before answers enter the store. Use an independently obtained source and original packet when possible. A key file maps case ID to `action`, `reference_sha256` and the full `measurement` for a delivery. The four reference actions are `deliver`, `keep_open`, `review` and `unsettled`. `independent-key.json` in a completed public rehearsal shows the precise measurement fields. Custodians retain the reference and its supporting evidence.
5. Give each route its own `tasks/<arm>.json`, authorized source files, deadline and rights. The custodian releases longitudinal tasks in cutoff order. Ticket recipients can verify the local file bytes against the assigned manifest. Collect answers in a packet with its `protocol_sha256`, assigned `operator`, and `responses`. Each response includes the assigned ticket, current source digest and its answer. Unknown original evidence or unsafe identity stays open or goes to review under the registered question. The intake date supplies the submission clock. Late decisions remain in the denominator.
6. Close intake and give the blinded output to registered independent reviewers. Assignments, operators, review codes and private receipts stay with the custodian. Reviewers receive only normalized decisions, their source material and independently evidenced downstream outcomes, using opaque codes in randomized order. Tell reviewers if a distinctive case or response is recognizable. Do not issue both the private database and the blinded batch to reviewers.
7. Each ratings packet includes the batch's `protocol_sha256`, `key_sha256`, `reviewer`, `reviewer_independent: true`, and `scores` keyed by every returned code. Record `use` as `observed_use`, `no_observed_use` or `unknown`. An observed affirmative or negative finding requires a `beneficiary_receipt_sha256`. A witnessed time of beneficiary acceptance additionally requires both `accepted_decision_utc` and `acceptance_receipt_sha256`. Enlist a previously registered independent third reviewer for disagreement. Preserve unresolved outcomes and explicitly explain any missing reviews before locking the panel and revealing arm labels.
8. Report absolute counts on the complete arm roster and counts per distinct target. `false_priorities` counts unsupported deliveries on open or review cases. `missed_priorities` counts returned decisions that failed to deliver the qualified decision on time. `missing_actions_on_deliverable` counts missing submissions separately. Overlap with the human incumbent is unknown until that incumbent has actually handled the cases. Cost per accepted useful decision requires matched observed beneficiary use and a documented complete cost.

A custodian can execute the field sequence locally:

```sh
python -B action_study/shadow/shadow.py bind-sources --dir sources --file notice.json --file original.avro --out bound.json
python -B action_study/shadow/shadow.py prepare --plan plan.json --cases cases.json --out private-study
python -B action_study/shadow/shadow.py lock-key --study private-study --key independent-key.json
python -B action_study/shadow/shadow.py verify-sources --dir sources --packet private-study/tasks/B.json --case-id CASE_ID
python -B action_study/shadow/shadow.py submit --study private-study --responses returned.json
python -B action_study/shadow/shadow.py blind --study private-study --out review-batch.json
python -B action_study/shadow/shadow.py review --study private-study --ratings ratings.json
python -B action_study/shadow/shadow.py close-reviews --study private-study --reason "record the actual completion or missing-review reason"
python -B action_study/shadow/shadow.py score --study private-study --costs actual-costs.json --out decision-scores.json
```

The optional cost file maps each arm to the registered `currency`, `horizon`, `costs`, `basis` and `measures`. Supply decimal amounts or null for every category in `fieldkit.CATEGORIES`. For each amount, record a `source` and `kind` of `measured` or `estimate`. Disclose what acquisition, infrastructure, failed work, correction, independent checking, historical construction, delivery, maintenance and support costs were allocated to the horizon. Operator seconds, verification and correction time, interventions and search counts are separate work measures. Record corrections, repeated work, adopted action and associated receipts in the beneficiary's private system. A missing price or unavailable use outcome leaves unit economics unresolved.

## Répétition scientifique et étude prospective

À 07 h UTC le 28 octobre 2026, la première mesure admissible en bande g permettait de transmettre un résultat pour ZTF26acbezdh. La question en bande r restait ouverte jusqu'à la mesure de 09 h 21 min 10,995 s UTC. Ces heures décrivent les expositions du relevé ZTF. L'heure à laquelle le courtier ou l'équipe aurait effectivement reçu ces données en octobre demeure inconnue.

La répétition porte sur deux avis déjà publiés pour un seul objet et trois échéances. La recherche conventionnelle, le récepteur intégré et un agent d’IA ayant construit sa propre procédure ont chacun reproduit les six décisions de référence. Ne prendre aucune nouvelle mesure a laissé trois occasions de transmettre un résultat sans réponse. Le fichier de résultats détaille les témoins, les erreurs formelles et les frais effectivement mesurés. Aucune équipe bénéficiaire n'a participé à cette répétition.

Pour la comparaison prospective, une équipe volontaire fixe d'abord sa question, sa pratique habituelle, son échéance, ses droits et son budget. Chaque méthode reçoit les mêmes sources et les mêmes droits. Les évaluateurs indépendants examinent les décisions sous des codes anonymisés avant la levée de l'insu. Un dossier incomplet, un retard et une priorité erronée sont comptés séparément. Le temps gagné, les observations de suivi évitées et le coût par décision utile nécessitent des décisions réellement acceptées par l'équipe et des coûts documentés. Les commandes ci-dessus permettent de préparer, de verrouiller, de vérifier et de reproduire l'étude localement.
