# Transition156 — isolated owner-safe reference for pending upgrade arbitration

**Scope:** P0 design fixture. This code is **not imported by the native engine, canonical CLI, financial journal, account authority, release builder, or private recovered accounts**. It cannot approve an upgrade or prove a migrated account. No financial source files, source guards, archive limits, signing material, original operator state, queues or liabilities are modified. The financial implementation owner remains on PR #40; this is an independent testable construction, not a competing writer.

## Why this exists

The frozen independent red tests in [Transition154](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/360#issuecomment-6866432918) and [Transition155](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/360#issuecomment-6867302408) expose **two** properties missing from PR #40's then-current `operations.prepare_upgrade`: concurrent conflicting preparations can both report success, and a fully serialized second distinct request can replace the first pending request against an unchanged checkpoint. Locks alone do not cure the second property.

This reference exercises the smallest **combined** mitigation in a disposable *non-financial* directory:

- Cross-process advisory exclusive `flock` spanning the entire synthetic prepare operation, rather than serializing only individual file writes.
- An immutable, create-only, directory-fsynced `PREPARE_INTENT.json`, written before any simulated authorization. A differing same-checkpoint request is refused **before** a second signer callback.
- A create-only `PREPARE_RESULT.json` for the first completed request. An identical retry returns the same receipt without re-signing or rewriting either file.
- A crash after intent publication but before durable result blocks **all** automatic retries, even identical ones. Recovery requires separately designed authenticated owner reconciliation; deleting the intent, bypassing the lock, initializing a new account or re-signing history is *not* a permitted repair.
- The fixture refuses stale checkpoint digests, malformed records and symlinked intent files. Its self-digests detect accidental tampering, **not** malicious replacement or provide financial authenticity.

## Execute locally

From the repository root on POSIX/Linux with standard-library Python:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest -v research.transition_arbitration156.test_gate
```

Seven tests exercise serial A/B rejection, byte-preserving A retries, a separate two-process race, synthetic exception interruption, actual process death mid-authorization, stale/corrupt records and symlink refusal. They use disposable directories and no private source, commercial revenue, money, account, real signer or paid API. Their pass means only this isolated reference obeys the stated properties. The original PR #360 tests stay **failed on their unchanged financial-parent source**, not retroactively rescued by this reference.

## Non-negotiable integration boundary

**Do not add this as a wrapper/facade around a financial migration or call it to approve a real account.** A safe reviewed owner-side forward-port must first obtain the actual owner-held account and writer checkpoint. All engine `run_world`/`operate`/`upgrade_world`/`prepare_upgrade` financial operations must share the *same* account-identified exclusive lease; a separate lock file that other writers ignore offers no concurrency protection. Canonical `JournalAccount`, mandatory adaptive `Account`, HMAC authority, immutable prior checkpoint/journal, CAS evidence, counters, remaining liabilities and nonempty due queues must remain mandatory.

The production pending record must be bound to all material inputs (authenticated account ID, complete source and manifest identities, counter, policy/terms, prior signed checkpoint and journal sequence), rather than this fixture's deliberately small three-field synthetic request. It must be attached to authenticated owner-controlled recovery and provide verified completed-predecessor progression before a different request can be prepared. Atomic descriptor/source staging must preserve crash consistency. The migration/claim/maturity financial ordering and same-account successor spend are **not** tested here.

| Acceptance tier | Status |
|---|---|
| Reference A/B serial/concurrent intent arbitration | Local synthetic tests only; CI requires exact-head confirmation |
| Canonical original-account authenticated migration and original queues | **BLOCKED** pending current owner custody and reviewed semantic forward-port |
| Protected merge, public release and downloaded byte execution | **NOT ATTEMPTED**; preserve qualified main/release |
| Real buyers, collections, complete-cost profit and causal successor | **NOT ESTABLISHED** |
| US$3B native trailing-365-day complete-cost profit | **NOT ACHIEVED** |

This is a constructive engineering mechanism, **not** a Blue Sky flagship, actual commerce, benchmark superiority, authenticated-source migration or recursive-discovery benefit. No costs are represented as zero: whole-campaign/model/host bills remain unmeasured.
