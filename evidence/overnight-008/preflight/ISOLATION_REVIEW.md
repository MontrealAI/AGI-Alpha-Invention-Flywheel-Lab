# Overnight verifier preflight

The inherited `flywheel/sandbox.py` at SHA256 `103e2a8828a7aaf31faac475fb48ccbba1a685b4f64191dae4f6fbe8a9b6c7c8` passes the actual ten effect/resource probes on this host, plus all nine existing sandbox tests. These execute module initialization after confinement, reject changed source and symlinks before execution, bound input/output/CPU/address-space/wall time, clear environment, close inherited descriptors and kill the worker if its supervisor dies. The separate verifier did not modify candidate or sandbox source.

Use this existing worker for generated JSON programs interpreted by a reviewed hash-pinned pure Python interpreter. The interpreter's imports must already be available after confinement; general numerical packages that need file access or dynamic loading do not qualify automatically. Trusted data preparation and ordinary numerical baselines require their own source-pinned bounded command receipts, and must not be represented as arbitrary generated-code confinement.

This qualification concerns the current host, Linux kernel, Python and libseccomp. The verifier and builder share the model, host and filesystem. Protection of hidden inputs is procedural, not hostile-user filesystem security or external certification.

Before confirmation, freeze exact candidate+dependency bytes, verifier bytes, input identities, all controls, full cohort/admission rules, functional endpoints, practical margins, uncertainty and full-cost treatment. The builder may not inspect verifier-owned truth or cases. Once any result is supplied for repair, that case is exposed for this campaign. Preserve every prior source/result rather than silently replacing it.

The inherited cycle-006 Norman/Wessels confirmations are already exposed and report no statistical superiority claim (alpha spent zero). They cannot be repurposed as fresh evidence. Maintain one explicit campaign-level claim/exposure ledger; a new branch/version does not replenish it. A one-time fixed-cohort engineering comparison is sufficient if described as such; do not invent sampling independence or statistical certification. Any population-level significance procedure must be prospectively justified and account for all claimed cycles.

Source receipts: `PREFLIGHT.json`, `SANDBOX_QUALIFICATION.json`, `SANDBOX_TESTS.log`. No paid calls, external network requests or real commerce were made by these probes.
