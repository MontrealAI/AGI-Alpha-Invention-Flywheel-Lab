# OUT-ACCELERATE analytical witness

This is an authored, exact, deterministic illustration of a two-stage pipeline. It is **not an empirical AI benchmark**, a measurement of real execution speed, an autonomous invention run, or a commercial result. The elapsed-time and worker-time parameters, capability effects, and applicability domain are stipulated. Every input is public and prespecified; the successor is a changed workload, not a concealed holdout.

Run with Python 3.9 or newer, using the standard library only:

```sh
python3 acceleration_witness.py
```

The command writes `results/results.json` and `results/summary.csv`, checks the exact recurrence and expected totals, and verifies the generated output contracts. It uses no model API, network service, stochastic sampling, or wall-clock timing. A custom destination can be supplied with `--output-dir PATH`.

## Model and contracts

Jobs pass through one construction server and one independent verification server. The servers can work concurrently on different jobs. Each server handles one job at a time; the intermediate queue is unlimited. Acquisition/adaptation must finish before a batch starts. Batches run consecutively.

The accepted output is the exact integer value required by the input domain. The primary and successor tasks require `3*x + 7`. A trace contains the input and affine coefficients; the certificate checker verifies both its applicability and the exact answer. A full checker supports both affine and quadratic tasks. Incorrect answers fail both checkers. An attempted affine-certificate transfer to a quadratic task fails even at an input where the numerical answers coincide. This is a small executable applicability contract, not a claim of novel proof technology.

The faster construction engine is assumed already available to every policy at zero incremental acquisition cost. Thus the baseline comparison deliberately gives local acceleration a favourable starting condition. The producer and checker capabilities incur the explicit acquisition costs below. A checker without the required trace falls back to full verification; its construction cost remains charged.

| Parameter | Primary | Prespecified successor |
| --- | ---: | ---: |
| Number of jobs | 12 | 10 |
| Inputs | Integers 1 through 12 | Integers 101 through 110 |
| Ordinary construction duration `d` | 4 | 8 |
| Full verification duration `v` | 12 | 20 |
| Available construction speed factor `s` | 4 | 4 |
| Trace production overhead `delta` | 1 | 1 |
| Certificate verification duration `c` | 1 | 2 |
| Full bundle acquisition/adaptation `S` | 24 | 8 |

All durations are abstract time units. Worker-time is the sum of work at both stages, plus acquisition/adaptation. It differs from elapsed time because stage work overlaps.

| Acquisition component | Trace only | Checker only | Both together |
| --- | ---: | ---: | ---: |
| Search | 4 | 4 | 4 |
| Producer construction | 6 | 0 | 6 |
| Checker construction | 0 | 6 | 6 |
| Integration | 2 | 2 | 4 |
| Qualification | 2 | 2 | 4 |
| Total initial acquisition | 14 | 14 | 24 |

The successor separately charges 4 units for adaptation and 4 for requalification. Rebuilding adds the entire original acquisition ledger to those 8 units. The comparison experiment does not establish that an agent can select the best policy without paying for search and failed alternatives. No discovery-policy gain is claimed.

## Results

Every main condition produces and accepts the same 22 correct products.

| Policy | Primary elapsed | Successor elapsed | Total elapsed | Total worker-time |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 148 | 208 | 356 | 472 |
| Faster construction only | 145 | 202 | 347 | 376 |
| Trace producer only | 163 | 217 | 380 | 516 |
| Certificate checker only | 162 | 216 | 378 | 494 |
| Complementary bundle | 85 | 100 | 185 | 214 |
| Bundle plus faster construction | 49 | 40 | 89 | 118 |
| Same combination rebuilt on successor | 49 | 64 | 113 | 142 |

The equal-content conventional comparator is a supplied, fixed ordinary workflow that executes the same combined design and pays the same costs. It therefore **ties at 89**, without invoking an optimizer. A separate transparent arithmetic check finds that this design also has the minimum makespan among the seven declared policies. That finite minimum is not evidence of autonomous discovery, cost-free model selection, or global optimality. The example gives no advantage to a label, a special kind of intelligence, or a uniquely transformational algorithm.

