"""P0-264 key-free transitive source selection probe; NOT a financial verifier."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(obj):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode())


def source_inventory(root):
    # Fixture-only implementation. Native adapter must use canonical inventory.
    return {p.relative_to(root).as_posix(): sha(p.read_bytes())
            for p in sorted(root.rglob('*.py')) if p.is_file()
            and not set(p.relative_to(root).parts) & {'historical-source-versions', '__pycache__', '.git', '.venv'}}


def bound(root, name):
    rel = Path(name)
    if not name or rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name:
        raise ValueError('UNSAFE_MEMBER')
    p = root / rel
    if not p.is_file() or any(q.is_symlink() for q in (p, *p.parents)):
        raise ValueError('UNSAFE_MEMBER')
    return sha(p.read_bytes())


def closure(record, root, manifest, *, inventory, decode, max_depth=4):
    """Return candidate context, never acceptance; caller must authenticate and audit.

    Reproduce original-then-fallback selection at every level. Only admitted
    record formats may be supplied by a reviewed native adapter. All errors
    mean no cache hit. No claim of concurrent filesystem isolation.
    """
    def visit(rec, parent, depth, ancestors):
        if depth > max_depth:
            raise ValueError('DEPTH')
        journal = rec['connected_journal']
        history = journal.get('source_history', [])
        if not isinstance(history, list):
            raise ValueError('HISTORY')
        mapping = rec.get('source_transitions', {})
        if not isinstance(mapping, dict) or len(mapping) != len(history):
            raise ValueError('HISTORY')
        children = []
        for ticket in history:
            body = decode(ticket)
            if mapping.get(body['id']) != ticket:
                raise ValueError('HISTORY')
            edge = digest(ticket)
            if edge in ancestors:
                raise ValueError('CYCLE')
            expected = body['verifier_files']
            options = [Path(body['historical_root']).absolute(),
                       parent / 'historical-source-versions' / body['from_source']['sha256']]
            chosen = None
            for candidate in options:
                try:
                    if (candidate.is_dir() and not any(p.is_symlink() for p in (candidate, *candidate.parents))
                            and inventory(candidate) == expected):
                        chosen = candidate
                        break
                except (OSError, ValueError):
                    continue
            if chosen is None:
                raise ValueError('NO_HISTORICAL_ROOT')
            for name, value in expected.items():
                if bound(chosen, name) != value:
                    raise ValueError('SOURCE_CHANGED')
            data = {}
            for job in manifest['jobs']:
                for field in ('input', 'artifact', 'receipt'):
                    name, value = job[field], job[field + '_sha256']
                    if bound(chosen, name) != value:
                        raise ValueError('SERVICE_CHANGED')
                    data[name] = value
            children.append({'ticket': edge, 'selected': str(chosen), 'source': expected,
                             'data': data, 'children': visit(body['prior_record'], chosen, depth+1, ancestors | {edge})})
        return children
    return digest(visit(record, Path(root).absolute(), 0, set()))


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mid = self.root / 'middle'
        self.leaf = self.root / 'leaf'
        self.fallback = self.mid / 'historical-source-versions' / ('a'*64)
        for p in (self.mid, self.leaf, self.fallback):
            p.mkdir(parents=True)
            (p/'module.py').write_bytes(b'x=1\n')
            (p/'data.json').write_bytes(b'{}')
        self.manifest = {'jobs': [{k:v for f in ('input','artifact','receipt') for k,v in ((f,'data.json'),(f+'_sha256',sha(b'{}')))}]}
        empty = {'connected_journal': {}, 'source_transitions': {}}
        first = self.ticket('first', self.leaf, empty)
        second = self.ticket('second', self.mid, self.record(first))
        self.rec = self.record(second)

    def ticket(self, ident, root, prior):
        return {'body': {'id': ident, 'historical_root': str(root), 'from_source': {'sha256':'a'*64},
                         'verifier_files':source_inventory(root), 'prior_record':prior}}

    def record(self, ticket):
        return {'connected_journal': {'source_history':[ticket]}, 'source_transitions':{ticket['body']['id']:ticket}}

    def context(self):
        return closure(self.rec, self.root, self.manifest, inventory=source_inventory, decode=lambda t:t['body'])

    def test_stable(self):
        self.assertEqual(self.context(), self.context())

    def test_root_selection_change_and_restore(self):
        old = self.context()
        (self.leaf/'module.py').write_bytes(b'x=2\n')
        self.assertNotEqual(old, self.context())
        (self.leaf/'module.py').write_bytes(b'x=1\n')
        self.assertEqual(old, self.context())

    def test_descendant_data_change(self):
        (self.leaf/'data.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError, 'SERVICE_CHANGED'):
            self.context()

    def test_no_valid_descendant(self):
        for p in (self.leaf, self.fallback):
            (p/'module.py').write_bytes(b'x=2\n')
        with self.assertRaisesRegex(ValueError, 'NO_HISTORICAL_ROOT'):
            self.context()

    def test_fallback_data_change(self):
        (self.leaf/'module.py').write_bytes(b'x=2\n')
        (self.fallback/'data.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError, 'SERVICE_CHANGED'):
            self.context()

    def test_inconsistent_history(self):
        self.rec['source_transitions'].clear()
        with self.assertRaisesRegex(ValueError, 'HISTORY'):
            self.context()

    def test_depth(self):
        with self.assertRaisesRegex(ValueError, 'DEPTH'):
            closure(self.rec, self.root, self.manifest, inventory=source_inventory, decode=lambda t:t['body'], max_depth=1)

if __name__ == '__main__':
    unittest.main()
