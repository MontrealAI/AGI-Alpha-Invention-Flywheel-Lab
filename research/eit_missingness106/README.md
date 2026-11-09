# EIT106: identify the external physical source obstruction, without declaring it solved

[Before-execution protocol](PROTOCOL.md) was frozen at `658ad434c4c3c76335ca59e29b92f6628bccde8e` on original main `de9546ef9083f64a25186f1c5163e3a3a4eaeae5`.

**Purpose:** The independently measured, public [SpectraEIT phantom data](https://zenodo.org/records/7192883) is an appropriate possible input to a *future* outcome-first sensing experiment. EIT105 owner PR #309 retains a genuine failure under a strict finite-voltage contract (run 42551099436) and a different genuine failure under an explicit `NA`-masked contract (run 42551635036). Rather than generalize from a Python exception, this independent diagnostic counts the CSV's real missing and malformed cell representations, preserving source identity and all refusals.

### Reproduce from the original source

```sh
python3 -m unittest tests.test_eit_missingness106 -v
python3 -O -m unittest tests.test_eit_missingness106 -v
python3 -m research.eit_missingness106.diagnose
```

The last command downloads **only** the registered 9.2 MB `circle_petg.csv` (source maximum 15 MB, public CC BY 4.0), validates its upstream MD5 and records a separate SHA-256. It never prints physical voltages or raw bad tokens. Each measured cell is counted as finite, exact `NA`, empty, whitespace, padded `NA`, padded finite, nonfinite or other. The result reports channel and injection-location distributions and CPU/wall process time. The source is neither repaired nor reinterpreted. Unknown cell representations are not accepted as voltage.

**Current scientific decision: NO BID / NO DEPLOY.** The diagnostic can explain what broke the old parser and whether a separately registered masking rule is worth investigating. It cannot prove why a channel is missing, create a new injection, achieve physical sensing, validate a beneficiary decision, establish specialist superiority, determine buyer willingness to pay, or fund a new enterprise. The original EIT105 branch, original signed account, other owners and all published releases remain untouched.

One source fetch, one bounded diagnostic, no retuning, no paid API or account key. Host/model billing remains unknown. Preserve a failed diagnostic result as failed instead of changing thresholds or source identity. A future constructive experiment would need an explicit beneficiary use, genuinely withheld specimens, physical injection-unit budget, competent complete alternatives, real delivery obligations and independently accepted outcomes.
