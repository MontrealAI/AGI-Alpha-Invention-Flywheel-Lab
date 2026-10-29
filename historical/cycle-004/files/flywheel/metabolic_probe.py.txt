"""Bounded reproduction of a published, non-seeded metabolic model defect."""
from __future__ import annotations
import argparse, hashlib, json, resource, time
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'campaign/cycle-004/metabolic_subnetwork.json'
SBML_SHA256 = '2eb450d8fa4307ec384782ffc03011473c4bf9ec8513c68e1341a66d0179895d'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def solve(reactions, diagnostic, species=None):
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
    all_reactions = [*reactions, diagnostic]
    species = species or sorted({s for r in all_reactions for s in r['stoichiometry']})
    index = {s: i for i, s in enumerate(species)}
    matrix = lil_matrix((len(species), len(all_reactions)))
    for j, reaction in enumerate(all_reactions):
        for s, value in reaction['stoichiometry'].items():
            matrix[index[s], j] = value
    objective = np.zeros(len(all_reactions)); objective[-1] = -1
    started = time.monotonic()
    result = linprog(objective, A_eq=matrix.tocsr(), b_eq=np.zeros(len(species)),
                     bounds=[r['bounds'] for r in all_reactions], method='highs')
    if not result.success:
        raise RuntimeError('LP_NOT_SOLVED: ' + result.message)
    residual = float(abs(matrix @ result.x).max())
    return {'diagnostic_flux': float(result.x[-1]), 'steady_state_max_residual': residual,
            'solver_status': result.message, 'solver_wall_seconds': time.monotonic()-started,
            'nonzero_fluxes': {r['id']: float(v) for r, v in zip(all_reactions, result.x) if abs(v)>1e-8},
            'species_count': len(species), 'source_reactions_count': len(reactions)}


def sbml_reactions(path):
    path = Path(path)
    if path.is_symlink() or digest(path) != SBML_SHA256:
        raise ValueError('ARCHIVE_IDENTITY_MISMATCH')
    root = ET.parse(path).getroot(); ns = {'s': 'http://www.sbml.org/sbml/level2'}
    reactions = []
    species = [s.get('id') for s in root.findall('.//s:species', ns)]
    for reaction in root.findall('.//s:reaction', ns):
        stoichiometry = {}
        for tag, sign in [('listOfReactants', -1), ('listOfProducts', 1)]:
            for s in reaction.findall('s:'+tag+'/s:speciesReference', ns):
                name = s.get('species')
                stoichiometry[name] = stoichiometry.get(name, 0)+sign*float(s.get('stoichiometry', '1'))
        params = {x.get('id'): float(x.get('value')) for x in reaction.findall('.//s:parameter', ns)}
        bounds = [params['LOWER_BOUND'], params['UPPER_BOUND']]
        if reaction.get('id').startswith('EX_'):
            bounds = [0, 0]
        reactions.append({'id': reaction.get('id'), 'stoichiometry': stoichiometry, 'bounds': bounds})
    return reactions, species


def probe(sbml=None):
    import scipy
    started, cpu = time.monotonic(), time.process_time()
    data = json.loads(DATA.read_text())
    reactions = data['reactions']; diagnostic = data['diagnostic_reaction']
    original = solve(reactions, diagnostic)
    repaired_reactions = json.loads(json.dumps(reactions))
    next(r for r in repaired_reactions if r['id']=='rxn10153')['bounds'][0] = 0
    repaired = solve(repaired_reactions, diagnostic)
    if original['diagnostic_flux'] <= 1e-7 or repaired['diagnostic_flux'] > 1e-7:
        raise AssertionError('PUBLISHED_SUBNETWORK_REPRODUCTION_FAILED')
    report = {'schema': 'metabolic-published-defect-probe/v1', 'source': data['source'],
              'subnetwork_input_sha256': digest(DATA), 'executing_source_sha256': digest(__file__),
              'scipy_version': scipy.__version__, 'defect_origin': 'Non-seeded, previously published; equations extracted from real archived SBML.',
              'subnetwork': {'original': original, 'published_direction_restriction': repaired,
                 'adjudication': 'ESTABLISHED_IN_SCOPE', 'constraint': 'No positive proton-dissipation flux when all modeled external inputs are absent.',
                 'repair_origin': 'Known published reaction direction restriction, not an invented repair.',
                 'interpretation': 'A flux-capacity diagnostic, not measured ATP production, growth, useful delivery, or physical validation.'},
              'baseline': {'method': 'Strong conventional FBA/LP diagnostic and published direction restriction; same source, bounds and solver.',
                 'candidate_advantage': 'NOT_ESTABLISHED',
                 'known_complete_alternative': 'Fritzemeier et al.2017 GlobalFit jointly removes all EGCs while retaining growth; MEMOTE provides established EGC detection.'},
              'full_model': {'status': 'NOT_RUN', 'reason': 'Pass the exact archived SBML with --sbml for full-model scope falsification.'},
              'verdicts': {'published_defect_reproduced': True, 'new_discovery_or_repair': False,
                 'consequential_new_capability': 'NOT_ESTABLISHED', 'commercial_success': 'NOT_ESTABLISHED'}}
    if sbml:
        full, species = sbml_reactions(sbml)
        atp = {'id': 'ATP_HYDROLYSIS_DIAGNOSTIC', 'stoichiometry': {'cpd00002_c': -1, 'cpd00001_c': -1,
               'cpd00008_c': 1, 'cpd00009_c': 1, 'cpd00067_c': 1}, 'bounds': [0, 10000]}
        full_original = solve(full, atp, species)
        next(r for r in full if r['id']=='rxn10153')['bounds'][0] = 0
        full_restricted = solve(full, atp, species)
        report['full_model'] = {'status': 'EXECUTED', 'archive_sha256': digest(sbml),
                'original': full_original, 'single_direction_restriction': full_restricted,
                'single_restriction_sufficient': full_restricted['diagnostic_flux'] <= 1e-7,
                'scope_counterexample': 'The Fig6A repair must not be promoted to a whole-model cure; other EGCs remain.',
                'closed_input_rule': 'All EX_ exchange reactions fixed to zero. All source species retained in steady-state equations.',
                'limits': 'No full GlobalFit repair, physiological growth preservation, concentration/thermodynamic model or experimental validation.'}
    report['resources'] = {'wall_seconds': time.monotonic()-started, 'cpu_seconds': time.process_time()-cpu,
                           'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           'model_calls': 0, 'complete_monetary_cost': None, 'unknown_costs': ['research','developer inference','integration','independent verification','maintenance']}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sbml', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = probe(args.sbml)
    with (args.output/'RESULT.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'output': str(args.output), 'published_defect_reproduced': True,
                     'full_model_single_restriction_sufficient': result['full_model'].get('single_restriction_sufficient')}))


if __name__ == '__main__':
    main()
