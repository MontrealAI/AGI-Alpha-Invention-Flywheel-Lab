# Public adaptive012 package replay

The original byte-identical public package passed all **160 native financial and 160 operating semantic replays** from extracted frozen source. This reproduces existing evidence; it is not a fresh commercial sample.

- Archive SHA256: `29aaa1e6ec81b145753550b3394c1684f503f804e8bc565af404d13e8d92be34` (20 parts, 59,775,697 bytes; CRC verified).
- Frozen source: `cff284ffdbd930f63c2dd182870aa9f952672624`, source SHA256 `805a6e047ec655b161ca1d0e76e4c479af7134b3f3d0a060c9de31f21dc19dcc`.
- Completed: `2026-10-30T18:19:45.611014+00:00`; wall 501.936 seconds; audit CPU 1,913.454 seconds; sampled peak RSS 397,619,200 bytes.
- No private signing keys, paid calls, outreach, real transactions or changes to frozen source/protocol.

See [receipt](RECEIPT.json), [exact audit output](audit.stdout), and [parsed audit](AUDIT.json). `EXECUTION.raw.json` preserves the original monitor output; its CPU/RSS values used a namespace-local PID against host `/proc` and are invalid. Correct CPU is audit self-measurement and correct sampled RSS is in [supplemental process monitor](PROCESS_MONITOR.json). Wall and scratch measurements remain valid.

Use a normalized absolute output root as documented in `artifacts/README.md`; the frozen package parent-relative path defect remains preserved.
