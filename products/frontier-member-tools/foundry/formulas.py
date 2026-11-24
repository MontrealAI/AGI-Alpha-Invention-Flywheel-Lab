"""Convert bounded scalar formulas into the existing HARNESS data language."""

import re

from bridge.instruments import compile_formula


def formula_candidate(task, response):
    if not isinstance(task, dict) or task.get('schema') != 'frontier/foundry-mission-v1':
        raise ValueError('Invalid mission')
    fields, outputs = task.get('inputs'), task.get('outputs')
    if not isinstance(fields, dict) or not isinstance(outputs, dict) or not (1 <= len(fields) <= 12 and 1 <= len(outputs) <= 12):
        raise ValueError('Invalid mission field set')
    raw = re.sub(r'^\x60{3}(?:python|text)?\n([\s\S]*?)\n\x60{3}$', r'\1', response.strip())
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) != len(outputs) or len(raw) > 13_000:
        raise ValueError('One formula per output required')
    compiled = {}
    for line in lines:
        part = re.fullmatch(r'([a-zA-Z][a-zA-Z0-9_]{0,31})\s*=\s*(.+)', line)
        if not part or part[1] not in outputs or part[1] in compiled:
            raise ValueError('Invalid output assignment')
        # compile_formula returns an expression tree. It never produces or executes bytecode.
        compiled[part[1]] = compile_formula(part[2], {})
    return {'name':'Compiled HARNESS formula','inputs':list(fields),'outputs':compiled}
