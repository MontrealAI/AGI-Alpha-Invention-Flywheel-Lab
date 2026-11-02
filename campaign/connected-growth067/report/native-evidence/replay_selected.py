"""Replay one pinned key-free public control export, never a private account."""
from pathlib import Path, PurePosixPath
import argparse, ast, hashlib, json, stat, sys, tempfile, zipfile

EXPECTED = 'f7415b3200eb0984961b6c17e7a90bf8ce1559559ebf3ec425bb025a43480c95'
PREFIX = 'dev-100000-distribution_first/'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-checkout', type=Path, required=True)
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
data = args.archive.read_bytes()
if len(data) != 2257538 or hashlib.sha256(data).hexdigest() != EXPECTED:
    raise ValueError('PINNED_ARCHIVE_IDENTITY_MISMATCH')
with zipfile.ZipFile(args.archive) as z:
    infos = z.infolist()
    names = [x.filename for x in infos]
    if len(names) != 125 or len(set(names)) != 125:
        raise ValueError('MEMBER_COUNT_OR_DUPLICATE')
    for x in infos:
        path = PurePosixPath(x.filename)
        if path.is_absolute() or '..' in path.parts or not x.filename.startswith(PREFIX) or x.is_dir():
            raise ValueError('UNSAFE_MEMBER')
        if stat.S_ISLNK(x.external_attr >> 16):
            raise ValueError('SYMLINK_MEMBER')
    manifest = json.loads(z.read(PREFIX + 'manifest.json'))
    exported = json.loads(z.read(PREFIX + 'public-export.json'))
    result = json.loads(z.read(PREFIX + 'result.json'))
    package = json.loads(z.read(PREFIX + 'PACKAGE.json'))
    allowed = {PREFIX + n for n in ['manifest.json', 'public-export.json', 'result.json', 'PACKAGE.json']}
    for job in manifest['jobs']:
        for name in [job['delivery_path'], job['delivery_path'].replace('/deliveries/', '/decisions/')]:
            allowed.add(PREFIX + 'source/' + name)
    if not set(names).issubset(allowed):
        raise ValueError('NONWHITELIST_MEMBER')
    files = exported['connected_journal']['source']['files']
    with tempfile.TemporaryDirectory(prefix='growth067-public-replay-') as tmp:
        root = Path(tmp)
        for name, expected in files.items():
            rel = PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('UNSAFE_SOURCE_PATH')
            source = args.source_checkout / name
            body = source.read_bytes()
            if hashlib.sha256(body).hexdigest() != expected:
                raise ValueError('SOURCE_HASH_MISMATCH:' + name)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        # The verified legacy engine pins two package bootstrap files outside
        # the 68-file journal map. Honor those pins; do not invent empty files.
        module = ast.parse((root / 'experiments/commerce006.py').read_text())
        pins = next(ast.literal_eval(n.value) for n in module.body
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PINS' for t in n.targets))
        bootstrap = 0
        for name, expected in pins.items():
            body = (args.source_checkout / name).read_bytes()
            if hashlib.sha256(body).hexdigest() != expected:
                raise ValueError('BOOTSTRAP_PIN_MISMATCH:' + name)
            target = root / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                bootstrap += 1
        for name in names:
            if name.startswith(PREFIX + 'source/'):
                target = root / name[len(PREFIX + 'source/'):]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
        sys.path.insert(0, str(root))
        from commercial.ledger import digest
        from growth067.audit import audit
        if digest(result) != package['result_sha256']:
            raise ValueError('RESULT_DIGEST_MISMATCH')
        checked = audit(root, manifest, result, exported)
        receipt = {'schema': 'agi-alpha/selected-public-replay/v1',
                   'archive_sha256': EXPECTED,
                   'source_files_matched': len(files),
                   'additional_engine_bootstrap_pins_matched': bootstrap,
                   'result_digest_matched': True,
                   'audit': checked,
                   'scope': 'PUBLIC_KEY_FREE_CONTROL_REPLAY_NOT_REAL_COMMERCE_OR_ACCOUNT_AUTHORITY'}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'accepted': checked['accepted'], 'source_files_matched': len(files),
                          'output': str(args.output)}))
