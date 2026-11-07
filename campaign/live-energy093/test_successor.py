"""Offline successor causality tests. No remote access or published forecast edits."""
import contextlib, datetime as dt, importlib.util, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

spec=importlib.util.spec_from_file_location('successor_runner',Path(__file__).with_name('run.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class Successor(unittest.TestCase):
    def test_frozen_rows_plus_two_new_days_and_equal_information_control(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); parent=root/'parent';parent.mkdir();out=root/'out'; key='BE_wind'
            old_dates=[(dt.date(2026,10,20)+dt.timedelta(days=i)).isoformat() for i in range(7)]
            X=np.tile(np.arange(6,dtype=float),(7*96,1))+100.;y=np.arange(7*96,dtype=float)/10
            original={'issue_date':'2026-11-04','members':r.MEMBERS,'series':{key:{'status':'available','complete_days':old_dates,'excluded_days':[],'weights':[1/6]*6}}}
            (parent/'forecast.json').write_text(json.dumps(original));(parent/'fit_inputs.json').write_text(json.dumps({key:{'X':X.tolist(),'y':y.tolist()}}))
            calls=[]
            def fake_fetch(date,folder):
                calls.append(date)
                self.assertIn(date,['2026-11-03','2026-11-04','2026-11-06'])
                value={'2026-11-03':300.,'2026-11-04':400.,'2026-11-06':600.}[date]
                models={m:{'p':[value+i]*96} for i,m in enumerate(r.MEMBERS)}
                doc={'issue_date':date,'n':96,'t0':'2026-11-06T23:00:00Z','series':{key:{'actual':None if date=='2026-11-06' else [value+1.5]*96,'models':models}}}
                return doc,{'bytes':123,'url':'mock:'+date}
            with patch.object(r,'SERIES',[key]),patch.object(r,'fetch',side_effect=fake_fetch),contextlib.redirect_stdout(io.StringIO()):
                r.construct(root/'snapshots',out,parent/'forecast.json')
            result=json.loads((out/'forecast.json').read_text());used=json.loads((out/'fit_inputs.json').read_text())[key]
            self.assertEqual(calls,['2026-11-03','2026-11-04','2026-11-06'])
            self.assertEqual(result['series'][key]['complete_days'],old_dates+['2026-11-03','2026-11-04'])
            self.assertEqual(np.shape(used['X']),(9*96,6));self.assertEqual(len(used['y']),9*96)
            np.testing.assert_array_equal(np.asarray(used['X'])[:7*96],X)
            np.testing.assert_array_equal(np.asarray(used['y'])[:7*96],y)
            np.testing.assert_array_equal(np.asarray(used['X'])[7*96:8*96],np.tile(np.arange(6)+300.,(96,1)))
            np.testing.assert_array_equal(np.asarray(used['X'])[8*96:],np.tile(np.arange(6)+400.,(96,1)))
            self.assertEqual(used['y'][7*96:8*96],[301.5]*96);self.assertEqual(used['y'][8*96:],[401.5]*96)
            p=result['series'][key]['predictions']
            np.testing.assert_array_equal(p['candidate'],p['equal_information_ordinary_refit'])
            np.testing.assert_allclose(p['frozen_parent'],[602.5]*96)
            self.assertEqual(result['issue_date'],'2026-11-06');self.assertEqual(result['delivery_date'],'2026-11-07')
            self.assertIn('parent_fit_inputs_sha256',result)
            # Parent inputs are immutable in this operation.
            self.assertEqual(json.loads((parent/'fit_inputs.json').read_text())[key]['y'],y.tolist())

if __name__=='__main__':unittest.main()
