import unittest
from experiments.capability_transfer_20261102.fetch_catalog import catalog_entries

class CatalogBoundaryTests(unittest.TestCase):
    def test_http_success_with_remote_error_rejected(self):
        for x in [{'error':400},{'errors':['bad request']},[],{},None,{'files':[{'id':'x'}]}]:
            with self.subTest(payload=x), self.assertRaises(ValueError): catalog_entries(x)
    def test_named_file_and_folder_catalogs(self):
        rows=[{'id':'file','filename':'data.mat','content_details':{'size':100}},{'id':'folder','name':'processed'}]
        for x in [rows,{'files':rows},{'data':{'files':rows}}]: self.assertEqual(catalog_entries(x),rows)

if __name__=='__main__': unittest.main()
