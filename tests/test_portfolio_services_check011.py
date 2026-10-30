import copy
import json
from pathlib import Path
import tempfile
import unittest

from commercial.portfolio_services import build_packet, render_packet
from commercial.portfolio_services_check import FREEZE, SOURCES, verify_packet, verify_services

ROOT = Path(__file__).resolve().parents[1]


class PortfolioPacketAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.packet = build_packet(ROOT)

    def test_actual_twelve_answer_packet(self):
        receipt = verify_packet(ROOT, self.packet, render_packet(self.packet))
        self.assertTrue(receipt['accepted'])
        self.assertEqual(receipt['claims_checked'], 12)
        self.assertFalse(receipt['actual_customer_acceptance'])

    def test_rejects_false_commercial_security_and_novelty_claims(self):
        for answer in ['We observed one billion USD in revenue.', 'We are SOC2 certified.', 'This is guaranteed novel and opens all inaccessible accounting work.', 'All customer books are guaranteed correct.', 'Exact host billing is zero.', 'There were 19 accepted deliveries and no rejected work.']:
            packet = copy.deepcopy(self.packet)
            packet['claims'][6]['answer'] = answer
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                verify_packet(ROOT, packet, render_packet(packet))

    def test_no_extra_markdown_prose_or_hidden_payload(self):
        rendered = render_packet(self.packet)
        for extra in [b'\nSOC2 certified.\n', b'\n<!-- Actual revenue: 1000000000 -->\n', b'\nGuaranteed novelty and financial accuracy.\n']:
            with self.assertRaises(ValueError):
                verify_packet(ROOT, self.packet, rendered + extra)

    def test_source_mutation_rejected_from_actual_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in SOURCES + [FREEZE]:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            path = root / 'commercial/service.py'
            path.write_bytes(path.read_bytes() + b'\n# Changed source after qualification.\n')
            with self.assertRaisesRegex(ValueError, 'FROZEN_SOURCE_CHANGED'):
                verify_packet(root, self.packet, render_packet(self.packet))

    def test_claim_count_ids_evidence_and_source_hashes(self):
        changes = [lambda x: x['claims'].pop(), lambda x: x['claims'].append(copy.deepcopy(x['claims'][0])), lambda x: x['claims'][0].__setitem__('id', 'guaranteed_soc2'), lambda x: x['claims'][0]['evidence'][0].__setitem__('sha256', '0'*64), lambda x: x['claims'][0]['evidence'][0].__setitem__('path', '../outside'), lambda x: x['source_hashes'].__setitem__('commercial/service.py', '0'*64), lambda x: x.__setitem__('scope', 'OBSERVED_COMMERCE'), lambda x: x.__setitem__('limits', 'Unlimited financial guarantees.'), lambda x: x.__setitem__('security_certification', 'SOC2')]
        for change in changes:
            packet = copy.deepcopy(self.packet)
            change(packet)
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                verify_packet(ROOT, packet, render_packet(packet))

    def test_json_packet_parsing_rejects_duplicate_fields(self):
        raw = json.dumps(self.packet)
        self.assertTrue(verify_packet(ROOT, raw, render_packet(self.packet))['accepted'])
        duplicate = raw[:-1] + ', "scope": "PUBLIC_REPO_EVIDENCE"}'
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SOURCE_FIELD'):
            verify_packet(ROOT, duplicate, render_packet(self.packet))

    def test_actual_service_portfolio_review_binds_rows_and_sources(self):
        import hashlib
        manifest = json.loads((ROOT / 'campaign/commercial-011/services/EXECUTED_SERVICES.json').read_bytes())
        receipt = verify_services(ROOT, manifest)
        expected = json.dumps({'rows': manifest['rows'], 'sourcefiles': manifest['sourcefiles']}, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        self.assertTrue(receipt['accepted'])
        self.assertEqual(receipt['rows_checked'], 4)
        self.assertEqual(receipt['payload_sha256'], hashlib.sha256(expected).hexdigest())

    def test_portfolio_cannot_substitute_artifacts_or_upgrade_scope(self):
        original = json.loads((ROOT / 'campaign/commercial-011/services/EXECUTED_SERVICES.json').read_bytes())
        mutations = [lambda x: x['rows'][0]['artifacts'][0].__setitem__('sha256', '0'*64), lambda x: x['rows'][1].__setitem__('accepted', False), lambda x: x.__setitem__('actual_collections_usd', 100), lambda x: x.__setitem__('scope', 'OBSERVED_COMMERCIAL_SUCCESS'), lambda x: x['rows'].pop()]
        for change in mutations:
            manifest = copy.deepcopy(original)
            change(manifest)
            with self.assertRaises(ValueError):
                verify_services(ROOT, manifest)


if __name__ == '__main__':
    unittest.main()
