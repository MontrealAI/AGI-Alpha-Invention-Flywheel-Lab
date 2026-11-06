"""Focused offline presentation tests; no checker qualification or customer evidence.

Tests ciblés de présentation hors ligne ; aucune qualification du vérificateur.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'continuity_passport.py'
SPEC = importlib.util.spec_from_file_location('continuity_passport', SCRIPT)
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def fixture():
    """Authored schema fixture, not a claim that an audit or delivery occurred."""
    sha = 'a' * 64
    gaps = [{'order_id': 'LBL-200', 'issue': 'MISSING_FROM_RESTORED_SNAPSHOT'}]
    return {
        'HANDOFF.json': {
            'schema': 'continuity-omega/handoff-v1', 'exercise_id': 'READING-001',
            'source_events_sha256': sha, 'required_units': 1900,
            'orders': [
                {'order_id': 'LBL-100', 'units': 1100, 'product': 'LABEL', 'spec_sha256': sha,
                 'deadline_hours': 48, 'source_sequences': [1, 4]},
                {'order_id': 'LBL-200', 'units': 800, 'product': 'LABEL', 'spec_sha256': sha,
                 'deadline_hours': 48, 'source_sequences': [2]},
            ],
            'supplier_id': 'PRINTER-02', 'supplier_failure_domain': 'REGION-B',
            'supplier_available_units_in_window': 2100, 'rehearsed_completion_hours': 22,
            'latest_required_hours': 48, 'idempotency_key': 'b' * 64,
            'scope': 'SYNTHETIC_ONLY_NOT_AN_AUTHORIZATION',
        },
        'PASSPORT.json': {
            'schema': 'continuity-omega/passport-v1', 'exercise_id': 'READING-001',
            'technical_verdict': 'READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT',
            'restoration_findings': deepcopy(gaps), 'source_events_sha256': sha,
            'handoff_sha256': 'c' * 64,
            'economics': {'currency': 'ILLUSTRATIVE_USD', 'offer': 5700, 'modeled_cost': 5050,
                          'modeled_contribution': 650, 'customer_budget': 5800},
            'comparison': {'conventional_route': 'SAME_INPUTS_AND_SUPPLIER_ACCESS',
                           'incremental_advantage': 'NOT_ESTABLISHED'},
            'evidence_boundary': {key: False for key in reader.BOUNDARIES},
            'successor_hypothesis': reader.SUCCESSOR,
        },
        'AUDIT.json': {
            'schema': 'continuity-omega/audit-v1', 'exercise_id': 'READING-001',
            'verdict': 'PASS_SYNTHETIC_ONLY', 'failure_count': 0, 'failures': [],
            'replayed_orders': 2, 'replayed_units': 1900, 'restoration_gaps': deepcopy(gaps),
            'scope': reader.AUDIT_SCOPE, 'source_digest_sha256': sha,
            'handoff_sha256': 'c' * 64, 'required_real_world_gates': list(reader.GATES),
        },
    }


class PassportReadingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / 'evidence'
        self.inputs.mkdir()
        self.write(fixture())
        # These historical artifacts are intentionally not consulted by the reader.
        (self.inputs / 'INPUT.json').write_text('unread original source\n', encoding='utf-8')
        (self.inputs / 'PASSPORT.md').write_text('original English view\n', encoding='utf-8')

    def write(self, records):
        for name, value in records.items():
            (self.inputs / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    def snapshot(self):
        return {str(p.relative_to(self.inputs)): p.read_bytes() for p in self.inputs.rglob('*') if p.is_file()}

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = reader.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_both_languages_preserve_tokens_amounts_and_recorded_status(self):
        en = reader.present(self.inputs, 'en')
        fr = reader.present(self.inputs, 'fr')
        for token in ('1900', '1100', '800', '2100', '22', '48', '5700', '5050', '650', '5800',
                      'LBL-100', 'LBL-200', 'PRINTER-02', 'REGION-B', 'PASS_SYNTHETIC_ONLY',
                      'READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT', 'MISSING_FROM_RESTORED_SNAPSHOT',
                      'SYNTHETIC_ONLY_NOT_AN_AUTHORIZATION', 'ILLUSTRATIVE_USD',
                      'SAME_INPUTS_AND_SUPPLIER_ACCESS', 'NOT_ESTABLISHED'):
            self.assertIn(token, en)
            self.assertIn(token, fr)
        for schema in reader.SCHEMAS.values():
            if 'rejection' not in schema:
                self.assertIn(schema, en)
                self.assertIn(schema, fr)
        self.assertIn('No fresh audit was performed', en)
        self.assertIn('shared research authorship', en)
        self.assertIn('Aucun nouvel audit n’a été exécuté', fr)
        self.assertIn('code distinct produit par les mêmes auteurs', fr)
        self.assertIn('aucune autorisation opérationnelle', fr)
        self.assertIn('**Unités requises :**', fr)
        self.assertNotIn(reader.SUCCESSOR, fr)
        for gate in reader.GATES:
            self.assertNotIn(gate, fr)
            self.assertIn(reader.GATES[gate], fr)

    def test_input_bytes_and_inventory_are_unchanged(self):
        before = self.snapshot()
        for lang in ('en', 'fr'):
            output = self.root / ('PASSPORT.' + lang + '.md')
            result = reader.present(self.inputs, lang, output)
            self.assertEqual(result, output.read_text(encoding='utf-8'))
            for name in ('HANDOFF.json', 'PASSPORT.json', 'AUDIT.json'):
                self.assertIn(hashlib.sha256(before[name]).hexdigest(), result)
        self.assertEqual(before, self.snapshot())

    def test_unsafe_outputs_do_not_overwrite_or_create_evidence(self):
        existing = self.root / 'existing.md'
        existing.write_text('preserve me', encoding='utf-8')
        symlink = self.root / 'alias.md'
        symlink.symlink_to(existing)
        alias_dir = self.root / 'evidence-alias'
        alias_dir.symlink_to(self.inputs, target_is_directory=True)
        before = self.snapshot()
        for output in (existing, symlink, self.inputs / 'NEW.md', alias_dir / 'NEW.md',
                       Path('relative.md'), self.root / 'missing' / 'NEW.md'):
            with self.subTest(output=output), self.assertRaises(reader.PresentationError):
                reader.present(self.inputs, 'fr', output)
        self.assertEqual('preserve me', existing.read_text(encoding='utf-8'))
        self.assertEqual(before, self.snapshot())

    def test_required_input_symlink_is_refused(self):
        original = self.root / 'original.json'
        path = self.inputs / 'PASSPORT.json'
        original.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(original)
        with self.assertRaises(reader.PresentationError):
            reader.present(self.inputs, 'fr')

    def test_symbolic_link_loops_receive_localized_cli_refusals(self):
        loop = self.root / 'loop'
        loop.symlink_to(loop)
        for args in (('--in-dir', str(loop)),
                     ('--in-dir', str(self.inputs), '--out', str(loop / 'new.md'))):
            code, stdout, stderr = self.invoke('--language', 'fr', *args)
            self.assertEqual(2, code)
            self.assertEqual('', stdout)
            self.assertTrue('chemin' in stderr or 'Impossible de lire' in stderr)
            self.assertNotIn('Traceback', stderr)

    def test_unknown_and_malformed_fields_never_produce_partial_reports(self):
        mutations = [
            lambda r: r.__setitem__('PASSPORT.json', None),
            lambda r: r['PASSPORT.json'].pop('economics'),
            lambda r: r['PASSPORT.json']['economics'].__setitem__('new_explanation', 'Trust this'),
            lambda r: r['PASSPORT.json']['economics'].__setitem__('offer', True),
            lambda r: r['PASSPORT.json'].__setitem__('successor_hypothesis', 'Unknown conclusion'),
            lambda r: r['AUDIT.json']['required_real_world_gates'].__setitem__(0, 'Unknown gate'),
            lambda r: r['AUDIT.json'].__setitem__('verdict', 'CERTIFIED'),
            lambda r: r['PASSPORT.json']['restoration_findings'][0].__setitem__('issue', 'UNKNOWN'),
            lambda r: r['HANDOFF.json']['orders'][0].__setitem__('order_id', 'X\n# TRUSTED'),
            lambda r: r['HANDOFF.json']['orders'][0].__setitem__('order_id', 'X<script>'),
            lambda r: r['AUDIT.json'].__setitem__('failures', [{}]),
            lambda r: r['AUDIT.json'].__setitem__('scope', 'CERTIFICATION'),
        ]
        for index, mutate in enumerate(mutations):
            records = fixture()
            mutate(records)
            self.write(records)
            output = self.root / ('unsupported-' + str(index) + '.md')
            with self.subTest(index=index):
                code, stdout, stderr = self.invoke('--in-dir', str(self.inputs), '--language', 'fr', '--out', str(output))
                self.assertEqual(2, code)
                self.assertEqual('', stdout)
                self.assertIn('Présentation refusée', stderr)
                self.assertNotIn('Traceback', stderr)
                self.assertFalse(output.exists())

    def test_json_duplicate_nonfinite_and_oversized_integer_are_localized(self):
        path = self.inputs / 'PASSPORT.json'
        original = json.dumps(fixture()['PASSPORT.json'])
        variants = [
            original.replace('"offer": 5700', '"offer": 5700, "offer": 5800'),
            original.replace('"offer": 5700', '"offer": NaN'),
            original.replace('"offer": 5700', '"offer": ' + '9' * 4301),
            original.replace('"offer": 5700', '"offer": 1e999'),
        ]
        for raw in variants:
            path.write_text(raw, encoding='utf-8')
            code, stdout, stderr = self.invoke('--in-dir', str(self.inputs), '--language', 'fr')
            self.assertEqual(2, code)
            self.assertEqual('', stdout)
            self.assertIn('Présentation refusée', stderr)
            self.assertNotIn('Traceback', stderr)

    def test_stale_handoff_is_displayed_without_upgrading_saved_pass(self):
        records = fixture()
        records['HANDOFF.json']['required_units'] = 1
        self.write(records)
        result = reader.present(self.inputs, 'fr')
        self.assertIn('**Unités requises :** ` 1 `', result)
        self.assertIn('**Unités réexécutées consignées :** ` 1900 `', result)
        self.assertIn('PASS_SYNTHETIC_ONLY', result)
        self.assertIn('ni leur validité actuelle', result)
        self.assertIn('Aucun nouvel audit', result)

    def test_coherent_rewrite_does_not_become_authentication(self):
        records = fixture()
        for data in records.values():
            data['exercise_id'] = 'REWRITTEN'
            for key in ('source_events_sha256', 'source_digest_sha256', 'handoff_sha256'):
                if key in data:
                    data[key] = 'd' * 64
        records['PASSPORT.json']['evidence_boundary']['real_payment'] = True
        self.write(records)
        result = reader.present(self.inputs, 'fr')
        self.assertIn('REWRITTEN', result)
        self.assertIn('real_payment = true', result)
        self.assertIn('La valeur true n’établit pas', result)
        self.assertIn('sans authentifier le scénario d’origine', result)
        self.assertIn('Aucun nouvel audit', result)

    def test_fail_preserves_pre_deduplication_count(self):
        records = fixture()
        records['AUDIT.json'].update(verdict='FAIL', failure_count=2, failures=['REQUIRED_UNITS'])
        self.write(records)
        code, stdout, stderr = self.invoke('--in-dir', str(self.inputs), '--language', 'fr')
        self.assertEqual(0, code)
        self.assertEqual('', stderr)
        self.assertIn('**Nombre d’échecs consigné :** ` 2 `', stdout)
        self.assertIn('Quantité requise incohérente', stdout)
        self.assertIn('` FAIL `', stdout)

    def test_refusal_has_complete_translation_and_success_means_reading(self):
        for name in ('HANDOFF.json', 'PASSPORT.json', 'AUDIT.json'):
            (self.inputs / name).unlink()
        self.write({'REJECTION.json': {
            'schema': 'continuity-omega/rejection-v1', 'exercise_id': 'REFUSED-001',
            'verdict': 'REJECTED_BEFORE_HANDOFF',
            'reason': 'no simulated supplier can satisfy capacity and deadline',
            'scope': reader.REJECTION_SCOPE,
        }})
        before = self.snapshot()
        for lang in ('en', 'fr'):
            code, stdout, stderr = self.invoke('--in-dir', str(self.inputs), '--language', lang)
            self.assertEqual(0, code)
            self.assertEqual('', stderr)
            self.assertIn('REJECTED_BEFORE_HANDOFF', stdout)
            self.assertIn('continuity-omega/rejection-v1', stdout)
        self.assertIn('Aucun fournisseur simulé ne satisfait la capacité et le délai', stdout)
        self.assertIn('n’a pas réexécuté cette décision', stdout)
        self.assertEqual(before, self.snapshot())

    def test_all_known_reasons_and_findings_have_french_and_unknowns_refuse(self):
        for raw, french in reader.REASONS.items():
            self.assertEqual(french, reader.reason_description(raw, 'fr'))
        for field, (label, suffix) in reader.FIELD_REASONS.items():
            self.assertIn(label, reader.reason_description(field + ': ' + suffix, 'fr'))
        self.assertEqual('quantité restaurée : entier strictement positif attendu',
                         reader.reason_description('recovered quantity: expected positive integer', 'fr'))
        for bad in ('This audit proves all customer orders were restored: invalid identifier',
                    'supplier failure domain: expected positive integer', 'unknown refusal'):
            with self.assertRaises(reader.PresentationError):
                reader.reason_description(bad, 'fr')
        for code, french in reader.FAILURES.items():
            self.assertEqual(french, reader.failure_description(code, 'fr'))
        for key in reader.BOUNDARIES:
            self.assertIn('Affirmation réelle non étayée', reader.failure_description('IMPROPER_REAL_WORLD_CLAIM_' + key.upper(), 'fr'))
        with self.assertRaises(reader.PresentationError):
            reader.failure_description('UNKNOWN_FINDING', 'fr')

    def test_help_and_argument_errors_are_localized(self):
        code, stdout, stderr = self.invoke('--help')
        self.assertEqual(0, code)
        self.assertIn('Read recorded', stdout)
        self.assertIn('Lire les artefacts', stdout)
        code, stdout, stderr = self.invoke('--help', '--language', 'fr')
        self.assertEqual(0, code)
        self.assertIn('utilisation :', stdout)
        self.assertNotIn('usage:', stdout)
        self.assertNotIn('Read recorded', stdout)
        for args in (('--language', 'fr', '--unknown'), ('--language', 'fr'),
                     ('--language', 'fr', '--in-dir'), ('--language', 'fr', '--in-dir', str(self.root / 'absent'))):
            code, stdout, stderr = self.invoke(*args)
            self.assertEqual(2, code)
            self.assertIn('Présentation refusée', stderr)
            self.assertNotIn('Traceback', stderr)

    def test_mixed_or_incomplete_record_sets_refuse(self):
        self.write({'REJECTION.json': {'schema': 'continuity-omega/rejection-v1'}})
        with self.assertRaises(reader.PresentationError):
            reader.present(self.inputs, 'fr')
        with self.assertRaises(reader.PresentationError):
            reader.render({'UNSUPPORTED.json': {}}, {}, 'fr')
        with self.assertRaises(reader.PresentationError):
            reader.render({'HANDOFF.json': fixture()['HANDOFF.json']}, {}, 'fr')


if __name__ == '__main__':
    unittest.main()
