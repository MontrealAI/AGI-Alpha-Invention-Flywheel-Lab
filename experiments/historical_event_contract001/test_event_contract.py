import csv, io, json, unittest
from event_contract import ingest, run

def fixture(states1,states2):
    manifest=[]; rows=[]
    for i,(a,b) in enumerate(zip(states1,states2)):
        f=f'img{i:02d}.jpg';t=f'2024-06-{i+1:02d}T12-00-00Z'
        m={'filename':f,'timestamp':t,'url':'https://example.org/'+f,'sha256':f'{i+1:064x}'}
        manifest.append(m)
        for q,s in [('road',a),('sidewalk',b)]:
            rows.append({**m,'query':q,'state':s})
    f=io.StringIO()
    w=csv.DictWriter(f,fieldnames=['filename','timestamp','url','sha256','query','state'])
    w.writeheader();w.writerows(rows)
    return f.getvalue().encode(),json.dumps(manifest).encode()

class TestEventContract(unittest.TestCase):
    def setUp(self):
        self.data=fixture(['no_water_contact']*4+['water_contact']*4+['no_water_contact']*4,['no_water_contact']*3+['water_contact']*6+['no_water_contact']*3)
    def test_all_policies_charge_and_source_bind(self):
        r=run(*self.data,budget=10)
        self.assertEqual(r['frames'],12)
        self.assertEqual(r['methods']['no_deploy']['image_reads'],0)
        self.assertEqual(r['methods']['exhaustive_upper_bound']['image_reads'],12)
        for k in ('uniform','joint_adaptive','ordinary_bisection'):
            self.assertLessEqual(r['methods'][k]['image_reads'],10)
            self.assertEqual(r['methods'][k]['target_assessments'],2*r['methods'][k]['image_reads'])
        self.assertTrue(r['methods']['exhaustive_upper_bound']['queries']['road']['eligible_for_conditional_interval'])
    def test_no_wet_abstains(self):
        a,b=fixture(['no_water_contact']*6,['no_water_contact']*6)
        r=run(a,b,3)
        self.assertEqual(r['methods']['joint_adaptive']['queries']['road']['status'],'NO_RECORDED_POSITIVE')
    def test_nonmonotone_episode_is_rejected_even_if_sparse_claim_looks_good(self):
        a,b=fixture(['no_water_contact','water_contact','no_water_contact','water_contact','no_water_contact','no_water_contact'],['no_water_contact']*6)
        r=run(a,b,6)
        self.assertFalse(r['methods']['exhaustive_upper_bound']['queries']['road']['eligible_for_conditional_interval'])
        self.assertEqual(r['methods']['exhaustive_upper_bound']['queries']['road']['interior_recorded_dry_violations'],1)
    def test_unknown_is_not_rewritten(self):
        a,b=fixture(['no_water_contact','unknown','water_contact','unknown','no_water_contact','no_water_contact'],['unknown']*6)
        r=run(a,b,6)
        self.assertEqual(r['methods']['exhaustive_upper_bound']['queries']['road']['unknown_frames'],2)
        self.assertEqual(r['methods']['exhaustive_upper_bound']['queries']['sidewalk']['status'],'NO_RECORDED_POSITIVE')
    def test_reject_modified_provenance_and_duplicates(self):
        a,b=self.data
        tampered=a.replace(b'https://example.org/img01.jpg',b'https://evil.test/img01.jpg')
        with self.assertRaisesRegex(ValueError,'IMAGE_PROVENANCE_DISAGREEMENT'):ingest(tampered,b)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE_QUERY'):
            ingest(a+a.split(b'\n',1)[1].splitlines()[0]+b'\n',b)
    def test_source_grid_missing_fails(self):
        a,b=self.data
        truncated=b'\n'.join(a.splitlines()[:-1])+b'\n'
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_SOURCE_QUERY_GRID'):ingest(truncated,b)

if __name__=='__main__':unittest.main()
