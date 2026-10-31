# Lean experiments

Keep useful mechanisms, compact results and complete accounting; discard redundant terminal logs and failed-run bundles. This cleanup changes storage, not outcomes.

Lessons:
- Broad checkout exceeded the download cap before replay: fetch only pinned dependencies.
- Recursive evidence packaging exceeded file limits: remove redundant output, not guards.
- Compatibility and source-binding failures require matching fixtures and exact-source checks; a rerun alone is not a repair.

The 85 removed engineering logs, 14 unreferenced empty terminal logs, failed-preflight job log and two failed-preflight ZIPs are recoverable in Git history. Exact log hashes are in the [prior omission manifest](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/07c84b0498d8052f3e02ee6ceef5ed40ba532697/docs/packaging/SOURCE_ONLY_OMISSIONS.json); original files are at [85fba7c](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/85fba7c94cac5f741d047807a0c83e8ce11f4216). The cleanup commit's diff lists exact deletions. Legacy references in `ARCHIVE_CAP_REPAIR.json`, `COMMERCIAL_STANDALONE_FAILURE_364.json` and `historical/cycle-006/POLICY_BOUNDARY.md` describe that historical tree, not current files.

The active omission list is retired: new packages include all remaining eligible files. Existing old-archive verification and the 10,000-file / 512 MiB guards are unchanged. Compact outcomes, charged costs, obligations, source code and successful operating evidence remain intact.
