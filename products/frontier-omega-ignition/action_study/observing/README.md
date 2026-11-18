# When a gravitational-wave candidate is withdrawn

**One official revision changes a shadow observing decision.** On 20 April 2024, the first three LVK notices for S240420aw supported retaining its entry for review. The fourth notice withdrew the candidate. Moving the issue-time cutoff from 05:06:22 to 05:06:23 UTC changes the recommendation to withdraw the entry. A conventional SQL query over the same public records reaches the same decision. A participant's actual receipt time is unknown. [Archived notices](https://gcn.gsfc.nasa.gov/notices_l/S240420aw.lvc) · [LVK circular](https://gcn.nasa.gov/circulars/36190)

## Reproduce the decision

Use Python 3.11 or later in this directory. Every command below runs offline with the standard library.

```sh
python desk.py --event S240420aw --as-of 2024-04-20T05:06:22Z
python desk.py --event S240420aw --as-of 2024-04-20T05:06:23Z
python desk.py --event S240420aw --as-of 2024-04-20T05:06:23Z --clock received
python desk.py --check
python test_observing.py
python cost.py
```

The decision includes the original packet identifier, exact trigger estimate for that revision, UTC issue time, status, original-body and packet SHA-256, archive address and retrieval time. It also identifies missing publication or receiver timestamps. A hash identifies the bytes used. LVK's identity, notice fields, coverage and official archive on acquisition supply the evidential context.

**Independent route.** The ordinary e-mail notice already states the status. The checker independently parses GCN's e-mail representation, joins the matching original packet's issue clock by event and serial, checks trigger time and the NASA index, and selects the latest eligible status in SQLite. Its first implementation assumed every e-mail included an event-page URL. The real withdrawal omitted that optional field. The corrected comparison checks the mandatory event ID, the packet's event page and any page supplied by the e-mail. It retains the original text with its omission. The circular and two serializations have a common LVK source. This tests interpretation and independent computation. [NASA notice definitions](https://gcn.nasa.gov/missions/lvk)

| S240420aw clock | UTC on 20 April 2024 | Meaning |
|---|---|---|
| Trigger estimate, revision 4 | 04:22:45.509470 | Candidate time in the original withdrawn notice |
| First preliminary packet | 04:30:11 | LVK issue clock for retaining the shadow review |
| Retraction, revision 4 | 05:06:23 | LVK issue clock for withdrawing the shadow review |
| GCN text notice | 05:06:26 | Timestamp on the e-mail representation |
| GCN Circular 36190 | 05:17:10.339 | Circular creation time in GCN's original JSON |
| Receipt by a particular observer | Unknown | Requires a dated delivery or ingestion witness |

