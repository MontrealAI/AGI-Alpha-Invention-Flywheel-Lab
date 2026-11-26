# Model-routing replay

**PROVEN for four archived panels.** Selecting among the frozen outputs has zero headroom for complete acceptance over the strongest fixed arm. The [public research finding](https://arxiv.org/abs/2611.34825v1) led to a decision to defer an acceptance-improving router on these portfolios and investigate the uncovered cases. [Replay scope](ROUTING-REGISTRATION.md)

| Panel | Strongest fixed arm | Perfect selector | Uncovered cases |
| --- | ---: | ---: | --- |
| Battery evidence primary | Direct and FRONTIER Ω tie at 14/16 | 14/16 | `batt-12`, `batt-16` |
| Battery evidence confirmation | Direct and FRONTIER Ω tie at 6/6 | 6/6 | None |
| Game Theory primary | Included Codex, 8/10 | 8/10 | `signal-two-causes`, `unequal-token-outcomes` |
| Game Theory confirmation | Four SmolLM2 arms tie at 0/8 | 0/8 | All eight |

On the battery cohorts the two arms agree on all 22 acceptance outcomes. The primary packet omitted the explicit BMS+PACK module heading, and the treatment constructor received two case outcomes before freezing its predictions. Recover the heading directly from the document in future original-source trials. The independently authored six-case confirmation keeps its separate receipt. [Battery report](../DPP.md)

In Game Theory primary, the two accepted Qwen3 4B cases fall within Codex's eight. The two uncovered cases concern rules open to another defensible reading. The published sensitivity gives Codex ten accepted cases under that alternate oracle. The confirmation covers four completed small-model arms on separately authored briefs. This is transfer of the diagnostic to a different inference task and portfolio. [Game Theory report](../game-theory/README.md)

## Reproduce

```sh
python3 publication/prove-advantage/research-activation/router_ceiling.py
```

The command verifies both frozen manifests and the underlying public input hashes, reuses the registered battery grader and matches every verdict by case ID. A fixture with complementary winners demonstrated nonzero headroom. Checks rejected incomplete and mismatched matrices, duplicate IDs, non-Boolean results and altered frozen bytes.

One execution took 0.037 seconds elapsed and 0.037 seconds CPU, including interpreter startup and local input reads. The experiment made zero paid requests. Original source acquisition, review attention, original model execution costs and matched complete costs were unmeasured. Choosing the least-cost acceptable workflow remains open. Actual cash savings, new prospective inference and commercial acceptance remain unobserved.

## Recovered original battery evidence

The follow-through fetched both original SolaX PDFs, matched their bytes to the published observations and visually checked their model and table headings. Page 2 of the Australia V1.2 datasheet identifies the T-BAT H 5.8 V3 BMS+PACK module and lists nominal net weight of 61.5 kg with ±1 kg tolerance. The different HV11550-A V3 battery model has a separate row. Section 3.3.2 of the Version 15.0 manual describes earlier models and cannot establish the Australian V3 weight. [Australian datasheet](https://au.solaxpower.com/uploads/file/solax-t-bat-sys-hv-5.8-t58-datasheet-en-au.pdf) · [Version 15.0 manual](https://uk.solaxpower.com/uploads/file/t-bat-sys-hv-5.8-user-manual-en.pdf) · [Frozen observations and source digests](../dpp-replay/PRIMARY-OBSERVATIONS.json)

The existing checker reproduced these results using separate copies of the cases. The full page 2 block was recovered using `pdftotext -f 2 -l 2 -layout`, and the typed scope identified the exact module and model.

| Input to the released checker | 72.2 kg, `batt-12` | 61.5 kg, `batt-16` |
| --- | --- | --- |
| Frozen observations | Insufficient | Insufficient |
| Restored source block alone | Insufficient | Insufficient |
| Corrected typed scope alone | Insufficient | Insufficient |
| Both restored | Contradicted | Supported as nominal |

An ordinary decimal comparison of 72.2 kg against the full 60.5–62.5 kg stated range and direct reading of the nominal value agreed. The original 14/16 score remains the frozen result. Automatic original-document interpretation, review effort, fresh operator acceptance and commercial value remain open.
