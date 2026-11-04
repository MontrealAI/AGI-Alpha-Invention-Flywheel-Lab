# A self-service SQL baseline for KPI variance

One parameterized SQLite query produced the same complete KPI-variance delivery as the incumbent Python procedure on **132 of 132** fixed synthetic orders. Both paths passed the repository’s independent source and delivery checks on every case. The checker rejected a one-cent modification to the first SQL output with `KPI_ARITHMETIC_OR_COMPLETENESS`. All 1,320 source metrics were represented. No operating account was opened or queried.

## What was compared

The input is an existing synthetic JSON order containing prior and current integer-cent values. The SQL query computes signed changes, direction, exact fractional change as a numerator and denominator, the undefined ratio at a zero prior, sorted rows and monetary totals. Both paths use the same ordinary identity intake adapter and public delivery contract. The SQL result is computed independently of the incumbent arithmetic and checker. The query and its envelope were authored once for this engineering check. Repeating it calls no model.

All 132 public slots at generator seed 392900, ordered indices 0–131, were fixed before scoring. These are synthetic examples from an existing generator. The comparison adds a self-service implementation of the KPI component. It does not benchmark full reconciliation, a combined basket, actual human speed or adoption. A separately qualified CSV backend already exists for conventional reconciliation. [Prior CSV control](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/bc8f1560dd1c1c90cdc246a8469a249024094fac/docs/mechanism-harness/CANONICAL-CSV029.md)

## Measured work

| Operation across 132 orders | Elapsed ms | Process CPU ms |
| --- | ---: | ---: |
| Shared fixture generation | 7.70 | 7.50 |
| SQL production, including JSON transport and identity adapter | 43.23 | 42.80 |
| Independent checking of SQL deliveries | 73.25 | 72.78 |
| Conventional Python production | 13.13 | 12.87 |
| Independent checking of conventional deliveries | 74.69 | 73.75 |

Opening and closing one in-memory SQL connection took another 0.19 ms elapsed. Both paths consumed the same 131,100 serialized input bytes and produced 325,294 bytes of semantic output. These timings are one local observation on a shared host. They exclude dependency installation, query design and the remaining enterprise lifecycle. Local host billing and human authoring, training and operating time are unmeasured. No paid service or network call was needed for either production path.

The result supports offering ordinary SQL as a complete alternative for these KPI fixtures. The specialized Python producer also tied on quality and took less production time in this run. Neither comparison establishes a commercial margin from replacing an analyst.

## Reproduce

Use the [pinned public source](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/bc8f1560dd1c1c90cdc246a8469a249024094fac) and Python with a SQLite build supporting JSON functions and ordered aggregation. The measured environment was Python 3.12.14 and SQLite 3.53.1 on x86-64 Linux. From this appendix directory, run

```sh
python compare.py --repo /absolute/path/to/AGI-Alpha-Invention-Flywheel-Lab > replay.json
```

The runner checks the five pinned mechanism, fixture and checker files against the Git commit. It reports timing, failures and a digest of every input and both semantic outputs. Expected digest `4be91d7f25371790e34d46ebfc5175f15b344ec33c243c27a261c6ebf67d50dc`. The observed run passed with zero failed cases. [Frozen local protocol](PROTOCOL.md) · [Executed query](kpi.sql) · [Runner](compare.py) · [Machine-readable receipt](EVIDENCE.json)
