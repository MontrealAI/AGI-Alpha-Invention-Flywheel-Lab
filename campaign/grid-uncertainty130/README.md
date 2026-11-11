# Grid130 — robust N−1 *DC-model* flow bounds

**Research-only independent construction. No grid control, buyer, bid, deployment, financial-account mutation or commercial qualification.**

The [pre-code protocol](PROTOCOL.md) fixes two existing CC-BY-4.0 PGLib v23.07 benchmarks (IEEE 14/30), symmetric non-slack-bus perturbation fractions 0%, 2%, and 10%, all existing active N−1 outages plus N−0, ratings, 1e−5 MW maximum discrepancy, false-safe rejection, the strongest ordinary full-post-outage linear-programming comparator and the NO DEPLOY alternative. The committed protocol's ancestor SHA is `e197e7f54c07e3cf122f7e88790943870e4e885a`. No candidate may drop difficult contingencies or make the test easier after seeing results.

The producer solves each connected post-outage DC network's equations, computes the sensitivity of active-line flow to each MW perturbation and returns the **exact support-function extremum for the declared independent box**, together with its actual attaining injection vector. The separate verifier instead uses **SciPy HiGHS LP with full network-balance equality constraints** for each positive and negative rated-line extreme, then independently solves the network with each claimed witness to validate Kirchhoff residual, overload and all statuses. Islanded states are `ISLANDING_UNKNOWN`, zero-rate lines are **unrated**, and any overload has a witness. A passing engineering result does **not** validate AC power flow, generation balancing, voltage/reactive limits, frequency, physical grid security or commercial demand. Existing PGLib data was curated for AC OPF, not physical DC-contingency certification.

Run from the repository root after installing included `requirements-cycle004.txt`, with no external API or credentials:

```bash
python3 -m pip install --only-binary=:all: -r requirements-cycle004.txt
python3 -m unittest tests.test_grid_uncertainty130 -v
PYTHONOPTIMIZE=1 python3 -m unittest tests.test_grid_uncertainty130 -v
python3 -m research.grid_uncertainty130 --output /absolute/new/CANDIDATE.json
python3 -m research.grid_uncertainty130_verify --candidate /absolute/new/CANDIDATE.json --output /absolute/new/RESULT.json
```

Use **nonexistent** output paths; create-only checks reject overwrites. Raw candidate witnesses are local temporary research inputs. Hosted CI retains only a small accepted/rejected independent LP receipt, input SHA-256, worst numerical discrepancies and process CPU/wall telemetry. It does not upload all candidate arrays or touch P0 originals. An independent reviewer should download the exact-head hosted artifact and check its source-bound result before any claim upgrade. If the original exact-head run fails, keep its failure and repair prospectively without changing the registered test.

**Commercial and Blue Sky decision — HOLD / NO BID / NO DEPLOY.** The point-only incumbent is not an adequate uncertainty certificate, but the *full conventional LP incumbent* is. A tie cannot justify claimed novel invention, transformative capability, a customer, a settlement, a funded successor or US$3 billion trailing-365-day complete-cost profit. Real load uncertainty, independent AC validation, contractual authority, full interventions/engineering costs, measured external billing, actual buyer outside options and paid acceptance remain unknown. The conditional math can identify an input region worth real instrument construction, not confer permission to operate electricity infrastructure. See the [PGLib benchmark](https://github.com/power-grid-lib/pglib-opf) and its [IEEE reference](https://arxiv.org/abs/1908.02788). Further real-grid research must be source-authorized and independently accepted; no physical actuation or outreach here.
