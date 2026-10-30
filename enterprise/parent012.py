"""Read-only reconstruction of the preserved enterprise-011 funding account."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import sys
import zipfile
from commercial.ledger import audit, digest

PARENT_PACKAGE_SHA256 = '7e21fe606108d6625c0aa851f040638d09decf7a8f77ec9efe6fa82b6987cdb7'


def audit_parent_archive(archive, destination):
    archive, destination = Path(archive), Path(destination)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PARENT_PACKAGE_SHA256:
        raise ValueError('PRESERVED_PARENT_PACKAGE_CHANGED')
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        frozen = json.loads(bundle.read('FROZEN.json'))
        for relative, expected in frozen['source']['files'].items():
            if hashlib.sha256(bundle.read('source/' + relative)).hexdigest() != expected:
                raise ValueError('PARENT_FROZEN_SOURCE_CHANGED:' + relative)
        for item in bundle.infolist():
            if not item.filename.startswith('source/') or item.is_dir():
                continue
            relative = Path(item.filename)
            if relative.is_absolute() or '..' in relative.parts or item.file_size > 2_000_000:
                raise ValueError('PARENT_EXTRACTION_SCOPE')
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(item))
        manifest = json.loads(bundle.read('SERVICES.json'))
        world_path = 'worlds/2610301101-ordinary-utility-responsive-strategic_autonomous.json.gz'
        world_raw = bundle.read(world_path)
        world = json.loads(gzip.decompress(world_raw))
        frontier = json.loads(bundle.read('FRONTIER.json'))
    root = destination / 'source'
    audit_input = destination / 'audit-input.json'
    audit_input.write_text(json.dumps({'manifest': manifest, 'base': world['ledger'], 'continuation': frontier['supplemental_ledger']}))
    program = 'import json,sys; from pathlib import Path; from commercial.ledger import audit; d=json.loads(Path(sys.argv[1]).read_text()); print(json.dumps({k:audit(d[k],root=Path.cwd(),manifest=d["manifest"]) for k in ["base","continuation"]}))'
    result = subprocess.run([sys.executable, '-c', program, str(audit_input.absolute())], cwd=root, text=True, capture_output=True, check=True)
    proofs = json.loads(result.stdout)
    base, continuation = proofs['base'], proofs['continuation']
    if base['summary'] != frontier['before'] or continuation['summary'] != frontier['after']:
        raise ValueError('PARENT_FUNDING_SUMMARY_MISMATCH')
    prefix = frontier['supplemental_ledger']['actions'][:len(world['ledger']['actions'])]
    if prefix != world['ledger']['actions'] or digest(prefix) != frontier['commercial_trajectory_actions_sha256']:
        raise ValueError('PARENT_CONTINUATION_LINEAGE_CHANGED')
    return {'schema': 'agi-alpha/growth012-parent-funding-audit/v1',
            'package_sha256': PARENT_PACKAGE_SHA256,
            'source_sha256': frozen['source']['sha256'], 'world_path': world_path,
            'world_sha256': hashlib.sha256(world_raw).hexdigest(),
            'native_base_audit_accepted': base['accepted'],
            'native_continuation_audit_accepted': continuation['accepted'],
            'base_actions_sha256': base['actions_sha256'],
            'current_actions_sha256': continuation['actions_sha256'],
            'base': base['summary'], 'after_recorded_frontier_allocation': continuation['summary'],
            'current_unrestricted_earned_microUSD': continuation['summary']['unrestrictedEarned'],
            'current_profit_microUSD': continuation['summary']['profit'],
            'scope': 'Read-only independent reconstruction of preserved simulated account; no new funds or revenue, no live bank account.',
            'comparison_funding': 'Equal-capital counterfactual tournament worlds are separate alternatives; parent earnings are neither reset nor added to them. This read-only audit spends none of the parent funds.'}
