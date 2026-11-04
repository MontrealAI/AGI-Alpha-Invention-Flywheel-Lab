import copy
import hashlib
import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from research import active_tender096 as m

IDS = tuple("ocds-h6vhtk-%06x" % n for n in [9, 2, 7, 4, 3, 1, 8])
AT = "2026-11-04T15:03:00Z"
LATER = "2026-11-04T15:04:00Z"
EARLIER = "2026-11-03T15:00:00Z"
LICENCE = "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"


def enc(obj):
    return json.dumps(obj, sort_keys=True).encode("utf-8")


def checked(obj):
    raw = enc(obj)
    return raw, hashlib.sha256(raw).hexdigest()


def release(ocid, rid="T1", at=EARLIER, tag=None, title="Observed public need",
            buyer="Public buyer", end="2026-11-11T12:00:00Z", status="active"):
    return {"ocid": ocid, "id": rid, "date": at, "tag": tag or ["tender"],
            "tender": {"title": title, "status": status,
                       "tenderPeriod": {"endDate": end}},
            "buyer": {"name": buyer, "contactPoint": {"email": "NO-EXPORT@example.org"}}}


def search():
    return {"license": LICENCE,
            "publishedDate": AT,
            "releases": [release(ocid, rid="R"+str(i)) for i, ocid in enumerate(IDS)]}


def record(ocid=IDS[0]):
    return {"license": LICENCE,
            "records": [{"ocid": ocid, "releases": [release(ocid)]}]}


def assess(obj=None, ocid=IDS[0], cap=AT, cut=LATER):
    raw, digest = checked(record(ocid) if obj is None else obj)
    return m.assess_record(raw, digest, ocid, cap, cut)


