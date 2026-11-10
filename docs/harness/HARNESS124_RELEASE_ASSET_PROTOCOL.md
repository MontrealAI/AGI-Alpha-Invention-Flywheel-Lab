# HARNESS124 — frozen release-asset preflight (10 November 2026)

## Source, historical failure, and boundary

Baseline main: `68c2c1a00c78579b76788955a87f74dace8cc404`. This is a **release-transport-only** correction. Product tree, model, evaluators, account/JournalAccount, native financial ownership, old releases, and protected liabilities are out of scope.

Exact-main [HARNESS workflow 42786474290](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42786474290) **FAILED** in job 129751761654: `gh release create` returned HTTP 400 `Bad Content-Length` uploading `Darwin-CODEX-HOST-VERIFICATION.stderr.txt`. The four upstream qualification/platform jobs passed, but there was **no qualified release and downloaded operation** for this source. The connected014 publishing gate [42786474182](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42786474182) **FAILED** with `EXACT_MAIN_QUALIFICATION_FAILED:alpha-genesis-harness.yml`; its downloaded release job was skipped. These original failures remain FAILED.

Read-only independent artifact inspection confirms zero-length optional stderr members in immutable macOS artifact `13749128766` (ZIP SHA-256 `0f51e30223192ee73ee21e357b6678de27e3262e5baf34f0e837a6064eeff91a`) and Windows artifact `13749937631` (SHA-256 `f13fad1077c7fd6c81144037e9ec8a993ec46f378b45d331b853a2a6f70bb5be`). The observed API error and these bytes establish a credible zero-length-upload failure mechanism; no unrelated transport error is retroactively ruled out.

## Frozen, prospective tests (before implementation)

1. Exactly enumerate a fresh direct-child release directory, binding each nonempty safe regular file's SHA-256/size and retaining all of them with no silent omission.
2. Omit **only zero-byte `*.stderr.txt`** probe logs from *Release API transport*, recording every omitted name and zero size in a canonical key-free inventory. Do not delete or modify the original hosted artifacts or historical failure evidence.
3. **Reject** empty nonoptional assets (including the source ZIP), missing/nonregular inputs, duplicates, symlinks, path traversal/unsafe names and unexpected nested folders before calling `gh release create`.
4. A nonempty `*.stderr.txt` is a real failure diagnostic and **must be published**, not filtered by suffix alone.
5. The preflight emits an exact null-separated, shell-safe ordered path list and inventory. The publication step consumes that list—not a broad wildcard. A malformed or empty selection blocks publication. No secret contents may be printed.
6. Source-provenance, candidate tests, source checks, source-matched workflows and independent downloaded-release operation must pass **on the prospective new commit** before promotion; no existing source is relabeled. This fix neither approves a failed model quote construction nor relaxes either release gate.

## Stop/decision

The preregistered action is a narrow prepublication fix and synthetic tests, not a new commercial confirmation. If any required asset is empty or another release error occurs, preserve the failure; investigate and issue a distinct prospectively registered correction. Keep prior releases immutable. No paid API, customer outreach, spending, new credentials, real transaction or deployment. Original signed accounts remain outside this branch. The US$3 billion trailing-365 complete-cost profit objective is unqualified.
