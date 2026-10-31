# Lean experiments

Keep useful mechanisms, compact results and complete accounting; discard redundant terminal logs and failed-run bundles. This cleanup changes storage, not outcomes.

Lessons:
- Expired measurement replay is manual-only; current regressions remain mandatory in `campaign.yml`, and actually observed same-head runs must pass.
- Broad checkout exceeded the download cap before replay: fetch only pinned dependencies.
- Recursive evidence packaging exceeded file limits: remove redundant output, not guards.
- Compatibility and source-binding failures require matching fixtures and exact-source checks; a rerun alone is not a repair.

The 85 removed engineering logs, 14 unreferenced empty terminal logs, failed-preflight job log and two failed-preflight ZIPs are recoverable in Git history. Exact log hashes are in the [prior omission manifest](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/07c84b0498d8052f3e02ee6ceef5ed40ba532697/docs/packaging/SOURCE_ONLY_OMISSIONS.json); original files are at [85fba7c](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/85fba7c94cac5f741d047807a0c83e8ce11f4216). The cleanup commit's diff lists exact deletions. Legacy references in `ARCHIVE_CAP_REPAIR.json`, `COMMERCIAL_STANDALONE_FAILURE_364.json` and `historical/cycle-006/POLICY_BOUNDARY.md` describe that historical tree, not current files.

The active omission list is retired: new packages include all remaining eligible files. Existing old-archive verification and the 10,000-file / 512 MiB guards are unchanged. Compact outcomes, charged costs, obligations, source code and successful operating evidence remain intact.

## Terminal transcript cleanup

Removed 136 redundant compiler, test and progress transcripts; kept code, successful paper sources, CSV/XML outputs, compact acceptance/resource records and financial accounting. Historical logfile links and digests refer to [the c488 source tree](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/c488e1c401d4d7eb276171e29fa82c48f927b8e5), not a promise that current packages contain retired transcripts.

Brief lessons: LaTeX failed on header ordering and unsupported Unicode minus; load dependencies first and normalize text. Confirmation/resume rejected reactivation ordering and uncommitted journal actions; repair state handling, never bypass audits. Earlier commercial rejection tests exposed missing validation (3/14 failed in 86.760s; 5/7 in 0.002s); the later repaired suites passed.

Historical successful test summaries (not new qualification), preserving counts and reported elapsed seconds: commercial adversarial 14/9.709s; onboarding 7/20.840s; pricing 6/0.001s then 7/0.001s; cancellation 26/7.767s; consequential artifact rejection 5/1.719s and archived-source 6/1.876s; checker 10/0.008s then 20/3.260s; operational repair 6/0.008s and 6/0.010s; replacement rejection 4/1.104s. These elapsed times are not monetary billing or new profit.
