"""Public GitHub release observation is a research trigger, never paid capability."""
import unittest
from frontier_omega import releases as m


class Store:
    def __init__(self): self.records={}
    def rows(self,table): return list(self.records.values())
    def add(self,row):
        existing=self.records.get(row["id"])
        self.records[row["id"]]=row
        return {"added":existing is None,"retests_queued":int(existing is None)}


class TestReleaseRadar(unittest.TestCase):
    def setUp(self):
        self.store=Store()
        self.config={"schema":"frontier-omega/github-release-sources/v1",
          "repositories":[{"repository":"ggml-org/llama.cpp",
                           "tags":["coding","local-inference"]}]}
        self.release={"tag_name":"v1","name":"Release v1",
          "body":"Performance claim not independently tested",
          "html_url":"https://github.com/ggml-org/llama.cpp/releases/tag/v1"}

    def test_idempotent_public_release(self):
        a=m.poll(self.store,self.config,fetch=lambda _:self.release,as_of="2026-11-16")
        b=m.poll(self.store,self.config,fetch=lambda _:self.release,as_of="2026-11-16")
        self.assertTrue(a["receipts"][0]["added"])
        self.assertFalse(b["receipts"][0]["added"])
        self.assertEqual(a["financial_effects"],0)
        self.assertEqual(next(iter(self.store.records.values()))["availability"],"REPORTED")

    def test_new_day_same_release_no_repeat_trigger(self):
        m.poll(self.store,self.config,fetch=lambda _:self.release,as_of="2026-11-16")
        r=m.poll(self.store,self.config,fetch=lambda _:self.release,as_of="2026-11-17")
        self.assertFalse(r["receipts"][0]["added"])
        self.assertEqual(len(self.store.records),1)
        self.assertEqual(next(iter(self.store.records.values()))["observed_on"],"2026-11-16")

    def test_new_release_does_trigger(self):
        m.poll(self.store,self.config,fetch=lambda _:self.release,as_of="2026-11-16")
        new={**self.release,"tag_name":"v2",
             "html_url":"https://github.com/ggml-org/llama.cpp/releases/tag/v2"}
        r=m.poll(self.store,self.config,fetch=lambda _:new,as_of="2026-11-17")
        self.assertTrue(r["receipts"][0]["added"])
        self.assertEqual(len(self.store.records),2)

    def test_rejects_non_github_owners_or_ssrf(self):
        self.config["repositories"][0]["repository"]="127.0.0.1/internal"
        with self.assertRaises(ValueError):m.validate_config(self.config)

    def test_rejects_unexpected_metadata_host(self):
        fake={**self.release,"html_url":"https://other-host.example/release"}
        r=m.poll(self.store,self.config,fetch=lambda _:fake,as_of="2026-11-16")
        self.assertEqual(r["receipts"][0]["status"],"NO_CLAIM_NO_TRIGGER")
        self.assertFalse(self.store.records)

    def test_network_error_never_creates_trigger(self):
        def offline(_):raise TimeoutError("offline")
        r=m.poll(self.store,self.config,fetch=offline,as_of="2026-11-16")
        self.assertEqual(r["receipts"][0]["status"],"NO_CLAIM_NO_TRIGGER")

    def test_public_source_never_claims_verified_model(self):
        m.poll(self.store,self.config,fetch=lambda _:self.release,as_of="2026-11-16")
        row=next(iter(self.store.records.values()))
        self.assertEqual(row["availability"],"REPORTED")
        self.assertIn("NOT independently benchmarked",row["description"])

    def test_redirects_are_refused(self):
        with self.assertRaises(ValueError):
            m._NoRedirect().redirect_request(None,None,302,"",{},"http://127.0.0.1")


if __name__=="__main__":unittest.main()
