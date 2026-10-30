import io
import unittest
from range_hdf5 import RangeFile

class Response:
    def __init__(self, status, header, body):
        self.status_code=status;self.headers={'Content-Range':header};self.raw=io.BytesIO(body);self.closed=False
    def close(self):
        self.closed=True

class Session:
    def __init__(self,response):self.response=response;self.calls=0
    def get(self,*args,**kwargs):self.calls+=1;return self.response
    def close(self):pass

class RangeTests(unittest.TestCase):
    def make(self,response,budget=4096):
        r=RangeFile('https://example.com/frozen',4096,max_bytes=budget,block_size=4096)
        r.session.close();r.session=Session(response);return r
    def test_full_response_refused_without_reading_body(self):
        p=Response(200,None,b'x'*8192)
        with self.make(p) as r:
            with self.assertRaisesRegex(ValueError,'RANGE_RESPONSE'):r.read(1)
            self.assertEqual(p.raw.tell(),0)
    def test_wrong_range_refuses(self):
        with self.make(Response(206,'bytes 1-4096/4096',b'x'*4096)) as r:
            with self.assertRaisesRegex(ValueError,'RANGE_RESPONSE'):r.read(1)
    def test_short_range_refuses(self):
        with self.make(Response(206,'bytes 0-4095/4096',b'x'*32)) as r:
            with self.assertRaisesRegex(ValueError,'RANGE_LENGTH'):r.read(1)
    def test_budget_checked_before_network(self):
        with self.make(Response(206,'bytes 0-4095/4096',b'x'*4096),budget=1) as r:
            with self.assertRaisesRegex(ValueError,'NETWORK_BYTE_BUDGET'):r.read(1)
            self.assertEqual(r.session.calls,0)
    def test_bounded_cached_read_and_seek(self):
        with self.make(Response(206,'bytes 0-4095/4096',b'x'*4096)) as r:
            self.assertEqual(r.read(2),b'xx');r.seek(-1,1);self.assertEqual(r.read(1),b'x')
            self.assertEqual(r.session.calls,1);self.assertEqual(r.received_bytes,4096)
            with self.assertRaisesRegex(ValueError,'UNBOUNDED'):r.read()
            with self.assertRaisesRegex(ValueError,'OUTSIDE'):r.seek(-1)

if __name__=='__main__':unittest.main()
