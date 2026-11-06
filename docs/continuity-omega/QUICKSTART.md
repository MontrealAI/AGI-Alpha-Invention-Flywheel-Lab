# CONTINUITY Ω · one promise, independently checked in a synthetic drill

**English** · [Français](QUICKSTART.fr.md) · [Research paper, edition 1.1.0](../continuity-omega-paper/README.md)

## Qualification note: the historical v0.1 source

The paper's reproduction is pinned to commit [`a755d0375693465f8f31c0c919cc186eae74bbcc`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/a755d0375693465f8f31c0c919cc186eae74bbcc/continuity_omega). Its **29 authored implementation tests pass**, but a separate five-probe examination reproduces one nominal positive control, acceptance of Boolean-valued money, an uncaught exception for malformed structure, an `inspect` view that returns the saved passport without a fresh audit after evidence is changed, and a coherently rewritten input accepted after its editable digest is recomputed. The last case illustrates the already disclosed source-authenticity boundary. These observations are evidence of weaknesses and a trust limit, **not qualification of the checker, real recovery or customer delivery**. The separately owned PR 279 hardening candidate is not integrated or qualified by this publication. See the [complete evidence guide](../continuity-omega-paper/EVIDENCE.md) and [recorded counterexamples](../continuity-omega-paper/evidence/COUNTEREXAMPLES.json). Commands below exercise the checked-out code; reproducing these historical observations requires the paper's pinned-source procedure.

> **The restored system is not the same as the restored business.**
>
> **Find what the recovery missed. Build a route that keeps the promise.**

**Executable research prototype v0.1.0, synthetic only.**

```sh
python3 -m continuity_omega demo --out /tmp/continuity-omega-demo-001
python3 -m continuity_omega verify --in-dir /tmp/continuity-omega-demo-001
python3 scripts/continuity_passport.py --in-dir /tmp/continuity-omega-demo-001 --language en
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
python3 -m unittest discover -s tests -p 'test_continuity_passport.py' -v
```

Choose a new evidence directory. The reading companion displays the saved result in English; use `--language fr` for French. It performs **no fresh audit**. The separate `verify` command prints a new result but does not update the stored `AUDIT.json`. See [Read the outputs](OUTPUTS.md) to save a complete localized report, read a refusal and understand every recorded status. The prototype’s original English output remains unchanged.

Read [the prototype guide](README.md) for product framing, the 1,900-unit synthetic worked example, negative controls, limitations and NIST references. Read [the proposed pilot](REAL_PILOT.md) for the exact next customer acceptance gates and full economic challenge.

This package does not scan for vulnerabilities, contact anybody, reserve real capacity, accept customer terms, access real business records or change financial authority. Only the synthetic rehearsal is runnable today. The actual paid service and market remain unproven.