The collaboration attributed the withdrawal to a period of detector noise at Hanford. The issue-clock interval from the first notice to withdrawal was 36 minutes 12 seconds. The observations concern official candidate status. Telescope activity, physical event truth and any time saved by a beneficiary require separate evidence. [Original circular JSON](https://gcn.nasa.gov/circulars/36190.json)

## Population, coverage and obstruction

[Registration](REGISTRATION.md) fixed the sample and rules in Git commit `c83c58ce893f014b8c6cf8c6f64c523a7a482c9a` before acquisition. The frozen source adapter at `01b164e5859dc9ad74147203c60ae93a3f939778` preceded adjudication of the fifth event. All records were downloaded together. The fifth event's identity and archive size were visible before adjudication. This is a held-out execution check on the receiver, with no claim of independent human blinding.

The April 10–30 register had 350 entries for 164 distinct public S-prefixed candidates. The first five eligible candidates by trigger time each had two preliminary notices. All five retained their shadow review entry throughout the registered seven days, including the fifth case S240410ax. The separate April control deliberately selects an event with a retraction. It shows a withdrawal and cannot estimate how often withdrawals occur. The portable roster preserves all 426 April entries for the April-wide control selection. [NASA GCN roster](https://gcn.gsfc.nasa.gov/lvc_events.html) · [Computed outcomes](result.json)

We examined one microsecond before and exactly at each of 14 issue times, plus each event's seven-day horizon. Direct SQL agreed at all 34 cutoffs. Six cutoffs preceded the first eligible packet. The issue clock supported 28 status decisions. At all 28, an observer-receipt contract deferred for missing delivery evidence. Keeping the control's first status unchanged would be wrong at two cutoffs. The qualified first-only route defers once a lifecycle check is required. The issuer's latest status is already available to competent direct clients.

To requalify new bytes, run `python capture.py --compare-official` with network access. This explicitly reads the registered public NASA routes and reports any differences without overwriting the capture. The full historical index body was 12,284,634 bytes. Only its April projection is distributed. Its parser and both hashes are supplied, so a changing index and a change within the April register can be distinguished. April rows qualify the scope of the captured archive. They cannot establish exactly which notices reached an observer in 2024.

## Costs and downstream test

The acquisition receipts record 15 requests and 20,384,783 body bytes. They include an initial 8,000,001-byte roster prefix that could not establish coverage. Per-request wall times sum to 134.635 seconds, with several requests running concurrently. The two representations share the roster. The six original histories used 82,752 bytes, the six conventional text histories 16,702 bytes, and the corroborating circular 694 bytes. Running an existing status client may have a lower incremental cost for an observer already collecting these notices. [Source receipts](sources.json) · [Measured replay costs and unknowns](costs.json)

Actual observer correction time, false priorities in an operational queue, avoided observations, value of downstream science, completed delivery, billing, maintenance and demand remain unmeasured. The next test requires a willing team, a frozen queue with arrival receipts, its actual conventional workflow, recorded resource costs and blinded scientific adjudication. No observer was recruited and no telescope was contacted. For new alerts IGWN retired VOEvent/GCN Classic distribution in favor of GCN Kafka JSON and SCiMMA Avro. A live study must bind its ingestion receipts to the current format. [IGWN change log, v30](https://rtd.igwn.org/projects/userguide/en/v30/changes.html)

## Quand une alerte gravitationnelle est retirée

**Le quatrième avis change une décision de suivi simulée.** Le 20 avril 2024 à 05 h 06 min 23 s UTC, la collaboration LIGO–Virgo–KAGRA a émis la rétraction de S240420aw. Une seconde auparavant, les trois premiers avis justifiaient encore de conserver le dossier dans la file d’examen. Le quatrième justifie de le retirer. Le texte de GCN porte l’heure de 05 h 06 min 26 s. La circulaire a été créée à 05 h 17 min 10,339 s. L’heure de réception par une équipe reste inconnue. [Avis archivés](https://gcn.gsfc.nasa.gov/notices_l/S240420aw.lvc) · [Circulaire de la collaboration](https://gcn.nasa.gov/circulars/36190)

Les cinq premiers candidats admissibles du registre du 10 au 30 avril ont tous conservé leur place pendant sept jours. S240420aw constitue un témoin distinct, choisi expressément pour sa rétraction. L’extraction SQL conventionnelle et l’instrument concordent aux 34 échéances inscrites. Six précèdent le premier avis. Aux 28 autres échéances, le statut émis peut être établi, tandis que l’absence d’accusé de réception oblige à différer toute décision fondée sur l’heure de réception. Pour reproduire cette distinction, exécutez les trois premières commandes ci-dessus. `--check` recalcule tous les résultats et `test_observing.py` vérifie les cas défavorables. [Résultats](result.json)

Le bénéfice pour une équipe dépend de la décision qu’elle aurait prise avec son propre logiciel et des mesures supplémentaires réellement évitées. Le coût complet du travail humain, le temps de télescope et le gain scientifique restent inconnus. L’expérience prospective exige une équipe volontaire, une vraie file d’examen et des horodatages d’arrivée exploitables. [Coûts mesurés](costs.json)
