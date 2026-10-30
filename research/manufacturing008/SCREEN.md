# Manufacturing screen, 30 October 2026

This is an opening investigation and a data-access execution receipt, not an invention or commercial success. Scope is distinct from PR #11's molecular measurement-selection work. No downloaded program was executed.

## Initial possibility: failure-informed solid-state synthesis routes

**Activity and consequence.** Produce functional inorganic materials whose predicted structures do not supply a reliable experimental recipe. The prospective users are industrial materials-development and autonomous-laboratory teams. A reusable route instrument could make a previously impractical compound experimentally accessible; predicting a stable compound is not equivalent to producing it.

**Proposed lever, and early falsifier.** Infer intermediate reactions from failed experiments, avoid free-energy-consuming intermediates, and retain learned reactions for new campaigns. This lever is already implemented in the published ARROWS3 system. Its public documentation explicitly covers failure-driven precursor changes and transferring its learned pairwise database between campaigns, with atmosphere applicability restrictions. Ordinary retrieval/reuse therefore receives that capability as a baseline. The proposed lever has not earned a new enabling gap.

**Strong complete alternatives.** ARROWS3 combines thermodynamics with experimentally observed reaction pathways; A-Lab joins that route to literature recipe retrieval and automated interpretation. The current LANL MCTS planner additionally exposes route grammars, balancing/redox checks, retrieval, and ordinary nearest-neighbor/frequency baselines; it labels its thermodynamic layer a proxy rather than a validated physical model. Merely joining these mechanisms would not demonstrate superiority.

**Real access check.** ARROWS main tree `cb630e944315c8ac19f5b9a3c9d8984be93258a6` was read. Its YBCO Exp.json is a Git LFS pointer to 52,463,427 bytes, SHA256 `61a9efa9e2adab31a453de80ed2a0457b53705b5c75807036c04e9bc0547f0e9`; the energy dataset points to 225,720,378 bytes, SHA256 `5497c103b18b2865c3b837e4ba1440816b1ff9cbfa115ed2b2aacc96baff9cd8`. The ordinary raw-file responses are pointers, not acquired experimental data. No runtime benchmark or physical synthesis was executed. Public source availability alone must not become a runtime-qualification claim.

**Decision.** INVESTIGATED / NOT ADMITTED. Preserve the known pairwise-reaction/atmosphere boundaries as incumbent knowledge. A new route outcome requires actual synthesis evidence or a calibrated retrospective study that first beats this capable incumbent; no evidence here establishes baseline losses, independent demand, complete costs, or profitable production.

Primary sources:

- Szymanski et al., *Autonomous and dynamic precursor selection for solid-state materials synthesis*, Nature Communications (2023), https://www.nature.com/articles/s41467-023-42329-9 ; code/data https://github.com/njszym/ARROWS .
- Szymanski et al., *An autonomous laboratory for the accelerated synthesis of inorganic materials*, corrected Nature article, https://www.nature.com/articles/s41586-023-06734-w . This screen does not reuse its disputed discovery count as evidence of our success.
- Current LANL primary implementation: https://github.com/lanl/mcts-material-synthesis .

## Constructive next possibility: constrained disassembly from imperfect CAD

**Activity and consequence.** Construct executable extraction/assembly motions for interlocking components, enabling repair, recycling, and production planning when straight-line extraction fails and CAD lacks usable joint semantics. This can be investigated computationally with real industrial CAD instead of inventing physical synthesis results.

**Proposed causal lever.** Transfer observability and invariant-manifold methods to infer a small set of contact-compatible motion coordinates, then synthesize and independently check motions on that manifold. A useful first instrument would infer coupled rotation/translation from geometry and reject an incorrect joint hypothesis using collision witnesses. This is an agent-proposed research direction, not a discovered or executed mechanism. Ordinary screw/helical primitives and contact-guided planning must remain available to controls.

**Strong complete current routes.** Assemble Them All (2022, current repository HEAD `29db7df4d7f2e6055f3f26fc5c11a424954f7308`) already uses assembly-by-disassembly, contact physics, and rotation-capable BFS/BK-RRT; its baseline collection includes conventional geometric planners. ASAP (2024) additionally addresses stability, limited holding resources, and robotic feasibility. A September 2026 geometric-symbolic paper reports 85.83% success on its ASAP dataset using learned relations and human correction. That percentage is for a different experiment; it does not establish failure on the 24 two-part cases downloaded here.

