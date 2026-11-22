# Source qualification before confirmation

Reviewed 2026-11-04, before the registered confirmation seeds were executed.

The bounded numerical source gate passed independent review: 38 regression tests, all 432 development arm-case outputs, and 1,000 additional exact-rational adversarial case pairs (2,000 estimator executions). All development bounds enclosed exact decimal truth without a comparison tolerance; all three arms completed 96/96 tighter-envelope cases and abstained on 48/144 cases. Maximum development Kirchhoff residual was 6.938893903907228e-18 A.

Review found and resolved malformed acceptance certificates, incomplete result acceptance, inconsistent offsets across reversal pairs, exact-threshold floating-point errors, tiny-gain overflow, invalid geometry, optional omission of the direct comparator, incomplete input binding, replay context replacement, and result overwrite/failure retention. These were development repairs, not retrospective changes to confirmation results.

The independent direct implementation was constructed from the declared interface without reading the proposed implementation or confirmation cases. The conventional arm deliberately uses the same mature complete method as the composition. This is an internal independent implementation/review, not external peer review or a model-population comparison.

Source and input SHA-256 identities:

- .github/workflows/genesis097.yml: a0c615fe98ddab38bcdcea16b7ce292b179bdb33f2a74cf23220bfbb9a97cf81
- campaign/genesis097/DESIGN_INPUT.json: 402ab0b858f9519696c04c30a7f72bf115bf4a92bdb59f00cfd4d75b761c88ea
- campaign/genesis097/PROTOCOL.md: 87996e53fc2974bc12ff0c2c60b65be06482f9c48100668db78e3a2f77418031
- campaign/genesis097/README.md: 5f86eab7132e64d64408679827cea76a9caf128f7cda07d958c517c5aa506339
- research/genesis097/__init__.py: 4ba75b5219e0347c0f0c2386c0f31aca41d74ca51283fa94104e4f30e79bcfa3
- research/genesis097/check.py: 98cad79f3c9469bfdca3bdbf7d359457c7a14cf933be4ac4170b420df9ac11a2
- research/genesis097/cli.py: a28ee14d5a01531d6f15ffff05a4b86909ad76d6470ec1e0c769342846cd6594
- research/genesis097/direct.py: f9c1e004e6a39c40d8a2be6474a463f2c4b8c5fba5e5ab6179cf89dfbcb795ce
- research/genesis097/experiment.py: 18932680a7fb754e30cc07f58a8c7ba9d331f4e45d3b37a67e2bae88fe9465af
- research/genesis097/forward.py: 27b4bd3cdb76ac08a7e51069b650e8ae6d687f44217dce2e5a4ba28f40a97e86
- research/genesis097/instrument.py: 996a2bf4f2b44dcab5de9819ac55c94b85db6e31445432a8c0577a2e87131f98
- research/genesis097/replay.py: de54e3beb6fd9b800b5482191ae21d67653e5e9eb0b6bc6f7dddaa870077a49a
- research/genesis097/test_direct.py: 02d70cdd1e334398c9af89ed6a0bdddb510c59fb6ff3234a6430706b90147ae5
- research/genesis097/test_instrument.py: 40eabbe6c61da15963d2ecc583979250b680f2891a1f255e73e5ee480c5df91c

Generic stored enclosure checks permit 1e-8 ohm numerical comparison tolerance; the independent development audit used strict exact truth enclosure. The numerical result is conditional on supplied geometry, calibration and offset/error envelopes. Per-channel intervals are conservative outer bounds, not a complete joint nuisance feasibility proof. No physical instrument, customer acceptance, commercial profit, scientific novelty or improved autonomous discovery is established.

The source/protocol commit containing this record must be verified publicly before confirmation. Confirmation uses root 980000; development used root 970000. Both retain the fixed 144-case, three-arm design in PROTOCOL.md.
