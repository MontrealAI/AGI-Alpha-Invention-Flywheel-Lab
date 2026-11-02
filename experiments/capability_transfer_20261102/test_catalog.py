import hashlib, io, json, tempfile, unittest, urllib.error
from pathlib import Path
from experiments.capability_transfer_20261102.fetch_catalog import Recorder, acquire, catalog_entries, endpoint

class Response(io.BytesIO):
    def __init__(self,payload,status=200):
        super().__init__(json.dumps(payload).encode()); self.status=status; self.headers={'Content-Type':'application/json'}

class CatalogBoundaryTests(unittest.TestCase):
    def test_http_success_with_remote_error_rejected(self):
        for x in [{'error':400},{'errors':['bad request']},{},None,{'files':[{'id':'x'}]}]:
            with self.subTest(payload=x), self.assertRaises(ValueError): catalog_entries(x)
    def test_named_file_and_folder_catalogs(self):
        rows=[{'id':'file','filename':'data.mat','content_details':{'size':100}},{'id':'folder','name':'processed'}]
        for x in [rows,{'files':rows},{'data':{'files':rows}}]: self.assertEqual(catalog_entries(x),rows)
    def test_empty_root_is_valid_empty_catalog(self):
        for payload in [[],{'files':[]},{'data':{'files':[]}}]: self.assertEqual(catalog_entries(payload),[])
    def test_files_and_folders_are_separate(self):
        payload={'files':[],'folders':[{'id':'folder','name':'processed'}]}
        self.assertEqual(catalog_entries(payload),[]); self.assertEqual(catalog_entries(payload,'folders'),payload['folders'])
    def test_semantic_failure_preserves_actual_response(self):
        with tempfile.TemporaryDirectory() as d:
            recorder=Recorder(d,lambda *a,**k:Response({'error':400}))
            self.assertIsNone(recorder.get(endpoint(),'files')); row=recorder.attempts[0]
            raw=(Path(d)/row['file']).read_bytes(); self.assertEqual(row['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertIn('REMOTE_ERROR',row['error']); self.assertEqual(row['schema']['keys'],['error'])
    def test_http_denial_preserved_without_retry(self):
        calls=[]
        def denied(request,**kwargs):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url,401,'Unauthorized',{},io.BytesIO(b'{"error":401}'))
        with tempfile.TemporaryDirectory() as d:
            result=acquire(Path(d)/'out',opener=denied)
            self.assertEqual(len(calls),1); self.assertTrue(result['access_denied']); self.assertFalse(result['success'])
            self.assertEqual(result['attempts'][0]['sha256'],hashlib.sha256(b'{"error":401}').hexdigest())
    def test_empty_root_follows_returned_folder_to_metadata_only(self):
        replies={endpoint():{'id':'zh58byr53c','version':2},endpoint('files',folder_id='root'):[],endpoint('folders'):[{'id':'returned-folder','name':'Processed characterization'}],endpoint('files',folder_id='returned-folder'):[{'id':'returned-file','filename':'sample.mat','content_details':{'size':100}}]}
        calls=[]
        def opener(request,**kwargs):
            calls.append(request.full_url); self.assertIn(request.full_url,replies)
            return Response(replies[request.full_url])
        with tempfile.TemporaryDirectory() as d:
            result=acquire(Path(d)/'out',opener=opener)
            self.assertTrue(result['success']); self.assertEqual(result['measurement_files_downloaded'],0)
            self.assertEqual(result['format_candidates'][0]['id'],'returned-file'); self.assertEqual(len(calls),4)
            self.assertTrue(result['attempts'][1]['empty_catalog'])
            self.assertFalse(any('api.data.mendeley.com' in x for x in calls))

if __name__=='__main__': unittest.main()
