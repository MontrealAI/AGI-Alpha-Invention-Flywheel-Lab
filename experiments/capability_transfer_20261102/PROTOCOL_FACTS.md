# Protocol facts and acquisition hypothesis

Checked against the [Piombo et al. primary paper](https://pangea.stanford.edu/ERE/pdf/OnoriPDF/Journals/91.pdf), DOI [10.1016/j.dib.2024.110227](https://doi.org/10.1016/j.dib.2024.110227), on 2 November 2026. This records protocol facts and unresolved interpretation, not model performance.

## Source facts

- Single-cell characterization occurred at **23°C**. Table 2 specifies a **C/20 discharge** to 2.5 V; associated fixed rests include 60, 30 and 30 minutes. The HPPC/MultiSine sequence traverses nominal 10% state-of-charge increments, with 60-minute rests and pulse tests. These costs precede module prediction.
- Module conditions span **10, 25 and 40°C**. Table 4 includes **90-, 30- and 60-minute rests**, C/3 CC-CV charging, and 0.75C discharge. Thus 25°C is a near-temperature transfer from characterization, while 10/40°C impose larger shifts.
- Figure 1 depicts the same-side-terminal ladder with interconnections on **both bus rails**. Table 3 lists nominal interconnection levels of 0, 1 and 3 milliohms.
- Table 5 row **32** labels `M2_NMC_UNAGED_1_25` unaged but assigns **Y1** to position 4. Section 3.1 identifies Y1 as the aged NMC cell. This is an unresolved metadata conflict.

## Consequences for the registered test

Do not equate a seconds-long computation with seconds-long characterization. C/20 implies roughly twenty nominal-capacity hours for that discharge alone; actual duration depends on charge delivered to cutoff. Measure elapsed acquisition from timestamps, including conditioning, rest and unsuccessful work.

Keep temperature groups separate. Do not infer thermal correction merely because nominal 25°C is close to 23°C. State whether the solver interprets the reported interconnection resistance per rail or as an effective loop sum; verify the circuit mapping before choosing a factor of two. Quarantine row 32 from clean aging-label comparisons until record provenance resolves it; do not silently relabel the measurement.

The paper describes the original release. Check the current [version 2 data](https://data.mendeley.com/datasets/zh58byr53c/2), file identities and any corrections independently before inheriting its mappings.

## One proposed acquisition change

Test **HPPC-only identification**, omitting the separate slow C/20 sweep from the production acquisition contract. Fit the full-span logged current, voltage and rest sequence jointly for capacity, OCV shape and polarization; retain the C/20 record only as blinded validation truth. Freeze this test before examining its comparison outcomes.

Short pulses alone do not identify full capacity or slow relaxation. Require a known initial conditioning state, calibrated current/time, a sufficiently informative charge span, and explicit parameter-identifiability and uncertainty checks. Do not mistake loaded cutoff capacity for equilibrium capacity. Where distinct parameter sets fit the observed trace but imply different module currents, abstain and charge the longer reference test as fallback. Test held-out cells and temperature shifts and compare the complete acquisition burden per accepted result.

This is an **unvalidated hypothesis**. Retrospective withholding can test informational sufficiency; it does not establish that a physically shortened protocol preserves conditioning or field accuracy.
