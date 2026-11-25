# Game Theory LLM · private information and certified strategies

Owner ambition: **Build frontier AI LLM for Game Theory.**

The first milestone is to convert a sourced strategic brief into an auditable simple game and report how a change in information rights affects its value. A separate author supplies previously unseen English and French briefs. The constructor receives the briefs and the interface below. The author retains the intended models, eligible comparisons and expected refusals until predictions are frozen. This milestone explores formalization and verification. A learned specialist and improvement over a strong ordinary workflow remain separate gates.

## Scope and acceptance

Two opposing players receive privately observed types drawn from a jointly known finite distribution. They each choose one action simultaneously. Payoffs are zero-sum. The source provides the same ordered action sets and row-player payoff table for each state. A brief lacking a required fact or describing a materially different game must be withheld with a source-grounded reason.

The declared game contains `actions: [row_count, col_count]` and `states`. Each state contains exact positive `p`, `row_type`, `col_type` and `payoff`. Probabilities sum to exactly one. Payoffs are integers or rational strings. Distinct states may share the same observed type pair. This must not give either player more information.

Report the unrevealed game and only the disclosure comparison allowed by the brief. A comparison may reveal the other player's realized type to the row player, to the column player, or to both. Every policy must choose a probability distribution over accessible actions at each observation. Calculate exact worst-case lower and upper bounds for the supplied policies. The numerical optimization proposes policies. The exact bounds determine certificate quality.

Use the exhaustive pure-plan strategic form with an ordinary linear-programming solver as the independent mathematical comparison on small exact inputs. Compare whole-case formalization in a competent same-model direct arm where feasible, counting exact facts, observations, source excerpts, withheld decisions and usable outputs. Keep optimization, semantic interpretation and end-to-end model quality separate. Compare a constructed mechanism with an equivalent conventional solver before any productivity claim.

A mechanism is eligible for scoped retention when the exact certificates contain the comparator values within a width of 1e-7 times the maximum absolute payoff, the comparator agrees on admissible disclosure directions, refusals hold and execution can be repeated. A technically correct solver alone cannot establish the ambition. Key blockers include unsupported game families, unverified semantics, true training gains and independent custody on real strategic data.
