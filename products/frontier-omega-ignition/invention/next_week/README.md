# A second week of ZTF difference photometry

**Five of six targets yielded a g/r pair within two hours. None did within ten minutes.** The first cohort had yielded four and one. Two targets appear in both cohorts. One of them, ZTF26abwpoui, had no qualifying two-hour pair in the first week. The second week yielded g−r = +0.158396 ± 0.159784 mag, with 35.44992 minutes between exposures. This is a derived measurement of difference-image light under the registered quality rule. Its formal uncertainty assumes independent per-band errors.

[Two-hour results](photometry-120m.csv) · [Ten-minute results](photometry-10m.csv) · [Complete result and abstentions](RESULT.json)

## What changed

| Stage | Second temporal cohort |
| --- | --- |
| Selection | Query public Fink/ZTF SLSN-candidate alerts from November 3 inclusive to November 10 exclusive, 2026 UTC. Eligibility precedes ranking. Keep the latest alert per target, rank by descending observation date and ascending target ID, and take the first six. |
| Source discrepancy | The class service returned 26 rows. One, ZTF26abhmfni, was dated beyond the decision cutoff. The initial source receiver at `5ef7447` withheld delivery. Applying the frozen half-open filter before ranking left 25 eligible rows for 25 targets. The UTC descriptor was also normalized from an offset to the receiver’s whole-second Z form before selection. |
| Independent selection | Standard SQLite ranks exact integer ticks from the publisher’s decimal Julian dates. It agrees with the corrected receiver on every selected ID, epoch and coordinate. Two selected IDs overlap the original six, ZTF26abrluog and ZTF26abwpoui. |
| Subsequent survey data | The six-target Fink object query returned 150 historical detection rows. Twenty-five fall in November 10 inclusive through November 17 exclusive, all with positive subtraction and a reported positive formal error. Every selected target has at least one such detection. ZTF26abrmbme has just one and cannot supply a two-band pair. |
| Scientific output | Choose the closest positive g- and r-band detections meeting the gap bound. Break ties by the g epoch, r epoch, then their detection IDs. At ten minutes all six rows explicitly withhold. The closest actual pair in this cohort is ZTF26aaywncn, at 15.95002 minutes. |
| Independent acceptance | An SQL self-join and a separate pair enumeration using the original decimal values check the per-band detection IDs, UTC and Julian times, signs, magnitudes, propagated formal errors, time gaps and no-pair decisions. The recipient verifies the pinned raw responses before recreating both CSVs. |

The new date windows and both gap bounds were recorded in draft PR #449 at 01:52:24 UTC on November 18, before either response was acquired. The public source bytes were read at 01:52:49 and 01:54:17 UTC. The two temporal samples share two objects, the same broker, the same survey and the same classification filter. The survey operated independently of this analysis. The result addresses archival availability within these two dated samples. It establishes neither a typical yield nor new telescope observations or confirmed supernova classifications. [Campaign registration](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/449) · [ZTF public data](https://www.ztf.caltech.edu/ztf-public-releases.html) · [Fink class search](https://doc.ztf.fink-broker.org/services/search/classsearch/)

## Reproduce without network access

Use Python 3.11+ from the product directory or the root of the portable instrument. Both files retain all six targets and give unpaired targets a disposition with empty measurement fields. When using a spreadsheet, import the two ZTF detection identifiers as text to preserve their full precision.

```sh
python3 -B invention/next_week/replay.py
python3 -B invention/next_week/replay.py --output /tmp/ztf-second-week
```

The first command checks the archived files. The second also writes the freshly verified scientific outputs into a new directory. The full small responses are retained once, 3,834 class-query bytes and 23,927 object-history bytes. The recipient reselects the observations and verifies the in-window projection digest without retaining a second copy. Metadata record the exact URLs and SHA-256 identities. The object query took 5.9898 seconds. Computing and independently checking the original recorded delivery from cached bytes took approximately 0.0042 seconds of process time after imports. Class-query timing, all engineering work including the failed boundary handling, maintenance, operator validation and complete cost are not measured. The conventional exact method reaches the same outcomes. There is no recorded buyer, avoided exposure, allocation, adoption or profit. [Alert source](sources/alerts-source.json) · [Object history source](sources/holdout-source.json)

**En français.** Sur la deuxième période, cinq des six cibles ont une paire g/r espacée d’au plus deux heures. Aucune n’en a une à dix minutes. Deux cibles étaient déjà présentes dans le premier échantillon. Pour ZTF26abwpoui, les nouvelles données permettent de mesurer une différence g−r là où la première fenêtre ne fournissait aucune paire admissible. Les mesures proviennent du relevé ZTF et sont servies par le courtier Fink. Les deux fichiers CSV conservent aussi les décisions d’abstention.
