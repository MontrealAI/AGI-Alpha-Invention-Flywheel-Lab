import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reuse036', ROOT/'scripts/adaptive_cohort_reuse036.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class ReuseTests(unittest.TestCase):
    def run_data(self):
        return dict(id=17, run_attempt=1, status='completed', conclusion='success', event='push', head_branch='main',
                    path=m.WORKFLOW, head_sha='a'*40, repository={'full_name':'x/y'}, head_repository={'full_name':'x/y'})

    def receipt(self):
        r = dict(schema=m.SCHEMA, kind='EXECUTED_COHORT', repository='x/y',run_id=17,run_attempt=1,
                 source_commit='a'*40,input_key='key',audit_accepted=True,worlds=160,qualification_scope='NATIVE_FINANCIAL_ONLY')
        r.update({k:'f'*64 for k in ('report_sha256','frozen_sha256','index_sha256','native_source_sha256')})
        return r

    def test_trusted_successful_main_ancestor_only(self):
        r=self.run_data()
        self.assertTrue(m.trusted_run(r,'x/y','b'*40,lambda _:True))
        for k,v in [('status','in_progress'),('conclusion','failure'),('event','pull_request'),('head_branch','other'),('path','other.yml'),('head_sha','b'*40),('repository',{'full_name':'fork/y'}),('head_repository',{'full_name':'fork/y'})]:
            with self.subTest(k=k):
                bad=copy.deepcopy(r);bad[k]=v
                self.assertFalse(m.trusted_run(bad,'x/y','b'*40,lambda _:True))
        self.assertFalse(m.trusted_run(r,'x/y','b'*40,lambda _:False))

    def test_receipt_exact_binding_and_no_chained_reuse(self):
        self.assertTrue(m.valid_receipt(self.receipt(),self.run_data(),'key','x/y'))
        for k,v in [('kind','REUSED_COHORT'),('run_id',18),('run_attempt',2),('source_commit','b'*40),('input_key','other'),('repository','fork/y'),('audit_accepted',False),('worlds',159),('qualification_scope','SMOKE'),('report_sha256','z'*64)]:
            with self.subTest(k=k):
                r=self.receipt();r[k]=v
                self.assertFalse(m.valid_receipt(r,self.run_data(),'key','x/y'))

    def key(self, rows, dirty=b'', untracked=b'', **env):
        def fake_git(root,*args):
            if args[0]=='status':return dirty
            if args[0]=='ls-files':return untracked
            return b'\0'.join(f'{mode} blob {blob}\t{name}'.encode() for name,mode,blob in rows)+b'\0'
        with patch.object(m,'git',side_effect=fake_git),patch.object(m.importlib.metadata,'distributions',return_value=[]),patch.object(m.sysconfig,'get_path',return_value=str(ROOT/'scripts')), patch.dict(os.environ,dict(ImageOS='ubuntu',ImageVersion='1',**env),clear=True):
            return m.fingerprint(ROOT)

    def test_only_exact_excluded_paths_allow_same_key(self):
        base=[('engine.py','100644','a'*40)]
        key=self.key(base)
        for name in m.EXCLUDED:
            self.assertEqual(key,self.key(base+[(name,'100644','b'*40)]))
        for name in ['config.json','README.md',m.WORKFLOW,'scripts/adaptive_cohort_reuse036.py','requirements-commercial010.txt','tests/test_adaptive.py']:
            self.assertNotEqual(key,self.key(base+[(name,'100644','b'*40)]))
        self.assertNotEqual(key,self.key([('engine.py','100644','c'*40)]))
        self.assertNotEqual(key,self.key(base,TZ='Etc/UTC'))

    def test_dirty_untracked_external_or_nonregular_rejected(self):
        for kwargs in [dict(dirty=b' M engine.py'),dict(untracked=b'shadow.py\0'),dict(PYTHONPATH='/external')]:
            with self.assertRaises(ValueError):self.key([],**kwargs)
        for mode in ['120000','160000']:
            with self.assertRaises(ValueError):self.key([('link',mode,'a'*40)])
        self.key([],untracked=b'__pycache__/ok.pyc\0')

    def test_unverifiable_lookup_falls_back_to_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp); env={'GITHUB_OUTPUT':str(out/'outputs'),'GITHUB_REPOSITORY':'x/y','GITHUB_RUN_ID':'9'}
            with patch.dict(os.environ,env),patch.object(m,'git',return_value=b'b'*40),patch.object(m,'fingerprint',return_value='key'),patch.object(m,'lookup',side_effect=RuntimeError('unavailable')),patch('sys.argv',['helper','lookup','--output',temp]),contextlib.redirect_stdout(io.StringIO()):
                m.main()
            self.assertFalse(json.loads((out/'REUSE.json').read_text())['reuse'])
            self.assertEqual((out/'outputs').read_text(),'reuse=false\n')

    def test_missing_expired_or_mismatched_artifact_never_reused(self):
        for artifact in [dict(expired=True,size_in_bytes=1),dict(expired=False,size_in_bytes=m.MAX_BYTES+1)]:
            with self.assertRaises(ValueError):m.archive('x/y',artifact)
        r=self.run_data();r['html_url']='https://github.com/x/y/actions/runs/17'
        with patch.object(m,'api',side_effect=[{'workflow_runs':[r]},{'artifacts':[{'name':m.ARTIFACT}]}]),patch.object(m.subprocess,'run') as proc,patch.object(m,'archive',side_effect=ValueError('digest')):
            proc.return_value.returncode=0
            self.assertIsNone(m.lookup(ROOT,'key','x/y','b'*40))

    def test_verified_original_receipt_can_be_reused(self):
        r=self.run_data();r['html_url']='https://github.com/x/y/actions/runs/17'
        item={'name':m.ARTIFACT,'id':7,'digest':'sha256:'+'f'*64}
        with patch.object(m,'api',side_effect=[{'workflow_runs':[r]},{'artifacts':[item]}]),patch.object(m.subprocess,'run') as proc,patch.object(m,'archive',return_value=self.receipt()):
            proc.return_value.returncode=0
            found=m.lookup(ROOT,'key','x/y','b'*40)
            self.assertEqual(found['run_id'],17)
            self.assertEqual(found['original_receipt'],self.receipt())

    def test_archive_digest_content_and_token_scope(self):
        def zipped(name, data):
            b=io.BytesIO()
            with zipfile.ZipFile(b,'w') as z:z.writestr(name,data)
            return b.getvalue()
        good=zipped('COHORT_RECEIPT.json',json.dumps(self.receipt()))
        for raw,digest,ok in [(good,m.sha(good),True),(good,'0'*64,False),(zipped('../other', '{}'),'auto',False)]:
            item={'id':7,'expired':False,'size_in_bytes':len(raw),'digest':'sha256:'+(m.sha(raw) if digest=='auto' else digest)}
            redirect=urllib.error.HTTPError('url',302,'redirect',{'Location':'https://signed.example/artifact'},None)
            with patch.dict(os.environ,{'GH_TOKEN':'not-forwarded'}),patch.object(m.urllib.request,'build_opener') as opener,patch.object(m.urllib.request,'urlopen',return_value=contextlib.closing(io.BytesIO(raw))) as download:
                opener.return_value.open.side_effect=redirect
                if ok:self.assertEqual(m.archive('x/y',item),self.receipt())
                else:
                    with self.assertRaises(ValueError):m.archive('x/y',item)
                self.assertIsInstance(download.call_args.args[0],str)
                self.assertNotIn('not-forwarded',download.call_args.args[0])

    def test_record_only_completed_executed_cohort(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);cohort=p/'cohort';cohort.mkdir()
            (p/'REUSE.json').write_text(json.dumps({'reuse':False,'input_key':'key','source_commit':'a'*40}))
            (cohort/'REPORT.json').write_text('{}')
            complete={'report_sha256':m.sha(b'{}'),'source_sha256':'f'*64}
            (cohort/'COMPLETE.json').write_text(json.dumps(complete))
            (cohort/'FROZEN012.json').write_text('{}');(cohort/'INDEX.json').write_text('{}')
            audit={'accepted':True,'native_worlds_replayed':160,'qualification_scope':'NATIVE_FINANCIAL_ONLY','source_sha256':'f'*64}
            (cohort/'FINANCIAL_AUDIT.json').write_text(json.dumps(audit))
            with patch.dict(os.environ,{'GITHUB_REPOSITORY':'x/y','GITHUB_RUN_ID':'17','GITHUB_RUN_ATTEMPT':'1'}),patch.object(m,'fingerprint',return_value='key'),patch('sys.argv',['helper','record','--output',temp,'--cohort',str(cohort)]):
                m.main()
                self.assertTrue(m.valid_receipt(json.loads((p/'COHORT_RECEIPT.json').read_text()),self.run_data(),'key','x/y'))
                (p/'COHORT_RECEIPT.json').unlink()
                audit['native_worlds_replayed']=159
                (cohort/'FINANCIAL_AUDIT.json').write_text(json.dumps(audit))
                with self.assertRaises(ValueError):m.main()
                self.assertFalse((p/'COHORT_RECEIPT.json').exists())
                (p/'REUSE.json').write_text(json.dumps({'reuse':True,'input_key':'key'}))
                m.main()
                self.assertFalse((p/'COHORT_RECEIPT.json').exists())

    def test_workflow_keeps_current_tests_package_and_smoke(self):
        s=(ROOT/m.WORKFLOW).read_text()
        for name in ['Current adaptive behavior','Imported allocation','Published package integrity','Clean no-Git']:
            step=s.split('- name: '+name,1)[1].split('      - ',1)[0]
            self.assertNotIn('if:',step)
        self.assertIn("if: steps.prior-cohort.outputs.reuse != 'true'",s.split('- name: Current default',1)[1].split('      - ',1)[0])
        self.assertIn('fetch-depth: 0',s)
        self.assertIn('actions: read',s)

if __name__=='__main__':unittest.main()
