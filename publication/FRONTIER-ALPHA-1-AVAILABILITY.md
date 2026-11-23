# ALPHA-1 availability correction / Correction de la date d’accès

## Verdict

The 22 November study reproduced technical catalog decisions for 24 compatibility inquiries and 18 process-screening cases. Its seven changes in compatibility over 20–21 October 2026 are a **scenario based on an assumed availability date**. Reports dated 29 September challenge that assumption. The earlier scenario moves only the date of the same complete catalog. It gives **0/24** changes on 20–21 October. This is a sensitivity test. A dated manufacturer snapshot with the offer and its exact model eligibility remains missing.

Funding, purchase, delivery, physical performance and advantage over the conventional workflow remain unproven. Keep the original experiment intact and retire the claim that 21 October is the demonstrated onset of the capability.

## Evidence

| Public source | Observation | Limit |
| --- | --- | --- |
| [Prusa forum, 29 September](https://forum.prusa3d.com/forum/english-forum-general-discussion-announcements-and-releases/ht-hotend-for-the-prusa-core-one-l/paged/3/?language=en) | A participant reported placing an order and another reported that ordering had opened. | Firsthand public reports. Neither documents fulfillment or an exhaustive list of supported models. |
| [3Druck, 29 September](https://3druck.com/en/printers-and-products/prusa-introduces-the-ht-hotend-for-the-core-one-the-interchangeable-hotend-prints-at-temperatures-up-to-400c-37163441/) | A dated trade report names the 400 °C upgrade, five compatible configurations and the option to buy a new machine with it installed. | The compatibility information is attributed to Prusa. This is corroboration of earlier public reporting, with a shared upstream source for specifications. |
| [Prusa announcement, 21 October](https://blog.prusa3d.com/ht-hotend-is-out-plus-we-offer-new-materials-and-hightemp-sheets-for-core-one-l_138625/) | Confirms the 400 °C retrofit, the factory option and the INDX exclusion. | The post date proves that Prusa announced this bundle on 21 October. |
| [Prusa product listing, consulted 23 November](https://www.prusa3d.com/product/ht-hotend-upgrade-for-core-one-and-core-one-l/) | The current listing specifies compatibility, exclusions and ordering. | The live listing may change. Its September version has yet to be authenticated. |

## Reproduce

```sh
git fetch origin 5cced81256c965797988cd682fb5f910fe72c981
python3 scripts/replay_frontier_alpha1_availability.py --check
```

The replay verifies four frozen input hashes, evaluates the cases against an independently implemented SQL decision table and process control, then changes only the assumed cutover date. Expected outputs are in [frontier-alpha-1-availability.json](frontier-alpha-1-availability.json). An archived manufacturer listing and a separate witness of actual supply would let a later replay replace the scenario with dated model-specific facts.

## Conclusion en français

Les 24 décisions de compatibilité et les 18 décisions de présélection reproduisent les résultats techniques figés. Les sept changements des 20 et 21 octobre reposaient sur une date d’accès supposée. Des publications du 29 septembre documentent des commandes rapportées et une liste de modèles compatibles. Si l’on suppose que le même catalogue s’appliquait dès le 29 septembre, le nouvel essai trouve **0 changement sur 24** entre les deux jours d’octobre.

Cette conclusion porte sur la sensibilité au choix de date. Il reste à retrouver la version datée de la fiche fabricant et à établir les conditions de disponibilité par modèle. Aucun gain économique, résultat physique ou avantage causal par rapport au processus conventionnel n’a été établi.
