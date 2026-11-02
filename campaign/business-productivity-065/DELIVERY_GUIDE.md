# Inventory policy delivery guide

## What this package supplies

For the pinned public OR-License finished-goods network, the accepted output specifies a replenishment policy and stock parameter for each of54 inventory points, plus six central-warehouse/product service commitments. A separate explicitly modeled scenario raises every daily demand observation to `ceil(1.2 × original)` while keeping network and cost inputs fixed.

The original task and Apache2.0 attribution remain in `inventory061/inputs/` and `inventory061/LICENSE-OR-License.txt`. Inputs originate from [NineAbyss/OR-License, pinned commit2bda4b8](https://github.com/NineAbyss/OR-License/tree/2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47/task13_inventory). Public task labels are not observed customers. The two scenarios are not a historical train/test split.

## Read the policy correctly

- `inventory_policy` identifies the node, product, source-supported policy family and integer stock parameter. A base-stock level is a target inventory position under the source model, not an instruction to purchase that many units immediately.
- `cdc_service_time` gives the central commitment in days. It changes the source model's central/regional protection windows; it is not a measured carrier promise.
- The source accounting treats the365 daily observations as circular historical windows. Each regional/product service count requires both the relevant central and regional windows to be covered at the same anchor. At least347/365 is a retrospective joint-cycle-service threshold—not a future95% probability guarantee, fill-rate guarantee, or lost-sales estimate.
- Yuan holding costs belong to the inventory planning model. They are never converted into USD customer revenue or realized savings in the business test.

## Reproduce and independently check

Use Python3.12 with NumPy2.3.5 and SciPy1.17.0 (the tested local numerical versions), and the repository's native-account dependencies for financial reproduction. No paid model endpoint is required.

```sh
python inventory061/quality_constructor.py --input inventory061/inputs/01.json --output /absolute/new/original-policy
python inventory061/quality_constructor.py --input business_productivity065/scenario_plus20.json --output /absolute/new/scenario-policy
python -m unittest discover -s tests -p 'test_business_productivity065*.py' -v
```

Constructor outputs include normal and empirical conventional comparators, candidate policies, `solution.json` and `RECEIPT.json`. The independent checker recomputes accounting; producer-reported service/cost values are not accepted as evidence.

For the funded reproduction, use `python -m business_productivity065.run --root "$PWD" --arm conditional --output /absolute/new/productivity065-conditional`. This creates an explicitly fresh simulated account. **Never substitute an existing output path, copy a balance, publish its signing material, or imply this is continuation of a historical account.** Follow the campaign protocol for other fixed arms and the read-only verifier.

## Before operational use

A warehouse operator would still need to validate current demand, stock positions, units, lead times, capacity, supplier constraints and service definitions; map node/product identifiers; agree responsibility for decisions; test against fresh periods; and approve integration. This package does not submit purchase orders, deploy to inventory systems, validate physical supply-chain behavior or warrant future service. The paid-work benchmark concerns bounded planning/validation output, not replacement of a complete inventory scientist role.

Support modeled here covers explanation, reproducing the supplied input and correcting artifact defects in this finite scope. A changed network, forecast, capacity constraint or ongoing live guarantee is a new scope—not an unpriced permanent obligation.
