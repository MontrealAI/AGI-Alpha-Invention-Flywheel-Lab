"""Trusted AST-to-SMT checker; never imports or executes submitted Python."""
import ast
import hashlib
import json
from pathlib import Path
import z3

MAX_BYTES = 65536
MAX_NODES = 512

class Rejected(ValueError):
    pass


def load_json(path):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise Rejected('duplicate JSON key: ' + k)
            out[k] = v
        return out
    data = Path(path).read_bytes()
    if len(data) > MAX_BYTES:
        raise Rejected('input too large')
    return json.loads(data, object_pairs_hook=unique)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def integer(x):
    if type(x) is not int or abs(x) > 2**128:
        raise Rejected('expected bounded integer literal')
    return x


def contract_check(c):
    if set(c) != {'schema', 'function', 'inputs', 'expected', 'output_range'} or c['schema'] != 1:
        raise Rejected('unsupported contract schema')
    if not isinstance(c['function'], str) or not c['function'].isidentifier():
        raise Rejected('invalid function name')
    if not isinstance(c['inputs'], dict) or not 1 <= len(c['inputs']) <= 16:
        raise Rejected('one to sixteen input ranges required')
    for name, bounds in c['inputs'].items():
        if not isinstance(name, str) or not name.isidentifier() or name.startswith('_'):
            raise Rejected('invalid input name')
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise Rejected('invalid range')
        if integer(bounds[0]) > integer(bounds[1]):
            raise Rejected('empty range')
    bounds = c['output_range']
    if not isinstance(bounds, list) or len(bounds) != 2 or integer(bounds[0]) > integer(bounds[1]):
        raise Rejected('invalid output range')
    if not isinstance(c['expected'], str):
        raise Rejected('expected expression required')


def tree(text, mode):
    if len(text.encode()) > MAX_BYTES:
        raise Rejected('input too large')
    try:
        t = ast.parse(text, mode=mode)
    except (SyntaxError, RecursionError) as e:
        raise Rejected('invalid syntax') from e
    if len(list(ast.walk(t))) > MAX_NODES:
        raise Rejected('expression too complex')
    return t


def expression(n, env):
    def numeric(x):
        if not z3.is_int(x):
            raise Rejected('integer expression required')
        return x
    def boolean(x):
        if not z3.is_bool(x):
            raise Rejected('boolean expression required')
        return x
    if isinstance(n, ast.Constant) and type(n.value) is int:
        return z3.IntVal(integer(n.value))
    if isinstance(n, ast.Name) and n.id in env:
        return env[n.id]
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        x = numeric(expression(n.operand, env))
        return -x if isinstance(n.op, ast.USub) else x
    if isinstance(n, ast.BinOp):
        a, b = numeric(expression(n.left, env)), numeric(expression(n.right, env))
        if isinstance(n.op, ast.Add): return a + b
        if isinstance(n.op, ast.Sub): return a - b
        if isinstance(n.op, ast.Mult): return a * b
        if isinstance(n.op, (ast.FloorDiv, ast.Mod)):
            # Positive constant divisor makes SMT integer div equal Python floor division.
            if not isinstance(n.right, ast.Constant) or type(n.right.value) is not int or n.right.value <= 0:
                raise Rejected('division/modulus requires positive integer literal')
            return a / b if isinstance(n.op, ast.FloorDiv) else a % b
    if isinstance(n, ast.IfExp):
        return z3.If(boolean(expression(n.test, env)), numeric(expression(n.body, env)), numeric(expression(n.orelse, env)))
    if isinstance(n, ast.BoolOp):
        args = [boolean(expression(v, env)) for v in n.values]
        if isinstance(n.op, ast.And): return z3.And(*args)
        if isinstance(n.op, ast.Or): return z3.Or(*args)
    if isinstance(n, ast.Compare):
        values = [numeric(expression(n.left, env))] + [numeric(expression(v, env)) for v in n.comparators]
        out = []
        for a, op, b in zip(values, n.ops, values[1:]):
            if isinstance(op, ast.Lt): out.append(a < b)
            elif isinstance(op, ast.LtE): out.append(a <= b)
            elif isinstance(op, ast.Gt): out.append(a > b)
            elif isinstance(op, ast.GtE): out.append(a >= b)
            elif isinstance(op, ast.Eq): out.append(a == b)
            elif isinstance(op, ast.NotEq): out.append(a != b)
            else: raise Rejected('unsupported comparison')
        return z3.And(*out)
    raise Rejected('unsupported syntax: ' + type(n).__name__)


