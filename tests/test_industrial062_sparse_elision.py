"""No-account regression: duplicate sparse graphs are unnecessary for a real CP-SAT plan."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SparseFreeIndustrialConstructorTests(unittest.TestCase):
    def test_source_does_not_allocate_an_unconsumed_sparse_graph(self):
        source = (ROOT / "industrial062/construct.py").read_text()
        self.assertNotIn("coo_matrix", source)
        self.assertNotIn("from scipy.sparse", source)
        self.assertIn("constraint_count=len(rows)", source)
        self.assertIn("for row,coeffs in rows.items():", source)

    @staticmethod
    def case(capacity=10):
        return {
            "variant": "direct", "days_per_year": 365, "service_distance_km": 100,
            "service_coverage_floor": 1.0, "totals": {"demand_pieces": 5},
            "products": {"p": {"category": "candy", "production_cost": 2,
                               "unit_value": 10, "unit_volume": 1}},
            "factories": {"f": {"fixed_operating_cost": 3, "capacity_pieces": capacity,
                               "products": ["p"], "holding_rate_finished": 0,
                               "holding_rate_material": 0}},
            "central_warehouses": {}, "regional_centers": {},
            "materials": {}, "bom": {"p": {}},
            "customers": {"k": {"temperature_zone": "ambient",
                               "demand": {"p": 5}}},
            "direct_delivery": {"allow_new_relations": False},
            "arcs": {
                "supplier_to_factory": {}, "factory_to_cdc": {},
                "cdc_to_rdc": {}, "factory_to_rdc": {},
                "node_to_customer": {
                    "distance_km": {"f": {"k": 10}},
                    "transit_days": {"f": {"k": 1}},
                    "freight_rate": {"candy": {"ambient": 1}}
                }
            }
        }

    def test_real_small_model_matches_independent_exact_cost_and_constraints(self):
        if importlib.util.find_spec("ortools") is None:
            self.skipTest("OR-Tools is not installed; hosted engineering qualification installs its pinned version")
        from industrial062 import construct as model
        with tempfile.TemporaryDirectory(prefix="industrial062-sparse-free-") as tmp:
            root = Path(tmp)
            folder = root / "input"
            folder.mkdir()
            (folder / "01.json").write_text(json.dumps(self.case()))
            output = root / "result"
            with patch.object(model, "prepare", return_value=self.case()):
                model.construct(folder, output, 10, 0.1)
            receipt = json.loads((output / "production.json").read_text())
            plan = json.loads((output / "solution.json").read_text())
            self.assertEqual(receipt["status"], "OPTIMAL")
            self.assertEqual(receipt["variables"], 3)
            self.assertEqual(receipt["constraints"], 6)
            self.assertAlmostEqual(receipt["objective_yuan"], 63.0)
            self.assertAlmostEqual(receipt["rounded_objective_yuan"], 63.0)
            self.assertEqual(plan["production"], [{"factory": "f", "product": "p", "pieces": 5}])
            self.assertEqual(plan["customer_service"], [{"customer": "k", "product": "p", "node": "f", "pieces": 5}])
            self.assertEqual(receipt["producer_sha256"], hashlib.sha256((ROOT / "industrial062/construct.py").read_bytes()).hexdigest())

    def test_insufficient_factory_capacity_cannot_be_made_to_look_feasible(self):
        if importlib.util.find_spec("ortools") is None:
            self.skipTest("OR-Tools not installed")
        from industrial062 import construct as model
        with tempfile.TemporaryDirectory(prefix="industrial062-capacity-") as tmp:
            root = Path(tmp)
            folder = root / "input"
            folder.mkdir()
            (folder / "01.json").write_text(json.dumps(self.case(capacity=4)))
            output = root / "result"
            with patch.object(model, "prepare", return_value=self.case(capacity=4)):
                model.construct(folder, output, 10, 0.1)
            receipt = json.loads((output / "production.json").read_text())
            self.assertEqual(receipt["status"], "INFEASIBLE")
            self.assertFalse((output / "solution.json").exists())


if __name__ == "__main__":
    unittest.main()
