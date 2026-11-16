"""Preregistered, separate buyer-source financial replay regression tests.

No customer data, payment operations, native enterprise Account or external calls.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from products.contract_value_omega import core, run, verify
from products.contract_value_omega import verify_replay


DEMO=Path(__file__).resolve().parents[1]/"products"/"contract_value_omega"/"demo"


class IndependentReplayTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.inputs=self.base/"source"
        shutil.copytree(DEMO,self.inputs)

    def build(self, report, *, name="review"):
        folder=self.base/name
        run.write(folder,report)
        return folder

    def fixture(self):
        return core.audit(core.validate(self.inputs))

    def test_original_fictional_buyer_data_is_preserved(self):
        original=self.fixture()
        out=self.build(original)
        old=verify.verify(self.inputs,out)
        new=verify_replay.verify_report(self.inputs,out)
        self.assertEqual(old["status"],"PASS_SCOPED_BUYER_SCREEN_RECONCILIATION")
        self.assertEqual(new["status"],"PASS_SOURCE_DERIVED_FINANCIAL_REPLAY")
        cad=new["summary_by_currency"]["CAD"]
        self.assertEqual(cad["net_review_cents"],2_070_000)
        self.assertEqual(cad["paid_review_cents"],1_670_000)
        self.assertEqual(cad["realized_recoveries_cents"],0)
        self.assertEqual(new["lines"],10)

    def test_self_consistent_forged_contract_exposure_passes_old_gate_but_fails_replay(self):
        forged=deepcopy(self.fixture())
        line=next(x for x in forged["all_lines"] if x["line_id"]=="A-001")
        delta=line["expected_cents"]
        self.assertGreater(delta,0)
        line["expected_cents"]=0
        line["gross_discrepancy_cents"]=line["billed_cents"]
        line["net_review_cents"]=line["gross_discrepancy_cents"]-line["applied_credit_cents"]
        money=forged["summary_by_currency"]["CAD"]
        for key in ("gross_review_cents","net_review_cents","paid_review_cents"):
            money[key]+=delta
        out=self.build(forged,name="self-consistent-false-finding")
        # The old verifier checks arithmetic and checksums but not the source-derived contract price.
        self.assertEqual(verify.verify(self.inputs,out)["status"],"PASS_SCOPED_BUYER_SCREEN_RECONCILIATION")
        with self.assertRaisesRegex(core.InputError,"SOURCE_REPLAY_REJECTED"):
            verify_replay.verify_report(self.inputs,out)

    def test_forged_quantity_and_contract_provenance_rejected(self):
        altered=deepcopy(self.fixture())
        x=next(x for x in altered["all_lines"] if x["line_id"]=="A-001")
        x["max_evidenced_quantity"]=10**9
        x["evidence"]["term_ref"]="INVENTED-CONTRACT-REFERENCE"
        out=self.build(altered,name="false-origin")
        self.assertEqual(verify.verify(self.inputs,out)["status"],"PASS_SCOPED_BUYER_SCREEN_RECONCILIATION")
        with self.assertRaisesRegex(core.InputError,"SOURCE_REPLAY_REJECTED"):
            verify_replay.verify_report(self.inputs,out)

    def test_misleading_buyer_html_rehashed_is_rejected(self):
        out=self.build(self.fixture())
        html=out/"index.html"
        html.write_bytes(html.read_bytes().replace(b"Not a collected recovery",b"Collected recovery confirmed"))
        manifest=out/"SHA256SUMS.json"
        m=json.loads(manifest.read_text("utf-8"))
        m["files"]["index.html"]=hashlib.sha256(html.read_bytes()).hexdigest()
        manifest.write_bytes(core.canonical(m))
        # A manifest with unkeyed hashes is an integrity checklist, not an external attestation.
        self.assertEqual(verify.verify(self.inputs,out)["status"],"PASS_SCOPED_BUYER_SCREEN_RECONCILIATION")
        with self.assertRaisesRegex(core.InputError,"SOURCE_REPLAY_REJECTED"):
            verify_replay.verify_report(self.inputs,out)

    def test_missing_or_changed_inputs_rejected_without_regenerating_authority(self):
        out=self.build(self.fixture())
        with (self.inputs/"credits.csv").open("a",encoding="utf-8") as f:
            f.write("C-SUBSEQUENT,A-001,1.00,CAD,SYNTHETIC-POSTRUN-CREDIT\n")
        with self.assertRaises((core.InputError,ValueError)):
            verify_replay.verify_report(self.inputs,out)

    def test_report_extra_undeclared_file_rejected(self):
        out=self.build(self.fixture())
        (out/"invented_recovery.txt").write_text("RECOVERED")
        with self.assertRaisesRegex(core.InputError,"SOURCE_REPLAY_REJECTED"):
            verify_replay.verify_report(self.inputs,out)


if __name__=="__main__":
    unittest.main()
