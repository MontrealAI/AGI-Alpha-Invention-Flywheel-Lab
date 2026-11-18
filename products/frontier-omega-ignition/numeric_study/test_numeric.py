"""Failure controls for scientific values, authority, and continuation geometry."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from receive import HERE,SPEC,combine,compare,reference,model_table
from audit import independent


class NumericEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads(SPEC.read_text())

    def test_independent_semantic_sources_agree(self):
        for key,spec in self.spec.items():
            self.assertEqual(reference(key,spec),independent(key))

    def test_changed_sign_decimal_precision_unit_denominator_or_group_is_rejected(self):
        original=independent("publication")
        for row,col,value in [(1,2,"$350.00"),(1,2,"$-35.00"),(1,2,"$-350.0"),
                              (1,3,"100.0"),(1,1,"0/23"),(1,0,"ordinary")]:
            with self.subTest(row=row,column=col,value=value):
                changed=copy.deepcopy(original);changed[0][row][col]=value
                self.assertFalse(compare(changed,original)["accepted"])

    def test_span_header_footnote_and_units(self):
        grid,notes=independent("calibration")
        first=[grid[0][:],grid[1][:],grid[2][:]]
        second=[grid[0][:],grid[3][:],grid[4][:]]
        first[2][0]="";second[2][0]=""
        self.assertEqual(combine("calibration",[(first,notes[0]),(second,notes[1])]),(grid,notes))
        wrong=copy.deepcopy(second);wrong[0][2]="Bias (V)"
        with self.assertRaises(ValueError): combine("calibration",[(first,notes[0]),(wrong,notes[1])])
        wrong=copy.deepcopy(first);wrong[2][0]="Other sensor"
        with self.assertRaises(ValueError): combine("calibration",[(wrong,notes[0])])
        self.assertFalse(compare((grid,["",notes[1]]),(grid,notes))["accepted"])

    def test_changed_reference_and_observation_refused(self):
        with self.assertRaisesRegex(ValueError,"Reference has changed"):
            reference("publication",{**self.spec["publication"],"html_sha256":"0"*64})
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            src=HERE/"model_observation"
            shutil.copy(src/"observation.json",folder)
            (folder/"page-1.txt").write_text("Not the observed output")
            with self.assertRaisesRegex(ValueError,"identity changed"):
                model_table("publication",self.spec["publication"],folder)
            d=json.loads((folder/"observation.json").read_text());d["calls"][0]["png_sha256"]="f"*64
            (folder/"observation.json").write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"mismatched model call"):
                model_table("publication",self.spec["publication"],folder)


if __name__=="__main__":unittest.main()
