"""Verify seven preserved interrupted prefixes against completed public exports.

This checker reads no original database or private authentication material. It
supplements, and never replaces, the unchanged full native economic auditor.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from commercial.ledger import canonical, digest, strict_json
from portfolio071.economics import CAPITALS_USD, World, registered_worlds
from portfolio071.verify_economics import audit_arm


PREFIX_SHA256 = "a7dd0bc5116922a8f510f5d483669a3b865896d1af53f5204903e3bf01d40ae6"
FINANCIAL_FREEZE_SHA256 = "3cfe1304592430bdea1329c42d4c4e5122dd7c90107302ada5fcff89ffbfd389"
PREFIX_PATH = "experiments/portfolio_20261102/RECOVERY_PREFIX_IDENTITIES.json"
SECOND_PREFIX_SHA256 = "b9915acbf852e713b154bfe8310c3525d7fe030e0d2f133527e7537d21d4fe5c"
SECOND_PREFIX_PATH = "experiments/portfolio_20261102/RECOVERY_SECOND_PREFIX_IDENTITIES.json"
RECOVERED_INDICES = [8, 9, 10, 11, 16, 17, 22]
PUBLIC_FILES = ("manifest.json", "trajectory.json", "native-at-horizon.json", "native-after-drain.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000_000:
        raise ValueError("BOUNDED_REGULAR_PUBLIC_JSON_REQUIRED")
    return strict_json(path.read_bytes())


def same(left, right):
    return canonical(left) == canonical(right)


def public_input_hashes(folder):
    result = {}
    for name in PUBLIC_FILES:
        path = Path(folder) / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000_000:
            raise ValueError("BOUNDED_REGULAR_PUBLIC_AUDIT_INPUT_REQUIRED")
        result[name] = sha(path)
    return result


def reaudit_current_inputs(root, folder, recorded):
    """A stale same-ID audit cannot authorize a different current native tail."""
    before = public_input_hashes(folder)
    started = time.process_time()
    fresh = audit_arm(Path(root), Path(folder))
    elapsed = time.process_time() - started
    if public_input_hashes(folder) != before:
        raise ValueError("PUBLIC_INPUT_CHANGED_DURING_NATIVE_REAUDIT")
    if fresh.get("accepted") is not True or not all(key in recorded for key in fresh):
        raise ValueError("CURRENT_NATIVE_REAUDIT_AND_COMPLETE_RECORDED_FIELDS_REQUIRED")
    if not same(fresh, {key: recorded[key] for key in fresh}):
        raise ValueError("RECORDED_AUDIT_DOES_NOT_MATCH_CURRENT_NATIVE_INPUTS")
    return {"accepted": True, "input_sha256": before, "audit": fresh,
            "process_cpu_seconds": elapsed}


def verify_prefix(identity, exported):
    """Compare exact original bytes/content; a later valid suffix is allowed."""
    checks = {}

    def require(name, condition):
        checks[name] = bool(condition)

    count, journal_count = identity["native_actions"], identity["journal_entries"]
    if type(count) is not int or type(journal_count) is not int or min(count, journal_count) <= 0:
        raise ValueError("POSITIVE_EXACT_PREFIX_COUNTS_REQUIRED")
    ledger, journal = exported["ledger"], exported["connected_journal"]
    actions, entries = ledger["actions"], journal["entries"]
    require("same_native_config", same(ledger["config"], identity["durable_header"]["config"]))
    require("native_prefix_not_truncated", len(actions) >= count)
    prefix = actions[:count]
    require("same_original_action_content", digest(prefix) == identity["native_actions_prefix_sha256"])
    require("original_exact_sequences", all(type(row.get("seq")) is int and row["seq"] == index
                                             for index, row in enumerate(prefix)))
    raw = canonical(identity["durable_header"]) + b"\n"
    raw += b"".join(canonical(row) + b"\n" for row in prefix)
    require("same_original_raw_action_tape", len(raw) == identity["durable_actions_file_bytes"]
            and hashlib.sha256(raw).hexdigest() == identity["durable_actions_file_sha256"])
    require("same_journal_authority", same({key: value for key, value in journal.items() if key != "entries"},
                                           identity["journal_header"]))
    require("journal_prefix_not_truncated", len(entries) >= journal_count)
    old_entries = entries[:journal_count]
    pending = identity.get("pending_entry")
    original_entries = old_entries
    if pending is not None:
        pending_index = identity.get("pending_entry_index")
        completed_count = identity.get("completed_journal_entries")
        if (type(pending_index) is not int or type(completed_count) is not int
                or pending_index != journal_count - 1 or completed_count != pending_index
                or pending.get("status") != "PENDING"):
            raise ValueError("ONE_RECORDED_FINAL_PENDING_INTENT_REQUIRED")
        # The actual pending boundary is a register_terms request that has not
        # yet appended a native action. Its original immutable intent is fixed
        # by the independent pre-open identity record, not chosen by producer.
        request = pending["request"]
        if (identity.get("index") != 22 or request.get("operation") != "execute"
                or request.get("op") != "register_terms"
                or pending["attempt"]["native_sequence"] != count):
            raise ValueError("EXACT_RECORDED_ARM22_PENDING_BOUNDARY_REQUIRED")
        require("same_completed_journal_prefix", digest(old_entries[:completed_count])
                == identity["completed_journal_entries_sha256"])
        require("old_complete_entries_remain_complete", len(old_entries) == journal_count
                and all(row["status"] == "COMPLETE" for row in old_entries[:completed_count]))
        resolved = old_entries[-1] if len(old_entries) == journal_count else {}
        immutable = ("key", "request", "plan", "funding", "attempt", "obligation_receipt")
        require("pending_intent_immutable_fields_preserved", all(key in resolved and key in pending
                and same(resolved[key], pending[key]) for key in immutable))
        require("pending_intent_completed", resolved.get("status") == "COMPLETE"
                and isinstance(resolved.get("receipt"), dict))
        next_action = actions[count] if len(actions) > count else {}
        require("first_appended_action_resolves_existing_pending_intent",
                type(next_action.get("seq")) is int and next_action["seq"] == count
                and next_action.get("op") == request["op"]
                and same(next_action.get("args"), request["args"])
                and type(next_action.get("day")) is int and next_action["day"] == request["day"])
        original_entries = [*old_entries[:pending_index], pending]
    else:
        require("original_entries_remain_complete", len(old_entries) == journal_count
                and all(row["status"] == "COMPLETE" for row in old_entries))
    require("same_original_journal_entries", digest(original_entries) == identity["journal_entries_sha256"])
    require("same_original_journal_body", digest({**identity["journal_header"], "entries": original_entries})
            == identity["journal_body_sha256"])
    require("same_last_original_request", bool(old_entries)
            and same(old_entries[-1]["request"], identity["last_journal_request"]))
    require("public_journal_commitment", exported["connected_journal_sha256"] == digest(journal))
    return {"accepted": all(checks.values()), "checks": checks,
            "original_native_actions": count, "final_native_actions": len(actions),
            "original_journal_entries": journal_count, "final_journal_entries": len(entries)}


def check(root, reproduction, audit_report):
    root, reproduction = Path(root), Path(reproduction)
    identity_path, freeze_path = root / PREFIX_PATH, root / "experiments/portfolio_20261102/ECONOMICS_FREEZE.json"
    second_path = root / SECOND_PREFIX_PATH
    if (sha(identity_path) != PREFIX_SHA256 or sha(freeze_path) != FINANCIAL_FREEZE_SHA256
            or sha(second_path) != SECOND_PREFIX_SHA256):
        raise ValueError("EXACT_ORIGINAL_INDEPENDENT_IDENTITIES_REQUIRED")
    identity, second, freeze, audit = read(identity_path), read(second_path), read(freeze_path), read(audit_report)
    if identity["interrupted_indices"] != list(range(8, 12)) or identity["registered_total_arms"] != 24:
        raise ValueError("ORIGINAL_FOUR_INTERRUPTED_ACCOUNTS_REQUIRED")
    if [row["index"] for row in identity["prefixes"]] != list(range(8, 12)):
        raise ValueError("ORDERED_FOUR_INTERRUPTED_PREFIX_IDENTITIES_REQUIRED")
    if (second["original_prefix_record_sha256"] != PREFIX_SHA256
            or second["additional_interrupted_indices"] != [16, 17, 22]
            or second["all_recovery_indices"] != RECOVERED_INDICES
            or [row["index"] for row in second["prefixes"]] != [16, 17, 22]
            or second["registered_total_arms"] != 24):
        raise ValueError("EXACT_SEPARATE_SECOND_INTERRUPTION_IDENTITIES_REQUIRED")
    expected_auditor = freeze["source_hashes"]["portfolio071/verify_economics.py"]
    if (audit["accepted"] is not True or audit["registered_arms"] != 24 or len(audit["arms"]) != 24
            or audit["verifier_sha256"] != expected_auditor
            or sha(root / "portfolio071/verify_economics.py") != expected_auditor):
        raise ValueError("UNCHANGED_ACCEPTED_24_ACCOUNT_NATIVE_AUDIT_REQUIRED")
    by_arm = {row["arm"]: row for row in audit["arms"]}
    if len(by_arm) != 24 or set(by_arm) != {f"arm-{i:02d}" for i in range(24)}:
        raise ValueError("UNIQUE_EXACT_24_AUDITED_DIRECTORIES_REQUIRED")
    recipes = [(World(), capital, "working_capital_aware", False) for capital in CAPITALS_USD]
    recipes += [(world, 100000, "working_capital_aware", False) for world in registered_worlds()[1:]]
    recipes += [(World(), 100000, "working_capital_aware", True),
                (World(), 100000, "stylized_prepaid_reach_capacity", False)]
    rows = []
    for item in [*identity["prefixes"], *second["prefixes"]]:
        index = item["index"]
        if item["directory"] != f"arm-{index:02d}":
            raise ValueError("EXACT_ORIGINAL_ACCOUNT_DIRECTORY_REQUIRED")
        # Completed recovery exports are separate from the original interrupted
        # directory. The owner keeps appending to the original native account.
        folder = reproduction / "recovery" / item["directory"]
        original_folder = reproduction / "economics" / item["directory"]
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("REGULAR_RECOVERED_EXPORT_DIRECTORY_REQUIRED")
        if original_folder.is_symlink() or not original_folder.is_dir():
            raise ValueError("REGULAR_ORIGINAL_ACCOUNT_DIRECTORY_REQUIRED")
        manifest, trajectory = read(folder / "manifest.json"), read(folder / "trajectory.json")
        current_audit = reaudit_current_inputs(reproduction / "native-source", folder, by_arm[item["directory"]])
        world, capital, policy, earned = recipes[index]
        expected_id = f"{world.name}-{capital}-{policy}-{int(earned)}"
        require = {
            "manifest_bytes_preserved": sha(folder / "manifest.json") == item["manifest_file_sha256"],
            "original_manifest_bytes_preserved": sha(original_folder / "manifest.json") == item["manifest_file_sha256"],
            "manifest_content_preserved": digest(manifest) == item["manifest_canonical_sha256"],
            "registered_recipe_preserved": same(trajectory["world"], asdict(world))
                and type(trajectory["capital_usd"]) is int and trajectory["capital_usd"] == capital
                and trajectory["policy"] == policy and trajectory["earned_only_k2"] is earned,
            "registered_identity_preserved": trajectory["id"] == expected_id
                and item["durable_header"]["config"]["contract"] == "portfolio071-" + digest(expected_id)[:24],
            "original_opening_no_new_equity": item["durable_header"]["config"]["opening"] == capital * 1000000
                and item["durable_header"]["config"]["working"] == 0,
            "accepted_native_audit_for_same_account": by_arm[item["directory"]]["accepted"] is True
                and by_arm[item["directory"]]["id"] == expected_id,
        }
        comparisons = {}
        final_drain = None
        for name, hash_field in (("native-at-horizon.json", "native_export_sha256"),
                                 ("native-after-drain.json", "drain_export_sha256")):
            exported = read(folder / name)
            comparison = verify_prefix(item, exported)
            comparisons[name] = comparison
            require[name + "_unchanged_original_prefix"] = comparison["accepted"]
            require[name + "_trajectory_binding"] = sha(folder / name) == trajectory[hash_field]
            closure = exported["connected_journal"]["source"]["files"]
            require[name + "_original_runtime_source"] = all(freeze["source_hashes"].get(path) == value
                and sha(reproduction / "native-source" / path) == value for path, value in closure.items())
            if name == "native-after-drain.json":
                final_drain = exported
        original_actions_path = original_folder / "account.sqlite.actions.jsonl"
        if original_actions_path.is_symlink() or not original_actions_path.is_file():
            raise ValueError("REGULAR_ORIGINAL_PUBLIC_ACTION_TAPE_REQUIRED")
        final_raw = canonical(item["durable_header"]) + b"\n"
        final_raw += b"".join(canonical(row) + b"\n" for row in final_drain["ledger"]["actions"])
        require["original_account_durable_tape_matches_final_export"] = (
            original_actions_path.stat().st_size == len(final_raw)
            and sha(original_actions_path) == hashlib.sha256(final_raw).hexdigest())
        original_journal = read(original_folder / "account.sqlite.connected-journal.json")["body"]
        require["original_account_public_journal_matches_final_export"] = same(
            original_journal, final_drain["connected_journal"])
        require["original_interruption_not_relabelled_complete"] = not (original_folder / "trajectory.json").exists()
        require["current_public_inputs_remain_bound_to_reaudit"] = public_input_hashes(folder) == current_audit["input_sha256"]
        rows.append({"index": index, "directory": item["directory"], "accepted": all(require.values()),
                     "checks": require, "exports": comparisons,
                     "current_native_reaudit": current_audit,
                     "trajectory_sha256": sha(folder / "trajectory.json")})
    preserved = {name: public_input_hashes(reproduction / "economics" / name) == hashes
                 for name, hashes in second["completed_public_file_sha256"].items()}
    return {"schema": "portfolio071/independent-recovered-prefix-audit/v2",
            "accepted": all(row["accepted"] for row in rows) and len(preserved) == 16 and all(preserved.values()),
            "registered_arms": 24, "recovered_indices": RECOVERED_INDICES, "arms": rows,
            "original_prefix_identities_sha256": PREFIX_SHA256,
            "second_prefix_identities_sha256": SECOND_PREFIX_SHA256,
            "sixteen_completed_public_accounts_preserved": preserved,
            "full_native_audit_sha256": sha(audit_report), "checker_sha256": sha(__file__),
            "additional_native_reaudit_cpu_seconds": sum(row["current_native_reaudit"]["process_cpu_seconds"] for row in rows),
            "scope": "Exact preservation of seven independently recorded native action prefixes and completed journal entries, with only the recorded final arm22 PENDING intent allowed its native resolution. This supplements the full24 native audit and recovery-source review; public hashes do not establish private HMAC ownership by themselves."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--reproduction-output", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.root, args.reproduction_output, args.audit_report)
    with args.output.open("xb") as stream:
        stream.write(canonical(report) + b"\n")
    print(json.dumps({"accepted": report["accepted"], "indices": report["recovered_indices"]}, sort_keys=True))
    if not report["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
