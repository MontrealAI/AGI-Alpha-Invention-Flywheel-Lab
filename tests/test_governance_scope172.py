"""Frozen OSCAL172 conservative-continuity tests; no real policy approvals."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from products.governance_impact140 import engine as native
from research import governance_scope172 as scope
from tests.test_governance_oscal171 import example


def sample():
    original = example()
    data = {
        "schema": scope.SCHEMA,
        "before_catalog": original["before_catalog"],
        "after_catalog": original["after_catalog"],
        "before_scope": original["before_scope"],
        "before_systems": original["systems"],
        "after_systems": copy.deepcopy(original["systems"]),
    }
    data["anchors"] = {
        "catalog_before_sha256": native.sha256(data["before_catalog"]),
        "catalog_after_sha256": native.sha256(data["after_catalog"]),
        "scope_before_sha256": native.sha256(data["before_scope"]),
        "systems_before_sha256": native.sha256(data["before_systems"]),
    }
    return data


def anchor_new(data):
    data["anchors"]["catalog_after_sha256"] = native.sha256(data["after_catalog"])


class FrozenScope172(unittest.TestCase):
    def test_t1_exact_content_and_inventory_carry_provisional_only(self):
        result = scope.propose(sample())
        self.assertEqual([x["id"] for x in result["provisional"]], ["c1", "c2"])
        self.assertEqual(result["review_required"], [])
        self.assertEqual(result["retired"], [])
        self.assertTrue(all("NOT_REVIEW_APPROVAL" in x["status"]
                            for x in result["provisional"]))
        self.assertEqual(result["authorization"], "NO_AUTHENTICATED_POLICY_OR_COMPLIANCE_APPROVAL")
        self.assertIsNone(result["actual_revenue"])

    def test_t2_changed_leaf_same_version_not_reusable(self):
        data = sample()
        data["after_catalog"]["catalog"]["groups"][0]["controls"][0]["parts"][0]["prose"] = "NEW TEST ONLY"
        self.assertEqual(data["before_catalog"]["catalog"]["metadata"]["version"],
                         data["after_catalog"]["catalog"]["metadata"]["version"])
        anchor_new(data)
        result = scope.propose(data)
        self.assertEqual([x["id"] for x in result["provisional"]], ["c2"])
        self.assertEqual(result["review_required"], [{
            "id": "c1", "reason": "CONTROL_OR_CONTEXT_CHANGED",
            "status": "EXPLICIT_NEW_SCOPE_REVIEW_REQUIRED", "proposed_scope": None
        }])

    def test_t3_add_retire_explicit_in_result(self):
        data = sample()
        controls = data["after_catalog"]["catalog"]["groups"][0]["controls"]
        controls.pop()
        controls.append({"id": "c3", "title": "new capability"})
        anchor_new(data)
        result = scope.propose(data)
        self.assertEqual([r["id"] for r in result["provisional"]], ["c1"])
        self.assertEqual([r["id"] for r in result["review_required"]], ["c3"])
        self.assertEqual(result["review_required"][0]["reason"], "CONTROL_ADDED")
        self.assertEqual([r["id"] for r in result["retired"]], ["c2"])

    def test_t4_parent_change_invalidates_descendants_not_unrelated(self):
        data = sample()
        root = {"id": "stable", "title": "outside group"}
        for stage in ("before", "after"):
            data[stage + "_catalog"]["catalog"]["controls"].append(copy.deepcopy(root))
        data["before_scope"]["stable"] = {"applies_to": ["ops"]}
        data["after_catalog"]["catalog"]["groups"][0]["title"] = "new context"
        for name, object_ in (("catalog_before_sha256", data["before_catalog"]),
                              ("catalog_after_sha256", data["after_catalog"]),
                              ("scope_before_sha256", data["before_scope"])):
            data["anchors"][name] = native.sha256(object_)
        result = scope.propose(data)
        self.assertEqual([x["id"] for x in result["provisional"]], ["stable"])
        self.assertEqual([x["id"] for x in result["review_required"]], ["c1", "c2"])

    def test_t5_inventory_mutation_invalidates_every_carry(self):
        data = sample()
        data["after_systems"][1]["tags"] = ["new-ops"]
        result = scope.propose(data)
        self.assertFalse(result["same_registered_system_inventory"])
        self.assertEqual(result["provisional"], [])
        self.assertEqual([r["reason"] for r in result["review_required"]],
                         ["SYSTEM_INVENTORY_CHANGED"] * 2)

    def test_t6_all_four_independent_anchors_rechecked(self):
        for field, mutate in [
            ("before_catalog", lambda x: x["catalog"]["metadata"].update({"version": "2"})),
            ("after_catalog", lambda x: x["catalog"]["metadata"].update({"version": "2"})),
            ("before_scope", lambda x: x["c1"].update({"applies_to": ["ops"]})),
            ("before_systems", lambda x: x[0].update({"id": "new-id"})),
        ]:
            with self.subTest(field=field):
                data = sample()
                mutate(data[field])
                with self.assertRaisesRegex(ValueError, "EXTERNAL_SOURCE_ANCHOR_MISMATCH"):
                    scope.propose(data)

    def test_t7_explicit_scope_and_identity_malformed_fail_closed(self):
        for mutate in [
            lambda d: d["before_scope"].pop("c1"),
            lambda d: d["before_scope"]["c1"].update({"applies_to": ["wrong"]}),
            lambda d: d["before_catalog"]["catalog"]["controls"].append({"id": "c1", "title": "duplicate"}),
        ]:
            data = sample()
            mutate(data)
            for field in ("catalog_before_sha256", "scope_before_sha256"):
                corresponding = "before_catalog" if field.startswith("catalog") else "before_scope"
                data["anchors"][field] = native.sha256(data[corresponding])
            with self.assertRaises(ValueError):
                scope.propose(data)
        data = sample()
        data["after_systems"].append(copy.deepcopy(data["after_systems"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SYSTEM_ID"):
            scope.propose(data)
        data = sample()
        data["anchors"]["catalog_before_sha256"] = "A" * 64
        with self.assertRaisesRegex(ValueError, "LOWERCASE_SHA256_ANCHOR_REQUIRED"):
            scope.propose(data)
        data = sample()
        data["extra"] = True
        with self.assertRaisesRegex(ValueError, "EXACT_SOURCE_CONTINUITY_INPUT_REQUIRED"):
            scope.propose(data)

    def test_t8_determinism_no_write_no_financial_or_approval(self):
        data = sample()
        unchanged = copy.deepcopy(data)
        self.assertEqual(scope.propose(data), scope.propose(data))
        self.assertEqual(data, unchanged)
        result = scope.propose(data)
        self.assertFalse(result["native_financial_account_modified"])
        for name in ("actual_customer_acceptance", "complete_actual_cost",
                     "actual_revenue", "trailing_365_profit"):
            self.assertIsNone(result[name])
        self.assertEqual(result["receipt_sha256"],
                         native.sha256({k: v for k, v in result.items() if k != "receipt_sha256"}))

    def test_t8b_create_only_bounded_strict_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            source, output = parent / "source.json", parent / "output.json"
            source.write_text(json.dumps(sample()), encoding="utf-8")
            cmd = [sys.executable, "-m", "research.governance_scope172", "--input", str(source), "--output"]
            self.assertEqual(subprocess.run(cmd + [str(output)], capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(cmd + [str(output)], capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(cmd + [str(source)], capture_output=True).returncode, 0)
            source.write_text('{"schema":1,"schema":2}')
            self.assertNotEqual(subprocess.run(cmd + [str(parent / "new.json")], capture_output=True).returncode, 0)


    def test_t11_changed_catalog_uuid_must_refuse_prior_proposals(self):
        data = sample()
        data["after_catalog"]["catalog"]["uuid"] = "22222222-2222-4222-8222-222222222222"
        anchor_new(data)
        result = scope.propose(data)
        self.assertTrue(result["same_registered_system_inventory"])
        self.assertEqual(result["provisional"], [])
        self.assertEqual([x["id"] for x in result["review_required"]], ["c1", "c2"])
        self.assertEqual([x["reason"] for x in result["review_required"]],
                         ["CATALOG_IDENTITY_CHANGED"] * 2)
        self.assertEqual(result["authorization"], "NO_AUTHENTICATED_POLICY_OR_COMPLIANCE_APPROVAL")


if __name__ == "__main__":
    unittest.main()
