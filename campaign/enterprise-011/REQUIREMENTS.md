# Enterprise-011 requirement-to-implementation and test map

This map defines intended current qualification coverage. Paths identify responsibility, **not a claim that a check passed**. Executed test logs, frozen source identity, run protocol and output receipts supply completion evidence. Historical market figures and source tests never become fresh enterprise-011 results automatically.

| Mandate requirement | Current implementation | Required check/evidence |
| --- | --- | --- |
| Independent commercial and invention outcomes; fixed capability allowed | `enterprise/runner.py`; current root policies | Five verdict fields; simulated revenue remains distinct from actual revenue; no forced invention prerequisite. |
| Current owner, fresh resources and historical preservation | `OWNERSHIP.md`; `SUPERSESSION.md`; `historical/enterprise011-prior-policy/MANIFEST.json` | Original hash checks; branch/source lineage; bounded CPU, wall and output receipts; no inferred remote activity. |
| Registry beyond 25 services; admission by executable contract | `portfolio_scale/universe.json`; `enterprise/services.py`; `enterprise/checkers.py` | Unique/versioned candidate IDs; only qualified public/synthetic inputs admitted; approval-required categories cannot imply authority. |
| Complete services and independent acceptance | `enterprise/services.py`; `enterprise/checkers.py` | Actual artifacts; input/output/source hashes; independent semantic checks; rejects and repairs; tampered acceptance and summaries rejected. |
| Buyer arrivals, acquisition, choice, activation, repeats and churn | `enterprise/model.py`; `enterprise/runner.py` | Distinct pipeline events/customer identities; no arrival means no purchase; acquisition failures costed; repeat transitions and attrition. |
| Multiple strategic models and four regime hypotheses | `enterprise/model.py`; `enterprise/pricing.py` | Ordinary, price-war, verified-differentiation and correlated-shock scenarios; responsive/lagged rivals; overlapping trust; buyer-choice alternatives. |
| Seller cannot read private values/future draws | `enterprise/model.py`; `enterprise/pricing.py` | Public observation boundary; hidden-value/RNG leakage adversarial regression; declared information and solution scope. |
| Premium human-cost anchoring with joint profit/price optimization | `enterprise/pricing.py` | Complete human-stage comparator; broad grid/refinement/boundary checks; no-bid; no fixed discount, close-rate objective or automatic AI-cost rule. |
| Complete autonomous costs; onboarding once | `enterprise/model.py`; `enterprise/runner.py` | Setup, failed acquisition, production, checking, repair, support, infrastructure, fees and obligations charged; first/repeat cost separation; resource envelopes labeled. |
| Protected settlement and event-derived finance | Reused qualified ledger boundary as integrated by `enterprise/runner.py` | Conservation; idempotent settlement; deposits/seed/taxes/reserves separated; failed/unpaid/refunded work; independent recomputation of financial summary. |
| Earned-funded delivery, reserves and seed separation | `enterprise/runner.py`; `enterprise/model.py` | Prior unrestricted earnings bound to additional profitable work; restricted cash misuse rejected; initial capital support disclosed. |
| Recurring bundles and portfolio allocation | `enterprise/model.py`; `enterprise/runner.py` | Customer/work deduplication; bundle replaces constituents; coordination/support/setup costs; context reuse and incremental allocation controls. |
| Dynamic scale and milestone uncertainty | `enterprise/scale.py` | Acquisition/adoption/capacity/cash horizon; annualized vs trailing-year/cumulative revenue; unreached targets, survival and capital constraints retained. |
| Operational frontier lane and retained mechanisms | Existing qualified invention components used by current runner when funded | Bounded surplus allocation; supplied/generated provenance; causal fresh-use tests versus ordinary reuse before compounding/Blue Sky claims. |
| Reliable recovery and repeated operations | Reused persistence boundary; `enterprise/runner.py` | Corrupt originals preserved; verified checkpoint/tape recovery; no duplicate jobs/revenue/costs/onboarding/seed resets; interruption and tampering tests. |
| Fresh confirmation and controlled comparisons | Source-bound protocol written by `enterprise/runner.py` | Freeze before fresh seeds; matched policy comparisons; all failures; declared cohort/cycle/profit/liquidity criteria and uncertainty; no policy edits mid-confirmation. |
| Actual current package qualification | `tests/test_enterprise*.py`; `.github/workflows/enterprise011.yml` | Explicit discovery of current suites and imported portfolio tests; documented CLI smoke; clean no-Git archive execution; exact-head CI logs. |
| Honest publication and continuation | Runner outputs; source/PR publication receipt | Exact tested source, assumptions, calibration scope, artifacts, ledger, failures, commands and remaining boundaries; action-time approval before merge/release. |

## Current checks

```sh
python3 -m unittest discover -s tests -p 'test_enterprise*.py' -v
python3 -m unittest discover -s portfolio25 -p 'test_*.py' -v
python3 -m unittest discover -s portfolio_scale -p 'test_*.py' -v
python3 -m enterprise run --output /tmp/enterprise011-NEW
```

CI also extracts `git archive HEAD` to a clean directory without `.git`, then executes the current documented runner there. Existing historical workflows retain their named-edition purpose. Their green status is not current enterprise acceptance unless current suites actually ran.
