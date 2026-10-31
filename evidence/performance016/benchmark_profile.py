import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import sys
import time

repo, output = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(repo)); output.mkdir(parents=True, exist_ok=True)
from tests.test_connected_verify import ConnectedEndToEndVerification as Fixture
from commercial.ledger import canonical
profiling = len(sys.argv) > 3 and sys.argv[3] == '--profile'
profile = cProfile.Profile(); started = time.process_time(); wall = time.monotonic()
try:
    if profiling: profile.enable()
    Fixture.setUpClass(); profile.disable()
    result = Fixture.result
    (output / 'RESULT.json').write_bytes(canonical(result) + b'\n')
    if profiling:
        profile.dump_stats(str(output / 'PROFILE.pstats'))
        with (output / 'PROFILE.txt').open('w') as stream:
            pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumtime').print_stats(45)
    receipt = {'fixture': 'existing tests.test_connected_verify.ConnectedEndToEndVerification.setUpClass; cohort/seed14003 baseline12days; exposed engineering only',
               'process_cpu_seconds': time.process_time() - started, 'wall_seconds': time.monotonic() - wall, 'cProfile_enabled': profiling,
               'finance_sha256': hashlib.sha256((repo / 'connected_enterprise/finance.py').read_bytes()).hexdigest(),
               'paid_jobs': result['paid_jobs'], 'accepted_jobs': result['accepted_jobs'], 'native_actions': len(result['owned_account']['ledger']['actions']), 'summary': result['summary']}
    (output / 'RECEIPT.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n'); print(json.dumps(receipt))
finally:
    profile.disable()
    if hasattr(Fixture, 'temporary'): Fixture.tearDownClass()
