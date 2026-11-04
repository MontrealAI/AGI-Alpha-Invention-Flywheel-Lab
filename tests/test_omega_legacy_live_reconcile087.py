"""Red-first authenticated-completion regressions for the inherited V3 native CLI.

This is deliberately disjoint from the financial owner: fresh temporary
synthetic accounts only; no P0 account, registered evidence or financial source
is changed. Public portable audit and local authenticated resume have different
responsibilities. The latter must reject missing live authority and legitimately
extended journal history, without re-signing the exported historical report.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanism_harness import mechanism_native as native
from mechanism_harness import mechanism_campaign as campaign
from mechanism_harness import market_cases

PILOT = ((1337, "substitute"),)
ORIGINAL_MARKET = market_cases.market
ORIGINAL_EXECUTE = campaign.execute


@contextmanager
def pilot():
    """Smaller deterministic engineering fixture, not a new business cohort."""
    def small(*args, **kwargs):
        kwargs["width"] = 2
        return ORIGINAL_MARKET(*args, **kwargs)
    with ExitStack() as stack:
        stack.enter_context(patch.object(campaign, "CASES", PILOT))
        stack.enter_context(patch.object(campaign, "market", side_effect=small))
        stack.enter_context(patch.object(market_cases, "market", side_effect=small))
        stack.enter_context(patch.object(campaign, "execute",
                                         side_effect=lambda: ORIGINAL_EXECUTE(PILOT)))
        yield


class CompletedV3NativeAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="omega-legacy-live087-")
        cls.path = Path(cls.temp.name) / "fresh-account"
        with pilot():
            cls.completed = native.run(cls.path)
            assert native.audit(cls.path)["accepted"]
        cls.recorded_bytes = (cls.path / "NATIVE_EXPORT.json").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_01_completed_resume_requires_existing_private_authority(self):
        """A key-free export may be audited, but must never authorize resume."""
        key = self.path / "account.sqlite.adaptive-simulation-key"
        self.assertTrue(key.is_file())
        held = key.with_name(key.name + ".held-by-review087")
        key.rename(held)
        try:
            with pilot():
                self.assertTrue(native.audit(self.path)["accepted"])
                with self.assertRaises((ValueError, FileNotFoundError, PermissionError)):
                    native.run(self.path, resume=True)
        finally:
            held.rename(key)
        self.assertEqual((self.path / "NATIVE_EXPORT.json").read_bytes(),
                         self.recorded_bytes)

    def test_02_completed_resume_rejects_later_genuine_native_debit(self):
        """A valid new debit is not tampering, but makes a cached report stale."""
        manifest = native.read(self.path / "MANIFEST.json")
        account = native.JournalAccount(
            self.path / "runtime", manifest, self.path / "account.sqlite",
            opening=native.OPENING, working=0, contract=native.CONTRACT
        )
        try:
            before = account.export()
            account.cost("review087-legitimate-post-report-expense", 1_000_000, 364)
            after = account.export()
            self.assertNotEqual(before, after)
            self.assertNotEqual(after, native.read(self.path / "NATIVE_EXPORT.json"))
        finally:
            account.close()

        with pilot():
            # Portable audit correctly addresses its recorded export only.
            self.assertTrue(native.audit(self.path)["accepted"])
            # Local resume instead must reconcile the *live* authenticated account.
            with self.assertRaises((ValueError, FileNotFoundError, PermissionError)):
                native.run(self.path, resume=True)
        self.assertEqual((self.path / "NATIVE_EXPORT.json").read_bytes(),
                         self.recorded_bytes)


if __name__ == "__main__":
    unittest.main()
