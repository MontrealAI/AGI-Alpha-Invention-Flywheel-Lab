"""Same-account recovery qualification on explicitly nonbusiness test fixtures."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from commercial.ledger import canonical
from connected_enterprise.finance import JournalAccount
from experiments.public_portfolio_20261102 import economics, recovery_run, service
from experiments.public_portfolio_20261102.native import BusinessAccount


class InjectedInterruption(BaseException):
    pass


ROOT = Path(__file__).resolve().parents[3]


class RecoveryTests(unittest.TestCase):
    """No campaign account is opened, modified or copied by these tests."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="r2-recovery-qualification-")
        cls.base = Path(cls.temporary.name)
        cls.products = json.loads((ROOT / economics.PREFIX / "PRODUCTS.json").read_text())
        if isinstance(cls.products, dict):
            cls.products = cls.products["products"]
        cls.protocol = json.loads((ROOT / economics.PROTOCOL).read_text())
        # Deliberately small guard-test world, not a rerun or market result.
        cls.protocol["months"] = 2
        cls.protocol["finite_market"]["prospects_per_route"] = 1
        cls.protocol["profiles_usd"]["interface"]["k2_development"] = 20
        cls.scenario = copy.deepcopy(next(s for s in cls.protocol["registered_scenarios"] if s["id"] == "central-100k"))
        cls.scenario["id"] = "recovery-guard-fixture"
        cls.baseline = cls.base / "baseline"
        (cls.baseline / "control").mkdir(parents=True)
        cls.reference = economics._run_case(ROOT, cls.baseline, cls.products, cls.protocol, "interface", cls.scenario)
        cls.reference_export = json.loads((cls.baseline / "public" / "interface-recovery-guard-fixture" / "account.public.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _interrupt(self, name, *, entry_number=None, pending=False, before_result=False,
                   partial_reserve=False, protocol=None, scenario=None):
        protocol = self.protocol if protocol is None else protocol
        scenario = self.scenario if scenario is None else scenario
        output = self.base / name
        (output / "control").mkdir(parents=True)
        trigger = {"fired": False}

        class InterruptedJournal(JournalAccount):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if partial_reserve:
                    original_reserve = self._account.reserve
                    def interrupted_reserve(*args, **kwargs):
                        result = original_reserve(*args, **kwargs)
                        if not trigger["fired"]:
                            trigger["fired"] = True
                            raise InjectedInterruption("Guard fixture: earned native reserve committed before resource finish")
                        return result
                    self._account.reserve = interrupted_reserve

            def _entry(self, key, request, **kwargs):
                row = super()._entry(key, request, **kwargs)
                if pending and not trigger["fired"] and len(self._journal["entries"]) == entry_number:
                    trigger["fired"] = True
                    raise InjectedInterruption("Guard fixture: durable pending intent before native execution")
                return row

            def _perform(self, entry):
                result = super()._perform(entry)
                if not pending and not trigger["fired"] and len(self._journal["entries"]) == entry_number:
                    trigger["fired"] = True
                    raise InjectedInterruption("Guard fixture: completed native operation, lost controller stack")
                return result

        class InterruptedBusiness(BusinessAccount):
            def __init__(self, root, manifest, path, *, opening, working=0, contract):
                self.root, self.manifest = Path(root).resolve(), copy.deepcopy(manifest)
                self.account = InterruptedJournal(root, manifest, path, opening=opening, working=working, contract=contract)

        def interrupt_save(path, value):
            if before_result and Path(path).name == "RESULT.json":
                trigger["fired"] = True
                raise InjectedInterruption("Guard fixture: ledger complete, result publication lost")
            economics._save(path, value)

        function = types.FunctionType(economics._run_case.__code__,
                                      {**economics._run_case.__globals__, "BusinessAccount": InterruptedBusiness,
                                       "_save": interrupt_save})
        with self.assertRaises(BaseException):
            function(ROOT, output, self.products, protocol, "interface", scenario)
        self.assertTrue(trigger["fired"])
        return output

    def _recover_and_compare(self, output, *, protocol=None, scenario=None, reference=None, reference_export=None):
        protocol = self.protocol if protocol is None else protocol
        scenario = self.scenario if scenario is None else scenario
        reference = self.reference if reference is None else reference
        reference_export = self.reference_export if reference_export is None else reference_export
        state, receipt = recovery_run.recover_case(ROOT, output, self.products, protocol, "interface", scenario)
        self.assertEqual(state, reference)
        exported = json.loads((output / "public" / ("interface-" + scenario["id"]) / "account.public.json").read_text())
        self.assertEqual(recovery_run._semantic_record(exported), recovery_run._semantic_record(reference_export))
        self.assertTrue(receipt["prefix_matched"])
        self.assertEqual(receipt["historical_requests_reexecuted_on_original"], 0)
        self.assertEqual(receipt["capital_copied_or_added_microUSD"], 0)
        return receipt

    def test_01_mid_begin_exact_same_account(self):
        entries = self.reference_export["connected_journal"]["entries"]
        number = next(i + 1 for i, e in enumerate(entries) if e["request"].get("op") == "offer")
        self._recover_and_compare(self._interrupt("mid-begin", entry_number=number))

    def test_02_after_prepared_delivery_and_cash_collection(self):
        entries = self.reference_export["connected_journal"]["entries"]
        number = next(i + 1 for i, e in enumerate(entries) if e["request"].get("op") == "event" and e["request"]["args"].get("action") == "release")
        self._recover_and_compare(self._interrupt("after-collection", entry_number=number))

    def test_03_pending_native_intent_normal_authenticated_reopen(self):
        entries = self.reference_export["connected_journal"]["entries"]
        number = next(i + 1 for i, e in enumerate(entries) if e["request"].get("op") == "event" and e["request"]["args"].get("action") == "fund")
        self._recover_and_compare(self._interrupt("pending-fund", entry_number=number, pending=True))

    def test_04_final_result_lost_after_complete_ledger(self):
        self._recover_and_compare(self._interrupt("lost-result", before_result=True))

    def test_05_manifest_mismatch_rejected_before_live_append(self):
        output = self._interrupt("manifest-mismatch", entry_number=3)
        folder = output / "public" / "interface-recovery-guard-fixture"
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["jobs"][0]["delivery_path"] += "-changed"
        (folder / "manifest.json").write_bytes(canonical(manifest) + b"\n")
        tape = output / "private" / "interface-recovery-guard-fixture" / "account.sqlite.actions.jsonl"
        before = tape.read_bytes()
        with self.assertRaisesRegex(ValueError, "EXACT_ORIGINAL_MANIFEST"):
            recovery_run.recover_case(ROOT, output, self.products, self.protocol, "interface", self.scenario)
        self.assertEqual(tape.read_bytes(), before)

    def test_06_controller_prefix_mismatch_rejected_before_append(self):
        output = self._interrupt("prefix-mismatch", entry_number=6)
        tape = output / "private" / "interface-recovery-guard-fixture" / "account.sqlite.actions.jsonl"
        before = tape.read_bytes()
        altered = copy.deepcopy(self.protocol)
        altered["profiles_usd"]["interface"]["monthly_fixed_overhead"] += 1
        with self.assertRaisesRegex(ValueError, "HISTORICAL_JOURNAL_REQUEST_OR_RESULT_MISMATCH"):
            recovery_run.recover_case(ROOT, output, self.products, altered, "interface", self.scenario)
        self.assertEqual(tape.read_bytes(), before)

    def test_07_complete_case_read_only_no_second_recovery(self):
        with self.assertRaisesRegex(ValueError, "COMPLETE_CASE_IS_READ_ONLY"):
            recovery_run.recover_case(ROOT, self.baseline, self.products, self.protocol, "interface", self.scenario)

    def test_08_pending_earned_reservation_keeps_authority_and_obligation(self):
        protocol = copy.deepcopy(self.protocol)
        protocol["profiles_usd"]["interface"]["research_and_failed_work"] = 1
        protocol["profiles_usd"]["interface"]["rights_and_setup"] = 0
        protocol["profiles_usd"]["interface"]["monthly_fixed_overhead"] = 0
        scenario = {**self.scenario, "id": "recovery-earned-fixture"}
        baseline = self.base / "earned-baseline"
        (baseline / "control").mkdir(parents=True)
        reference = economics._run_case(ROOT, baseline, self.products, protocol, "interface", scenario)
        export = json.loads((baseline / "public" / ("interface-" + scenario["id"]) / "account.public.json").read_text())
        self.assertTrue(export["action_proofs"])
        interrupted = self._interrupt("pending-earned", partial_reserve=True, protocol=protocol, scenario=scenario)
        self._recover_and_compare(interrupted, protocol=protocol, scenario=scenario, reference=reference, reference_export=export)

    def test_09_historical_refused_spend_uses_historical_cash(self):
        protocol = copy.deepcopy(self.protocol)
        profile = protocol["profiles_usd"]["interface"]
        profile["research_and_failed_work"] = 1
        profile["rights_and_setup"] = 0
        protocol["months"] = 4
        profile["monthly_fixed_overhead"] = 1
        profile["acquisition"] = 55
        scenario = {**self.scenario, "id": "recovery-refusal-fixture", "policy": "greedy"}
        baseline = self.base / "refusal-baseline"
        (baseline / "control").mkdir(parents=True)
        reference = economics._run_case(ROOT, baseline, self.products, protocol, "interface", scenario)
        export = json.loads((baseline / "public" / ("interface-" + scenario["id"]) / "account.public.json").read_text())
        self.assertTrue(any(d.get("reason") == "ELIGIBLE_CONTACT_UNAFFORDABLE" for d in reference["decisions"]))
        number = next(i + 1 for i, e in enumerate(export["connected_journal"]["entries"])
                      if e["request"].get("args", {}).get("id") == "monthly-fixed-maintenance-3")
        interrupted = self._interrupt("historical-refused-spend", entry_number=number,
                                      protocol=protocol, scenario=scenario)
        self._recover_and_compare(interrupted, protocol=protocol, scenario=scenario, reference=reference, reference_export=export)

    def test_10_changed_helper_identity_rejected_without_mutating_source(self):
        output = self._interrupt("changed-helper-identity", entry_number=3)
        tape = output / "private" / "interface-recovery-guard-fixture" / "account.sqlite.actions.jsonl"
        before = tape.read_bytes()
        original_hashes = service._source_hashes
        def changed_hashes(root):
            hashes = original_hashes(root)
            hashes["production060/service.py"] = "0" * 64
            return hashes
        # In-memory source-identity fault injection only; frozen source files are
        # never edited. Actual helper-file mutation is covered by guard002.
        with patch.object(service, "_source_hashes", changed_hashes):
            with self.assertRaisesRegex(ValueError, "EXACT_ORIGINAL_MANIFEST"):
                recovery_run.recover_case(ROOT, output, self.products, self.protocol, "interface", self.scenario)
        self.assertEqual(tape.read_bytes(), before)

    def test_11_corrupt_partial_public_output_fails_without_overwrite(self):
        output = self._interrupt("corrupt-existing-aggregation", before_result=True)
        folder = output / "public" / "interface-recovery-guard-fixture"
        aggregation = folder / "aggregation.json"
        corrupted = aggregation.read_bytes() + b" "
        aggregation.write_bytes(corrupted)
        tape = output / "private" / "interface-recovery-guard-fixture" / "account.sqlite.actions.jsonl"
        before = tape.read_bytes()
        with self.assertRaisesRegex(ValueError, "EXISTING_PUBLIC_ARTIFACT_MUST_BE_IDENTICAL"):
            recovery_run.recover_case(ROOT, output, self.products, self.protocol, "interface", self.scenario)
        self.assertEqual(aggregation.read_bytes(), corrupted)
        self.assertEqual(tape.read_bytes(), before)
        self.assertFalse((folder / "RESULT.json").exists())

    def test_12_two_maturities_in_one_advance_switch_individually(self):
        products = [p for p in self.products if p["route"] == "interface"]
        manifest = economics.prepare_manifest(ROOT, products, "interface-multiple-maturity-guard")
        artifact = json.loads((ROOT / next(p["product_path"] for p in products if p["id"] == "interface-k1")).read_text())
        settings = {"opening": 100_000_000, "working": 0, "contract": "public-portfolio-multiple-maturity-guard"}
        def before_maturities(account):
            account.cost("guard-origin", 0, 0)
            for number in range(2):
                order = "multiple-maturity-guard-" + str(number)
                account.begin("interface-k1", order, "guard-buyer-" + str(number),
                              1_000_000, 3_000_000, 0, 2, 12, 20_000)
            for number in range(2):
                order = "multiple-maturity-guard-" + str(number)
                account.deliver(order, "interface-k1", artifact, 1)
            for number in range(2):
                order = "multiple-maturity-guard-" + str(number)
                account.event(order, "release", 2)
        baseline = self.base / "multi-maturity-baseline"
        path = baseline / "private" / "case" / "account.sqlite"
        path.parent.mkdir(parents=True)
        with BusinessAccount(ROOT, manifest, path, **settings) as account:
            before_maturities(account)
            account.advance(13)
            reference = account.export()
        interrupted = self.base / "multi-maturity-interrupted"
        (interrupted / "control").mkdir(parents=True)
        path = interrupted / "private" / "case" / "account.sqlite"
        path.parent.mkdir(parents=True)
        with BusinessAccount(ROOT, manifest, path, **settings) as account:
            before_maturities(account)
            original_perform = account.account._perform
            trigger = {"fired": False}
            def interrupt_first_maturity(entry):
                result = original_perform(entry)
                if not trigger["fired"] and entry["request"].get("op") == "mature":
                    trigger["fired"] = True
                    raise InjectedInterruption("Guard fixture: first of two maturities committed")
                return result
            account.account._perform = interrupt_first_maturity
            with self.assertRaises(InjectedInterruption):
                account.advance(13)
            prefix = account.export()
        receipt = {}
        account = BusinessAccount.__new__(BusinessAccount)
        account.root, account.manifest = ROOT, manifest
        account.account = recovery_run.PrefixRelay(ROOT, manifest, path, receipt=receipt, **settings)
        try:
            before_maturities(account)
            account.advance(13)
            actual = account.export()
            self.assertEqual(recovery_run._semantic_record(actual), recovery_run._semantic_record(reference))
            self.assertEqual(actual["ledger"]["actions"][:-1], prefix["ledger"]["actions"])
            self.assertTrue(receipt["prefix_matched"])
            self.assertEqual([a["op"] for a in actual["ledger"]["actions"][-2:]], ["mature", "mature"])
        finally:
            account.close()


if __name__ == "__main__":
    unittest.main()
