"""Provider transport fixtures are explicitly mocks, not live model evidence."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from products.proof_omega.provider import repair

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.c={'schema':1,'function':'f','inputs':{'x':[0,10]},'expected':'x','output_range':[0,10]}
    def fake(self,cmd,**kwargs):
        if cmd[1:]==['login','status']:
            return subprocess.CompletedProcess(cmd,0,'Logged in using ChatGPT','')
        Path(cmd[cmd.index('--output-last-message')+1]).write_text(json.dumps({'source':'def f(x): return x'}))
        self.assertIn('read-only',cmd)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',cmd)
        return subprocess.CompletedProcess(cmd,0,'','')
    def test_mock_roundtrip(self):
        with tempfile.TemporaryDirectory() as d,patch('shutil.which',return_value='/codex'),patch('subprocess.run',side_effect=self.fake):
            r=repair('def f(x): return 0',self.c,Path(d)/'out')
            self.assertEqual(r['status'],'PROVED_SCOPED')
            self.assertEqual(r['accepted_bundle'],'candidate-bundle')
    def test_final_unknown_never_success(self):
        with tempfile.TemporaryDirectory() as d,patch('shutil.which',return_value='/codex'),patch('subprocess.run',side_effect=self.fake),patch('products.proof_omega.provider.bundle',return_value={'status':'UNKNOWN'}):
            r=repair('def f(x): return 0',self.c,Path(d)/'out')
            self.assertEqual(r['status'],'UNKNOWN');self.assertIsNone(r['accepted_bundle'])
    def test_api_auth_rejected(self):
        with tempfile.TemporaryDirectory() as d,patch('shutil.which',return_value='/codex'),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'Logged in with API key','')):
            r=repair('def f(x): return 0',self.c,Path(d)/'out')
            self.assertEqual(r['status'],'BLOCKED')
    def test_missing_cli(self):
        with tempfile.TemporaryDirectory() as d,patch('shutil.which',return_value=None):
            self.assertEqual(repair('def f(x): return 0',self.c,Path(d)/'out')['status'],'BLOCKED')
    def test_login_timeout(self):
        with tempfile.TemporaryDirectory() as d,patch('shutil.which',return_value='/codex'),patch('subprocess.run',side_effect=subprocess.TimeoutExpired('codex',30)):
            self.assertEqual(repair('def f(x): return 0',self.c,Path(d)/'out')['reason'],'CODEX_LOGIN_STATUS_UNAVAILABLE')
