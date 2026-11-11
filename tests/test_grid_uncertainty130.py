"""Frozen synthetic and pinned public-source contract; not physical grid acceptance."""
import copy
import hashlib
import json
import math
import unittest
from unittest import mock
from pathlib import Path

from research.grid_uncertainty130 import InvalidModel, case, radii_for
from research.grid_uncertainty130_verify import independently_verify


def triangle():
    return {
        "base_mva": 100.0, "buses": [1, 2, 3],
        "p_mw": [0.0, 20.0, -20.0],
        "branches": [
            {"id":1,"from_bus":1,"to_bus":2,"x":0.10,"tap":1.0,"shift_deg":0.0,"rate_mw":60.0,"status":1},
            {"id":2,"from_bus":2,"to_bus":3,"x":0.10,"tap":1.0,"shift_deg":0.0,"rate_mw":60.0,"status":1},
            {"id":3,"from_bus":1,"to_bus":3,"x":0.10,"tap":1.0,"shift_deg":0.0,"rate_mw":60.0,"status":1},
        ],
    }

class GridUncertainty130(unittest.TestCase):
    def test_t0_zero_box_full_lp_and_status(self):
        model=triangle()
        answer=case(model,[0,0]); result=independently_verify(model,answer)
        self.assertEqual(result["lp_checked_rated_branch_outage_pairs"],9)
        self.assertLess(result["maximum_lp_gap_mw"],1e-8)
        self.assertTrue(all(o["status"]=="DC_BOX_N1_WITHIN_DECLARED_RATED_LIMITS" for o in answer["outcomes"]))

    def test_t1_uncertainty_produces_actual_attaining_witness(self):
        model=triangle()
        model["branches"][0]["rate_mw"]=10.0
        answer=case(model,[40,40]); result=independently_verify(model,answer)
        self.assertGreater(result["outcomes_with_overload"],0)
        self.assertTrue(any(o["status"]=="MODEL_UNSAFE" for o in answer["outcomes"]))
        self.assertTrue(result["sample_violations"])

    def test_t2_outage_islanding_unknown_not_safe(self):
        model=triangle()
        model["branches"][2]["status"]=0
        answer=case(model,[0.3,0.3]); result=independently_verify(model,answer)
        self.assertGreaterEqual(result["islanding_outages"],1)
        self.assertTrue(any(o["status"]=="ISLANDING_UNKNOWN" for o in answer["outcomes"]))

    def test_t3_missing_thermal_rating_never_certified(self):
        model=triangle()
        model["branches"][0]["rate_mw"]=0.0
        answer=case(model,[0.0,0.0]); independently_verify(model,answer)
        self.assertEqual(answer["outcomes"][0]["status"],"UNRATED_NO_COMPLETE_CERTIFICATE")
        self.assertIn(1,answer["outcomes"][0]["unrated_ids"])

    def test_t4_negative_nonfinite_or_wrong_box_rejected(self):
        model=triangle()
        for radii in ([1.0],[-1.0,0.0],[float("nan"),0.0],[float("inf"),0.0],[True, 0.0]):
            with self.subTest(radii=radii),self.assertRaises(InvalidModel):case(model,radii)
        with self.assertRaises(InvalidModel):radii_for(model,-0.01)

    def test_t5_disconnected_base_rejected(self):
        model=triangle()
        model["branches"][1]["status"]=0
        model["branches"][2]["status"]=0
        with self.assertRaisesRegex(InvalidModel,"DISCONNECTED_BASE"):
            case(model,[0.0,0.0])

    def test_t6_tampered_flow_bound_witness_and_status_rejected(self):
        model=triangle()
        a=case(model,[0.8,1.0])
        for change in ("bound","witness","status","outage"):
            b=copy.deepcopy(a)
            if change=="bound":b["outcomes"][0]["rated"][0]["maximum_absolute_mw"]+=2
            if change=="witness":b["outcomes"][0]["rated"][0]["attaining_delta_non_slack_mw"]=[1000,1000]
            if change=="status":b["outcomes"][0]["status"]="MODEL_UNSAFE"
            if change=="outage":b["outcomes"][0]["outage_id"]=999
            with self.subTest(change=change),self.assertRaises(AssertionError):
                independently_verify(model,b)

    def test_t7_nontrivial_phase_shift_tap_and_sign(self):
        model=triangle()
        model["branches"][0]["tap"]=1.1
        model["branches"][1]["shift_deg"]=11.0
        model["branches"][2]["x"]=0.24
        data=case(model,[2.0,4.0]); result=independently_verify(model,data)
        self.assertLess(result["maximum_lp_gap_mw"],1e-5)

    def test_t8_false_unrated_label_rejected(self):
        model=triangle(); data=case(model,[0,0])
        data["outcomes"][0]["unrated_ids"]=[1]
        with self.assertRaises(AssertionError):independently_verify(model,data)

    def test_t9_original_pglib_blobs_frozen_if_repo_available(self):
        root=Path(__file__).resolve().parents[1]
        actual={"pglib_opf_case14_ieee.m":"2c8260fff0311c902c3d36dcabcbe861576fc97c",
                "pglib_opf_case30_ieee.m":"d429394621c797fa3893d4e4b6d8efa220a4015a"}
        for name,expected in actual.items():
            path=root/"research"/name
            if not path.exists():
                self.skipTest("Pinned public PGLib fixtures available in actual repository checkout")
            data=path.read_bytes()
            blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
            self.assertEqual(blob,expected,"Actual source fixture modified")

    def test_t10_nonfinite_branch_and_model_not_accepted(self):
        model=triangle();model["branches"][0]["x"]=float("nan")
        with self.assertRaises(InvalidModel):case(model,[0,0])
        model=triangle();model["buses"]=[1,1,3]
        with self.assertRaises(InvalidModel):case(model,[0,0])

    def test_t12_independent_reference_rejects_correlated_producer_matrix_defect(self):
        from research import grid_uncertainty130 as producer
        m=triangle()
        original=producer._matrix
        def incorrect_admittance(*args, **kwargs):
            active, a, w, shift, B=original(*args,**kwargs)
            return active, a, w*1.17, shift, B
        with mock.patch.object(producer, "_matrix", incorrect_admittance):
            corrupt=producer.case(m,[0.4,1.2])
        with self.assertRaises(AssertionError):
            independently_verify(m, corrupt)

    def test_t11_unmodified_source_remains_untouched(self):
        model=triangle();before=json.dumps(model,sort_keys=True)
        case(model,[0.3,2]); self.assertEqual(before,json.dumps(model,sort_keys=True))

if __name__=="__main__":unittest.main()
