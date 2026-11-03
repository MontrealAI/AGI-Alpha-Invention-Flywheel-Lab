from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from commercial.ledger import canonical
from .service import PREFIX, APPROVAL

FUNCTIONS = {
    'purpose': ('Finite robust reach/recovery controller certificate', 'Safe active fault diagnosis preserving recovery'),
    'interface': ('Reference-normalized material areal-density inference', 'Spatial material/void reconstruction'),
    'complementarity': ('Heat-pump/storage process-heat design', 'Hypersaline-feed water-recovery feasibility design'),
    'arrangement': ('Voluntary risk-bounded maneuver study', 'Two-impulse servicing endpoint study'),
    'foundry': ('Finite-envelope near-infrared antireflection design', 'Distinct two-band spectral-routing designs')}
ARTIFACTS = {
    'purpose': (['results/K1_00.json', 'kernel.py', 'specialist.py'], ['results/K2_00.json', 'results/K2_POLICY_TRACES.json', 'kernel.py', 'diagnosis.py', 'specialist.py']),
    'interface': (['results/K1_ARTIFACT.json', 'instrument.py'], ['results/K2_ARTIFACT.json', 'instrument.py']),
    'complementarity': (['evidence/RESULTS.json', 'thermal.py', 'fresh.py'], ['evidence/RESULTS.json', 'thermal.py', 'fresh.py']),
    'arrangement': (['evidence-confirmation-01/RESULTS.json', 'orbital.py'], ['evidence-confirmation-01/RESULTS.json', 'orbital.py']),
    'foundry': (['results/RESULTS.json', 'results/retained_K1_manifest.json', 'optics.py', 'run.py', 'silica.yml', 'magnesium_fluoride.yml', 'tantalum_pentoxide.yml'],
                ['results/RESULTS.json', 'results/retained_K1_manifest.json', 'optics.py', 'run.py', 'silica.yml', 'magnesium_fluoride.yml', 'tantalum_pentoxide.yml'])}

def _save(path, value):
    data = canonical(value) + b'\n'
    if path.exists() and path.read_bytes() != data:
        raise ValueError('REGISTERED_PRODUCT_BYTES_CANNOT_BE_OVERWRITTEN:' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def build(root):
    root = Path(root).resolve()
    products = []
    for route in FUNCTIONS:
        folder = root / PREFIX / route
        for index, stage in enumerate(('k1', 'k2')):
            names = ['PREREGISTRATION.json'] + ARTIFACTS[route][index]
            product = {'schema': 'public-portfolio/computational-package/v1', 'id': route + '-' + stage,
                'route': route, 'stage': stage, 'scope': 'COMPUTATIONAL_CONTRACT_ONLY',
                'function': FUNCTIONS[route][index],
                'unit': 'Access to these already constructed nonexclusive bytes plus separately costed checking/support; not a fresh physical or scientific delivery per sale.',
                'rights': 'No blanket commercial license inferred from public visibility. Commercial use and third-party rights must be separately cleared; scenario rights clearance is hypothetical.',
                'physical_qualification': False, 'actual_commerce': False,
                'artifacts': [{'path': (Path(PREFIX) / route / name).as_posix(),
                    'sha256': hashlib.sha256((folder / name).read_bytes()).hexdigest()} for name in names]}
            path = folder / 'products' / (stage + '.json')
            _save(path, product)
            products.append({'id': product['id'], 'route': route, 'stage': stage,
                'product_path': path.relative_to(root).as_posix(), 'product_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return products

def approved_records(root):
    root = Path(root).resolve()
    approval_path = root / APPROVAL
    data = json.loads(approval_path.read_text())
    approval_hash = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    result = []
    for row in data['products']:
        if row['accepted']:
            result.append({key: row[key] for key in ('id', 'route', 'stage', 'product_path', 'product_sha256')}
                | {'approval_path': APPROVAL, 'approval_sha256': approval_hash})
    _save(root / PREFIX / 'PRODUCTS.json', result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'approved'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(build(args.root) if args.command == 'build' else approved_records(args.root), indent=2))

if __name__ == '__main__': main()
