# Prospective tax-bound repair

F02 exposed a planning-input omission: $1,950 is the non-tax cost, not the
complete cost. With an authored outside price of $2,050.02, the original planner
would quote $1,950.01 despite a $20.002 interim tax provision and a $19.992 final
loss. This analytical counterexample follows the actual native tax chronology;
it is not a new observed customer or an executed extra financial arm.

Before testing the repair, freeze three additional small exact-integer cases:
outside price 205543 / tax 1:4; 270717 / 2:5; 361286 / 1:3. Common inputs are
friction 10000, non-tax cost 195000, tax deduction before closing 185000 and tick
1. Exhaustively enumerate every candidate price as an ordinary comparator.
These are arithmetic confirmation cases, not a new economic confirmation.

Version 2 receives non-tax cost and explicit provisional-tax terms. It subtracts
the tax provision at the candidate price, with no retrospective closing credit,
before deciding whether contribution is positive. The highest price remains
optimal only in this finite declared price/tax model with tax fraction in [0,1].
Unknown tax regimes or costs remain unsupported; this is not tax advice.

The original central prices/native results remain unchanged. Reproductions after
this input repair are labeled exposed engineering controls, not fresh businesses
or primary-enterprise continuation. Preserve F01/F02 and their predecessor source.
