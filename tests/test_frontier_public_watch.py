"""Qualify the public watch projection without task or wallet data."""

from base64 import b64encode
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import Mock

from scripts import frontier_public_watch as watch

PAPER = '2601.01234'
TAG = 'v4.36.0'


def item(ref, source='arxiv', decision='test'):
    return {'source': source, 'ref': ref, 'decision': decision}


def inbox(unseen=(), possible=(), verified=None):
    data = {'schema': watch.SCHEMA, 'living-possibility-watch': list(unseen), 'possible-now': list(possible)}
    if verified is not None:
        data['verified-invention-watch'] = list(verified)
    return json.dumps(data).encode()


def github_file(raw):
    identity = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw, usedforsecurity=False).hexdigest()
    return json.dumps({
        'type': 'file', 'encoding': 'base64', 'path': watch.INBOX_FILE,
        'size': len(raw), 'sha': identity, 'content': b64encode(raw).decode(),
    }).encode()


def paper_page(ref, title='Source &amp; &lt;test&gt;'):
    return (f'<meta name="citation_arxiv_id" content="{PAPER}">'
            f'<meta name="citation_title" content="{title}">'
            '<meta name="citation_online_date" content="2026/01/10">'
            f'<a href="https://arxiv.org/abs/{ref}">arXiv:{ref}</a>').encode()


def release_record(tag=TAG, draft=False):
    return json.dumps({'tag_name': tag, 'draft': draft, 'published_at': '2026-11-16T12:00:00Z'}).encode()


def stage_template(directory):
    for page in watch.PAGES:
        (directory / page).write_text(f'<p>Preserve this packet.</p>\n{watch.MARKER}\n', encoding='utf-8')


