"""Offline adversarial scoring tests; python -m unittest discover -s this_folder."""
import copy, importlib.util, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('energy_score',Path(__file__).with_name('score.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixtures():
    meta={'issue_date':'2026-11-04','delivery_date':'2026-11-05','t0':'2026-11-04T23:00:00Z','n':96}
    f=dict(meta,series={});a=dict(meta,series={})
    for z in ['BE','NL','FR','DE','DK1','DK2']:
        for t in ['wind','load']:
            key=z+'_'+t
            f['series'][key]={'status':'available','predictions':{n:[v]*96 for n,v in {'candidate':1,'selected_incumbent':2,'ens_hybrid':3,'naive_weekly':4,'strong_other':0,'tso_final':0}.items()}}
            a['series'][key]={'actual':[0]*96}
    return f,a

class Scoring(unittest.TestCase):
    def test_primary_is_not_full_field_superiority(self):
        f,a=fixtures();r=m.score(f,a)
        passed=r.get('restricted_primary_accuracy_criterion_met',r.get('restricted_restricted_primary_accuracy_criterion_met'))
        self.assertTrue(passed)
        self.assertEqual(r['wins_on_both_primary_controls'],12)
        self.assertEqual(r['series']['BE_wind']['strongest_observed_comparator'],'strong_other')
    def test_missing_actual_cannot_pass(self):
        f,a=fixtures();a['series']['BE_wind']['actual'][0]=None;r=m.score(f,a)
        self.assertFalse(r['complete_96_points_all_series'])
        self.assertFalse(r.get('restricted_primary_accuracy_criterion_met',r.get('restricted_restricted_primary_accuracy_criterion_met')))
        self.assertEqual(r['series']['BE_wind']['observed_points'],95)
    def test_zero_baseline_cannot_pass(self):
        f,a=fixtures();f['series']['BE_wind']['predictions']['naive_weekly']=[0]*96;r=m.score(f,a)
        self.assertFalse(r.get('restricted_primary_accuracy_criterion_met',r.get('restricted_restricted_primary_accuracy_criterion_met')))
        self.assertIsNone(r['macro_relative_mae']['candidate'])
    def test_wrong_day_rejected(self):
        f,a=fixtures();a['issue_date']='2026-11-05'
        with self.assertRaises(ValueError):m.score(f,a)
    def test_every_comparator_uses_same_observations(self):
        f,a=fixtures();a['series']['BE_wind']['actual'][0]=None
        f['series']['BE_wind']['predictions']['candidate'][0]=999999
        r=m.score(f,a);self.assertEqual(r['series']['BE_wind']['mae']['candidate'],1)
    def test_held_out_ties_are_not_wins(self):
        f,a=fixtures()
        for v in f['series'].values():v['predictions']['candidate']=[2]*96
        r=m.score(f,a);self.assertEqual(r['wins_on_both_primary_controls'],0)
    def test_missing_model_excluded_from_macro_not_per_series(self):
        f,a=fixtures();del f['series']['BE_wind']['predictions']['strong_other'];r=m.score(f,a)
        self.assertNotIn('strong_other',r['macro_relative_mae'])
        self.assertIn('strong_other',r['series']['BE_load']['mae'])

if __name__=='__main__':unittest.main()
