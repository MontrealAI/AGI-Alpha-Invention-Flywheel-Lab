# FRONTIER Ω ALPHA · ALPHA-1

## Engineering result

ALPHA-1 qualifies a documented retrofit path for non-safety-critical fabrication work. It screens an exact installed printer model and a requested equipment limit, returns the supporting source identifiers, and holds inquiries outside the registered catalog. Its successor checks a separate question about the installed process envelope, including chamber limits, the installed configuration, an accessory match and supplied site evidence. Both tools are read-only.

| Question | Executed result |
| --- | --- |
| What changed? | Prusa announced its HT Hotend retrofit on October 21, 2026. The OEM records document a 290 °C stock nozzle limit and up to 400 °C with the retrofit on supported configurations. INDX is explicitly excluded. [Launch](https://blog.prusa3d.com/ht-hotend-is-out-plus-we-offer-new-materials-and-hightemp-sheets-for-core-one-l_138625/) · [Retrofit compatibility](https://www.prusa3d.com/product/ht-hotend-upgrade-for-core-one-and-core-one-l/) · [Stock comparison](https://www.prusa3d.com/en/product/prusa-core-one/) |
| Does the new catalog option change decisions? | Yes. Seven of 24 registered and fresh inquiries moved from no documented route to a retrofit candidate in a matched before/after replay. Direct SQL reproduced all 24 decisions in both periods. The cutoff replays removal and addition of the dated option in a fixed catalog, with known device profiles. |
| Did retaining S₁ help construct S₂? | The exact frozen selector ran in the process screen. The inherited path, direct SQL without the artifact, and ordinary reuse all matched the 18 successor decisions. A difference in construction costs, eventual productive value or inventor performance remains unmeasured. |
| Does the evidence establish commercial value? | The technical result is Level 1. The hardware sources share one upstream manufacturer. The Reflective Gate confirms that replay agreement gives no independent physical or economic evidence. Actual acceptance, stock, fulfillment, payment, complete cost and economic alpha remain unobserved. |

The [opportunity register](research/economic_alpha/opportunities.json) compares three material possibilities. PARTS-TO-ORDER was selected for the pilot because the dated physical capability has a clear predecessor and a public OEM alternative. Docling's page-range evidence fix needs authorized original RFQs and a matched citation trial. The Lean experiment's older explicit proof already met the same two valid acceptance cases. The [Open Repair Alliance release](https://openrepair.org/open-data/downloads/) records repair activity. It supplies no evidence of orders or market demand for this retrofit. [Partium](https://www.partium.io/parts-intelligence/spare-parts-identification) already offers industrial identification and inventory lookup. Customer-specific comparison against the installed specialist, a competent human with conventional software, an authorized frontier-model workflow, and outsourcing or no deployment remains open.

[Frozen contract](research/economic_alpha/protocol.json) · [S₁ identity and first replay](research/economic_alpha/s1_freeze.json) · [Exact observation and result](research/economic_alpha/qualification.json)

## Run the pilot

Use Python 3.11 or newer from `products/frontier-omega-alpha`. The public observation uses `curl` and named HTTPS endpoints. The qualification and verification run offline. The financial packet interface uses local OpenSSL. Use a private working directory outside the checkout for input and output. Live public HTML can change and the observation records digests and time. A missing required source or changed model row calls for review and a newly registered scope.

```sh
python3 -m research.economic_alpha select
python3 -m research.economic_alpha observe --allow-network --output /tmp/alpha-observation.json
python3 -m research.economic_alpha qualify --observation /tmp/alpha-observation.json --output /tmp/alpha-receipt.json
python3 -m research.economic_alpha verify --receipt /tmp/alpha-receipt.json
```

For offline replay, copy the committed `research/economic_alpha/source_observation.json` to the private working directory and use it in `qualify`. The eight upstream responses, hashes and limited content checks are recorded. The tests use constructed inquiries with the same catalog facts for every arm. Fresh cases were recorded separately after the S₁ source was frozen. The same engineering session designed the experiment and built the controls. `verify` reruns the separately implemented relational logic on the frozen cases. Its output qualifies only the case decisions.

For a permissioned supplier pilot, map the verified model label, requested nozzle limit in whole degrees Celsius and use class into a structured request. Use `fit --request … --output …` for compatibility. The result's `part` value is an internal catalog identifier. Confirm the vendor's actual ordering reference, availability, deadline, terms and installation prerequisites with the supplier. Use `process --request … --output …` for an installed configuration. Add `claimed_installed`, `required_chamber_c`, `sheet` and `site_review` as specified by the [frozen input examples](research/economic_alpha/registered_cases.json). Site and equipment labels are input assertions. An appropriate reviewer must check the actual deployment and manufacturer requirements. All inputs should come from records the operator is authorized to use. Regulated, safety-critical or unidentified uses are held for external review.

### Real commercial trial

1. A named, willing distributor or operating shop grants written rights to use its relevant inquiries, catalog, stock and disposition history. Record the beneficiary and independent reviewer, actual materiality threshold, accepted outcome, comparison period, currency and MONTREAL.AI's agreed payment mechanism. Authorize any contact and transaction separately.
2. Freeze the complete comparison before opening new cases. Provide the same permitted records, opportunity window, approval requirements and service obligations to the incumbent and ALPHA-1 arms. Include the direct specialist, competent human-assisted or conventional route, and no-deployment alternative. Retain failed attempts, missing records, elapsed work, actual cost and unacceptable or undeliverable outputs. Stop or revise scope when the incumbent meets the same outcome at lower full cost.
3. A qualified reviewer reconciles buyer acceptance, a separately sourced fulfillment record, incremental beneficiary benefit, cleared money received by MONTREAL.AI, refunds, any documented reduction in cash expense, and all attributable costs. Distinguish invoice totals, merchandise value, capacity freed and cash. Record buyer and operator roles and the origin of mirrored data. The reviewer must validate the underlying records independently and sign the exact packet. Keep that packet, raw records, outputs and keys outside GitHub.

For `reconcile`, the packet schema is `frontier-omega-alpha/reviewed-economic-pilot-v1`. Provide `period` as two ISO dates, `currency`, `beneficiary`, `operator` (`montreal-ai`), `reviewer`, `minimum_benefit_minor`, and the `authorization`, `acceptance` and `fulfillment` evidence IDs. Provide `benefit` under the actual beneficiary ledger. Each evidence row carries `id`, local `file` basename, `sha256`, `role` and `upstream`. Every amount is an integer `minor` plus a `source` ID, or `null` where unmeasured. Each registered route has `collected`, `refunds`, `cash_reduction`, `costs`, `matched` and `comparison_source`. Include every named cost category even if the reviewed value is zero or unknown. The operator uses a reviewer public key fingerprint approved independently of the packet.

```sh
python3 -m research.economic_alpha reconcile --packet /private/pilot/review.json \
  --signature /private/pilot/review.sig --reviewer-key /private/pilot/reviewer.pem \
  --reviewer-key-sha256 '<owner-approved SHA-256>' --evidence-dir /private/pilot/records \
  --output /private/pilot/reconciliation.json
```

The verifier checks the detached signature and source bytes, then computes exact minor-unit results. It reports MONTREAL.AI's collected funds and retained payment separately from benefit to the shop. It subtracts refunds and complete costs and adds observed cash expense reductions. Incremental value subtracts the strongest supported matched alternative. Missing complete costs or comparators leave incremental value unknown. Monetary claims are conditional on an authorized independent audit of the actual documents. The code cannot infer facts from bank files or grant a commercial authorization. A delivered second deployment or causal successor benefit needs separate genuine evidence.

## Français

### Résultat technique

ALPHA-1 recherche une option de mise à niveau documentée pour un usage de fabrication courant. Le premier outil vérifie le modèle exact, la limite requise et les sources applicables. Le second examine une installation et un procédé distincts en tenant compte de la configuration installée, de la chambre, de l’accessoire et des justificatifs du site. Les décisions sont consultatives.

- **Changement observé.** Le 21 octobre 2026, Prusa a annoncé un module qui porte à 400 °C la limite de buse des configurations compatibles, contre 290 °C en configuration de série. Les configurations INDX sont exclues. [Annonce](https://blog.prusa3d.com/ht-hotend-is-out-plus-we-offer-new-materials-and-hightemp-sheets-for-core-one-l_138625/) · [Compatibilité officielle](https://www.prusa3d.com/product/ht-hotend-upgrade-for-core-one-and-core-one-l/)
- **Comparaison.** Sept demandes d’essai sur 24 ont changé de verdict lorsque l’option est devenue disponible dans le catalogue de l’expérience. La méthode SQL a reproduit les 24 décisions dans les deux périodes. Les trois voies ont obtenu les mêmes résultats dans les 18 cas du successeur. Les données d’équipement proviennent toutes de Prusa. Le contrôle réflexif conserve cette dépendance commune.
- **Niveau de preuve.** Les cas techniques sont au niveau 1. Ils utilisent des demandes construites et des faits publics du fabricant. Les bénéfices réalisés, les commandes livrées, les paiements encaissés, le coût complet et le gain causal d’invention demeurent inconnus. Les temps mesurés portent sur l’exécution locale et ne constituent pas une mesure de coût commercial. [Résultats chiffrés et comparaison des options](research/economic_alpha/qualification.json)

### Exécution et essai commercial

Dans `products/frontier-omega-alpha`, exécutez les commandes de la section anglaise avec Python 3.11 ou ultérieur. Utilisez un dossier privé à l’extérieur du dépôt. `observe` relève les documents publics, `qualify` exécute les comparaisons, et `verify` reproduit les décisions en SQL. La copie de la collecte enregistrée permet une reproduction hors ligne. `fit` et `process` acceptent les demandes structurées selon les exemples du registre. Le matériel réel, sa disponibilité et son installation exigent des preuves propres à la commande. Un usage réglementé, critique ou inconnu déclenche une attente de revue qualifiée. [Cas enregistrés](research/economic_alpha/registered_cases.json)

Le propriétaire doit obtenir l’accord d’un distributeur ou d’un atelier identifié et les droits d’utiliser ses dossiers. Fixez avec lui la période, la devise, le seuil de bénéfice, le résultat attendu, les autorisations et les conditions du paiement à MONTREAL.AI. Comparez le travail complet sur de nouveaux cas, avec les mêmes données, délais et obligations. Enregistrez les échecs, les coûts, les refus, la livraison effective, son acceptation par le bénéficiaire et les paiements réglés. Faites contrôler ces pièces par un tiers indépendant et obtenez sa signature détachée. Sa clé publique doit être approuvée en dehors du dossier lui-même. Les commandes, documents privés et clés restent hors du dépôt. La commande `reconcile` vérifie la signature et les pièces, puis rapproche les montants en unités monétaires entières. Elle distingue la valeur pour l’atelier, les encaissements de MONTREAL.AI, les remboursements et le résultat net après comparaison. Un dossier incomplet laisse le résultat incrémental indéterminé.
