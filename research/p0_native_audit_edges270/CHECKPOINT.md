# P0-270 checkpoint — 2026-11-24

## Decisive source finding and decision

Read seven public files at the actual draft PR40 head `ced6c1cb004887dcdafaea59a2976020be649f8e`; connector blob identities match the pinned list. The frozen literal-anchor scanner ([source bba3d2b](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/bba3d2b211e513c64ddb69b15d4f694ef2daf896/research/p0_native_audit_edges270/inspect.cjs)) was executed against the retrieved text. Standalone Node wrapper not separately executed. [All 33 outcomes](RESULT.json) are retained; **30 matched their frozen expectations, three did not. Static acceptance FAIL.** The mismatches are scope/count errors in the instrument, not financial failures: the directory-scope anchor appears in replay and owned authorization (upgrades.py:83,134); the unlink/fsync anchor appears in recovery and publication (transition_evidence.py:256,304); two owned adaptive calls include key/root/path (account.py:399,647), with a distinct key/path-only loader call (line500). No retry or retroactive pass.

The source evidence narrows the native prerequisite left by P0-269:

* finance.py:859–860 and :939 call adaptive audit and history validation before and after journal-entry reconciliation. account.py:282 and finance.py:137 each invoke historical verification for committed history; pending and owned paths are separate. This is call structure, not measured launches or a complete historical-version graph.
* upgrades.py:73–77 binds ticket, manifest, selected root and verifier file map, but separately resolves the evidence-store route for the child; a cache hit returns before child launch. Direct evidence bytes and jobs are still checked on the path before this lookup. Do not infer an actual cross-context collision.
* **Native directory entry is not necessarily side-effect-free.** upgrades.py:81–85 enters evidence_directory in the historical child. transition_evidence.py:260–268 locks the directory and invokes _recover_published_aliases; :237–256 can remove a proven same-inode staging alias and fsync the directory after validating the published object's hash. That recovery is a required effect, not an audit result. Equal JSON and even a sealed source module do not by themselves establish equivalent execution effects.
* Native evidence_scope uses an immutable byte mapping (:66–86), but current_store_directory (:308–310) carries only a directory route. A pathless scope does not automatically propagate across the historical process boundary. No runtime failure is inferred from this source alone.
* Owner HMAC, original signed checkpoint, native prefix, write-ahead recovery, and journal coverage remain independent obligations. The key-bearing source_transition at account.py:644–678 is explicitly excluded from reuse; public semantic audit cannot authorize a transition. No protected source was changed.

Decision: **do not adopt whole-child graph caching.** First establish effect-preserving native storage entry and an explicitly bound immutable evidence view. Then trace actual historical nodes (including transitive stores, service data, imports, launcher policy and version-specific effects) against the unchanged successive-migration acceptance. Keep owned recovery and authorization outside any reusable result. If the actual closure cannot be established, use fresh replay. No alternate verifier or financial account.

## One targeted native prerequisite experiment, P0-270B

[Protocol](PROTOCOL_NATIVE_EFFECT.md) frozen at 61e86eec85d8ae21b0e60b49ad31f367d8fc758d. [Probe](native_effect_probe.py) frozen at 28e19d5d6067435413917bd063b8b04da8cb6bde (Git blob 34ddd1e25ab84f98ffe11840d20e86f861b55f36). [Exact workflow](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/9bb5469f6e517cb4110f7a5a047c5e2eade7f27a) checks actual owner source blob, uses standard public runner, no dependencies or keys. It invokes the **original native CAS module** on disposable nonfinancial codec inputs, comparing actual recovery, byte-view resolution, corruption rejection and explicit child routing. This is not a rerun of P0-268 or a ledger test. Exact-head workflow https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45488959269, completed, conclusion success. No artifact or acceptance verified in this checkpoint.

## Acceptance matrix

| Item | Verdict |
|---|---|
| Seven exact pinned source blobs retrieved | Achieved (connector identity) |
| Frozen literal source-anchor scanner | Failed, 30/33; result immutable |
| Static evidence of directory recovery side effect | Established at inspected source only |
| Actual native codec/storage boundary | Pending P0-270B; no result yet |
| Actual historical dependency closure and effect-preserving native replay | Partial, not qualified |
| Successive native migration, prospective lifecycle and release | Blocked; P0-262/263/267/268 failure verdicts unchanged |
| Original owner checkpoint/custody | Unknown; public draft not an actual task handoff |
| New genuine commerce, audited $3B trailing-365 complete-cost profit, recursive discovery | Not established |

Current main refreshed at 97dffcd9c40d3a7504466b6ed74140bcb53b2a8c; prior connected014 release 3e229271a5408961a8ad686fa32d0b0f2fd08663 and workflow45456595620 all three jobs succeeded. Current main release workflow45485175678 jobs at inspection: [{"name":"release-qualification","status":"in_progress","conclusion":null}]. Historical release and six durable handoff files were retrieved. PR40 still draft, PR77 still draft. No actual separate task state endpoint or original account custody established. No modifications to other owners' branches, historical evidence, account records or liabilities. No spending, outreach, real transactions or production deployment. Local GitHub DNS unavailable; no attempt to obtain new credentials. Static connector retrieval/inspection wall telemetry is in RESULT.json, process CPU and actual billing unknown. No new financial output. The US$3B objective remains open.
