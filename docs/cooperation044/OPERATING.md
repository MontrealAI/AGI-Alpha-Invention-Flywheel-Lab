# Cooperation 044: an executed opportunity-to-capacity-to-successor sequence

## Contribution and boundaries

This opt-in experiment integrates the released complete-offer selector, public buyer-choice model, capacity recourse, exact-money native account and independent service/financial auditor. It adds a source-frozen runner, a prospective-decision-bound sequence witness and adversarial tests. It does not replace the operating engine, ledger, active financial accounts, default policy or any other owner's branch. It is developer-authored integration of established mechanisms, not evidence that an autonomous inventor created the mechanisms.

The experimental opportunity set is finite and public. The same incumbent optimizer compares complete services, buyer outside options and refusal. The ablation allows zero additional units; the candidate can buy up to two complementary capacity units from current unrestricted earnings. These bounds describe this experiment, not a universal business or scale ceiling. Four authored buyers and 112 generated inventory records do not establish demand or production at enterprise scale.

## Executed local result

Based on released main `7333cb483a9fb261177e89a094f72ab896aab82c`, using source identity `efa9d94f058e0780ae082f1b2d9c5ebc669ebea1f79063d55d05fca98b6126d5` (228 canonical source files). Both arms begin with exactly USD100,000 simulated capital, use seed341014, operate for42 simulated days and drain their queues. All four final worlds independently passed the native auditor; both comparisons independently re-audited their two worlds.

| Registered case | Additional capacity allowed | Accepted collected orders | Collected USD | Complete modeled expenses USD | Modeled profit USD |
|---|---:|---:|---:|---:|---:|
| Central | 0 | 9 | 180.000 | 128.096 | 51.904 |
| Central | 2 earned-funded units | 10 | 230.000 | 149.496 | 80.504 |
| No demand | 0 | 0 | 0 | 146.400 | -146.400 |
| No demand | 2 earned-funded units | 0 | 0 | 146.400 | -146.400 |

The central matched profit difference is USD28.600. This is a targeted action-set ablation, not superiority over every equally permitted conventional strategy. The policy is itself an existing conventional finite optimizer. No-demand correctly reports NOT_ESTABLISHED, not successful cooperation.

### Machine-recorded sequence

- Hour627: a prior reconciliation order collects USD20, with USD17.12 order contribution.
- Hour672: the native policy compares zero, one and two extra capacity units. One extra unit still cannot execute the three-unit packet. The policy selects a two-unit contract costing USD6, explicitly linked in its prospective recourse to the future packet job.
- The original native account records USD10.046 unrestricted earnings before reservation and funds the USD6 invoice as EARNED. This is aggregate earned-pool funding, not a claim that one fungible receipt uniquely paid the invoice. Opening capital continues backing other protections.
- Hour696: purchased units become active. Hour840: the machine selects the source-linked packet, and the modeled buyer chooses it over its stated outside options or refusal.
- Hour843: independent acceptance. Hour867: USD50 collected for the receivables packet. Complete order cost is USD8.25; order contribution is USD41.75. After the unique USD6 enabler invoice the source-linked component contributes USD35.75. This figure is NOT enterprise profit; enterprise profit is USD80.504 after the full modeled envelope.

The packet produces reconciliation, receivables metrics and exception evidence for coherent source data. Artifact SHA256: `fa33d2c14e5c9e46dbeb4dc9017acd7594cbb5a58835e0b076ec0acf47e3ef4a`.

The witness requires the recorded pre-investment choice, prospective job link, actual native reservation, current earned liquidity, capacity activation/expiry, later delivery selection, buyer choice, independent acceptance and collection. It closes the linked investment/order component, charges losses and unpaid-work costs, and charges each unique invoice once even when its plan ID is repeated for multiple capacity units. It is only emitted after native audit.

## Reproduce without paid models or external commerce

Use the repository's pinned Python3.12 environment and `requirements-commercial010.txt`. No API key, customer contact or external payment is required.

```sh
python -m unittest tests.test_connected_cooperation044 tests.test_connected_capacity_contract tests.test_connected_temporal_boundaries tests.test_connected_finance -v
python -m connected_enterprise.cooperation044 run --case central --arm fixed_capacity --output /absolute/new/control044
python -m connected_enterprise.cooperation044 run --case central --arm earned_capacity --output /absolute/new/candidate044
python -m connected_enterprise.cooperation044 compare --control /absolute/new/control044 --candidate /absolute/new/candidate044 --report /absolute/new/CENTRAL044.json
```

Repeat both arms with `--case no_demand`, using distinct new output directories, and compare them. Do not select another seed or edit acceptance thresholds to obtain success. The run command freezes its own source and executes from that copy; each run has a finite180-second subprocess deadline. An interruption must retain the original private account and frozen source. To continue that same bounded run, execute from its `source` directory:

```sh
python -m connected_enterprise.cooperation044 _execute --output /absolute/original/run044
python -m connected_enterprise.cooperation044 verify --output /absolute/original/run044
```

Never rerun `run` over an existing account or copy balances. Keep native account keys and journals private. Publish only the generated `public/SUMMARY.json`, inert `public/LESSON.json`, comparison report and appropriate resource metadata. Compact reports are not a portable full financial re-audit archive; fresh source reproduction or the original private/native audit environment is needed to independently rederive them. The lesson is scoped applicability knowledge without financial authority; improved invention or automatic learning from this lesson is not established.

## Qualification and retained failures

Local qualification:27 new adversarial tests plus12 inherited capacity/temporal tests and24 finance tests passed,63 in total. The native runs are additional executed integration evidence, not mocked tests. Local runtime was Python3.13.5 / cryptography46.0.4, not the pinned Python3.12 / cryptography50.0.2 environment. Exact-head hosted CI, independent review and normal release gates remain required before adoption. A prior broader local test invocation could not import an inherited helper absent from the released source ZIP; another broader invocation hit its deadline in large-money tests. Those are not recorded as full-suite passes.

Development lessons are retained without relabeling exploratory evidence as fresh confirmation: an initial all-packet market produced no earnings; a two-customer planning shortlist missed fundable smaller jobs; a28-day run did not reach the reinvestment transition. Expanding the fixed development horizon to42days exposed the sequence. The final protocol therefore explicitly labels all results EXPOSED_DEVELOPMENT_NOT_FRESH_CONFIRMATION. An initial runner integration failed on the inherited operations_bundle inventory; the mapping was corrected and has a regression. Both no-demand worlds were interrupted by the local tool's short command window and resumed with their original accounts, not reseeded. Resource receipts measure each finishing process only and omit interrupted-process telemetry; they are not total campaign CPU or monetary billing.

Costs are authored native envelopes, not measured full host/model/developer bills. Real customers, real collections, novel capability invention, improved discovery, billion-dollar annual profit, physical productive expansion and global game-theoretic optimality remain unestablished. The next stronger experiment must compare against equally permitted strong complete alternatives on fresh markets and validate a newly constructed capability rather than only purchased capacity.
