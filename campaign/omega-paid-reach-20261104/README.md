# Can collected earnings buy profitable incremental reach?

A simulated seller offers checked KPI-variance and reconciliation work. The organic arm waits for its scheduled contacts. The pilot arm may spend earned cash on an expiring audience contract and may renew once. Each contacted buyer can refuse, buy a feasible basket, or buy a fresh job on a later visit within a persistent wallet. Only an independently accepted, settled basket can produce a collection. The experiment tests distribution for the existing cart service. The [frozen protocol](PROTOCOL.md) specifies the draws, costs, capacity and decision rules.

Each of the five environments gets its own pair of accounts. The first 27 opportunities replay an already exposed favorable history, paying all costs again from a fresh US$100,000 simulated opening balance per account. The qualifying history ends before day 90. The remainder of the same 365-day window contains the fresh cohort. A pilot purchase on day 90 costs $6.25 including support. A renewal on day 118 uses only observed first-tranche collections, costs and current liquidity. The trial estimate must be positive, the invoice must fit current earned funds, and available cash must cover both the invoice and the $12 annual maintenance. The organic counterfactual is unavailable to either investment decision.

## Run and recover

Use Python 3.12 on a local POSIX filesystem with exclusive custody of each account. From the candidate revision, use an existing environment with the pinned dependencies or create one with the following commands. No customer, credential, payment service or API key is needed.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-omega-mechanisms-v3.txt
python -m unittest discover -s tests -p 'test_omega_reach_*.py' -v
```

Choose a fresh **absolute path outside the repository** for the account tree and a separate existing directory for the public comparison. Set these once for this run. The account runner refuses a preexisting account directory. The loops below use each scenario's specified name and run one account at a time.

```sh
set -eu
umask 077
run_root=/absolute/private/reach-run
result_dir=/absolute/results
mkdir -p "$run_root" "$result_dir"
for scenario in central weak copycat no_demand failed_activation; do
  for arm in organic pilot; do
    python -m mechanism_harness.reach_native run "$run_root/$scenario/$arm" \
      --arm "$arm" --scenario "$scenario"
  done
done
python scripts/summarize_omega_reach.py --input "$run_root" \
  --output "$result_dir/PAIRED_EVIDENCE.json"
```

For an interrupted account, retain its entire directory and return to the same source and dependencies. Resume reconciles the original authority and uses its stored arm and environment. A completed resume also reconciles the live native account to its recorded export. After recovering, run only the remaining unstarted cells before summarizing. The following commands target one cell.

```sh
python -m mechanism_harness.reach_native resume "$run_root/central/pilot"
python -m mechanism_harness.reach_native audit "$run_root/central/pilot"
```

If a source, journal, signer, artifact or cost fails verification, preserve the original files and diagnose the mismatch. Restore a matching complete backup when one exists. An unavailable authority leaves that cell unresolved. Keep the account tree private, including its signer, SQLite files, action tape, journal and order-level data. The summarizer writes a new aggregate JSON only after all ten independent audits pass. Choose a new evidence filename on a subsequent replay.

## Read the comparison

Money is integer microUSD, with 1,000,000 microUSD per US dollar. Each pair covers model days [0,365). Positive differences favor the pilot for profit, settled volume or available cash. A positive expense difference reports additional costs.

| Evidence | Interpretation |
| --- | --- |
| `shared_design_and_prefix` | Compares the complete logical job manifest and menu study, every warm contact, accepted artifact, economic request, funding source and native account transition before the first review. Measured CPU time is reported separately. Reserve/finish proof digests bind each independently formed account. The native auditor verifies those bindings separately. |
| `reach_and_work` | Counts actual exposures, offered contacts, qualified buyers, outcomes, refunds, repeated settlements, consumed capacity and unused slots. Same-day overlap counts one offered contact. An unsettled offer, unfilled slot or activation promise earns zero collections. |
| `tranches` | Shows cash available before each decision, the action, reason, paid invoice, activation, expiry and realized first-plan evidence. Attributed contribution credits only collections from buyers outside the entire organic roster and deducts every paid-routed variable cost plus the invoice. |
| `financial_microUSD` | Gives recognized revenue, realized collections, every paid and incurred expense, modeled profit after tax, reserves, outstanding payables, cash and available cash. Available earned cash is the subset eligible for earned-only reinvestment. |
| `comparison` | Subtracts organic from pilot within one environment. Enterprise profit includes changes in organic work displaced by paid contacts, which the local renewal estimate cannot measure. The zero-profit nonentry comparator is arithmetic and operates no account. |

Setup and discovery are expensed at startup. Annual maintenance and a 20% provision on positive modeled pretax income are charged at day 364. See each account's expense breakdown for quotes, paid access, production, payment fees and tax. Both arms use the same menus, operating rules and buyer population. One environment halves values after the warm period, one lets a copycat match surplus, one sets subsequent values to zero and one introduces an unobserved supplier activation failure. The supplier advertises its baseline 95% activation reliability to every decision maker. Only the simulated environment changes it to zero in the failure case, so the agent learns from the failed activation after it has paid. Actual demand, realized human attention, development labor, hosting and model opportunity cost remain unmeasured. There is no observed annual real profit or validated larger market.

## How the research changes the test

Development checks use alternate seeds or small fixtures. Once the ten registered accounts have completed, the clean-package and downloaded-release checks may repeat a registered input to demonstrate reproducibility. These later engineering runs never count as additional observations, profit, or funding of the original enterprise.

The paper's economic-usability criterion separates a participating buyer's surplus, realized profit and cash available before commitment. Here a paid contact can refuse, the underlying delivery must pass its checker, and the full invoice must be affordable from earned funds before the supplier can grant access. The post-period organic control measures actual incremental settlements and cash after costs. [Construction, “When an arrangement is economically usable”](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/247d0dbebb6b04bee52bf18bbfe11a9d9a2737c5/docs/flywheel-omega/sections/construction.tex)

The succession criterion keeps a capable incumbent eligible and charges the cost of improving. Organic service retains the same production and verification tools. Renewal can stop after paying the first invoice, and organic remains eligible to win in every world. This contrasts channel policies. A claim about a better discovery method would require separate equal-content comparisons and measured lifecycle burdens, including any human work. [Succession, “Let the stronger method remain the incumbent” and “Count the cost of becoming better”](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/247d0dbebb6b04bee52bf18bbfe11a9d9a2737c5/docs/flywheel-omega/sections/succession.tex)
