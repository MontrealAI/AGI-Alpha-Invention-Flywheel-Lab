"""Preregistered EIT174 source-metadata checks; fixtures are not physical data."""
import json
import unittest
from unittest.mock import patch
from research.eit_observability174 import (MAX_BYTES,PreflightError,validate_metadata,
                                             ZenodoOnlyRedirect,download_metadata)

def example():
    return {'id':24120439,'doi':'10.5281/zenodo.24120439',
            'metadata':{'title':'Fixture only, NOT an official observation','version':'1.0',
                        'license':{'id':'cc-by-4.0'}},
            'files':[{'key':n+'.zip','size':1000+i,'checksum':'md5:'+'a'*32}
                     for i,n in enumerate(('AgarCylinderPhantom','AgarChestPhantom','HeadPhantom'))]}
def parse(v):
    return validate_metadata(json.dumps(v,sort_keys=True).encode())

class MetadataOnlyTests(unittest.TestCase):
    def test_exact_three_family_claim_never_means_verified_data(self):
        a=parse(example())
        self.assertEqual(a['status'],'METADATA_PREFLIGHT_PASS')
        self.assertEqual(len(a['archive_families']),3)
        self.assertFalse(a['raw_experimental_data_verified'])
        self.assertTrue(all(x['independent_file_digest'] is None for x in a['listed_publisher_files']))

    def test_missing_family_refused(self):
        a=example();a['files'][2]['key']='OtherArchive.zip'
        with self.assertRaisesRegex(PreflightError,'THREE_EXACT'):parse(a)

    def test_conflicting_duplicate_refused(self):
        a=example();a['files'].append({**a['files'][0],'key':'AGARCYLINDERPHANTOM.zip'})
        with self.assertRaises(PreflightError):parse(a)

    def test_traversal_refused(self):
        a=example();a['files'][0]['key']='../AgarCylinderPhantom.zip'
        with self.assertRaisesRegex(PreflightError,'BASENAME'):parse(a)

    def test_wrong_doi_or_record_refused(self):
        for change in ({'doi':'10.5281/zenodo.24120440'},{'id':24120440}):
            with self.subTest(change=change),self.assertRaises(PreflightError):
                parse({**example(),**change})

    def test_oversized_invalid_json_and_invalid_unicode_refused(self):
        for raw in [b' '*(MAX_BYTES+1),b'not json',bytes([255])]:
            with self.subTest(size=len(raw)),self.assertRaises(PreflightError):
                validate_metadata(raw)

    def test_additional_file_retained_not_selected(self):
        a=example();a['files'].append({'key':'GettingStarted.pdf','size':2026,'checksum':None})
        receipt=parse(a)
        self.assertEqual(len(receipt['listed_publisher_files']),4)
        self.assertEqual(len(receipt['archive_families']),3)
        self.assertIsNone(receipt['listed_publisher_files'][-1]['publisher_claimed_checksum'])

    def test_missing_optional_checksum_stays_unknown(self):
        a=example();a['files'][1].pop('checksum')
        self.assertIsNone(parse(a)['listed_publisher_files'][1]['publisher_claimed_checksum'])

    def test_malformed_checksum_refused(self):
        a=example();a['files'][0]['checksum']='verified'
        with self.assertRaisesRegex(PreflightError,'CHECKSUM_SHAPE'):parse(a)

    def test_untrusted_size_and_name_refused(self):
        for key,value in [('size',-1),('size','1000'),('key','HeadPhantom'+chr(92)+'secrets.zip')]:
            a=example();a['files'][0][key]=value
            with self.subTest(key=key),self.assertRaises(PreflightError):parse(a)

    def test_external_or_insecure_redirect_refused(self):
        h=ZenodoOnlyRedirect()
        for url in ['http://zenodo.org/api/records/24120439',
                    'https://example.org/record','https://zenodo.org.evil.example/api']:
            with self.subTest(url=url),self.assertRaisesRegex(PreflightError,'REDIRECT'):
                h.redirect_request(None,None,302,'moved',{},url)

    def test_duplicate_normalized_basename_refused(self):
        a=example();a['files'].append({**a['files'][1]})
        with self.assertRaisesRegex(PreflightError,'DUPLICATE'):parse(a)

    def test_http_status_or_final_origin_refused(self):
        class Response:
            def __init__(self,status,url):self.status=status;self.url=url
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return self.url
            def read(self,n):return json.dumps(example()).encode()
        class Opener:
            def __init__(self,response):self.response=response
            def open(self,*args,**kwargs):return self.response
        for status,url in [(403,'https://zenodo.org/api/records/24120439'),
                           (200,'https://attacker.example.net/record')]:
            with self.subTest(status=status,url=url):
                with patch('research.eit_observability174.build_opener',
                           return_value=Opener(Response(status,url))):
                    with self.assertRaises(PreflightError):download_metadata()

if __name__=='__main__':
    unittest.main(verbosity=2)
