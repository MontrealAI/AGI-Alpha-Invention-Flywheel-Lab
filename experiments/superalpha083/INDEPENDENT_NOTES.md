# Verification and limits

Independent polynomial GF(256) checks cover 65,536 products, all 16,384 survivor subsets per method, exact helper minima, 198,240 decoder cases, 5,880 actual minimum-read repairs and 9,440 successor cases. All pass. Five tests include seven corruption probes and Python -O refusal. Source and preregistration hashes fail closed.

Correctness is not Super Alpha: ordinary methods meet the service and outperform the candidate on relevant metrics. Original timings describe full-source decoding; supplementary timings separately cover minimum-read repairs. Neither is network performance or complete business cost.

Original protocol deviations: only 24 final search states were retained, not a full proposal trace; ties use lexicographic order, not a complexity measure; candidate joint mutation and controls' dedicated placement search have unequal opportunities. No causal superiority claim is justified.

The initial reviewer recorded provenance mismatches without rejecting them. This was corrected and tested before publication; REVIEW_HISTORY.json preserves the earlier identities. Original producer source is unchanged. JSON compaction preserves every outcome; byte-hash bindings are requalified separately. No private data or account authority exists in this package.
