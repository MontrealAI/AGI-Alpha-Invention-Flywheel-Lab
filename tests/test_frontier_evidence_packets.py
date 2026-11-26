from email.message import Message
from io import BytesIO
from itertools import combinations
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import frontier_evidence_packets as packets


class EvidencePacketsTest(TestCase):
    def test_minimum_cover_matches_independently_enumerated_cuts(self):
        orders = ((1, 4, 5, 18, 23), (0, 4, 8, 12), (0, 2, 30, 34, 40, 70))
        for order in orders:
            intervals = [(lo, lo + 2) for lo in order]
            for budget in range(1, len(intervals) + 1):
                measured = packets.plan(intervals[::-1], budget)
                possible = []
                for count in range(budget):
                    for edges in combinations(range(1, len(intervals)), count):
                        groups = (0, *edges, len(intervals))
                        possible.append(sum(intervals[hi - 1][1] - intervals[lo][0]
                                            for lo, hi in zip(groups, groups[1:])))
                self.assertEqual(sum(hi - lo for lo, hi in measured), min(possible))
                self.assertLessEqual(len(measured), budget)
                self.assertTrue(all(any(left <= lo < hi <= right for left, right in measured)
                                    for lo, hi in intervals))

    def source(self):
        names = {'file.txt': b'known first evidence', 'study/review.txt': b'known second evidence'}
        output = BytesIO()
        with ZipFile(output, 'w') as archive:
            archive.writestr('file.txt', names['file.txt'])
            archive.writestr('unused.txt', b'ignore this unselected content' * 50)
            archive.writestr('study/review.txt', names['study/review.txt'])
        raw = output.getvalue()
        spec = packets.index_archive(raw, 'frontier-activation-1.5.0.zip', packets.fingerprint(raw),
                                     {name: packets.fingerprint(body) for name, body in names.items()})
        return raw, spec, names

    def test_only_independently_verified_members_are_restored(self):
        raw, spec, names = self.source()
        read = lambda packet, start, end: (raw[start:end], '"frozen"')
        result, receipt = packets.restore(spec, 2, read)
        self.assertEqual(result, names)
        self.assertEqual(receipt['range_requests'], 2)
        self.assertEqual(receipt['response_body_bytes'], sum(map(len, names.values())))

    def test_consistent_http_metadata_does_not_admit_wrong_bytes(self):
        raw, spec, _ = self.source()
        def replace(packet, start, end):
            return bytes(end - start), '"frozen"'

        with self.assertRaisesRegex(ValueError, 'independently pinned member'):
            packets.restore(spec, 2, replace)

    def test_slices_from_different_archive_representations_are_refused(self):
        raw, spec, _ = self.source()
        with self.assertRaisesRegex(ValueError, 'representation changed'):
            packets.restore(spec, 2, lambda packet, start, end: (raw[start:end], f'"{start}"'))

    def test_invalid_archive_or_member_identity_is_refused(self):
        raw, spec, _ = self.source()
        with self.assertRaisesRegex(ValueError, 'archive bytes or identity'):
            packets.index_archive(raw, spec['archive'], '0' * 64, {'file.txt': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'independently pinned source'):
            packets.index_archive(raw, spec['archive'], packets.fingerprint(raw), {'file.txt': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'Invalid evidence member path'):
            packets.index_archive(raw, spec['archive'], packets.fingerprint(raw), {'study/../file.txt': '0' * 64})

    def test_complete_release_cases_bind_the_independent_contract(self):
        for case, spec in json.loads(packets.INDEX.read_bytes())['packets'].items():
            packets.verify_contract(case, spec)
            spec['members'].pop(next(iter(spec['members'])))
            with self.assertRaisesRegex(ValueError, 'exact reviewed packet contract'):
                packets.verify_contract(case, spec)

    def test_http_length_and_singleton_headers_are_required_to_agree(self):
        raw, spec, _ = self.source()
        for extra in (('Content-Length', '100'), ('Content-Range', f'bytes 0-1/{len(raw)}')):
            response = Mock(status=206, url=packets.SITE + spec['archive'])
            response.headers = Message()
            response.headers['Content-Range'] = f'bytes 0-1/{len(raw)}'
            response.headers['ETag'] = '"test"'
            response.headers[extra[0]] = extra[1]
            opened = Mock()
            opened.open.return_value.__enter__ = Mock(return_value=response)
            opened.open.return_value.__exit__ = Mock(return_value=None)
            with patch.object(packets, 'build_opener', return_value=opened):
                with self.assertRaisesRegex(ValueError, 'range reply'):
                    packets.download_range(spec, 0, 2)
            response.read.assert_not_called()

    def test_untrusted_or_existing_output_is_refused_before_network(self):
        with TemporaryDirectory() as name, patch.object(packets, 'restore') as restore:
            output = Path(name)
            with self.assertRaises(FileExistsError):
                packets.restore_into('ACT15', output)
            if os.name == 'posix':
                output.chmod(0o777)
                with self.assertRaisesRegex(ValueError, 'trusted, protected parent'):
                    packets.restore_into('ACT15', output / 'restored')
            restore.assert_not_called()
