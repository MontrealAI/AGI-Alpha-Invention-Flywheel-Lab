import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from research.economic_alpha import economics, eligibility, process, study


class EconomicAlphaTechnicalTests(unittest.TestCase):
    def test_replays_registered_and_fresh_cases_on_separate_controls(self):
        report = study.qualify(study.named('source_observation.json'))
        self.assertEqual(study.verify(report), report['verification'])
        self.assertEqual(report['verification']['s1_reproduced'], 24)
        self.assertEqual(report['verification']['s2_reproduced'], 18)
        self.assertEqual(report['verification']['new_catalog_routes'], 7)
        self.assertEqual(report['source_group_check']['distinct_groups'], 1)
        self.assertFalse(report['verification']['economic_promotion_authorized'])

    def test_refuses_modified_route_source_or_cash_claim(self):
        report = study.qualify(study.named('source_observation.json'))
        for change in ('source', 'decision', 'promotion'):
            edited = copy.deepcopy(report)
            if change == 'source':
                edited['source_receipt']['sources']['stock']['content_sentinels'] = [False, True]
            elif change == 'decision':
                edited['s2'][0]['with_inheritance'] = 'site-evidence-required'
            else:
                edited['commercial']['collected_funds'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                study.verify(edited)

    def test_structured_inquiry_fails_closed_on_malformed_or_unapproved_scope(self):
        plan = study.named('protocol.json')
        inquiry = {'model': 'Core One L+', 'use': 'non_safety_critical', 'nozzle_requirement_c': True}
        with self.assertRaises(ValueError):
            eligibility.assess(inquiry, plan, plan['after'])
        result = eligibility.assess({**inquiry, 'nozzle_requirement_c': 400, 'use': 'regulated'}, plan, plan['after'])
        self.assertEqual(result['decision'], 'external-review-required')
        self.assertFalse(result['fulfillment_authority'])
        inquiry = {**study.registered()['s2'][0]['input'], 'site_review': 'approved-evidence'}
        self.assertFalse(process.screen(inquiry, plan)['process_authority'])


class PrivateEvidenceGateTests(unittest.TestCase):
    def test_reviewed_arithmetic_and_source_independence(self):
        plan = study.named('protocol.json')
        with TemporaryDirectory(prefix='test-alpha-1-private-') as temp:
            root = Path(temp)
            test_key, public_key = root / 'key.pem', root / 'public.pem'
            packet_path, sig_path = root / 'review.json', root / 'review.sig'
            self.openssl('genpkey', '-algorithm', 'ED25519', '-out', test_key)
            self.openssl('pkey', '-in', test_key, '-pubout', '-out', public_key)
            key_hash = sha256(public_key.read_bytes()).hexdigest()
            schema = [('auth','owner_authorization','fixture-owner'), ('accepted','beneficiary_acceptance','fixture-beneficiary'),
                      ('fulfillment','fulfillment','fixture-distributor'), ('benefit','benefit_ledger','fixture-beneficiary'),
                      ('settlements','settlement','fixture-financial-institution'), ('cash','cash_reduction','fixture-auditor'),
                      ('costs','cost_ledger','montreal-ai'), ('baseline','matched_outcome','fixture-direct-comparison')]
            evidence = []
            for name, role, origin in schema:
                raw = ('synthetic unit test only ' + name).encode()
                filename = name + '.txt'
                (root / filename).write_bytes(raw)
                evidence.append({'file': filename, 'role': role, 'upstream': origin, 'id': name,
                                 'sha256': sha256(raw).hexdigest()})

            def amount(value, source):
                return {'minor': value, 'source': source}

            def route(collected):
                return {'collected': amount(collected, 'settlements'), 'refunds': amount(5, 'settlements'),
                        'cash_reduction': amount(0, 'cash'), 'costs': {kind: amount(1, 'costs') for kind in plan['cost_categories']},
                        'matched': True, 'comparison_source': 'baseline'}

            packet = {'schema': 'frontier-omega-alpha/reviewed-economic-pilot-v1', 'period': ['2026-01-01','2026-01-31'],
                      'currency': 'CAD', 'beneficiary': 'fixture-beneficiary', 'operator': 'montreal-ai',
                      'reviewer': 'fixture-independent-reviewer', 'authorization': 'auth', 'acceptance': 'accepted',
                      'minimum_benefit_minor': 10,
                      'fulfillment': 'fulfillment', 'benefit': amount(25, 'benefit'), 'evidence': evidence,
                      'routes': {name: route(50) for name in plan['alternatives']} | {'alpha': route(70)}}

            def signed(candidate):
                packet_path.write_text(json.dumps(candidate))
                self.openssl('pkeyutl', '-sign', '-inkey', test_key, '-rawin', '-in', packet_path, '-out', sig_path)

            def run():
                return economics.review(packet_path, sig_path, public_key, key_hash, root, plan)

            signed(packet)
            result = run()
            self.assertEqual((result['montreal_collected_minor'], result['montreal_retained_payment_minor']), (70, 65))
            self.assertEqual(result['incremental_net_minor'], 20)
            self.assertTrue(result['level_4_positive_economic_alpha'])
            self.assertFalse(result['external_action_authorized'])
            unknown = copy.deepcopy(packet)
            unknown['routes']['direct-specialist']['costs']['failed_attempts'] = None
            signed(unknown)
            self.assertIsNone(run()['incremental_net_minor'])
            self.assertFalse(run()['level_4_positive_economic_alpha'])
            circular = copy.deepcopy(packet)
            circular['evidence'][2]['upstream'] = 'fixture-beneficiary'
            signed(circular)
            with self.assertRaisesRegex(ValueError, 'separately sourced'):
                run()
            mirror = copy.deepcopy(packet)
            mirror['evidence'][2]['file'] = mirror['evidence'][1]['file']
            mirror['evidence'][2]['sha256'] = mirror['evidence'][1]['sha256']
            signed(mirror)
            with self.assertRaisesRegex(ValueError, 'multiple independent origins'):
                run()
            signed(packet)
            packet_path.write_bytes(packet_path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'signature'):
                run()

    @staticmethod
    def openssl(*args):
        subprocess.run(['openssl', *args], check=True, capture_output=True, timeout=10)
