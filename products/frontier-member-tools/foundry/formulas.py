"""Convert bounded scalar formulas into the existing HARNESS data language."""

import ast
import re

from bridge.instruments import compile_formula


def bound_expansion(value):
    # Count occurrences, including repeated references. A DAG's expanded JSON
    # size can exceed its compact in-memory representation by many orders.
    pending = [(value, 0)]
    remaining = 1600
    while pending:
        node, depth = pending.pop()
        remaining -= 1
        if remaining < 0 or depth > 32:
            raise ValueError('Compiled formula exceeds the expansion bound')
        if isinstance(node, (dict, list)):
            children = node.values() if isinstance(node, dict) else node
            if len(children) > remaining:
                raise ValueError('Compiled formula exceeds the expansion bound')
            pending.extend((child, depth + 1) for child in children)
        elif isinstance(node, str) and len(node) > 240:
            raise ValueError('Compiled formula text exceeds the scalar bound')


def formula_candidate(task, response):
    if not isinstance(task, dict) or task.get('schema') != 'frontier/foundry-mission-v1':
        raise ValueError('Invalid mission')
    fields, outputs = task.get('inputs'), task.get('outputs')
    if not isinstance(fields, dict) or not isinstance(outputs, dict) or not (1 <= len(fields) <= 12 and 1 <= len(outputs) <= 12):
        raise ValueError('Invalid mission field set')
    raw = re.sub(r'^\x60{3}(?:python|text)?\n([\s\S]*?)\n\x60{3}$', r'\1', response.strip())
    if len(raw) > 13_000:
        raise ValueError('Formula response exceeds the declared bound')
    try:
        statements = ast.parse(raw, mode='exec').body
    except (SyntaxError, RecursionError) as error:
        raise ValueError('Invalid formula syntax') from error
    if len(statements) != len(outputs):
        raise ValueError('One formula per output required')
    compiled = {}
    for statement in statements:
        if (not isinstance(statement, ast.Assign) or len(statement.targets) != 1
                or not isinstance(statement.targets[0], ast.Name)):
            raise ValueError('Only named scalar assignments are supported')
        name = statement.targets[0].id
        if name not in outputs or name in compiled:
            raise ValueError('Invalid output assignment')
        # Inspect syntax only. compile_formula returns data, and no model-supplied bytecode is created.
        compiled[name] = compile_formula(ast.unparse(statement.value), {})
    artifact = {'name':'Compiled HARNESS formula','inputs':list(fields),'outputs':compiled}
    bound_expansion(artifact)
    return artifact
