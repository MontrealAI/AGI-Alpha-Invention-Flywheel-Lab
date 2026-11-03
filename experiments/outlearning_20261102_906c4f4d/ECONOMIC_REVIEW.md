# Economic and native-account review

## Scope and verdict

The campaign's economic implementation is suitable for the registered **conditional simulation**, subject to source-matched confirmation and native audits. This review does not establish actual demand, revenue, measured model costs, human productivity, or a new industry. No confirmation outcomes were used in this review.

The reviewer authored the treatment constructor but did not author the economic implementation. The review concerns the coordinator's `economics.py`, `native.py`, `service.py`, `study.py`, economic protocol, and additive native schema dispatch. This is procedural separation on a shared host, not external independent experimentation or a blinded human comparison. Treatment source was not tuned against economic or confirmation outcomes.

## Defects found and corrected before confirmation

| Finding | Consequence | Verified correction |
| --- | --- | --- |
| Positive buyer ties could select the seller through the lexical fallback. | Violated the declared outside-option tie rule. A reproduced $500 seller/autonomous tie selected the seller. | The fallback now considers outside options only. The targeted counterexample passes. |
| A completed checkpoint could precede audit and export writes; resume returned directly without restoring missing public receipts or rejecting a failed audit. | Interrupted completion could leave unrecoverable public evidence, or report unaudited commerce. | The completed branch requires an accepted audit and reconstructs public account/result files. Recovery preserves the original native action hash. |
| A profitable account could be labeled closed commerce despite unresolved protocol effects. | A monetary correction charge could be mistaken for actual repair. | Outstanding protocol obligations are reported and veto closed commercial success; charging harm does not erase effects. |
| The economic text described 72-hour spacing and released unused call reserves while code used 168 hours and prepaid capacity. | Protocol and executed cost/timing semantics disagreed. | The protocol now describes 168-hour opportunities and nonrefundable provider capacity lots, with actual utilization recorded separately. |
| A later construction charge appeared to finance a method already used in K1. | Could misstate the causal financing sequence. | Initial method construction is included in opening research. The later $300 assumption is explicitly K2 deployment, qualification, and support. |
| Method call-path reuse was conflated with useful successor delivery. | A refused or failed K2 call could look like accepted capability transfer. | Call-path reuse and accepted K2 delivery are reported separately. Neither implies superiority over ordinary reuse. |

## Native accounting and acceptance inspected

- All economic actions use `JournalAccount` and its mandatory adaptive account. The new service schema adds request-bound loading, independent checking, dynamic delivery hashes, and prepared-output rebinding during both prefix and complete audits. It does not introduce a separate balance or ledger.
- Opening equity is not revenue. Each arm, demand region, and capital scenario has a separate account; results are not pooled. Existing accounts and protected campaigns are not used.
- Acquisition, qualification, and method probes are charged before their work. A purchase requires a voluntary buyer choice and voluntary provider capacity acceptance. Production capacity is funded before executing the bound delivery.
- The customer offer and accepted payment terms precede production. The service manifest binds the request, world, operating schedule, source, and delivery path. Native prepare requires independent safety across all declared challenges and complete delivery on the precommitted operating schedule. Safe refusal and refunds do not produce accepted revenue.
- Collections and profit remain distinct. Declared support and principal exposure have dated native maturity; a later release restores liquidity without creating revenue. Failed production, refunds, correction charges, development, and tax provision remain in the account.
- K2 deployment records the actual native `EARNED` or `SEED` funding receipt after K1 settlement. A positive anticipated value cannot create spendable funds. Lack of affordable funding defers the successor.
- The queue uses signed native-prefix checkpoints and deterministic action identities. Source and manifest changes are rejected. Completed-account resume restores evidence without reseeding or repeating financial actions.

## Targeted verification

Executed before confirmation:

```sh
python -m unittest experiments.outlearning_20261102_906c4f4d.test_native -v
```

**Four tests passed.** They exercise positive-tie refusal, incomplete confirmation denominators, substituted easier worlds or schedules, false native delivery artifacts, and completed-account recovery after removing public receipt files. The recovery assertion requires the same native actions and public account content. These are engineering checks on exposed development inputs, not new commercial confirmation outcomes.

The independent scientific evaluator separately owns protocol execution, hidden schedules, safety checks, and its adversarial tests.

## Conditional assumptions and limitations

Prices, demand, buyer budgets, supplier costs, competing offers, acquisition costs, and all dollar resource envelopes are authored scenario inputs. The source distinguishes them from observed bills. The positive region is favorable by construction; the adverse supplier ranges imply refusal because even their lowest cost plus outside surplus exhausts the offered quote. Neither is an estimated market probability.

Common opening research covers initial construction and all exposed development attempts, including failures. Qualification and maintenance envelopes cover deterministic construction for declined opportunities. The $300 K2 premium is an assumed deployment cost, not measured extra model effort. Actual model tokens, billing, and human labor equivalents remain unknown. CPU time is not converted into fictional worker hours.

Supplier commitments are finite prepaid 48-call lots. Unused capacity is paid capacity, not released cash. The supplier model has a declared lead time and voluntary participation, but it is not an observed procurement arrangement or a real supplier audit. Ordinary, human-plus-software, human-plus-AI, autonomous, self-service, and no-purchase alternatives are disclosed scenarios; the implementation does not measure actual human completion time.

A noncash capital opportunity-cost sensitivity is separate from native accounting profit. The native cohort is much shorter than 365 days and has a finite acquired opportunity set. Neither annualization nor extrapolated demand is used to claim the $3 billion trailing-year profit milestone.

The primary retained-method metric and its $3 materiality threshold are model-conditional. Passing a technical comparison, earning conditional native profit, delivering an accepted K2 outcome, and establishing a consequential newly economical industry remain separate claims.
