# Auditing performance, without skipping acceptance

The development comparison preserves the complete native audit before every new
journal write. It indexes native actions and hashes canonical action prefixes once
inside each audit. The source validator checks once before and again after the
unchanged per-artifact semantic checks; standalone `check_job` keeps its own source
checks. No persistent audit or semantic success cache was introduced.

On the same 14-day, eight-customer development configuration, the source-906
baseline used 26.204 CPU seconds. Prefix indexing alone used 31.078 seconds and is
preserved as a negative end-to-end result. The combined batch source validation
and prefix implementation used 14.339 seconds: a measured 1.83-fold improvement,
short of the fivefold target. Full financial summaries, accepted/paid jobs,
customer counts, native action counts and event counts match exactly. These are
engineering measurements on one authored world, not commercial confirmation or a
population throughput guarantee.

The 400-row hash microbenchmark agrees on every prefix and isolates a larger
hashing improvement; its repeated action rows are a byte-shape fixture, not a
second executable financial history. Benchmark receipts bind their source copies.
RESULT.json binds the final owned source files. Final composed qualification is
required separately. The development test log preserves three multiprocessing
harness errors caused by executing its wrapper through stdin; the correct CLI
recheck passed all three tests. No adverse run or harness error was suppressed.