class ActiveTender096Tests(TestCase):
    def test_registered_fixed_query_freezes_narrow_one_page(self):
        self.assertIn("2026-11-04T15%3A00%3A00", m.SEARCH_URL)
        self.assertIn("stages=tender&limit=20", m.SEARCH_URL)
        self.assertEqual(m.MAX_PROCESSES, 5)
        raw, digest = checked(search())
        s = m.select(raw, digest)
        self.assertEqual(s["selected_ocids"], sorted(set(IDS))[:5])
        self.assertEqual(s["source_release_count"], 7)
        self.assertEqual(s["unique_source_process_count"], 7)

    def test_smaller_page_retains_all_without_favorable_substitution(self):
        x = search()
        x["releases"] = x["releases"][:2]
        data, sha = checked(x)
        self.assertEqual(m.select(data, sha)["selected_ocids"], sorted(IDS[:2]))
        x["releases"] = []
        data, sha = checked(x)
        self.assertEqual(m.select(data, sha)["selected_ocids"], [])

    def test_public_future_deadline_is_not_a_buyer_or_spend_authority(self):
        s = assess()
        self.assertTrue(s["public_deadline_in_future_unverified_eligibility"])
        self.assertFalse(s["open_reachable_willing_buyer_confirmed"])
        self.assertFalse(s["authorized_bid_or_purchase"])
        self.assertEqual(s["decision"], "RESEARCH_ONLY_NO_BID")
        self.assertEqual(s["native_account_operations"], 0)
        self.assertIsNone(s["our_service_eligibility"])
        self.assertIsNone(s["complete_delivery_and_acquisition_costs"])
        self.assertEqual(s["public_tender_title"], "Observed public need")
        self.assertNotIn("NO-EXPORT@example.org", json.dumps(s))
        self.assertIsNone(s["first_seen_external_attestation"])

    def test_expired_and_absent_deadline_are_not_active(self):
        d = record()
        d["records"][0]["releases"][0]["tender"]["tenderPeriod"]["endDate"] = EARLIER
        s = assess(d)
        self.assertFalse(s["public_deadline_in_future_unverified_eligibility"])
        self.assertEqual(s["reason"], "DEADLINE_MISSING_OR_EXPIRED")
        del d["records"][0]["releases"][0]["tender"]["tenderPeriod"]
        self.assertEqual(assess(d)["reason"], "INCOMPLETE_LATEST_TENDER_OR_AMENDMENT")

    def test_new_complete_tender_amendment_replaces_stale_title(self):
        d = record()
        amend = release(IDS[0], "T2", "2026-11-04T12:30:00Z",
                        tag=["tenderAmendment"], title="Changed need; verified prospectively")
        d["records"][0]["releases"].append(amend)
        s = assess(d)
        self.assertEqual(s["latest_tender_release_id"], "T2")
        self.assertEqual(s["public_tender_title"], "Changed need; verified prospectively")
        self.assertTrue(s["public_deadline_in_future_unverified_eligibility"])
        self.assertNotIn("Observed public need", json.dumps(s))

    def test_incomplete_latest_amendment_fails_closed_without_inheriting_old_title(self):
        d = record()
        d["records"][0]["releases"].append({
            "ocid": IDS[0], "id": "T2", "date": "2026-11-04T12:00:00Z",
            "tag": ["tenderAmendment"], "tender": {"title": "Changed scope"}})
        s = assess(d)
        self.assertEqual(s["reason"], "INCOMPLETE_LATEST_TENDER_OR_AMENDMENT")
        self.assertFalse(s["public_deadline_in_future_unverified_eligibility"])
        self.assertIsNone(s["public_buyer_organization"])
        self.assertIsNone(s["public_deadline_utc"])

    def test_award_and_cancellation_block_even_with_future_deadline(self):
        for tag in ("award", "tenderCancellation", "contract", "tenderTermination"):
            with self.subTest(tag=tag):
                d = record()
                d["records"][0]["releases"].append({
                    "ocid": IDS[0], "id": "X2", "date": AT, "tag": [tag]})
                s = assess(d)
                self.assertEqual(s["reason"], "PUBLIC_CLOSING_STAGE_PRESENT")
                self.assertFalse(s["public_deadline_in_future_unverified_eligibility"])
                self.assertIsNone(s["public_tender_title"])

    def test_future_award_not_available_at_cutoff_and_not_leaked(self):
        d = record()
        d["records"][0]["releases"].append({
            "ocid": IDS[0], "id": "AW2", "date": "2026-11-05T12:00:00Z",
            "tag": ["award"], "awards": [{"suppliers": ["DO_NOT_COPY"]}]})
        s = assess(d)
        self.assertTrue(s["public_deadline_in_future_unverified_eligibility"])
        self.assertEqual(s["asof_end_stage_count"], 0)
        self.assertNotIn("DO_NOT_COPY", json.dumps(s))

    def test_late_capture_cannot_create_retrospective_prospective_proof(self):
        s = assess(cap="2026-11-05T00:00:00Z", cut=LATER)
        self.assertEqual(s["reason"], "SOURCE_NOT_CAPTURED_BY_DECISION")
        self.assertFalse(s["public_deadline_in_future_unverified_eligibility"])
        self.assertIsNone(s["public_tender_title"])

    def test_unverified_inactive_or_unknown_status_not_promoted(self):
        for status in ("complete", "cancelled", None):
            with self.subTest(status=status):
                d = record()
                d["records"][0]["releases"][0]["tender"]["status"] = status
                self.assertEqual(assess(d)["reason"], "UNKNOWN_OR_INACTIVE_TENDER_STATUS")

    def test_source_and_data_corruption_fail(self):
        data, sha = checked(search())
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_CHANGED"):
            m.select(data + b" ", sha)
        bad = data.replace(b'"license": ', b'"license": "BAD", "license": ', 1)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            m.select(bad, hashlib.sha256(bad).hexdigest())
        x = search(); x["license"] = "https://fake.example/open-government-licence/version/3/"
        raw, sha = checked(x)
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_OPEN_LICENCE"):
            m.select(raw, sha)
        x = search(); x["releases"][0]["ocid"] = "ocds-h6vhtk-nothex"
        raw, sha = checked(x)
        with self.assertRaisesRegex(ValueError, "INVALID_PROCESS_ID"):
            m.select(raw, sha)

    def test_duplicate_ids_nonfinite_excess_and_ambiguous_time_rejected(self):
        x = search(); x["releases"].append(copy.deepcopy(x["releases"][0]))
        raw, sha = checked(x)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_INVALID_RELEASE_ID"):
            m.select(raw, sha)
        bad = enc(search()).replace(b'"status": "active"', b'"status": NaN')
        with self.assertRaisesRegex(ValueError, "NONFINITE_JSON"):
            m.select(bad, hashlib.sha256(bad).hexdigest())
        raw = b"x" * (m.MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "SOURCE_SIZE"):
            m.select(raw, hashlib.sha256(raw).hexdigest())
        x = record(); x["records"][0]["releases"][0]["date"] = "2026-11-03"
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_OR_INVALID_TIME"):
            assess(x)

    def test_foreign_record_and_illegal_destination_rejected(self):
        x = record()
        x["records"][0]["ocid"] = IDS[1]
        with self.assertRaisesRegex(ValueError, "FOREIGN_RECORD_PACKAGE"):
            assess(x)
        self.assertEqual(m.RECORD_PREFIX, "https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages/")

    def test_one_live_search_five_fixed_records_and_no_output_overwrite(self):
        x, sh = checked(search())
        bodies = {m.SEARCH_URL: x}
        for o in sorted(set(IDS))[:5]:
            bodies[m.RECORD_PREFIX + o] = checked(record(o))[0]
        actual_calls = []

        def mock_fetch(url, path):
            actual_calls.append(url)
            return bodies[url]

        with tempfile.TemporaryDirectory() as d, mock.patch.object(m, "get_official", side_effect=mock_fetch), \
             mock.patch.object(m, "timestamp", return_value=AT):
            path = str(Path(d) / "receipt.json")
            output = m.run(path)
            self.assertTrue(output["all_registered_source_retrievals_succeeded"])
            self.assertEqual(len(actual_calls), 6)
            self.assertEqual(actual_calls[0], m.SEARCH_URL)
            self.assertEqual(actual_calls[1:], [m.RECORD_PREFIX + v for v in sorted(set(IDS))[:5]])
            self.assertEqual(len(output["records"]), 5)
            self.assertEqual(output["genuine_buyer_commitments"], 0)
            self.assertEqual(output["decision"], "RESEARCH_ONLY_NO_BID")
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS_NO_REPLACEMENT"):
                m.run(path)
