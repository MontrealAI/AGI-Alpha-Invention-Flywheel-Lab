"""Adversarial checks for the independent public-prefix comparison only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from commercial.ledger import canonical, digest
from scripts.verify_portfolio071_recovery_prefix import PUBLIC_FILES, reaudit_current_inputs, verify_prefix


def fixture():
    header = {"schema": "test-public-tape", "config": {"contract": "original", "opening": 100, "working": 0}}
    actions = [{"seq": 0, "op": "cost", "args": {"amount": 3}, "day": 0},
               {"seq": 1, "op": "wallet", "args": {"amount": 5}, "day": 1}]
    journal_header = {"contract": "original", "opening": 100, "source": {"files": {"controller.py": "frozen"}}}
    entries = [{"status": "COMPLETE", "request": {"id": "a"}, "receipt": {"amount": 3}},
               {"status": "COMPLETE", "request": {"id": "b"}, "receipt": {"amount": 5}}]
    journal = {**journal_header, "entries": entries}
    raw = b"".join(canonical(value) + b"\n" for value in [header, *actions])
    identity = {"native_actions": 2, "journal_entries": 2, "durable_header": header,
                "native_actions_prefix_sha256": digest(actions), "durable_actions_file_bytes": len(raw),
                "durable_actions_file_sha256": hashlib.sha256(raw).hexdigest(),
                "journal_header": journal_header, "journal_entries_sha256": digest(entries),
                "journal_body_sha256": digest(journal), "last_journal_request": entries[-1]["request"]}
    exported = {"ledger": {"config": header["config"], "actions": actions},
                "connected_journal": journal, "connected_journal_sha256": digest(journal)}
    return copy.deepcopy(identity), copy.deepcopy(exported)


def pending_fixture():
    identity, exported = fixture()
    pending = {"key": "native:register_terms:test", "status": "PENDING",
               "request": {"operation": "execute", "op": "register_terms",
                           "args": {"id": "test", "terms": {"declared": True}}, "day": 2},
               "plan": None, "funding": None, "attempt": {"native_sequence": 2},
               "obligation_receipt": None, "receipt": None}
    entries = copy.deepcopy(exported["connected_journal"]["entries"])
    original_entries = [*entries, pending]
    identity.update(index=22, journal_entries=3, pending_entry_index=2,
                    pending_entry=copy.deepcopy(pending), completed_journal_entries=2,
                    completed_journal_entries_sha256=digest(entries),
                    journal_entries_sha256=digest(original_entries),
                    journal_body_sha256=digest({**identity["journal_header"], "entries": original_entries}),
                    last_journal_request=copy.deepcopy(pending["request"]))
    resolved = {**copy.deepcopy(pending), "status": "COMPLETE", "receipt": {"sequence": 3}}
    exported["connected_journal"]["entries"].append(resolved)
    exported["ledger"]["actions"].append({"seq": 2, "op": "register_terms",
        "args": copy.deepcopy(pending["request"]["args"]), "day": 2})
    exported["connected_journal_sha256"] = digest(exported["connected_journal"])
    return identity, exported


class PrefixChecks(unittest.TestCase):
    def test_exact_prefix_allows_later_append(self):
        identity, exported = fixture()
        exported["ledger"]["actions"].append({"seq": 2, "op": "cost", "args": {"amount": 2}, "day": 2})
        exported["connected_journal"]["entries"].append({"status": "COMPLETE", "request": {"id": "c"}})
        exported["connected_journal_sha256"] = digest(exported["connected_journal"])
        self.assertTrue(verify_prefix(identity, exported)["accepted"])

    def test_changed_historical_cash_action_refused(self):
        identity, exported = fixture()
        exported["ledger"]["actions"][0]["args"]["amount"] = 0
        self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_reordered_prefix_refused(self):
        identity, exported = fixture()
        exported["ledger"]["actions"].reverse()
        self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_changed_opening_or_authority_refused(self):
        for field, value in (("opening", 200), ("contract", "replacement")):
            identity, exported = fixture()
            exported["ledger"]["config"][field] = value
            self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_receipt_mutation_refused_even_with_updated_public_commitment(self):
        identity, exported = fixture()
        exported["connected_journal"]["entries"][0]["receipt"]["amount"] = 0
        exported["connected_journal_sha256"] = digest(exported["connected_journal"])
        self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_source_change_refused(self):
        identity, exported = fixture()
        exported["connected_journal"]["source"]["files"]["controller.py"] = "changed"
        exported["connected_journal_sha256"] = digest(exported["connected_journal"])
        self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_truncation_refused(self):
        identity, exported = fixture()
        exported["ledger"]["actions"].pop()
        exported["connected_journal"]["entries"].pop()
        exported["connected_journal_sha256"] = digest(exported["connected_journal"])
        self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_boolean_prefix_count_refused(self):
        identity, exported = fixture()
        identity["native_actions"] = True
        with self.assertRaises(ValueError):
            verify_prefix(identity, exported)

    def test_only_recorded_pending_intent_can_resolve_at_first_appended_action(self):
        identity, exported = pending_fixture()
        self.assertTrue(verify_prefix(identity, exported)["accepted"])

    def test_mutated_pending_intent_or_preattempt_refused(self):
        for field in ("request", "attempt", "funding"):
            identity, exported = pending_fixture()
            exported["connected_journal"]["entries"][-1][field] = {"changed": True}
            exported["connected_journal_sha256"] = digest(exported["connected_journal"])
            self.assertFalse(verify_prefix(identity, exported)["accepted"], field)

    def test_pending_resolution_cannot_skip_or_precede_an_unrelated_action(self):
        for mutation in ("missing", "different", "wrong-time"):
            identity, exported = pending_fixture()
            if mutation == "missing":
                exported["ledger"]["actions"].pop()
            elif mutation == "different":
                exported["ledger"]["actions"][-1]["op"] = "wallet"
            else:
                exported["ledger"]["actions"][-1]["day"] = 3
            self.assertFalse(verify_prefix(identity, exported)["accepted"], mutation)

    def test_unresolved_or_rejected_pending_intent_is_not_recovery_success(self):
        for status in ("PENDING", "REJECTED"):
            identity, exported = pending_fixture()
            exported["connected_journal"]["entries"][-1]["status"] = status
            exported["connected_journal_sha256"] = digest(exported["connected_journal"])
            self.assertFalse(verify_prefix(identity, exported)["accepted"], status)

    def test_pending_resolution_does_not_relax_prior_completed_entries(self):
        identity, exported = pending_fixture()
        exported["connected_journal"]["entries"][0]["receipt"]["amount"] = 0
        exported["connected_journal_sha256"] = digest(exported["connected_journal"])
        self.assertFalse(verify_prefix(identity, exported)["accepted"])

    def test_stale_same_identity_audit_refused_after_suffix_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name in PUBLIC_FILES:
                (folder / name).write_text('{"suffix_profit":12}\n')
            recorded = {"accepted": True, "arm": "arm-08", "id": "same-registered-identity", "profit": 10}

            def current_native_audit(root, current_folder):
                current = json.loads((current_folder / "native-after-drain.json").read_text())
                return {**recorded, "profit": current["suffix_profit"]}

            with mock.patch("scripts.verify_portfolio071_recovery_prefix.audit_arm", side_effect=current_native_audit) as native:
                with self.assertRaisesRegex(ValueError, "RECORDED_AUDIT_DOES_NOT_MATCH_CURRENT_NATIVE_INPUTS"):
                    reaudit_current_inputs(folder, folder, recorded)
                native.assert_called_once()

    def test_input_mutation_during_reaudit_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for name in PUBLIC_FILES:
                (folder / name).write_text('{}\n')
            recorded = {"accepted": True, "arm": "arm-08"}

            def mutating_audit(root, current_folder):
                (current_folder / "trajectory.json").write_text('{"changed":true}\n')
                return recorded

            with mock.patch("scripts.verify_portfolio071_recovery_prefix.audit_arm", side_effect=mutating_audit):
                with self.assertRaisesRegex(ValueError, "PUBLIC_INPUT_CHANGED_DURING_NATIVE_REAUDIT"):
                    reaudit_current_inputs(folder, folder, recorded)


if __name__ == "__main__":
    unittest.main()
