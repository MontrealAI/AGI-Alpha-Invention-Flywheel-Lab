import copy
import random
import unittest

from commercial.service_verifier import audit_delivery


def order():
    return {"scope": "SYNTHETIC_PUBLIC_WORKLOAD", "currency": "USD", "order_id": "checker-control", "invoices": [{"id": "I1", "customer": "A", "amount_cents": 100}, {"id": "I2", "customer": "A", "amount_cents": 200}], "payments": [{"id": "P1", "customer": "A", "amount_cents": 100, "invoice_refs": ["I1", "I2"]}, {"id": "P2", "customer": "A", "amount_cents": 200, "invoice_refs": ["I1", "I2"]}]}


def delivery():
    return {"scope": "SYNTHETIC_PUBLIC_WORKLOAD", "currency": "USD", "order_id": "checker-control", "matches": [{"invoice_ids": ["I1", "I2"], "payment_ids": ["P1", "P2"], "invoice_cents": 300, "payment_cents": 300, "status": "MATCHED"}], "unmatched_invoices": [], "unmatched_payments": [], "exceptions": [], "totals": {"invoice_cents": 300, "payment_cents": 300, "matched_invoice_cents": 300, "matched_payment_cents": 300, "open_invoice_cents": 0, "unallocated_payment_cents": 0}, "accepted": True}


def unresolved(source):
    return {"scope": source["scope"], "currency": source["currency"], "order_id": source["order_id"], "matches": [], "unmatched_invoices": [r["id"] for r in source["invoices"]], "unmatched_payments": [r["id"] for r in source["payments"]], "exceptions": [{"kind": "UNMATCHED_INVOICE", "id": r["id"]} for r in source["invoices"]] + [{"kind": "UNMATCHED_PAYMENT", "id": r["id"]} for r in source["payments"]], "totals": {"invoice_cents": sum(r["amount_cents"] for r in source["invoices"]), "payment_cents": sum(r["amount_cents"] for r in source["payments"]), "matched_invoice_cents": 0, "matched_payment_cents": 0, "open_invoice_cents": sum(r["amount_cents"] for r in source["invoices"]), "unallocated_payment_cents": sum(r["amount_cents"] for r in source["payments"])}, "accepted": True}


