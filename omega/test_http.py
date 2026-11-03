"""Actual local HTTP intake path, not just direct solver calls."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=subprocess.Popen([sys.executable,'-m','omega','serve','--port','0'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        cls.url=cls.server.stdout.readline().strip().split('Local only: ',1)[1]
    @classmethod
    def tearDownClass(cls):
        cls.server.terminate(); cls.server.wait();cls.server.stdout.close()
    def test_page_and_solve_then_repeated_solve(self):
        with urlopen(self.url) as response:self.assertIn('FLYWHEEL',response.read().decode())
        body={'request':json.loads((ROOT/'omega/request.json').read_text()),'proposal':None}
        req=Request(self.url+'/solve',json.dumps(body).encode(),{'Content-Type':'application/json','Origin':self.url})
        with urlopen(req) as response: first=json.load(response)
        with urlopen(req) as response: second=json.load(response)
        self.assertEqual(first,second)
        self.assertEqual(first['certificate']['reuse_units'],6)
    def test_cross_site_post_is_rejected(self):
        request=Request(self.url+'/solve',b'{}',{'Origin':'https://example.com'})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,403)
    def test_invalid_request_does_not_kill_server(self):
        with self.assertRaises(HTTPError) as error:urlopen(Request(self.url+'/solve',b'{'))
        self.assertEqual(error.exception.code,400)
        with urlopen(self.url) as response:self.assertEqual(response.status,200)
    def test_huge_integer_request_returns_resource_checkpoint(self):
        body={'request':json.loads((ROOT/'omega/request.json').read_text()),'proposal':None}
        body['request']['sources'][0]['capacity']=10**100
        body['request']['sinks'][0]['demand']=10**100
        request=Request(self.url+'/solve',json.dumps(body).encode(),{'Content-Type':'application/json','Origin':self.url})
        with self.assertRaises(HTTPError) as error:urlopen(request)
        self.assertEqual(error.exception.code,400)
        self.assertEqual(json.load(error.exception),{'error':'RESOURCE_CHECKPOINT_NOT_INFEASIBILITY'})
        with urlopen(self.url) as response:self.assertEqual(response.status,200)
if __name__=='__main__':unittest.main()
