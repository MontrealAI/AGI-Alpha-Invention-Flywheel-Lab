import unittest

from audit import independent
from prepare import HERE
from receive import compare,combine
from recover import decode


class SpanRecoveryTests(unittest.TestCase):
    def setUp(self):
        folder=HERE/"model_observation"
        self.raw=[(folder/f"page-{i}.txt").read_text() for i in (2,3)]

    def test_empty_macro_only_in_explicit_covered_slot(self):
        for wrong in (self.raw[0].replace(r"\multirow{2}{*}{Alpha}","Alpha"),
                      self.raw[0].replace(r"\mbox{}",r"\mbox{quantity}"),
                      self.raw[0].replace("4.00",r"\mbox{}",1)):
            with self.assertRaises(ValueError):decode(wrong)

    def test_changed_value_or_note_stays_withheld(self):
        original=independent("calibration")
        for before,after in [("-2.50","+2.50"),("20 C.","25 C.")]:
            pages=[decode(self.raw[0].replace(before,after)),decode(self.raw[1])]
            self.assertFalse(compare(combine("calibration",pages),original)["accepted"])


if __name__=="__main__": unittest.main()
