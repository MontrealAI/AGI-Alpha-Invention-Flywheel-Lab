import hashlib
import json
import unittest
from research import public_notice095 as m

OCID = m.IDS[0]
DAY0 = '2025-07-02T11:08:00Z'
DAY1 = '2025-10-16T11:46:00Z'
CAPTURE = '2026-11-04T15:00:00Z'
NOW = '2026-11-04T15:00:01Z'


def fixture():
    return {
      'license': 'http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/',
      'publishedDate': DAY1, 'records': [{
        'ocid': OCID,
        'releases': [
          {'ocid': OCID,'id':'036697-2025','date': DAY0,'tag':['tender'],
           'tender': {'title': 'Month End Close & Accounting Software',
                      'classification': {'id': '48000000'},
                      'value': {'amount': 300000, 'currency': 'GBP'}},
           'buyer': {'name': 'Science Museum Group',
                     'contactPoint': {'email': 'do-not-copy@example.org'}}},
          {'ocid': OCID,'id':'065861-2025','date': DAY1,'tag':['award'],
           'awards': [{'value': {'amount': 123456789}, 'suppliers':['DO_NOT_COPY']}],
           'tender': {'title': 'Changed award title'}},
        ]}]
    }


def raw(obj=None):
    return json.dumps(fixture() if obj is None else obj, sort_keys=True).encode()


def summary(obj=None, cap=CAPTURE, cut=NOW):
    data = raw(obj)
    return m.public_snapshot(data, OCID, hashlib.sha256(data).hexdigest(), cap, cut)


class RegisteredContractTest(unittest.TestCase):
    def test_three_exact_fixed_sources_and_research_only(self):
        self.assertEqual(len(m.IDS),3)
        s=summary()
        self.assertEqual(s['decision'],'RESEARCH_ONLY_NO_BID')
        self.assertFalse(s['authorized_bid_or_purchase'])
        self.assertEqual(s['native_account_operations'],0)
        self.assertEqual(s['public_tender_title'],'Month End Close & Accounting Software')
        self.assertEqual(s['public_buyer_organization'],'Science Museum Group')
        self.assertTrue(s['historically_awarded_not_open_lead'])
        self.assertIsNone(s['prospective_buyer_willingness_to_pay_our_service'])
        self.assertIsNone(s['actual_signed_capture_or_first_seen_attestation'])

    def test_late_capture_not_historically_predecision(self):
        s=summary(cap=CAPTURE,cut='2025-09-01T00:00:00Z')
        self.assertFalse(s['capture_available_at_cutoff'])
        self.assertEqual(s['tender_releases_observable_at_cutoff'],0)
        self.assertIsNone(s['public_tender_title'])
        self.assertEqual(s['reason'],'NOT_CAPTURED_BY_CUTOFF')

    def test_future_award_excluded_even_with_valid_capture(self):
        s=summary(cap='2025-07-03T00:00:00Z', cut='2025-08-03T00:00:00Z')
        self.assertEqual(s['tender_releases_observable_at_cutoff'],1)
        self.assertEqual(s['awards_already_public_by_cutoff_count'],0)
        self.assertFalse(s['historically_awarded_not_open_lead'])
        self.assertEqual(s['public_tender_title'],'Month End Close & Accounting Software')
        encoded=json.dumps(s)
        self.assertNotIn('DO_NOT_COPY',encoded)
        self.assertNotIn('Changed award title',encoded)
        self.assertNotIn('123456789',encoded)
        self.assertNotIn('do-not-copy@example.org',encoded)
        self.assertNotIn('300000',encoded)

    def test_award_only_does_not_produce_offer(self):
        d=fixture();d['records'][0]['releases']=d['records'][0]['releases'][1:]
        s=summary(d)
        self.assertIsNone(s['public_tender_title'])
        self.assertEqual(s['reason'],'NO_PREDECISION_TENDER')

    def test_modification_and_foreign_process_rejected(self):
        data=raw()
        with self.assertRaisesRegex(ValueError,'SOURCE_SHA_MISMATCH'):
            m.public_snapshot(data+b'\n',OCID,hashlib.sha256(data).hexdigest(),CAPTURE,NOW)
        d=fixture();d['records'][0]['ocid']='ocds-h6vhtk-ffffaa'
        with self.assertRaisesRegex(ValueError,'WRONG_OR_AMBIGUOUS_PROCESS'):
            summary(d)
        with self.assertRaisesRegex(ValueError,'UNREGISTERED_PROCESS'):
            m.read_package(data,'ocds-h6vhtk-ffffaa',hashlib.sha256(data).hexdigest())

    def test_duplicate_keys_or_release_identifiers_rejected(self):
        d=fixture();d['records'][0]['releases'][1]['id']=d['records'][0]['releases'][0]['id']
        with self.assertRaisesRegex(ValueError,'DUPLICATE_OR_MISSING_RELEASE_ID'):
            summary(d)
        data=raw().replace(b'"license": ',b'"license": "bad", "license": ',1)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):
            m.read_package(data,OCID,hashlib.sha256(data).hexdigest())

    def test_malformed_time_and_unverified_license_rejected(self):
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS_TIME'):
            summary(cut='2025-10-10')
        d=fixture();d['records'][0]['releases'][0]['date']='2025-07-02T12:00:00'
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS_TIME'):
            summary(d)
        d=fixture();d['license']='unknown'
        with self.assertRaisesRegex(ValueError,'PUBLIC_LICENSE_UNVERIFIED'):
            summary(d)

    def test_missing_buyer_abstention(self):
        d=fixture();d['records'][0]['releases'][0]['buyer']={}
        s=summary(d,cap=CAPTURE,cut=NOW)
        self.assertIsNone(s['public_buyer_organization'])
        self.assertFalse(s['authorized_bid_or_purchase'])
        d['records'][0]['releases']=d['records'][0]['releases'][:1]
        s=summary(d,cap=CAPTURE,cut=NOW)
        self.assertEqual(s['reason'],'MISSING_BUYER_OR_OUTCOME')

    def test_nonfinite_and_source_size_rejected(self):
        d=raw().replace(b'"amount": 300000',b'"amount": NaN')
        with self.assertRaisesRegex(ValueError,'NONFINITE_JSON'):
            m.read_package(d,OCID,hashlib.sha256(d).hexdigest())
        with self.assertRaisesRegex(ValueError,'SOURCE_SIZE'):
            m.read_package(b'a'*(m.LIMIT+1),OCID,'0'*64)


if __name__=='__main__':unittest.main()
