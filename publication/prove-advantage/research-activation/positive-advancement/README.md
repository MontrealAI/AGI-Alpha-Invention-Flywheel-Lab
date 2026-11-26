# Recover verified evidence from a live release

**MONTREAL.AI recovered and independently replayed two real release review packets using two live reads each.** The indexed method transferred 97.7% fewer response bytes than downloading the complete Activation archive and 58.0% fewer for Inventor. An independently implemented interval optimizer achieved the same minimum sizes. Full downloads used one request and were slightly faster in the final matched comparison. [Complete results](RESULT.json) · [Independent conventional control](CONVENTIONAL.json)

| Work performed | Replayed outcome | Full archive | Two verified ranges | Pinned Git files |
| --- | --- | ---: | ---: | ---: |
| Activation 1.5 industrial evidence review | Two documented availability cutoffs and seven correctly withheld claims | 1,805,184 B / 1 read | 41,922 B / 2 reads | 41,922 B / 2 reads |
| Inventor 1.0 conventional qualification | 27/27 checks across release dependency, Atlas and endpoint work | 371,811 B / 1 read | 156,203 B / 2 reads | 93,071 B / 3 reads |

The first case preserves the scope of the Prusa offer and Bambu software-support decisions, including the withheld onset and continuity claims. The second use runs the released relational checker on a different archive, input set and accepted result. Each program and input matched a Git-pinned source outside its ZIP. Ordinary full-archive and direct Git retrieval produced identical results. [Acceptance registration](REGISTRATION.json) · [Approved evidence index](PACKETS.json)

## Why this work was selected

The existing Activation planner treated each full archive or pinned Git file as one source. Its published replay reduced transferred bytes with eight reads, and the full archive remained faster. The 10:33 a.m. Toronto Unseen Advantage report surfaced a verification study that validates the connection from source inputs through the reviewed result. The report completed before the 10:38:22 prospective cutoff and entered the historical backlog. The study supplied the rationale for pinning each recovered member to an independently verified source. The archive representation and exact range planner came from direct inspection and standard interval mathematics. [Prior Activation report](../../../activation/REPORT.md) · [Primary research](https://arxiv.org/abs/2611.28704v1)

For an already indexed stored ZIP, the planner merges required byte intervals and leaves the largest gaps between reads. With up to two reads, one gap may remain. Every other gap between requested bytes must be transferred. Leaving the largest saves at least as many bytes as leaving any other. The independent control derived member extents using the original ZIP and compared the same certificate against an ordinary optimizer. The two accepted uses establish the scoped capability in Opportunity Capture. The ordinary method ties on accepted output and minimum bytes.

## Use the retained capability

Run from the release checkout with Python 3.11 or newer. Choose a new output directory under a trusted, owner-controlled parent. Use `ACT15` for the evidence decisions or `INV10` for the Inventor review.

```sh
frontier_review_dir=$(mktemp -d)
python3 -B scripts/frontier_opportunity_capture.py --research restore-packet ACT15 "$frontier_review_dir/activation"
python3 -B scripts/frontier_opportunity_capture.py --research restore-packet INV10 "$frontier_review_dir/inventor"
```

The final `receipt.json` binds the exact recovered member bytes. The command checks range metadata, the common representation identifier and each reviewed source digest. It writes the verified files for inspection. When a source or request changes, the command fails before a successful receipt. Windows operation requires an owner-controlled destination and access settings.

The original selected fields and comparison outputs can be reproduced with the existing published replay software. The comparison uses zero paid model calls.

```sh
python3 -B publication/prove-advantage/research-activation/positive-advancement/compare_evidence.py compare
```

Index construction tested the two published ZIPs and all five independently pinned source members. The observed setup took **20.59 seconds**, nine public reads and **2,323,338 response-body bytes**, including two reads of the release manifest. The table measures each use from the retained index, with one distinct productive case for each archive. In the final comparison the complete downloads were slightly faster than the two-range reads on both cases. Transfer bytes, process time and replay results are recorded. Human time, energy, future maintenance and actual financial benefit remain unmeasured. Direct pinned Git remains attractive where the number of reads is flexible. [Observed timings and cost boundary](RESULT.json)

## PatternMiner follow-through

The original clean-room mathematical replay reproduced the published width-two counterexample. One correction coefficient was −1. The associated hook term added +1, giving zero after the terms were combined. An exact extension checked 4,505 coefficients across 651 skew shapes without a negative full coefficient in that finite scope. The replay used independently written code and ordinary exact controls. The upstream project exposed the proof artifact, and a recognized code license was unavailable at the inspected revision. [PatternMiner preprint](https://arxiv.org/abs/2611.33966v1) · [Independent result](PATTERN-RESULT.json)

The same counterexample-to-proof process clarified the real archived Québec dispatch ambiguity. Under the stated equal-cost authenticated row-query model, at most six queries distinguish 50 admissible missing-order positions. The median rule achieved that bound and tied exhaustive dynamic programming. Two of 98 hypothetical single anchor responses resolve the omission. Actual recovery still requires an authenticated source identification and the eight missing travel values. [Original pinned dispatch evidence](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/71172b1842a2aed710faebe8c22997d9fcf391fa/publication/unseen-advantage/evidence/dispatch-recovery.json)

The mathematics alone uses standard-library Python. To reproduce the optional exploratory classifier on the archived dispatch receipt, provide that exact file and use scikit-learn 1.8.0. Exact controls remain preferred in this scope.

```sh
python3 -B publication/prove-advantage/research-activation/positive-advancement/patternminer_replay.py
```

## Récupérer et vérifier les preuves

Deux lectures par dossier ont suffi pour récupérer les entrées exactes et reproduire les décisions publiées. Le dossier Activation a confirmé deux constats documentaires et sept abstentions. Le dossier Inventor a réussi 27 vérifications. Le volume transféré a baissé de 97,7 % et de 58,0 % par rapport au téléchargement complet. Le contrôle exact classique a obtenu les mêmes volumes. Les téléchargements complets ont été légèrement plus rapides lors de la comparaison finale.

Exécutez `--research restore-packet ACT15 DOSSIER` ou `--research restore-packet INV10 DOSSIER` à partir du dépôt. Choisissez un nouveau dossier sous un répertoire privé et contrôlé. Le fichier `receipt.json` confirme l’identité des fichiers récupérés. Les instructions complètes ci-dessus couvrent les deux parcours. [Résultats et mesures](RESULT.json)
