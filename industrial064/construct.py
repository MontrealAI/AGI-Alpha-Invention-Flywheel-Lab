"""Run the retained conventional network constructor only after caller funding."""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

TIMEOUT_SECONDS = 155

def _stream_commitment(value):
    raw = value if isinstance(value, bytes) else (value or '').encode('utf-8', errors='replace')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

class ProducerFailure(RuntimeError):
    def __init__(self, kind, **details):
        self.diagnostics = {'kind': kind, **details}
        super().__init__(json.dumps(self.diagnostics, sort_keys=True, separators=(',', ':')))

def construct(root, request, output):
    root = Path(root); output = Path(output)
    if output.exists(): raise ValueError('FRESH_OUTPUT_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='industrial064-request-') as td:
        folder = Path(td); shutil.copyfile(root/request['input_path'], folder/'01.json')
        code = 'from industrial062.construct import construct; from pathlib import Path; construct(Path(__import__("sys").argv[1]),Path(__import__("sys").argv[2]),120,0.10)'
        try:
            proc = subprocess.run([sys.executable, '-c', code, str(folder), str(output)], cwd=root, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise ProducerFailure('PRODUCER_TIMEOUT', timeout_seconds=TIMEOUT_SECONDS,
                                  stdout=_stream_commitment(exc.stdout), stderr=_stream_commitment(exc.stderr),
                                  output_created=output.exists()) from None
        if proc.returncode:
            raise ProducerFailure('PRODUCER_NONZERO_EXIT', returncode=proc.returncode,
                                  signal=-proc.returncode if proc.returncode < 0 else None,
                                  stdout=_stream_commitment(proc.stdout), stderr=_stream_commitment(proc.stderr),
                                  output_created=output.exists())
    if not (output/'production.json').is_file():
        raise ProducerFailure('PRODUCER_RECEIPT_MISSING', returncode=0, output_created=output.exists())
    receipt = json.loads((output/'production.json').read_text())
    if not (output/'solution.json').exists(): raise ValueError('NO_ACCEPTABLE_PLAN:' + receipt['status'])
    return json.loads((output/'solution.json').read_text()), receipt
