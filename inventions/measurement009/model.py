import ctypes as c
import hashlib
import json
from pathlib import Path
import time

UPSTREAM = '11eec7d5bf0a9367ffe04d75707918f0c0a890a1'
INPUTS = Path(__file__).parent / 'inputs'
EXPECTED_BLOBS = {'Net1.inp': 'fb114141f6fda79f7a827835c06af1a5eadf686d', 'Net3.inp': '1bfc21bc17d22c265727833885e1232e06012752', 'libepanet22.so': 'd0da2ba2e3ec07e98b502644cc00cfe3ada056be'}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def simulate(network, output, horizon_seconds=86400, sample_seconds=3600, model_path=None, expected_blob=None):
    if network not in {'Net1', 'Net3'} and model_path is None:
        raise ValueError('UNREGISTERED_NETWORK; a verifier-supplied fresh model needs explicit model_path and expected_blob')
    if type(horizon_seconds) is not int or type(sample_seconds) is not int or not (0 < sample_seconds <= horizon_seconds <= 7 * 86400):
        raise ValueError('INVALID_HORIZON')
    model = Path(model_path) if model_path is not None else INPUTS / (network + '.inp')
    library = INPUTS / 'libepanet22.so'
    for path, expected in [(model, expected_blob or EXPECTED_BLOBS.get(model.name)), (library, EXPECTED_BLOBS['libepanet22.so'])]:
        raw = path.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\x00' + raw).hexdigest()
        if expected is None or actual != expected:
            raise ValueError('UPSTREAM_BLOB_MISMATCH:' + path.name)
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    lib = c.CDLL(str(library.resolve()))
    project = c.c_uint64()
    warnings = []
    code = lib.EN_createproject(c.byref(project))
    if code:
        raise RuntimeError(('createproject', code))
    opened = False
    def call(name, *args):
        code = getattr(lib, 'EN_' + name)(project, *args)
        if code >= 100:
            raise RuntimeError((name, code))
        if code:
            warnings.append({'function': name, 'code': code})
    start, own = time.monotonic(), time.process_time()
    try:
        call('open', str(model.resolve()).encode(), str((out / 'epanet.rpt').resolve()).encode(), str((out / 'epanet.bin').resolve()).encode()); opened = True
        n = c.c_int(); call('getcount', 0, c.byref(n))
        native_duration = c.c_long(); call('gettimeparam', 0, c.byref(native_duration))
        call('settimeparam', 0, c.c_long(horizon_seconds))
        call('settimeparam', 5, c.c_long(sample_seconds))
        names, indices = [], []
        for i in range(1, n.value + 1):
            kind = c.c_int(); call('getnodetype', i, c.byref(kind))
            if kind.value:
                continue
            buf = c.create_string_buffer(64); call('getnodeid', i, buf)
            names.append(buf.value.decode()); indices.append(i)
        call('solveH')
        values, expected_times = [], list(range(0, horizon_seconds, sample_seconds))
        for name in names:
            call('setqualtype', 3, b'', b'', name.encode())
            call('openQ'); call('initQ', 0)
            rows, times = [], []
            while True:
                t = c.c_long(); call('runQ', c.byref(t))
                if t.value % sample_seconds == 0 and t.value < horizon_seconds:
                    row = []
                    for i in indices:
                        v = c.c_double(); call('getnodevalue', i, 12, c.byref(v)); row.append(v.value)
                    rows.append(row); times.append(t.value)
                dt = c.c_long(); call('nextQ', c.byref(dt))
                if not dt.value:
                    break
            call('closeQ')
            if times != expected_times:
                raise RuntimeError('INCOMPLETE_OR_DUPLICATED_SAMPLING_GRID')
            values.append(rows)
        result = {'schema': 'agi-alpha/measurement-corpus009/v1', 'network': network,
            'numeric_semantics': 'canonical-json-finite-binary64-decimal-rational-v1',
            'numeric_semantics_definition': 'Finite parsed binary64 values are canonically serialized by Python json.dumps; each resulting numeric decimal is interpreted as Fraction(str(value)), not Fraction.from_float and not an arbitrary original JSON lexeme.',
            'nodes': names, 'sources': names, 'times_seconds': expected_times, 'signal': values,
            'units': 'source_contribution_percentage_points', 'network_sha256': file_sha(model),
            'simulator_sha256': file_sha(library), 'upstream_commit': UPSTREAM,
            'model_configuration': {'quality': 'TRACE', 'native_duration_seconds': native_duration.value,
                'authored_horizon_seconds': horizon_seconds, 'sampling_seconds': sample_seconds,
                'restriction': 'First declared horizon of the supplied model, not a field-calibrated contamination event.'},
            'scope': 'DEVELOPMENT simulation; no field measurements, physical calibration, customer obligation, or external certification.'}
        (out / 'corpus.json').write_bytes(canonical(result) + b'\n')
        receipt = {'corpus_sha256': digest(result), 'wall_seconds': time.monotonic() - start,
            'process_cpu_seconds': time.process_time() - own, 'warnings': warnings,
            'source_cases': len(names), 'times': len(expected_times), 'sensors': len(names),
            'complete_monetary_cost': None}
        (out / 'simulation_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if warnings:
            raise RuntimeError('EPANET_WARNINGS_REQUIRE_ADJUDICATION')
        return result
    finally:
        if opened:
            lib.EN_close(project)
        lib.EN_deleteproject(project)
