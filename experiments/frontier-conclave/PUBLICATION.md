# Public experiment revision Ω.001-r1

Supersedes original complete ZIP SHA256 2bb402163ceb53b5e1c563dcfcfd7dc45dd3800b07a59b31c88b7ab5f2eac5ab, retained at Git commit 8b5ea7e4862458bb5ddc5973b70cb3703a3b55d9.

Tried: candidate qualification with original negative case. Outcome: missing-nonnegativity mutant passed 10/10 because the negative case also breached a cap. Repair: isolate negative contribution with valid caps, funding and consent; add a mutation regression. Revised result: reference 10/10, deliberately weakened candidate 9/10, nine unit tests pass. This does not prove exhaustive correctness.

Bounded negative integers parse but reject acceptance; malformed types are parser errors. Presenter INVALID shorthand refers to proposal rejection. No live frontier-model or commercial qualification claim.
