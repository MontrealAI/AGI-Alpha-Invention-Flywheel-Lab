import importlib.util
import json
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / 'campaign' / 'frontier-genesis-001' / 'watch.py'
s = importlib.util.spec_from_file_location('genesis_watch', P)
w = importlib.util.module_from_spec(s)
s.loader.exec_module(w)


class FakeResponse:
    def __init__(self, b): self.b = b
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.b[:n]


def fetch(req, timeout):
    assert timeout <= 15
    assert req.full_url.startswith('https://api.github.com/repos/openai/codex/releases')
    return FakeResponse(json.dumps([
        {'draft': False, 'prerelease': False, 'html_url': 'https://github.com/openai/codex/releases/tag/v1',
         'tag_name': 'v1', 'published_at': '2026-11-04T12:00:00Z', 'name': 'First'},
        {'draft': True, 'html_url': 'https://github.com/openai/codex/releases/tag/private'}]).encode())


class WatchTests(unittest.TestCase):
    def test_record_is_read_only_unknown(self):
        e = w.get_public_releases('openai/codex', transport=fetch)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]['access'], 'UNVERIFIED')
        self.assertEqual(e[0]['operational_capability'], 'NOT_DEMONSTRATED')

    def test_untrusted_host_blocked(self):
        with self.assertRaises(ValueError): w.get_public_releases('evil.invalid/a/../../secret', transport=fetch)

    def test_unexpected_url_blocked(self):
        with self.assertRaises(ValueError):
            w.get_public_releases('openai/codex', transport=lambda req, timeout: FakeResponse(json.dumps([
                {'html_url': 'https://evil.test/phish', 'draft': False}]).encode()))

    def test_non_list_payload_blocked(self):
        with self.assertRaises(ValueError):
            w.get_public_releases('openai/codex', transport=lambda req, timeout: FakeResponse(b'{"message":"rate limited"}'))

    def test_no_arbitrary_limit(self):
        with self.assertRaises(ValueError): w.get_public_releases('openai/codex', limit=100, transport=fetch)


if __name__ == '__main__': unittest.main()
