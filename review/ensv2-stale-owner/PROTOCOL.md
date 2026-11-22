# ENSv2 entitlement regression — frozen protocol

Source target: PR #541 `dcaa91fe2a78561aafd3de2cefd77a8256cd4be3`; main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. External specification: https://docs.ens.domains/ensv2/migration/ . This is an independent read-only synthetic counterexample, not new Club-owner authority or evidence of a real migrated name.

Before test implementation, freeze two mock-world cases: **REGISTERED** current v2 owner B with a stale v1 owner A must demonstrate that legacy-only `ownsClub` accepts A and denies B, with no v2 contract call; **RESERVED** unmigrated v1 name A must remain accepted by the ordinary v1 path. Count two cases, no success selection, no live RPC, no real names, keys or money. Do not weaken checks, reinterpret this negative witness as production security, or write to the protected product-owner branch.

Fail if pinned source SHA or blob differs, source does not behave as registered, or mock RPC binds the wrong node/contract/block. Native accounting P0, original signers and liabilities are out of scope. Production gate: no Club entitlement release until migration-aware status/hierarchy and current owner are independently qualified at one canonical block, with expiry/transfer/stale-owner regressions and preserved v1 RESERVED semantics. Token-balance entitlement is separately evaluated.
