# Agent cache ceiling 259 — final public-metadata checkpoint (2026-11-24 UTC)

**Decision: reject switch-only cache warming as the flagship on these workload slices.** Retain the verified instrument and source receipts for applicable workload screening. No new serving product, customer, payment, account, or deployment. No repeated data arms.

## Frozen execution and independent receipt verification

The exact first hosted run [45325372739](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45325372739), head 8ef2cc44c7d29ce431d8ead48405e523a7ef6dd2, succeeded. Job 138213568258 logs show all seven registered tests OK, explicit PASS for each of the fixed June 1 and June 7 arms, and bash pipefail for both steps. Independently downloaded [artifact 14889416550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45325372739/artifacts/14889416550) (3463 bytes) with SHA256 126a1e4d6aa165dc1f95d06c6ddda95d7c54033a864592ae4bda3afde4a62554; ZIP CRC check passed; both registered exits zero. Both receipts bind replay.py SHA256 34d611003227673c0c29bb67ecf2ccb67c5674041154ff4fa69e9bec648b2b03. Independent local integer/rational recomputation verified all 24 price rows, class totals, prompt=cached+miss, shard session counts and malformed-call conservation. This is independent verification of the published aggregate receipt, **not** independent raw-data reprocessing.

Source: [Azure public release](https://github.com/Azure/AzurePublicDataset/releases/tag/ghcp-coding-agent-2026), Liu et al. [Agentic Coding in the Wild](https://arxiv.org/abs/2608.00101), metadata-only CC-BY. First two lexicographically sorted shards per date, no extrapolation or causal sampling claim. Actual archive identities (reported by executed collector):
- June 1: 594479134 bytes, cacad69f23d3c87ac54d788fec3f8e9c84df82c0cc9638d693340423c14e68e9; shards 0000/0001 SHA256 8004cdf1382a699590d96be4bcbb919213e56781d6fed2c21dc9d476ee82e205 / 3c3d1ebeec7b437768ab29e257e44ebed300aac2999b3fafcd2647bed286540f.
- June 7: 139262550 bytes, 8b6da125b486aea3eb37c752adf6be14d61dd1e6a584f5967bca7077fafe8c3c; shards 0000/0001 SHA256 26a6fe550da6f01d0b2cf86feb722f13951f1c9085d2a2b08f04bc92488af08a / 237cab967875654d3a2ae76557b58cc584fb4891006598bcd2dc02c8c85d623c.

| Registered date | Sessions | Turns | All calls | Excluded malformed token counts | Valid calls | Valid switch calls | Prompt | Cached | Output | Switch misses | Ambiguous misses |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-06-01 | 1000 | 3887 | 30887 | 667 | 30220 | 91 | 2022249370 | 1765416506 | 14781181 | 1091972 | 54665787 |
| 2026-06-07 | 1000 | 3972 | 32652 | 922 | 31730 | 86 | 2195702608 | 1964202102 | 22210339 | 1246609 | 53329138 |
| Descriptive sum | 2000 | 7859 | 63539 | 1589 | 61950 | 177 | 4217951978 | 3729618608 | 36991520 | 2338581 | 107994925 |

## Consequential necessary-condition result

Fixed call trace, homogeneous normalized uncached input price 1, cached/input price q and output/input r, baseline B=M+q*C+r*O. Costless oracle converts all valid nonoverlap switch misses into cache hits. It cannot save more than (1-q)*M_switch/B on this defined subset. It does not change call count, model, output, quality or physical execution. Excluded malformed-token rows are not bounded, and ambiguous rows, first calls, cross-turn changes, heterogeneous prices and unobserved workloads may behave differently. No population inference.

| q | r | June 1 switch bound | June 7 switch bound | Descriptive pooled switch bound | Pooled all-call bound |
|---|---:|---:|---:|---:|---:|
| 0 | 4 | 0.345607% | 0.389150% | 0.367528% | 76.745842% |
| 0.1 | 4 | 0.199548% | 0.217111% | 0.208541% | 43.546704% |
| 0.5 | 4 | 0.045549% | 0.047857% | 0.046751% | 9.762338% |

Additional post-run descriptive sensitivity (not a frozen estimand): even crediting **every** ambiguous valid miss as well as every detected switch miss, the pooled q=0.5,r=4 envelope is 2.205692%. This sensitivity does not identify actual switches in the ambiguous class. Across all registered price combinations, the largest pooled detected-switch ceiling is 0.445169% (q=0,r=1). At q=0.5,r=4 the mathematical required annual comparable token-bill pool to capture USD3B of gross savings even at 100% capture, zero expenses and these same ratios would be USD6.417 trillion. This is conditional arithmetic only, **not** a market size, reachable demand estimate or profit. No paid inference or serving benchmark occurred. The result is a reason not to allocate scarce construction effort to this specific proposed mechanism without materially different evidence, not a universal impossibility theorem for cache reuse.

Verification procedure (standard library, run on the downloaded public receipt ZIP):
```python
from fractions import Fraction as F
import hashlib, json, zipfile
from pathlib import Path
p = Path("github-actions-artifact-14889416550.zip")
assert hashlib.sha256(p.read_bytes()).hexdigest() == "126a1e4d6aa165dc1f95d06c6ddda95d7c54033a864592ae4bda3afde4a62554"
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    assert z.read("exits.txt") == b"2026-06-01 0\n2026-06-07 0\n"
    ds = [json.loads(z.read(date+".json")) for date in ("2026-06-01","2026-06-07")]
for d in ds:
    assert d["status"] == "PASS"
    assert d["source_sha256"] == "34d611003227673c0c29bb67ecf2ccb67c5674041154ff4fa69e9bec648b2b03"
    a = d["aggregate"]; t = a["all"]; c = a["classes"]; n = a["denominators"]
    assert sum(v["calls"] for v in c.values()) + n["malformed_tokens"] == n["calls"]
    assert all(sum(v[k] for v in c.values()) == t[k] for k in t)
    assert all(v["prompt"] == v["cached"]+v["miss"] for v in [t,*c.values()])
    assert sum(s["sessions"] for s in d["selected_shards"]) == n["sessions"]
    assert len(d["price_envelopes"]) == 12
    for row in d["price_envelopes"]:
        q,r = F(row["q"]),row["r"]
        b = t["miss"] + q*t["cached"] + r*t["output"]
        assert F(row["all_call_bound"]["exact"]) == (1-q)*t["miss"]/b
        assert F(row["switch_bound"]["exact"]) == (1-q)*c["switch"]["miss"]/b
t = {k:sum(d["aggregate"]["all"][k] for d in ds) for k in ds[0]["aggregate"]["all"]}
s = sum(d["aggregate"]["classes"]["switch"]["miss"] for d in ds)
a = sum(d["aggregate"]["classes"]["ambiguous"]["miss"] for d in ds)
for q in (F(0),F(1,10),F(1,2),F(1)):
    for r in (1,4,10):
        b = t["miss"]+q*t["cached"]+r*t["output"]
        v = (1-q)*s/b
        print(q,r,v,(1-q)*(s+a)/b,(1-q)*t["miss"]/b,F(3000000000)/v if v else None)
```

## Resource and acceptance checkpoint

Two hosted arms process CPU 10.868717659s, summed wall 34.232692554s, peak reported process RSS 145656 KiB. Independent local outer command user 1.01s, sys 0.23s, wall 0.84s, RSS 95632 KiB. These exclude other work and model/host billing remains unknown; no actual new spending, account, authority, obligations or real transactions.

- ACHIEVED: frozen two-arm public metadata execution and independent receipt arithmetic; registered evidence now complete, no new replay.
- ACHIEVED: refreshed main 39e76570c851b3527d78a526053a9ea2a611a993, AGENTS, resource/operator/developer guides and overnight022 handoff records. Latest observed release collection head connected014-3cc6bc95a13f991b5158e5bd5064b766b21632a4 published 2026-11-24 01:08:28Z; existing push release workflow 45296234913 success. New main release run 45327425758 in progress at inspection; no success claimed.
- REJECTED for new flagship: switch-only price-reduction route on these slices. Keep strong incumbents; no serving or commercial advantage established. Alternative future arrangements must demonstrate new beneficiary outcomes against complete alternatives, not just larger token counts.
- BLOCKED: original finance task actual status/checkpoint and exclusive writer remain UNKNOWN, PR40 head ced6c1cb004887dcdafaea59a2976020be649f8e unchanged; PR553 head 1851100612b8c80a1852f413057bdb635de62d3a unchanged. Prior P0-255/P0-258 isolated successes and all failures preserved. No overlapping source writes, signer/account changes or competing ledger.
- UNQUALIFIED: protected financial integration, new native profit, real commerce, recursive improvement and USD3B trailing-365 complete-cost milestone. No new financial action. Continue independent Blue Sky construction only for a newly evidenced consequential residual; do not run this completed study again for new confirmation.