**Important unmet constraint remains unproven.** Geometry-only motion is not a complete industrial delivery: gripper access, tolerances, contact forces, stability, damaged fasteners and robot reachability can matter. Replacing an industrial obligation with a nominal collision-free path after observing results would be invalid. This screen has not established which important cohort current complete routes cannot serve economically.

**Executed access/readiness probe.** The official rotational CAD archive downloaded successfully (5,350,863 bytes; SHA256 `cea592bc010801de9cbbeabe53125ea91478bd4a1f9c8db2a1476fdd28a7af3b`). A bounded, owned standard-library data parser checked member paths, size ceilings, triangle indices and finite coordinates without extracting or executing files. It found 24 two-part assemblies, evenly divided into screw, general and puzzle categories, with 48 meshes. See DATA_READINESS.json for all exact mesh identities and measurements. This establishes usable geometric input, not motion success or physical validity.

**Native execution boundary.** The downloaded baseline was inspected but not run. Its native RedMax/OpenGL stack is not qualified here. `bwrap --unshare-net --unshare-pid ... /usr/bin/true` failed with `Operation not permitted`; Docker is absent. The inherited qualified pure-JSON interpreter cannot run arbitrary native RedMax code. A weakened straight-translation-only implementation must not substitute for its rotation-capable baseline.

**Cheapest decisive next experiment.** Qualify the full native baseline in a permitted isolation environment; freeze a CAD cohort, normalization, clearance/tolerance, robot/holding obligations, runtime and semantic inputs before comparison. Run rotation-capable BFS/BK-RRT plus simple analytic screw primitives and current applicable complete methods. If they meet the obligation cheaply, reject the gap. Only on verified residual failures construct an invariant-derived motion strategy and test continuous collision/stability independently. Data are already downloaded; no paid API or new external access is needed for the geometric research. Production validation requires real force/tolerance/robot measurements.

**Rights and commerce.** The code is MIT, but much of the CAD corpus derives from Fusion360 Gallery, whose license limits use to noncommercial research and forbids redistribution of the entire corpus. Keep the archive local; publish a source URL and hashes, not the corpus. A commercial product would require appropriately licensed or customer-authorized CAD. Stanford's current CAD drawing rate (USD105/hour) is a weak adjacent comparator, not the price or unavoidable labor cost of complete assembly planning. No independent purchase evidence, negative baseline economics or price for this exact obligation was established.

**Decision.** INVESTIGATED / PROVISIONALLY EXECUTABLE GEOMETRIC PROBE / NOT ADMITTED. The source and real data support a useful next experiment; the gap and commercial bridge remain open. This possibility should not consume the flagship budget until the competent native baseline and obligations are settled.

Primary sources:

- Tian et al., *Assemble Them All*, https://assembly.csail.mit.edu/ ; source https://github.com/yunshengtian/Assemble-Them-All . Official archive URL is recorded in DATA_READINESS.json.
- Tian et al., *ASAP*, https://asap.csail.mit.edu/ ; source https://github.com/yunshengtian/ASAP .
- Harlacher and Friedrich, *CAD-Based Relation Learning and Geometric-Symbolic Planning for Robotic Assembly*, 15 September 2026, https://arxiv.org/abs/2609.17263 .
- Dataset rights: https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/LICENSE.md .
- Adjacent price only: https://uit.stanford.edu/rates/other/timeandmaterials .

## Further enabling direction kept distinct

NIST identifies qualification of additively manufactured parts as burdened by extensive tests, complex internal geometry, defects and anisotropy. This substantiates importance but not a new AGI ALPHA solution or a buyer commitment. An overnight software claim cannot replace physical equivalence/qualification measurements. The current NIST AM-Bench data are lawfully public and the NIST data host is reachable here; a bounded specimen analysis is feasible, whereas a new part-qualification claim is not established.

Sources: https://www.nist.gov/programs-projects/additive-manufacturing-part-qualification ; https://www.nist.gov/ambench/direct-am-bench-data-links-and-referencing-guidance .