class ServiceVerifierTests(unittest.TestCase):
    def test_valid_split_payment_group(self):
        self.assertTrue(audit_delivery(order(), delivery())["accepted"])

    def test_order_and_reference_permutations(self):
        rng = random.Random(39491)
        for _ in range(30):
            source, result = order(), delivery()
            rng.shuffle(source["invoices"])
            rng.shuffle(source["payments"])
            for payment in source["payments"]:
                rng.shuffle(payment["invoice_refs"])
            rng.shuffle(result["matches"][0]["invoice_ids"])
            rng.shuffle(result["matches"][0]["payment_ids"])
            self.assertTrue(audit_delivery(source, result)["accepted"])

    def test_summary_partition_and_identity_mutations(self):
        changes = [lambda x: x["totals"].__setitem__("payment_cents", 301), lambda x: x.__setitem__("scope", "OBSERVED"), lambda x: x.__setitem__("currency", "CAD"), lambda x: x.__setitem__("accepted", False), lambda x: x["matches"][0]["invoice_ids"].append("I1"), lambda x: x["matches"][0].__setitem__("payment_cents", 299), lambda x: x["unmatched_payments"].append("P1"), lambda x: x["exceptions"].append({"kind": "UNMATCHED_PAYMENT", "id": "P1"}), lambda x: x.__setitem__("order_id", "another-order"), lambda x: x["matches"][0].__setitem__("status", "PAID"), lambda x: x.__setitem__("matches", {}), lambda x: x["totals"].__setitem__("open_invoice_cents", False)]
        for change in changes:
            result = delivery()
            change(result)
            with self.subTest(result=result):
                self.assertFalse(audit_delivery(order(), result)["accepted"])

    def test_correct_arithmetic_cannot_hide_wrong_customer(self):
        source = order()
        source["payments"][0]["customer"] = "B"
        self.assertFalse(audit_delivery(source, delivery())["accepted"])

    def test_failing_to_do_unique_work_rejected(self):
        self.assertFalse(audit_delivery(order(), unresolved(order()))["accepted"])

    def test_ambiguous_amounts_remain_unmatched(self):
        source = order()
        for row in source["invoices"]:
            row["amount_cents"] = 100
        source["payments"] = [{"id": "P1", "customer": "A", "amount_cents": 100, "invoice_refs": []}]
        self.assertTrue(audit_delivery(source, unresolved(source))["accepted"])
        source["require_complete"] = True
        result = unresolved(source)
        result["accepted"] = False
        self.assertIn("REQUIRED_COMPLETE_UNMET", audit_delivery(source, result)["errors"])

    def test_reference_conflicts_not_resolved_by_arbitrary_order(self):
        source = order()
        source["payments"] = [{"id": "P1", "customer": "A", "amount_cents": 100, "invoice_refs": ["I1"]}, {"id": "P2", "customer": "A", "amount_cents": 300, "invoice_refs": ["I1", "I2"]}, {"id": "P3", "customer": "A", "amount_cents": 200, "invoice_refs": []}]
        self.assertTrue(audit_delivery(source, unresolved(source))["accepted"])

    def test_invalid_inputs_fail_closed(self):
        mutations = [lambda x: x.__setitem__("currency", "EUR"), lambda x: x["payments"][0].__setitem__("amount_cents", -1), lambda x: x["invoices"][0].__setitem__("amount_cents", True), lambda x: x["invoices"][0].__setitem__("amount_cents", float("nan")), lambda x: x["payments"][0].__setitem__("invoice_refs", ["I1", "I1"]), lambda x: x["invoices"].append(copy.deepcopy(x["invoices"][0])), lambda x: x["payments"][0].__setitem__("currency", "EUR"), lambda x: x.__setitem__("require_complete", 1)]
        for mutate in mutations:
            source = order()
            mutate(source)
            self.assertFalse(audit_delivery(source, delivery())["accepted"])
        self.assertFalse(audit_delivery(None, None)["accepted"])

    def test_receipts_bind_exact_inputs_and_deliveries(self):
        first = audit_delivery(order(), delivery())
        source = order()
        source["provenance"] = "different-source"
        second = audit_delivery(source, delivery())
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])
        self.assertEqual(first["delivery_sha256"], second["delivery_sha256"])

    def test_declared_contract_bounds_and_references(self):
        changes = [lambda x: x.__setitem__("invoices", []), lambda x: x.__setitem__("payments", []), lambda x: x.__setitem__("order_id", " "*10), lambda x: x["invoices"][0].__setitem__("customer", "x"*201), lambda x: x["payments"][0].__setitem__("invoice_refs", ["unknown"]), lambda x: x["payments"][0].__setitem__("customer", "other-customer"), lambda x: x["payments"][0].__setitem__("amount_cents", 10**14+1), lambda x: x.__setitem__("invoices", [{"id": str(i), "customer": "A", "amount_cents": 1} for i in range(1001)])]
        for change in changes:
            source = order()
            change(source)
            self.assertFalse(audit_delivery(source, delivery())["accepted"])
        source = order()
        source["invoices"][0]["amount_cents"] = 10**14
        source["payments"][0]["amount_cents"] = 10**14
        result = delivery()
        amount = 10**14+200
        result["matches"][0]["invoice_cents"] = result["matches"][0]["payment_cents"] = amount
        for field in ("invoice_cents", "payment_cents", "matched_invoice_cents", "matched_payment_cents"):
            result["totals"][field] = amount
        self.assertTrue(audit_delivery(source, result)["accepted"])

    def test_thousand_source_rows_independent_expected_result(self):
        source = {"scope": "SYNTHETIC_PUBLIC_WORKLOAD", "currency": "USD", "order_id": "thousand-source-rows", "require_complete": True, "invoices": [], "payments": []}
        result = {"scope": source["scope"], "currency": "USD", "order_id": source["order_id"], "matches": [], "unmatched_invoices": [], "unmatched_payments": [], "exceptions": [], "accepted": True}
        for i in range(500):
            iid, pid, amount = "I"+str(i), "P"+str(i), i+1
            source["invoices"].append({"id": iid, "customer": "A", "amount_cents": amount})
            source["payments"].append({"id": pid, "customer": "A", "amount_cents": amount, "invoice_refs": [iid] if i%2 else []})
            result["matches"].append({"invoice_ids": [iid], "payment_ids": [pid], "invoice_cents": amount, "payment_cents": amount, "status": "MATCHED"})
        total = 500*501//2
        result["totals"] = {"invoice_cents": total, "payment_cents": total, "matched_invoice_cents": total, "matched_payment_cents": total, "open_invoice_cents": 0, "unallocated_payment_cents": 0}
        rng = random.Random(90416)
        for _ in range(5):
            rng.shuffle(source["invoices"])
            rng.shuffle(source["payments"])
            rng.shuffle(result["matches"])
            self.assertTrue(audit_delivery(source, result)["accepted"])
        forged = copy.deepcopy(result)
        forged["matches"].pop()
        self.assertFalse(audit_delivery(source, forged)["accepted"])


if __name__ == "__main__":
    unittest.main()
