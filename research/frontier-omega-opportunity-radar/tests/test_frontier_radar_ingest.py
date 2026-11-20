import datetime as dt
import sqlite3
import tempfile
import unittest
from pathlib import Path
from frontier_radar import ingest

NOW=dt.datetime(2026,11,20,tzinfo=dt.timezone.utc)
def atom(title="Example", link="https://github.com/openai/openai-python/releases/tag/v0?utm=x", published=""):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <title>{title}</title><link href="{link}"/><updated>2026-11-19T02:00:00Z</updated>
    {published}<content type="html">&lt;b&gt;Model update&lt;/b&gt;</content></entry></feed>'''.encode()
def rss():
    return b'''<rss version="2.0"><channel><item><title>News</title><link>https://openai.com/index/news/</link><description>Content</description><pubDate>Thu, 19 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'''

class IngestTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.db=Path(self.d.name)/"test.db"

    def test_atom_publication_not_faked(self):
        a=ingest.parse_feed("openai-python",atom())[0]
        self.assertIsNone(a["published_at"])
        self.assertTrue(a["url"].endswith("/v0"))
        self.assertEqual(a["summary"],"Model update")

    def test_conflicting_duplicate_does_not_drop_others(self):
        entry = lambda name, url: f"<item><title>{name}</title><link>https://openai.com/index/{url}/</link></item>"
        xml = ('<rss><channel>'+entry('One','x')+entry('Conflict','x')+entry('Remain','y')+'</channel></rss>').encode()
        stats={}
        rows=ingest.parse_feed("openai-news",xml,stats=stats)
        self.assertEqual([x["title"] for x in rows],["Remain"])
        self.assertEqual(stats,{"feed_entries":3,"duplicate_conflicts":1})

    def test_rss_date(self):
        self.assertEqual(ingest.parse_feed("openai-news",rss())[0]["published_at"],"2026-11-19T12:00:00.000000Z")

    def test_reject_external_and_out_of_repo_citations(self):
        for link in ["https://evil.invalid/x","https://github.com/other/repo/releases/tag/v1","https://github.com@evil.invalid/openai/openai-python/releases/tag/v1"]:
            with self.assertRaises(ValueError):
                ingest.parse_feed("openai-python",atom(link=link))

    def test_reject_dtd_and_bounded_input(self):
        for body in [b'<!DOCTYPE rss [<!ENTITY thing "a">]><rss/>',b" "* (ingest.MAX_BYTES+1), b"<notafeed/>"]:
            with self.assertRaises(ValueError):
                ingest.parse_feed("openai-news",body)

    def test_persist_dedupe_conditional_and_change(self):
        calls=[]; bodies=[(200,atom()),(304,b""),(200,atom()),(200,atom("Changed"))]
        def fetch(s,e,m):
            calls.append((s,e,m));code,body=bodies.pop(0);return {"status":code,"etag":"a"},body
        reports=[ingest.run(self.db,["openai-python"],now=NOW+dt.timedelta(days=i),transport=fetch) for i in range(4)]
        self.assertEqual([r["sources"][0]["status"] for r in reports],["ok","not_modified","ok","ok"])
        self.assertEqual([len(r["new_observations"]) for r in reports],[1,0,0,1])
        self.assertEqual(calls[1],("openai-python","a",""))
        obs=ingest.observations(self.db)[0]
        self.assertEqual(obs["title"],"Changed")
        self.assertEqual(obs["first_seen"],"2026-11-20T00:00:00.000000Z")
        self.assertEqual(obs["last_seen"],"2026-11-23T00:00:00.000000Z")
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM radar_observation_versions").fetchone()[0],2)

    def test_backoff_and_recovery(self):
        calls=[]
        def f(*args):
            calls.append(args)
            return ({"status":429,"retry_after":"120"},b"") if len(calls)==1 else ({"status":200},rss())
        for seconds,want in [(0,"error"),(119,"backoff"),(120,"ok")]:
            r=ingest.run(self.db,["openai-news"],now=NOW+dt.timedelta(seconds=seconds),transport=f)
            self.assertEqual(r["sources"][0]["status"],want)
        self.assertEqual(len(calls),2)
        self.assertEqual(ingest.health(self.db)[0]["failures"],0)

    def test_source_vocab_fails_before_transport(self):
        def unreachable(*a):
            raise AssertionError()
        for ss in [["https://127.0.0.1"],["vllm","vllm"]]:
            with self.assertRaises(ValueError):
                ingest.run(self.db,ss,now=NOW,transport=unreachable)

    def test_invalid_update_preserves_observation(self):
        ingest.run(self.db,["openai-news"],now=NOW,transport=lambda *_:({"status":200},rss()))
        x=ingest.run(self.db,["openai-news"],now=NOW+dt.timedelta(days=1),transport=lambda *_:({"status":200},b"<html>ERROR</html>"))
        self.assertEqual(x["sources"][0]["status"],"error")
        self.assertEqual(ingest.health(self.db)[0]["last_success"],"2026-11-20T00:00:00.000000Z")
        self.assertEqual(len(ingest.observations(self.db)),1)

if __name__=="__main__":
    unittest.main()