The seven-condition illustrative sweep is outside any one policy's acquisition account. Its summed worker-time charges are 2,332; if all seven complete two-batch conditions were run consecutively, their stipulated elapsed times would sum to 1,848. Those are model totals, not measured computer resources. Selecting a policy through an actual experimental sweep would need to charge the sweep itself rather than attributing only the winning run's costs.

The main contrasts isolate the intended mechanisms:

- Faster construction alone barely changes elapsed time when verification remains the bottleneck.
- Either new component alone is worse after its acquisition cost.
- Their combination changes the bottleneck and makes the already available faster constructor more useful.
- Reuse avoids 24 units of rebuilding, while successor adaptation and qualification remain charged.
- With just one primary job, the complete combination takes 27 units; baseline takes 16 and faster construction takes 13. Acquisition loses over this short horizon.
- A deliberately forced invalid transfer completes no accepted products. The same output contract stays in force. The fallback full checker accepts the correct products and pays its full modeled cost.

The JSON preserves per-job traces, ledgers, negative controls, and all check outcomes. The CSV is the compact manuscript table.

## Exact finite-horizon proposition

For a nonempty homogeneous batch of `n` jobs with construction time `d`, verification time `v`, and non-overlapping acquisition time `S`, the exact makespan is

`T(n; S,d,v) = S + d + v + (n-1) max(d,v)`.

To see this, construction of job `i` ends at `S+i*d`. Verification follows the recurrence `V_i = max(S+i*d,V_(i-1))+v`, with `V_0=S`. If `v >= d`, verification remains occupied after the first job arrives, yielding `S+d+n*v`. If `d >= v`, every verification can finish before the next constructed job arrives, yielding `S+n*d+v`. These are the two branches of the displayed expression.

Now let ordinary full verification satisfy `v >= d/s`. Local acceleration alone has makespan `T_local = d/s+n*v`. A complementary producer/checker bundle incurs acquisition `S`, adds trace cost `delta` to construction, and reduces verification to `c`. Assume its transformed construction duration `d/s+delta >= c`. Then

`T_bundle = S+c+n*(d/s+delta)`.

Subtracting gives the exact strict improvement condition

`n*(v-d/s-delta) > S+c-d/s`.

Equality is a tie. A nonpositive left-hand coefficient gives no general long-horizon benefit. For the primary parameters, the combined design beats local acceleration when `10*n > 24`, hence for integer `n >= 3`. This is a statement about the declared schedule and assumptions, not a universal theorem that constructing instruments is preferable.

The assumptions include correctness and domain-validity of faster verification. Those are premises of the time comparison, with a deliberately narrow executable contract here. A real application must establish them independently and measure the actual durations, failures, demand, and maintenance burden.

## Conditional serial-floor observation

For an optional manuscript discussion, suppose comparable accepted advances have durations `a_k = h + u_0*rho^k + s_k`, where `h >= 0` is irreducible serial work, `u_0 >= 0`, `0 < rho < 1`, and `s_k >= 0` is the separately charged setup/verification burden. This is an assumed model, not a result of the witness.

For `N` advances numbered from zero,

`sum(a_k) = N*h + u_0*(1-rho^N)/(1-rho) + sum(s_k)`.

If the average setup burden converges to `s_bar`, the average duration converges to `h+s_bar`. A positive floor prevents unbounded long-run throughput. Growing setup or verification costs can erase the nominal gain; monotonic acceleration does not follow merely from `rho < 1`. The advances must use a comparable outcome unit before comparing their rates. Do not present the geometric term as evidence of observed compounding.

## Checks performed

The script checks the exact schedule against its closed form, all published totals, loss from isolated components, charged rebuilding, equal acceptance across the main policies, corrupted answers, incorrect certificate coefficients/domain/input, invalid transfer, verified fallback, short-horizon loss, and the algebraic break-even condition over multiple horizons. The full verifier implements the affine and quadratic specifications separately from the producer's target helper. These are regression checks for this authored illustration. They are not independent confirmation of a research hypothesis.
