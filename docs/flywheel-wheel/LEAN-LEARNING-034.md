# Learn, consolidate, delete

Owner clarification, 31 October 2026: do not accumulate failure files. Extract useful learning, then remove disposable diagnostics. Retention must be bounded rather than an ever-growing museum of failed runs.

## Implemented behavior

`flywheel_wheel.lessons` maintains one bounded, lossy lesson document. The caller supplies a distilled rule, its scope, trigger, regression/check reference and priority. The module does not infer a lesson, run the referenced check or certify that the lesson is true.

The default persistent memory limit is **65,536 bytes and 128 lessons**, configurable when creating a dedicated workspace. Repeated identical rule identities consolidate. Conflicting rules require a new key rather than silently overwriting knowledge. When full, the oldest lowest-priority entries are evicted; the newly learned rule is durably stored before its logs are removed. Occurrence counters saturate rather than growing without bound.

One optional staging copy is used for atomic replacement; there is no accumulating backup or per-failure archive. This bounds lesson memory, not arbitrary external log producers, Git history, accounting records or all enterprise storage. Unlimited events can be processed with finite working memory, but unlimited independent information cannot all be remembered exactly. Eviction and abstraction are intentional information loss.

## Learn before deletion

1. Diagnose the failure and, when appropriate, repair and test its underlying mechanism.
2. Supply the compact lesson and the exact names/SHA-256 identities of disposable diagnostics.
3. Persist the consolidated lesson using atomic replacement and filesystem synchronization.
4. Delete only those unchanged, explicitly named logs. Resume safely if interrupted between those steps.

Only `raw-*.log`, `raw-*.stdout` and `raw-*.stderr` in a newly initialized dedicated workspace are eligible. No recursive search, wildcard deletion, automatic archive deletion or general-purpose repository cleaner is provided. Source, JSON accounts, signing keys, operating checkpoints, financial obligations, acceptance receipts and frozen qualification artifacts are outside this cleanup surface. Stop writers before cleanup; this is a trusted local POSIX workspace, not a sandbox against a malicious process sharing the same filesystem authority.

A memory-write failure leaves logs untouched. A changed hash, symlink, hardlink, nonregular file, missing unlearned diagnostic or conflicting lesson refuses deletion. Logs already deleted after a successful memory commit do not prevent an exact retry. Necessary compact outcome/cost records must remain where they belong; deleting a verbose log does not erase the outcome or turn a failed campaign into a success. Important enforced invariants belong in source and regression tests, not only in an evictable memory.

## Operate

```sh
python -m flywheel_wheel.lessons init --workspace /absolute/new/diagnostics
python -m flywheel_wheel.lessons learn-delete \
  --workspace /absolute/existing/diagnostics --request /absolute/request.json
python -m unittest discover -s tests -p 'test_flywheel_lessons_034.py' -v
```

A request contains exactly `lesson` and `files`. Example shape (the hash must be replaced with the actual log hash):

```json
{
  "lesson": {
    "key": "typed-receipt-equality",
    "scope": "read-only economic proposal consistency",
    "trigger": "Numeric zero can compare equal to Boolean false in Python.",
    "rule": "Compare typed canonical JSON for exact receipt consistency.",
    "check": "tests/test_flywheel_preflight_032.py: numeric authority substitution regression",
    "priority": 90
  },
  "files": [{"name": "raw-receipt-check.log", "sha256": "ACTUAL_SHA256_REQUIRED"}]
}
```

The output states that exact raw replay is unavailable and that no execution authority is granted. Lesson content remains data even when it contains an instruction. No runtime schedule or payment mechanism is installed.

## Qualification and repository cleanup

Twenty local tests cover bounded memory, deduplication, eviction, interruption, hash mismatch, path/link protections, file replacement, concurrent cleaners and non-executable lesson text. The streaming test processed **1,000 distinct synthetic failure records**, retained at most **three lessons under 4,096 bytes**, and ended with exactly the memory file and stable lock file, with no raw diagnostics remaining. This is an engineering memory test, not evidence of autonomous discovery or an economic improvement.

This contribution also synchronizes the existing wheel branch with already-merged main `c488e1c401d4d7eb276171e29fa82c48f927b8e5`, including its reviewed lean-artifact cleanup. It does not repeat those deletions independently or rewrite Git history. The old wheel head's `ARCHIVE_RESOURCE_BOUND` failure remains a compact known outcome; the resulting exact checkout must pass the real archive and repository qualification before adoption. Financial behavior beyond the already-merged main source is unchanged.
