"""Financial assurance and adversarial qualification for CONTRACT VALUE Ω."""
from __future__ import annotations

import csv
from pathlib import Path
import shutil
import tempfile
import unittest

from products.contract_value_omega import core,run,verify


ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/"products"/"contract_value_omega"/"demo"


class ContractValueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.inputs=self.base/"input"
        shutil.copytree(DEMO,self.inputs)

    def test_demo_financial_reconciliation_is_source_grounded(self):
        result=core.audit(core.validate(self.inputs))
        cad=result["summary_by_currency"]["CAD"]
        self.assertEqual(result["rows_screened"],10)
        self.assertEqual(cad["billed_cents"],6300000)
        self.assertEqual(cad["gross_review_cents"],2100000)
        self.assertEqual(cad["net_review_cents"],2070000)
        self.assertEqual(cad["paid_review_cents"],1670000)
        self.assertEqual(cad["unpaid_or_unclear_review_cents"],400000)
        self.assertEqual(cad["candidate_lines"],5)
        self.assertEqual(cad["evidence_gaps"],2)
        self.assertEqual(cad["realized_recoveries_cents"],0)
        findings={x["line_id"]:x for x in result["all_lines"]}
        self.assertEqual(findings["A-001"]["gross_discrepancy_cents"],100000)
        self.assertEqual(findings["A-001"]["net_review_cents"],70000)
        self.assertEqual(findings["A-003"]["net_review_cents"],1100000)
        self.assertEqual(findings["A-004"]["net_review_cents"],200000)
        self.assertEqual(findings["B-001"]["net_review_cents"],300000)
        self.assertEqual(findings["B-002"]["net_review_cents"],400000)
        self.assertEqual(findings["B-002"]["decision"],"PREPAYMENT_OR_PAYMENT_EVIDENCE_REVIEW")
        self.assertEqual(findings["A-005"]["decision"],"EVIDENCE_GAP")
        self.assertEqual(findings["A-007"]["decision"],"EVIDENCE_GAP")

    def test_exact_duplicate_requires_entire_supplier_document(self):
        loaded=core.validate(self.inputs)
        self.assertEqual(loaded["duplicates"],{"A-101"})
        parsed=core.audit(loaded)
        affected=[x for x in parsed["all_lines"] if x["invoice_id"]=="A-101"]
        self.assertEqual(sum(x["net_review_cents"] for x in affected),1300000)
        self.assertTrue(all("EXACT_DUPLICATE_SUPPLIER_DOCUMENT" in x["reasons"] for x in affected))

    def test_deployment_creates_human_usable_artifacts_and_verifies(self):
        result=core.audit(core.validate(self.inputs))
        output=self.base/"buyer-review"
        summary=run.write(output,result)
        self.assertTrue((output/"index.html").is_file())
        self.assertTrue((output/"review.csv").is_file())
        self.assertTrue((output/"SHA256SUMS.json").is_file())
        self.assertEqual(len(list((output/"supplier_packets").glob("*.md"))),2)
        self.assertEqual(summary["candidates"],5)
        self.assertEqual(summary["evidence_gaps"],2)
        proof=verify.verify(self.inputs,output)
        self.assertEqual(proof["status"],"PASS_SCOPED_BUYER_SCREEN_RECONCILIATION")
        with self.assertRaises(core.InputError):
            run.write(output,result)

    def test_changed_customer_source_invalidates_published_audit(self):
        report=self.base/"report"
        run.write(report,core.audit(core.validate(self.inputs)))
        with (self.inputs/"payments.csv").open("a") as f:
            f.write("P-999,B-201,4000.00,CAD,SYNTHETIC-POSTAUDIT-PAYMENT\n")
        with self.assertRaisesRegex(core.InputError,"inputs modified"):
            verify.verify(self.inputs,report)

    def test_modified_report_is_rejected(self):
        report=self.base/"report"
        run.write(report,core.audit(core.validate(self.inputs)))
        with (report/"review.csv").open("a") as f:
            f.write("INVENTED,CLAIM,999999.00\n")
        with self.assertRaisesRegex(core.InputError,"modified report"):
            verify.verify(self.inputs,report)

    def test_incomplete_usage_does_not_fabricate_billed_units(self):
        (self.inputs/"usage.csv").write_text(
            "supplier_id,service_code,service_period,currency,billable_quantity,usage_ref\n")
        r=core.audit(core.validate(self.inputs))
        rows={x["line_id"]:x for x in r["all_lines"]}
        self.assertEqual(rows["B-001"]["net_review_cents"],0)
        self.assertEqual(rows["B-002"]["net_review_cents"],0)
        self.assertEqual(rows["B-001"]["decision"],"EVIDENCE_GAP")
        # Valid independently sourced rate evidence still permits a bounded rate check.
        self.assertEqual(rows["A-001"]["net_review_cents"],70000)

    def test_ambiguous_contract_does_not_make_up_a_price(self):
        with (self.inputs/"contracts.csv").open("a") as f:
            f.write("MSA-2026-X,NORTHSTAR-MSP,SEATS,CAD,2026-01-01,2026-12-31,90.00,UNSIGNED-AMENDMENT\n")
        r=core.audit(core.validate(self.inputs))
        rows={x["line_id"]:x for x in r["all_lines"]}
        self.assertEqual(rows["A-001"]["net_review_cents"],0)
        self.assertIn("MISSING_OR_AMBIGUOUS_CONTRACT",rows["A-001"]["reasons"])
        self.assertEqual(rows["A-003"]["net_review_cents"],1100000)

    def test_cannot_inject_html_from_invoice_source_ref(self):
        p=self.inputs/"invoices.csv"
        s=p.read_text()
        s=s.replace("SYNTHETIC-INVOICE-NS-200","<script>alert(1)</script>")
        p.write_text(s)
        r=core.audit(core.validate(self.inputs))
        html=run.report_html(r).decode()
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>alert(1)</script>",html)

    def test_malformed_amounts_and_forged_credits_rejected(self):
        p=self.inputs/"invoices.csv"
        original=p.read_text()
        p.write_text(original.replace("11000.00,CAD","11000.01,CAD",1))
        with self.assertRaisesRegex(core.InputError,"line amount"):
            core.validate(self.inputs)
        p.write_text(original)
        credits=self.inputs/"credits.csv"
        credits.write_text(credits.read_text()+"C-002,A-001,99999.00,CAD,SYNTHETIC-INVALID-CREDIT\n")
        with self.assertRaisesRegex(core.InputError,"credits exceed"):
            core.validate(self.inputs)

    def test_payment_id_and_unknown_invoice_are_rejected(self):
        p=self.inputs/"payments.csv"
        original=p.read_text()
        p.write_text(original+"P-001,B-201,4000.00,CAD,DUPLICATE-PAYMENT\n")
        with self.assertRaisesRegex(core.InputError,"duplicate payment"):
            core.validate(self.inputs)
        p.write_text(original+"P-999,GHOST,100.00,CAD,UNKNOWN-INVOICE\n")
        with self.assertRaisesRegex(core.InputError,"unknown invoice"):
            core.validate(self.inputs)

    def test_currency_buckets_do_not_sum_different_units(self):
        with (self.inputs/"contracts.csv").open("a") as f:
            f.write("MSA-EUR,EU-SUPPLIER,STORAGE,EUR,2026-01-01,2026-12-31,50.00,SYNTHETIC-EUR-TERM\n")
        with (self.inputs/"invoices.csv").open("a") as f:
            f.write("EU-001,EU-100,EU-SUPPLIER,EU-NUM-100,2026-10-06,2026-09,STORAGE,10,55.00,550.00,EUR,SYNTHETIC-EU-INV\n")
        with (self.inputs/"usage.csv").open("a") as f:
            f.write("EU-SUPPLIER,STORAGE,2026-09,EUR,10,SYNTHETIC-EU-USAGE\n")
        r=core.audit(core.validate(self.inputs))
        self.assertEqual(r["summary_by_currency"]["CAD"]["net_review_cents"],2070000)
        self.assertEqual(r["summary_by_currency"]["EUR"]["net_review_cents"],5000)
        self.assertEqual(r["summary_by_currency"]["EUR"]["realized_recoveries_cents"],0)

    def test_exactly_reproducible_local_outputs(self):
        r=core.audit(core.validate(self.inputs))
        a=self.base/"first";b=self.base/"second"
        run.write(a,r);run.write(b,r)
        for p in a.rglob("*"):
            if p.is_file():
                self.assertEqual(p.read_bytes(),(b/p.relative_to(a)).read_bytes())

if __name__=="__main__":
    unittest.main()
