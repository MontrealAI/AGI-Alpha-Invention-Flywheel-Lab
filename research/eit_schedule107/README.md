# EIT107 — is the missing-data encoding an instrument schedule?

**Research-only, source-locked, not an enterprise release or physical acceptance.**

The independently audited EIT106 input showed 52,640 measurements with 12 finite electrode voltages per row, exact `NA` and blank `E_16` tokens. It did not establish which electrodes the actual apparatus sensed or why blanks occur. EIT107's registered question is narrower but decisive for constructing a legitimate next physical-data contract:

> Do all repetitions of a given *ordered* current-excitation pair have one identical complete F/N/E electrode representation mask, independent of phantom identity and pose?

The preregistration is `PROTOCOL.md` at **929f0b0fb1fb70a9298d520bfa668536b4133b27** and comes before the implementation. The program independently downloads the one exact original CC-BY-4.0 third-party CSV (MD5 and SHA256 pinned), inventories the conditional masks without inserting any voltages, and publishes counts and a YES/NO H1 conclusion. The positive conclusion would identify a regular *CSV representation schedule only*, not prove a particular ground electrode, physical masking semantics or a reduction in actual injection count. A negative conclusion rules out pair-only projection. Both retain NO BID / NO DEPLOY.

```sh
python3 -m unittest tests.test_eit_schedule107 -v
python3 -O -m unittest tests.test_eit_schedule107 -v
python3 -m research.eit_schedule107.diagnose > /tmp/EIT107_SOURCE_SCHEDULE.json
```

The last command makes one bounded public-source retrieval. No private evidence or credentials. The GitHub workflow uses exact checkout and publishes compact JSON with source SHA, per-pair ternary masks, counterexample counts, distinct specimen keys, resource measurements and a preserved decision. Source or parsing failures are actual failures, not accepted on a retry or hidden by a changed protocol.

**Alternatives for the ultimate productive outcome:** a full specialist 16-electrode tomographic system or independent direct property measurements; the ordinary measured-channel-only inversion; self-service or no purchase. They require end-use and cost parity before adoption. EIT107 proves none of their values, no buyer willingness, no real revenue and no recursive advantage. It operates no Account/JournalAccount and touches no P0 owner history or obligations. Existing EIT105 strict and masked failures remain in their original runs.

**Next if H1 is supported:** use external apparatus documentation to specify the reference/ground and timing meanings and then preregister a new physically meaningful 12-channel inference/withheld-phantom acceptance experiment against complete specialist alternatives. Do not treat this diagnostic as that experiment. If H1 is rejected, investigate non-pair determinants or select a different physical opportunity instead of adjusting these exposed data to achieve a positive.
