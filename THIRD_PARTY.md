# Source closure and rights

The original PGLib data files are unmodified from power-grid-lib/pglib-opf
commit `dc6be4b2f85ca0e776952ec22cbd4c22396ea5a3` (v23.07).
Their CC BY 4.0 terms, individual case attribution and repository software
license are preserved in `research/PGLIB_LICENSE.txt`,
`research/PGLIB_README.md` and the case headers. DC reduction and first-bus
mismatch balancing are adaptations performed at load time, not changes to
the source files. PGLib is an AC-OPF benchmark, not a utility service cohort.

The two files under `vendor/alpha_claim/` are unmodified source from
MontrealAI/AGI-Alpha-Agent-v0 commit
`a6b2d869a7736e7c414d7d615d86c616c2f82615`:

| File | Original path below alpha_factory_v1/ | Git blob |
| --- | --- | --- |
| protected_exchange.py | core/runtime/claim_probe/protected_exchange.py | 378bf67ae24c18ad58b684ce8b13492fd06f8556 |
| contracts.py | core/runtime/claim_probe/contracts.py | a26129ff4ee72ed8b4f8467f6c9de07b8d67508c |

Their Apache-2.0 license is preserved in `vendor/alpha_claim/LICENSE`.
`exchange_boundary.py` verifies both Git blob identities before importing
them. The simulated provider key is a public fixture, not a credential.
This is actual reuse of the existing exchange through validator/checker
injection, not a new accounting implementation or native Jobs settlement.

PR #2's charter, instructions and evidence-gap tool remain inherited under
their existing terms. PR #1 is retained by exact public source reference in
the bootstrap review; its conflicting root executable was not copied.
