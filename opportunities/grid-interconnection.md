# Research lead: faster reliable grid-interconnection decisions

**UNADMITTED · public-evidence research only · no physical grid control**

- Beneficiaries: generation/storage developers and grid-study teams; indirect beneficiaries include electricity users.
- Desired productive outcome: materially faster, reliable decisions about which project configurations can connect safely and at acceptable complete cost.
- Evidence: Lawrence Berkeley National Laboratory's [Queued Up](https://emp.lbl.gov/queues), accessed 2026-10-29, reports more than 2,060 GW seeking connection at end-2025 and median request-to-operation duration exceeding five years for projects built in 2025. This establishes scale and delay, **not** the causal bottleneck or a profitable service.
- Strong alternative to investigate: current utility/ISO cluster studies, competent power-system analysis and reformed queue procedures with the same data and engineering permissions. No baseline performance has yet been measured here.
- Structural hypothesis (not a finding): counterexample-guided refinement from formal verification might accelerate screening of candidate network configurations by reusing independently checked infeasibility witnesses, while retaining full engineering checks for surviving candidates.
- Mapping to test: candidate program → interconnection configuration; failed specification → violated network constraint; counterexample → reproducible violating operating condition; refinement → exclude only the proven invalid configuration class.
- Decisive failure: a reused witness excludes a genuinely feasible configuration, or ordinary caching/solver warm starts match all gains at lower complete cost. Distribution shift, nonlinear dynamics, unavailable private data, reliability obligations, and changing network assumptions can break transfer.
- Cheapest next step: establish an openly licensed benchmark with a domain-qualified independent checker; compare reuse against ordinary caching and unrestricted solver baselines on held-out network configurations. No benchmark has been selected or downloaded in this starter.
- Unknown: actual study-team bottleneck, full legal/data permissions, demand, price, liability, qualified human review effort, complete costs and successor benefit. Do not infer these from queue size.

This is one research lead, not the chosen flagship. Screen additional materially different opportunities before admission. The executable bootstrap is unrelated plumbing and cannot answer this question.
