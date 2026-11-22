# SPDX-License-Identifier: Apache-2.0
"""Runs ONLY inside an isolated disposable container. No trusted timing here."""
import importlib.util
import json
import sys

if __name__ == '__main__':
    payload = json.loads(sys.stdin.read())
    spec = importlib.util.spec_from_file_location('solution', '/task/solution.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.solve(payload)
    sys.stdout.write(json.dumps(result, sort_keys=True, allow_nan=False, separators=(',', ':')))
