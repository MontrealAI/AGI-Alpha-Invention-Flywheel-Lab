# Battery passport source review

**Outcome for MONTREAL.AI.** The pilot produced a runnable, read-only review of proposed capacity, weight and voltage values from source-located measurements. It checked actual labeled battery configurations across four held manufacturers. Competent direct Codex and FRONTIER Ω tied on both panels. This is a scoped engineering asset. A commercial or whole-system advantage was not established.

The European Commission announced the Registry technical material on 16 November 2026. Its semantic resources are dated 30 October. Its v4 battery data-point matrix is dated 19 November. Earlier registry services and commercial pilots already existed. The experiment concerns source support for exact product fields against these concrete published artifacts. [Commission announcement](https://single-market-economy.ec.europa.eu/news/digital-product-passport-registry-technical-guidance-available-2026-11-16_en) · [Official technical resources](https://single-market-economy.ec.europa.eu/single-market/digital-product-passport/resources-documentation_en)

## Executed comparisons

| Arm | Primary on FENECON and SolaX | Fresh confirmation on Sungrow and GoodWe |
| --- | --- | --- |
| Competent direct included Codex with exact ordinary computation | 14/16, zero false support | 6/6, zero false support |
| Included Codex, source annotations and the FRONTIER Ω check | 14/16, zero false support | 6/6, zero false support |
| FRONTIER Ω check with product scope removed | 6/16 dispositions, 5/16 joint disposition and attribution, three false supports | Not run |
| Ordinary operation of the exact instrument | Not run | Identical six decisions and attributions from the same typed data in 31 new Node processes |

The registered primary acceptance required 15/16 with zero false support. Both arms withheld the same two cases. The author later confirmed that the original source header identifies the BMS+PACK as a battery module. The abbreviated packet supplied to both arms omitted that header. The evaluator mentioned the two case grades after direct predictions froze and before treatment predictions froze, so treatment was not fully blind for that pair. Both arms obtained 14/14 on the other registered cases. The separate untouched six-case confirmation froze both predictions before unblinding and passed in both arms. Authors and constructors used the same workspace administration.

The typed check passed the five separate synthetic scope and conflict cases. With scope removed it passed three of five dispositions and produced two false supports. The withdrawn arm supplied no rationales, so it did not qualify as a complete submission. A separately observed challenge also showed that a wrong column label can pass the arithmetic check when both values occur in the same excerpt. Independent source interpretation still matters.

Review exposed partial matches after the freeze, including grouping, bounds, compound units and tolerance suffixes. The corrected check requires a complete supported label and measurement from the cited source note. All 27 frozen primary, adverse and confirmation decisions and attributions reproduce. The stricter check changes two primary and one adverse withdrawal decisions. The archived withdrawal counts and ordinary-reuse timing describe the original experiment. [Exact inputs, references and replay](dpp-replay/README.md)

The official conventional JSON Schema accepted the supplied official example and three individually altered, correctly typed measurement values. It rejected the same three fields when assigned invalid types. This tests shape, while a competent conventional source review can perform the independent evidence assessment. The October schema's nested declaration object also rejected a hypothetical integrity member at that location. The November matrix describes integrity information for the declaration. The test observes a seam in those particular artifacts. Registry-level representations and legal treatment remain outside the experiment.

## Operate the retained artifact

Use the original manufacturer documentation and an independent review of its table headers, model, version, units and scope. Transcribe only source-located observations. Keep unknowns when an applicable value cannot be found. Add the resulting JSON to a mission's result files. Choose **Check supplied battery measurements**. The site compares the specified scope, source excerpt, and exact compatible quantities. Keep or download the resulting receipt. This workflow accepts data and executes the checked application code. Imported source files remain inert.

The demonstration JSON contains fictional data. It returns `contradicted` for the proposed 68 kg when the specified complete battery source states 64 kg. Run the same code with a local JavaScript runtime:

```sh
node --input-type=module -e '
  import {readFileSync} from "node:fs";
  import {reviewBatterySources} from "./docs/research/frontier-omega-alpha/dpp-source-review.mjs";
  console.log(JSON.stringify(reviewBatterySources(JSON.parse(readFileSync(process.argv[1]))), null, 2));
' docs/research/frontier-omega-alpha/frontier-battery-source-example.json
```

The ordinary reuse experiment's median startup-inclusive wall time was 89.549 ms, with 2.185 ms median inside the verifier. It reused the same expert projections. The timer excludes source acquisition, interpretation and review. Direct case-reading-to-freeze windows were about 39 seconds for the primary panel and 20 seconds for confirmation. No matched complete-cost or actual human-attention improvement was measured. There was no paid inference, actual buyer acceptance, filing, or revenue. The supported value today is reproducible triage of supplied observations.

[Registration and thresholds](REGISTRATION.md)

## Français

Le contrôle examine la capacité électrique documentée en Ah, le poids et la tension nominale pour une configuration précise. La méthode directe et FRONTIER Ω ont obtenu 14/16, puis 6/6 sur six cas nouveaux. Le retrait du contrôle de portée a causé trois fausses validations au premier essai. L’instrument compare les observations transcrites et leurs extraits sources. L’interprétation du document demeure à vérifier. Le gain économique et la conformité réglementaire restent à établir.