class PublicWatchTests(unittest.TestCase):
    def test_parses_live_two_stream_compatibility_and_third_selection(self):
        self.assertEqual(watch.parse_inbox(inbox())['verified-invention-watch'], {})
        ref = item(PAPER + 'v2')
        self.assertEqual(watch.parse_inbox(inbox(verified=[ref]))['verified-invention-watch'],
                         {f'arxiv:{PAPER}': ref})

    def test_only_registered_exact_public_references(self):
        for ref in (
            item(PAPER), item('https://arxiv.org/abs/' + PAPER + 'v2'), item(PAPER + 'v0'),
            item('v4.36', 'lean4'), item(TAG, 'unregistered'), item(TAG, 'lean4', 'verified'),
            {**item(TAG, 'lean4'), 'text': 'unexpected content'},
        ):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                watch.parse_inbox(inbox(verified=[ref]))
        with self.assertRaises(ValueError):
            watch.parse_inbox(inbox(verified=[item(PAPER + 'v1'), item(PAPER + 'v2')]))
        with self.assertRaises(ValueError):
            watch.parse_inbox(inbox(verified=[item(f'2601.0123{i}v1') for i in range(5)]))

    def test_ambiguous_unexpected_and_oversized_metadata_fails_closed(self):
        for raw in (
            inbox()[:-1] + b', "transcript": ""}', inbox()[:-1] + b', "possible-now": []}',
            b' ' * 4097, b'[]',
        ):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                watch.parse_inbox(raw)
        for raw in (b'[]', b'{}', b' ' * 16_385,
                    json.dumps({'schema': watch.HOLD_SCHEMA, 'canonical_reference_sha256': ['secret']}).encode()):
            with self.assertRaises(ValueError):
                watch.parse_holds(raw)

    def test_github_file_requires_matching_blob(self):
        safe = github_file(inbox())
        self.assertEqual(watch.read_inbox(Mock(return_value=safe)), watch.parse_inbox(inbox()))
        record = json.loads(safe)
        record['sha'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'Git blob'):
            watch.read_inbox(Mock(return_value=json.dumps(record).encode()))

    def test_exact_version_and_release_identity(self):
        entry = item(PAPER + 'v2')
        metadata = Mock(return_value=paper_page(PAPER + 'v2'))
        self.assertEqual(watch.evidence(entry, metadata),
                         ('Source & <test>', 'https://arxiv.org/abs/' + PAPER + 'v2', '2026-01-10'))
        metadata.assert_called_once_with('https://arxiv.org/abs/' + PAPER + 'v2', 256_000)
        with self.assertRaisesRegex(ValueError, 'exact requested version'):
            watch.evidence(entry, Mock(return_value=paper_page(PAPER + 'v1')))
        self.assertEqual(watch.evidence(item(TAG, 'lean4'), Mock(return_value=release_record()))[:2],
                         ('leanprover/lean4 · ' + TAG, 'https://github.com/leanprover/lean4/releases/tag/' + TAG))
        for bad in (release_record('v4.35.0'), release_record(draft=True)):
            with self.assertRaises(ValueError):
                watch.evidence(item(TAG, 'lean4'), Mock(return_value=bad))

    def test_held_paper_excluded_across_streams_without_source_request(self):
        holds = watch.parse_holds(json.dumps({
            'schema': watch.HOLD_SCHEMA,
            'canonical_reference_sha256': [hashlib.sha256(f'arxiv:{PAPER}'.encode()).hexdigest()],
        }).encode())
        selection = watch.parse_inbox(inbox(
            [item(PAPER + 'v2')], [item(PAPER + 'v1')],
            [item(PAPER + 'v3'), item(TAG, 'lean4')],
        ))
        request = Mock(return_value=release_record())
        result = watch.collect(selection, holds, request)
        self.assertEqual(result['living-possibility-watch'], [])
        self.assertEqual(result['possible-now'], [])
        title, _, _, decision = result['verified-invention-watch'][0]
        self.assertIn(TAG, title)
        self.assertEqual(decision, 'test')
        request.assert_called_once_with('https://api.github.com/repos/leanprover/lean4/releases/tags/' + TAG, 128_000)

    def test_duplicate_across_monitors_displays_once(self):
        selection = watch.parse_inbox(inbox(
            [item(PAPER + 'v2')], verified=[item(PAPER + 'v1')],
        ))
        request = Mock(return_value=paper_page(PAPER + 'v2'))
        snapshot = watch.collect(selection, frozenset(), request)
        self.assertEqual(len(snapshot['living-possibility-watch']), 1)
        self.assertEqual(snapshot['verified-invention-watch'], [])
        request.assert_called_once()

    def test_bilingual_render_and_no_redeploy_on_unchanged_feed(self):
        raw = inbox(verified=[item(PAPER + 'v2')])
        active = {watch.INBOX_URL: github_file(raw),
                  'https://arxiv.org/abs/' + PAPER + 'v2': paper_page(PAPER + 'v2')}
        request = Mock(side_effect=lambda url, limit: active[url])
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            stage_template(directory)
            adjacent = directory / 'other.html'
            adjacent.write_text('untouched', encoding='utf-8')
            self.assertTrue(watch.stage(directory, holds=frozenset(), request=request))
            for page, decision in (('index.html', 'Matched test proposed'), ('fr.html', 'Essai comparatif proposé')):
                html = (directory / page).read_text(encoding='utf-8')
                self.assertIn('Ω ALPHA — Verified Invention Watch', html)
                self.assertIn('Source &amp; &lt;test&gt;', html)
                self.assertIn(decision, html)
                self.assertIn('Preserve this packet.', html)
                self.assertNotIn(watch.MARKER, html)
                active[watch.SITE + page] = html.encode()
            self.assertEqual(adjacent.read_text(encoding='utf-8'), 'untouched')
            stage_template(directory)
            self.assertFalse(watch.stage(directory, holds=frozenset(), periodic=True, request=request))

    def test_bad_source_preserves_prepublication_templates(self):
        raw = inbox(verified=[item(PAPER + 'v2')])
        request = Mock(side_effect=[github_file(raw), paper_page(PAPER + 'v1')])
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            stage_template(directory)
            with self.assertRaises(ValueError):
                watch.stage(directory, holds=frozenset(), request=request)
            for page in watch.PAGES:
                self.assertIn(watch.MARKER, (directory / page).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
