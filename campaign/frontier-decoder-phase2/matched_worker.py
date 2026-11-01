"""One bounded matched decoder call. Input contains syndrome only, never truth."""
import time
process_start = time.perf_counter()
import os, sys, json, argparse, resource
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
if hasattr(os, 'sched_getaffinity'):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--variant', choices=['A', 'B', 'C', 'anchor'], required=True)
p.add_argument('--extension-dir', required=True)
p.add_argument('--helper-dir', required=True)
p.add_argument('--deps', required=True)
p.add_argument('--circuit', required=True)
a = p.parse_args()
try:
    request = json.load(sys.stdin)
    if set(request) != {'detectors'}:
        raise ValueError('Worker accepts detector indices only')
    extension_dir = Path(a.extension_dir).resolve()
    possible = list(extension_dir.glob('tesseract_decoder*.so'))
    if not possible:
        raise FileNotFoundError(f'No compiled Tesseract extension in {extension_dir}')
    sys.path[:0] = [str(extension_dir), str(Path(a.helper_dir).resolve()),
                    str(Path(a.deps).resolve())]
    import_start = time.perf_counter()
    import numpy as np
    import stim
    import tesseract_decoder as td
    extension_file = Path(td.__file__).resolve()
    if extension_file not in {f.resolve() for f in possible}:
        raise RuntimeError(f'Wrong extension imported: {extension_file}')
    from diagnostic_common import Fallback, mask, select
    import_seconds = time.perf_counter() - import_start
    prep_start = time.perf_counter()
    circuit = stim.Circuit.from_file(a.circuit)
    original_dem = circuit.detector_error_model(decompose_errors=False)
    normalized = td.tesseract.TesseractConfig(original_dem).compile_decoder().config.dem
    kwargs = {} if a.variant == 'anchor' else dict(
        det_beam=5, pqlimit=200000, no_revisit_dets=a.variant == 'A',
        merge_errors=False, beam_climbing=False)
    decoder = td.tesseract.TesseractConfig(normalized, **kwargs).compile_decoder()
    # Normalized DEM IDs and retained IDs must coincide for the checks below.
    h = [mask(e.symptom.detectors) for e in decoder.errors]
    logicals = [mask(e.symptom.observables) for e in decoder.errors]
    fallback = Fallback(original_dem)
    s = np.zeros(circuit.num_detectors, dtype=bool)
    for index in request['detectors']:
        if not isinstance(index, int) or not 0 <= index < circuit.num_detectors:
            raise ValueError('Invalid detector index')
        s[index] = not s[index]
    target = mask(s.nonzero()[0])
    prep_seconds = time.perf_counter() - prep_start
    decode_start = time.perf_counter(); work = None; candidates = []; invalid = 0
    if a.variant == 'C':
        result = decoder.decode_to_error_candidates(s, 0, 5, 64)
        raw = [(list(c.errors), float(c.cost), mask(c.observables)) for c in result.candidates]
        work = {name: getattr(result, name) for name in [
            'pushed', 'popped', 'expanded', 'max_queue', 'max_arena', 'raw_goals',
            'duplicate_goals', 'stop_reason', 'truncated', 'first_goal_seconds',
            'elapsed_seconds']}
    else:
        ids = list(decoder.decode_to_errors(s) if a.variant == 'anchor'
                   else decoder.decode_to_errors(s, 0, 5))
        raw = [(ids, float(decoder.cost_from_errors(ids)),
                mask(i for i, value in enumerate(decoder.get_observables_from_errors(ids)) if value))]
    decode_seconds = time.perf_counter() - decode_start
    validation_start = time.perf_counter(); seen = set()
    for ids, cost, reported_logical in raw:
        key = tuple(sorted(i for i in set(ids) if ids.count(i) % 2))
        if any(not 0 <= i < len(h) for i in key):
            raise AssertionError('Returned original IDs do not match normalized retained IDs')
        got = logical = 0
        for i in key: got ^= h[i]; logical ^= logicals[i]
        if got != target:
            invalid += 1
            if a.variant == 'C': raise AssertionError('List returned syndrome-invalid goal')
            continue
        checked_cost = float(decoder.cost_from_errors(list(key)))
        if not np.isclose(cost, checked_cost, rtol=1e-12, atol=1e-12) or logical != reported_logical:
            raise AssertionError('Candidate logical/cost contract failed')
        if key in seen:
            if a.variant == 'C': raise AssertionError('List exposed duplicate physical configuration')
            continue
        seen.add(key)
        candidates.append({'errors': list(key), 'logical': logical, 'cost': checked_cost,
                           'error_namespace': 'normalized_dem_original_ids'})
    used_fallback = not candidates
    if used_fallback: candidates = [fallback.solve(target)]
    minimum, mass, weights = select(candidates)
    first_goal_cost = candidates[0]['cost'] if not used_fallback else None
    final_min_cost = min(c['cost'] for c in candidates) if not used_fallback else None
    first_goal_seconds = (work['first_goal_seconds'] if work is not None else
                          (decode_seconds if not used_fallback and a.variant != 'anchor' else None))
    reduction_seconds = time.perf_counter() - validation_start
    answer = {'status': 'complete', 'variant': a.variant, 'extension_file': str(extension_file),
              'stim_version': stim.__version__, 'import_seconds': import_seconds,
              'prep_seconds': prep_seconds, 'decode_seconds': decode_seconds,
              'validation_fallback_reduction_seconds': reduction_seconds,
              'worker_seconds': time.perf_counter()-process_start,
              'maxrss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'low_confidence': bool(decoder.low_confidence_flag),
              'invalid_candidates': invalid, 'fallback': used_fallback,
              'first_goal_cost': first_goal_cost, 'final_min_cost': final_min_cost,
              'first_goal_seconds': first_goal_seconds, 'final_collection_seconds': decode_seconds,
              'cost_improvement_after_first': (first_goal_cost-final_min_cost) if first_goal_cost is not None else None,
              'minimum_prediction': minimum, 'mass_prediction': mass,
              'classes': len(weights), 'candidate_count': len(candidates),
              'candidates': candidates, 'work': work,
              'actual_config': {'orders': len(decoder.config.det_orders),
                                'pqlimit': decoder.config.pqlimit,
                                'beam': decoder.config.det_beam,
                                'beam_climbing': decoder.config.beam_climbing,
                                'no_revisit_dets': decoder.config.no_revisit_dets},
              'baseline_work_counters': 'unknown' if work is None else 'instrumented'}
    print(json.dumps(answer), flush=True)
except Exception as exc:
    print(json.dumps({'status': 'error', 'error': type(exc).__name__ + ': ' + str(exc),
                      'worker_seconds': time.perf_counter()-process_start}), flush=True)
    sys.exit(2)
