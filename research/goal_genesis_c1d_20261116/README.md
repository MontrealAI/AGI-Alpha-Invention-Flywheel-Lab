# 🌌♾️ GOAL GENESIS Ω — A strictly improved signed-autoconvolution bound

**MONTREAL.AI · November 16, 2026 · Mathematically certified candidate, independent academic review pending**

## Result

The signed third autocorrelation constant `C_1d` is the largest constant such that

```
 max_t |∫ f(t-x) f(x) dx| ≥ C_1d (∫ f)^2
```

for every real integrable function `f` supported on `[-1/4, 1/4]`.

A signed step function with **4,800 equal cells** and the exact integer weights in `certificate4800.json` gives

```
C_1d ≤ 2798811552689704931099200 / 1919999999995200000000003
     = 1.4577143503628656...
```

This is **strictly less** than the strongest bound `1.4578548849219886...` listed on November 16, 2026 in the optimization-constants registry (a self-archived 800-cell result of SCiEL, October 21). The exact difference is positive by integer cross-multiplication; the numerical improvement is approximately `0.000140534559123`.

**Scope:** A new explicit finite *upper-bound witness*, not an exact determination of `C_1d`, a physical discovery, automatically peer-reviewed mathematics, or evidence that MONTREAL.AI is the world's leading AI institution. The discovery process used seeded L-BFGS-B numerical optimization, but **no solver output is trusted in the mathematical proof**.

## Mathematical certificate

Let `n = 4800`, `h=1/(2n)` and integers `w[0], ..., w[n-1]` be those in the JSON certificate. Define `f(x)=w[i]` on cell `[-1/4+i*h, -1/4+(i+1)*h)` and zero elsewhere. Multiplication by a common nonzero scale changes neither side's ratio, so the reported `normalization_scale` is provenance-only.

The convolution `f*f` is continuous and piecewise-linear with knot spacing `h`. At knot `t_k=-1/2+(k+1)*h`, the convolution equals `h * sum_{i+j=k} w[i]w[j]`. The maximum of the absolute value of a piecewise-linear function on each cell interval occurs at a knot. Consequently,

```
C_1d ≤ (2*n)*max_{0≤k≤2n-2} |sum_{i+j=k} w[i] w[j]| / (sum_i w[i])².
```

The exact peak is attained at `k=4799`, with peak absolute integer convolution coefficient `3498514440862131163874`, and all **9,599** knots were checked. It yields the exact fraction above. Note that the certificate weights have sum `4799999999994`, nonzero.

The incumbent fraction used for strict comparison is

```
38534420343892614563110610373646557184000
------------------------------------------------------
26432274393314964174848236787785831382961
```

Source: https://teorth.github.io/optimizationproblems/constants/1d.html (accessed Nov 16, 2026). The registry marks the prior best with `*` and notes that its 800-cell raw data is access-restricted; our new witness is included in full and independently reproducible.

## Two different exact verifiers

Run from this directory using **Python 3 standard library only**:

```
python3 -S verify_exact.py certificate4800.json
python3 -S verify_ntt.py certificate4800.json
python3 -S -m unittest -v test_proof.py
```

- `verify_exact.py` uses three carry-free **big-integer Kronecker products** (positive-positive, negative-negative and positive-negative), reconstructs every signed coefficient, independently directly sums selected knot coefficients, computes the exact fraction and compares it by rational arithmetic.
- `verify_ntt.py` independently squares the signed coefficient sequence using **three modular NTTs**, then reconstructs all coefficients by CRT. The product of primes is proven greater than twice an a priori bound on every possible coefficient, so signed recovery is unique. It recomputes the exact fraction and performs the same strictly stronger-than-incumbent comparison, without importing the first verifier.
- `test_proof.py` contains **nine tests**, including exact hand-checkable small examples, falsified rational numerator, tampered unselected weight, forged maximizing knot and peak, invalid coefficients, changed length, and a valid but non-improving constant function.

All nine tests passed locally, and `reproduce.py` recomputes both frozen exact verdicts. Exact outputs are in `verdict4800.json` and `independent_ntt_verdict.json`. The frozen JSON certificate SHA-256 is

```
c3f7e58875ddc3759703374e6bd34a68b074aae5a002ae36ee9141208a3c4200
```

## Discovery lineage and fair comparison

The seeded reference was the *publicly accessible* 600-cell `[AER2026]` construction at commit `4b3bbd2a44db92442e4ebb4e64e0bb90f229aad1`, not the access-restricted 800-cell incumbent. Its public reported value is approximately `1.4599890469053831`. We transcribed the 600 real coefficients, quantized them to one-millionth (the resulting initial score was `1.459989201874218`), and investigated differentiable soft maxima of signed autoconvolutions, high-temperature continuation, multiresolution splitting to 1,200/2,400/4,800 cells, and seeded perturbation/restarts. The resulting continuous candidate scored `1.457714350321628` by both NumPy direct convolution and SciPy FFT convolution. Rounding every weight to a multiple of `10^-9` gave the complete exact JSON certificate.

The optional `discovery.py` searches for new real-valued witnesses from the published, quantized 600-cell `seed600.json` (NumPy/SciPy required). It is **not an exact historical optimization replay** and is not an input to either final proof verifier. The precise frozen integer certificate is the only mathematical witness needed. An additional local downloadable research bundle retains the intermediate `best4800.npy` floating-point array for provenance; that binary is not necessary for reproducing the exact inequality. The optimization history is an exploration record, not a fully deterministic reproduction claim across different numerical libraries/platforms. The final integer witness and complete exact verification *are* deterministic.

The incumbent's **actual strongest listed value** is used, not an intentionally weak public-seed comparator. We have not established that the old self-archived incumbent is independently reproducible, because its raw Zenodo attachment was restricted when checked, and we have not established that no unpublished better construction exists.

## Admission and external review

1. **Mathematics:** the new exact upper bound passes two computationally independent exact checkers on all 9,599 knots, with negative controls. This qualifies the narrowly defined mathematical witness.
2. **Novelty/prior art:** current maintained registry checked November 16, 2026 lists a weaker bound, but mathematical priority is not confirmed until domain-expert/maintainer review and wider literature search.
3. **Institution:** one valid mathematical improvement does **not** establish eight-mechanism causal superiority, recursive successor benefits, external commercial outcomes or `#1 in AI` status.
4. **Next step:** have independent mathematicians and the registry maintainers review the exact rational inequality and certificate; test fresh unselected optimization problems under matched budgets to establish repeatability rather than relying on one case.

This new positive result is **separate from**, and does not replace, the active physical/economic Blue Sky 064 candidates (currently HOLD) or the older degree-diameter unsuccessful search. No paid model API, outside spending, external outreach, payments or real-world physical action was undertaken.
