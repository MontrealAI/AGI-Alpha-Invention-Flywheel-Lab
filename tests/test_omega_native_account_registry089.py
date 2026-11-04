"""Red-first signed-account registration tests for Ω V4 (protocol 089).

Only disposable, legitimate, source-matched native JournalAccounts are used.
The native journal is valid in each arm. The independent V4 report verifier must
also check the originally registered financial account configuration, not just
report labels or the ledger's own self-consistent replay.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from connected_enterprise.finance import audit_journal
from mechanism_harness import cart_campaign as campaign
from mechanism_harness import cart_native as native
from mechanism_harness import market_cases as cases_module

PILOT = ((1337, "substitute"),)
ORIGINAL_MARKET = cases_module.market
ORIGINAL_EXECUTE = campaign.execute
ALT_CONTRACT = native.CONTRACT + "-alternate-fixture"
ASSERT_REGISTRATION = r"REGISTERED|ACCOUNT_CONFIGURATION|NATIVE_CONFIG|WRONG_.*ACCOUNT"


@contextmanager
def small_source_equivalent_market():
    """Same fixture transform already used by existing V4 native unit tests."""
    def small(*args, **kwargs):
        kwargs["width"] = 2
        return ORIGINAL_MARKET(*args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(campaign, "CASES", PILOT))
        stack.enter_context(patch.object(campaign, "market", side_effect=small))
        stack.enter_context(patch.object(cases_module, "market", side_effect=small))
        stack.enter_context(patch.object(
            campaign, "execute", side_effect=lambda: ORIGINAL_EXECUTE(PILOT)))
        yield


class RegisteredNativeAccountConfiguration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="omega-v4-registry089-")
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "account"

    def _independent_native_receipt(self, opening, working, contract):
        exp = native.read(self.out / "NATIVE_EXPORT.json")
        cfg = exp["ledger"]["config"]
        self.assertEqual(
            (cfg["opening"], cfg["working"], cfg["contract"]),
            (opening, working, contract),
            "The fault arm must have a genuine alternate signed native identity",
        )
        canonical_audit = audit_journal(
            exp, root=self.out / "runtime",
            manifest=native.read(self.out / "MANIFEST.json"),
        )
        self.assertTrue(canonical_audit, "The actual native account must replay")
        self.assertGreater(
            len(exp["ledger"]["actions"]), 0,
            "The attempted source-bound economic operation must exist",
        )
        return exp

    def _require_public_rejection(self):
        before_export = (self.out / "NATIVE_EXPORT.json").read_bytes()
        before_report = (self.out / "REPORT.json").read_bytes()
        with small_source_equivalent_market(), self.assertRaisesRegex(
            ValueError, ASSERT_REGISTRATION
        ):
            native.audit(self.out)
        self.assertEqual(before_export, (self.out / "NATIVE_EXPORT.json").read_bytes())
        self.assertEqual(before_report, (self.out / "REPORT.json").read_bytes())

    def _run_alt(self, override):
        # The implementation may correctly reject a mismatch after it has
        # written the native export/report and entered its own final audit.
        with small_source_equivalent_market(), patch.object(
            native, "JournalAccount", side_effect=override
        ):
            try:
                native.run(self.out, stress="no_demand")
            except ValueError:
                if not (self.out / "NATIVE_EXPORT.json").is_file():
                    raise
        self.assertTrue((self.out / "REPORT.json").is_file())

    def test_01_alternate_opening_not_laundered_by_report_label(self):
        alternate_opening = 200_000 * 1_000_000
        with small_source_equivalent_market(), patch.object(
            native, "OPENING", alternate_opening
        ):
            native.run(self.out, stress="no_demand")
        self._independent_native_receipt(
            alternate_opening, 0, native.CONTRACT)
        # The recorded display field is not a financial authority.
        report = copy.deepcopy(native.read(self.out / "REPORT.json"))
        self.assertEqual(report["opening_microUSD"], alternate_opening)
        report["opening_microUSD"] = native.OPENING
        native.save(self.out / "REPORT.json", report)
        self._require_public_rejection()

    def test_02_alternate_working_reserve_must_not_audit_as_registered(self):
        original = native.JournalAccount
        def alternate(*args, **kwargs):
            kwargs["working"] = 1_000_000
            return original(*args, **kwargs)
        self._run_alt(alternate)
        self._independent_native_receipt(
            native.OPENING, 1_000_000, native.CONTRACT)
        self._require_public_rejection()

    def test_03_alternate_contract_must_not_audit_as_registered(self):
        original = native.JournalAccount
        def alternate(*args, **kwargs):
            kwargs["contract"] = ALT_CONTRACT
            return original(*args, **kwargs)
        self._run_alt(alternate)
        self._independent_native_receipt(
            native.OPENING, 0, ALT_CONTRACT)
        self._require_public_rejection()


if __name__ == "__main__":
    unittest.main()