def source_expression(source, c, env):
    t = tree(source, 'exec')
    if len(t.body) != 1 or not isinstance(t.body[0], ast.FunctionDef):
        raise Rejected('exactly one function required')
    f = t.body[0]
    a = f.args
    if (f.name != c['function'] or f.decorator_list or f.returns or f.type_comment or f.type_params
        or a.posonlyargs or a.kwonlyargs or a.defaults or a.kw_defaults or a.vararg or a.kwarg
        or [x.arg for x in a.args] != list(c['inputs']) or any(x.annotation for x in a.args)
        or len(f.body) != 1 or not isinstance(f.body[0], ast.Return)):
        raise Rejected('function must have contract arguments and one return, no annotations/defaults/decorators')
    out = expression(f.body[0].value, env)
    if not z3.is_int(out): raise Rejected('return must be integer')
    return out


def check(source, c, timeout_ms=30000):
    contract_check(c)
    if type(timeout_ms) is not int or timeout_ms <= 0:
        raise Rejected('positive solver timeout required')
    env = {k: z3.Int(k) for k in c['inputs']}
    actual = source_expression(source, c, env)
    expected = expression(tree(c['expected'], 'eval').body, env)
    if not z3.is_int(expected): raise Rejected('expected must be integer')
    s = z3.Solver()
    s.set(timeout=timeout_ms)
    for name, (lo, hi) in c['inputs'].items(): s.add(env[name] >= lo, env[name] <= hi)
    s.add(z3.Or(actual != expected, actual < c['output_range'][0], actual > c['output_range'][1]))
    obligation = s.to_smt2()
    verdict = s.check()
    result = {'schema':1, 'status': 'PROVED_SCOPED' if verdict == z3.unsat else 'COUNTEREXAMPLE' if verdict == z3.sat else 'UNKNOWN',
              'source_sha256':digest(source), 'contract_sha256':digest(json.dumps(c, sort_keys=True, separators=(',', ':'))),
              'solver':z3.get_version_string(), 'semantics':'Python mathematical integers; finite declared domain',
              'scope':'equivalence to supplied expression AND declared output bounds; no whole-system security claim',
              'counterexample':None, 'unknown_reason':None}
    if verdict == z3.sat:
        m = s.model()
        result['counterexample'] = {'inputs':{k:m.eval(v, model_completion=True).as_long() for k,v in env.items()},
                                   'actual':m.eval(actual, model_completion=True).as_long(), 'expected':m.eval(expected, model_completion=True).as_long()}
    elif verdict == z3.unknown: result['unknown_reason'] = s.reason_unknown()
    return result, obligation


def bundle(source, c, out, timeout_ms=30000):
    result, obligation = check(source, c, timeout_ms)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'candidate.py').write_text(source)
    (out/'contract.json').write_text(json.dumps(c, indent=2)+'\n')
    (out/'obligation.smt2').write_text(obligation)
    (out/'verdict.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def verify(path, timeout_ms=30000):
    path = Path(path)
    names = {'candidate.py','contract.json','obligation.smt2','verdict.json'}
    if {x.name for x in path.iterdir()} != names or any((path/n).is_symlink() for n in names):
        raise Rejected('unexpected or symlinked bundle contents')
    source = (path/'candidate.py').read_text()
    c = load_json(path/'contract.json')
    prior = load_json(path/'verdict.json')
    current, obligation = check(source, c, timeout_ms)
    # Recompute semantics, rather than trusting a saved PASS or unsigned checksum.
    for key in ['schema','status','source_sha256','contract_sha256','semantics','scope']:
        if prior.get(key) != current[key]: raise Rejected('saved verdict mismatch: '+key)
    if (path/'obligation.smt2').read_text() != obligation:
        raise Rejected('obligation differs from reconstructed source and contract')
    return current
