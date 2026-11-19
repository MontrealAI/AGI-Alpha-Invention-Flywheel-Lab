"""Offline adversarial tests for machine asset 001."""
import copy
import json
import unittest
from gate import Refused, checked_request, digest, produce, run, strict_json, verify


def sample():
    return {
        "contract": {
            "id_field": "id",
            "rules": [
                {"from": "name", "to": "customer", "op": "strip"},
                {"from": "country", "to": "region", "op": "upper"},
                {"from": "count", "to": "quantity", "op": "copy"},
            ],
        },
        "source_rows": [
            {"id": "a", "name": "  André  ", "country": "ca", "count": 2},
            {"id": "b", "name": "  Marie ", "country": "fr", "count": 0},
        ],
    }


class GateTests(unittest.TestCase):
    def test_accepted_output_and_receipt(self):
        result = run(sample())
        self.assertTrue(result["receipt"]["accepted"])
        self.assertEqual(result["delivery"][0],
                         {"id": "a", "customer": "André", "region": "CA", "quantity": 2})
        self.assertEqual(len(result["receipt"]["receipt_sha256"]), 64)
        self.assertEqual(result["receipt"]["delivery_sha256"], digest(result["delivery"]))

    def test_canonical_hash_independent_of_dict_order(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_unverified_tampering(self):
        payload = sample()
        accepted = run(payload)["delivery"]
        accepted[0]["quantity"] += 1
        self.assertEqual(verify(payload["contract"], payload["source_rows"], accepted),
                         ["VALUE_MISMATCH"])

    def test_missing_or_duplicate_delivery(self):
        payload = sample()
        delivery = produce(*checked_request(payload))
        self.assertEqual(verify(payload["contract"], payload["source_rows"], delivery[:1]),
                         ["ROW_COMPLETENESS"])
        replacement = copy.deepcopy(delivery)
        replacement[1]["id"] = replacement[0]["id"]
        self.assertEqual(verify(payload["contract"], payload["source_rows"], replacement),
                         ["DUPLICATE_OUTPUT_ID"])

    def test_additional_output_column_refused(self):
        payload = sample()
        delivery = produce(*checked_request(payload))
        delivery[0]["secret"] = "leak"
        self.assertEqual(verify(payload["contract"], payload["source_rows"], delivery),
                         ["OUTPUT_FIELDS"])

    def test_duplicate_id(self):
        payload = sample()
        payload["source_rows"][1]["id"] = "a"
        self.assertEqual(run(payload)["receipt"]["errors"],
                         ["INVALID_OR_DUPLICATE_ROW_ID"])

    def test_missing_source_column(self):
        payload = sample()
        del payload["source_rows"][0]["name"]
        self.assertEqual(run(payload)["receipt"]["errors"], ["MISSING_SOURCE_FIELD"])

    def test_wrong_type_for_text_transform(self):
        payload = sample()
        payload["source_rows"][0]["country"] = 10
        self.assertEqual(run(payload)["receipt"]["errors"],
                         ["TEXT_OPERATION_REQUIRES_STRING"])

    def test_reserved_target(self):
        payload = sample()
        payload["contract"]["rules"][0]["to"] = "id"
        self.assertEqual(run(payload)["receipt"]["errors"],
                         ["DUPLICATE_OR_RESERVED_TARGET"])

    def test_duplicate_target(self):
        payload = sample()
        payload["contract"]["rules"][1]["to"] = "customer"
        self.assertEqual(run(payload)["receipt"]["errors"],
                         ["DUPLICATE_OR_RESERVED_TARGET"])

    def test_unknown_operation(self):
        payload = sample()
        payload["contract"]["rules"][0]["op"] = "execute"
        self.assertEqual(run(payload)["receipt"]["errors"], ["UNSUPPORTED_OPERATION"])

    def test_contract_field_injection(self):
        payload = sample()
        payload["contract"]["merchant_wallet"] = "fake"
        self.assertEqual(run(payload)["receipt"]["errors"], ["EXACT_CONTRACT_FIELDS_REQUIRED"])

    def test_bad_shape(self):
        self.assertFalse(run({"source_rows": []})["receipt"]["accepted"])
        self.assertEqual(run({"contract": {}, "source_rows": []})["receipt"]["errors"],
                         ["EXACT_CONTRACT_FIELDS_REQUIRED"])

    def test_nested_input_rejected(self):
        payload = sample()
        payload["source_rows"][0]["count"] = {"nested": "not supported"}
        self.assertEqual(run(payload)["receipt"]["errors"],
                         ["NESTED_OR_UNSUPPORTED_SOURCE_VALUE"])

    def test_nonfinite_rejected(self):
        with self.assertRaises(Refused):
            strict_json('{"value":NaN}')

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(Refused):
            strict_json('{"value":1,"value":2}')

    def test_no_payment_claim(self):
        result = run(sample())
        self.assertNotIn("paid", json.dumps(result).lower())
        self.assertNotIn("signature", json.dumps(result).lower())

    def test_utf8(self):
        payload = sample()
        raw = json.dumps(payload, ensure_ascii=False)
        self.assertTrue(run(strict_json(raw))["receipt"]["accepted"])

    def test_empty_and_oversized_rows(self):
        payload = sample()
        payload["source_rows"] = []
        self.assertEqual(run(payload)["receipt"]["errors"], ["ROW_COUNT"])
        payload = sample()
        payload["source_rows"][0]["name"] = "x" * 10001
        self.assertEqual(run(payload)["receipt"]["errors"], ["SOURCE_VALUE_TOO_LARGE"])


if __name__ == "__main__":
    unittest.main()
