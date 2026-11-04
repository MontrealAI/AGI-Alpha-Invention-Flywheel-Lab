"""Synthetic unit fixtures only; scientific validation is the measured-cell run."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from .cli import screen
from .measurement import FIELDS
from .prognosis import ENDPOINTS, METHODS, fit_bank, interval_decision, predict, prefix_features
from .test_measurement import discharge


def feature_fixture():
    cycles={c:{'capacity_ah':3-c*.001,'curve':[[4.3,0],[4.1,.3],[3.2,2.8],[3.,3-c*.001]]} for c in range(1,101)}
    return SimpleNamespace(cycles=cycles)

class PrognosisTests(unittest.TestCase):
    def test_cycle_zero_invariant(self):
        m=feature_fixture();a=prefix_features(m)
        m.cycles[0]={'capacity_ah':800,'curve':[[0,700]]}
        b=prefix_features(m)
        self.assertEqual(a,b)
    def test_future_cycle_feature_invariant(self):
        m=feature_fixture();a=prefix_features(m)
        m.cycles[500]={'capacity_ah':800,'curve':[[0,700]]}
        self.assertEqual(a,prefix_features(m))
    def test_partial_targets_not_silently_imputed(self):
        p=prefix_features(feature_fixture())
        bank=fit_bank([{'group':'g','cell':'train','prefix':p,'targets':{'500':.9}}])
        self.assertIsNone(bank['ridge'])
        self.assertEqual(predict(p,'g',bank,'adjusted_peer'),{'500':.9})
    def test_explicit_protocol_confirmation(self):
        self.assertEqual(screen('nonexistent','g','nonexistent')['status'],'CONTINUE_TESTING')
    def test_all_models_fixed_and_finite(self):
        p=prefix_features(feature_fixture())
        training=[{'group':str(i),'cell':str(i),'prefix':copy.deepcopy(p),'targets':{'500':.9,'1000':.8}} for i in range(9)]
        bank=fit_bank(training)
        for method in METHODS:
            result=predict(p,'0',bank,method)
            self.assertEqual(set(result),{'500','1000'})
    def test_missing_calibration_abstains(self):
        self.assertEqual(interval_decision({'500':.9},{})['500']['decision'],'CONTINUE_TESTING')
    def test_cli_full_history_equals_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f=root/'cell.csv'
            rows=[]
            for c in range(1,101):
                rows.extend([(r[0]+(c-1)*3700,*r[1:]) for r in discharge(cycle=c)])
            with f.open('w',newline='') as out:
                w=csv.writer(out);w.writerow(FIELDS);w.writerows(rows)
            bank={'groups':{'g':{'rated_capacity_ah':3}},'peers':{'g':{'targets':{'500':.9,'1000':.85},'last_retention':1}},'widths':{'adjusted_peer':{'500':.01,'1000':.02}}}
            model=root/'model.json';model.write_text(json.dumps(bank))
            prefix=screen(f,'g',model,protocol_confirmed=True)
            with f.open('a',newline='') as out:csv.writer(out).writerow([999999,10,900,101,1,'corrupt_future'])
            full=screen(f,'g',model,protocol_confirmed=True)
            self.assertEqual(prefix,full)
            self.assertEqual(full['accepted_prefix_cycles'],100)

if __name__=='__main__':unittest.main()
