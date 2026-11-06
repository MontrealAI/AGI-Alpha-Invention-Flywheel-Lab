"""Read-only preflight of P0 source registries; never import or open an Account."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

REGISTRIES = ('SOURCE_PATHS', 'PRODUCTION_SOURCE_PATHS', 'INVENTORY_SOURCE_PATHS')


def checked_path(root, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('P0_INVALID_SOURCE_PATH')
    parsed = PurePosixPath(name)
    if parsed.is_absolute() or '..' in parsed.parts or parsed.as_posix() != name:
        raise ValueError('P0_INVALID_SOURCE_PATH')
    path = root.joinpath(*parsed.parts)
    if any(p.is_symlink() for p in (root, path, *path.parents)):
        raise ValueError('P0_SYMLINK_SOURCE_REFUSED')
    if not path.is_file():
        raise ValueError('P0_MISSING_SOURCE:' + name)
    return path


def sha256(root, name):
    return hashlib.sha256(checked_path(root, name).read_bytes()).hexdigest()


# Deliberately narrow static grammar. The preflight does not execute finance.py;
# accepting a referenced name in a dead operand is not a live service route.
_SCHEMA_SELECTOR = ast.parse(
    "manifest.get('schema') if isinstance(manifest, dict) else None",
    mode='eval').body
_SOURCE_ROOT = ast.parse("Path(__file__).resolve().parents[1]", mode='eval').body


def _same_ast(node, reference):
    return ast.dump(node, include_attributes=False) == ast.dump(reference, include_attributes=False)


def _named(node, name):
    return isinstance(node, ast.Name) and node.id == name


def _call(node, name, count):
    return (isinstance(node, ast.Call) and _named(node.func, name)
            and len(node.args) == count and not node.keywords)


def _active_service_closure(value):
    """Accept only a live, direct source union, optionally deduplicated.

    This checks structural dispatch, not imported producer semantics or all
    transitive dependencies. Unsupported expressions fail closed.
    """
    if (_call(value, 'tuple', 1) and _call(value.args[0], 'fromkeys', 1)):
        return False  # fromkeys must be qualified by dict, never a bare alias.
    if _call(value, 'tuple', 1):
        inner = value.args[0]
        if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                and _named(inner.func.value, 'dict') and inner.func.attr == 'fromkeys'
                and len(inner.args) == 1 and not inner.keywords):
            value = inner.args[0]
    if not (isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add)
            and _named(value.left, 'SOURCE_PATHS')):
        return False
    right = value.right
    if _named(right, 'PRODUCTION_SOURCE_PATHS') or _named(right, 'INVENTORY_SOURCE_PATHS'):
        return True
    if not _call(right, 'tuple', 1):
        return False
    producer = right.args[0]
    if not _call(producer, 'source_paths', 1):
        return False
    root = producer.args[0]
    return (isinstance(root, ast.Constant) and root.value is None) or _same_ast(root, _SOURCE_ROOT)


def load_registry(root):
    source = checked_path(root, 'connected_enterprise/finance.py').read_text(encoding='utf-8')
    program = ast.parse(source)
    found = {}
    for node in program.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in REGISTRIES:
                    if target.id in found:
                        raise ValueError('P0_DUPLICATE_REGISTRY:' + target.id)
                    try:
                        value = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError, RecursionError) as exc:
                        raise ValueError('P0_NONLITERAL_REGISTRY:' + target.id) from exc
                    if not isinstance(value, (tuple, list)) or not all(isinstance(x, str) for x in value) or len(set(value)) != len(value):
                        raise ValueError('P0_INVALID_REGISTRY:' + target.id)
                    for name in value:
                        checked_path(root, name)
                    found[target.id] = tuple(value)
    # A literal first assignment is not authoritative if later Python binds the
    # same registry name. Refuse unsupported writes rather than certify a stale
    # lexical inventory as the effective source dependency closure.
    bindings = {name: [] for name in REGISTRIES}
    for node in ast.walk(program):
        if isinstance(node, ast.Name) and node.id in bindings and isinstance(node.ctx, (ast.Store, ast.Del)):
            bindings[node.id].append(node)
    for name, nodes in bindings.items():
        if len(nodes) != (1 if name in found else 0):
            raise ValueError('P0_REGISTRY_REBIND_OR_DYNAMIC_WRITE:' + name)
    if 'SOURCE_PATHS' not in found:
        raise ValueError('P0_BASE_FINANCIAL_REGISTRY_MISSING')
    # Static guard only: name a dispatched manifest version through an actual
    # conditional branch retaining producer closure; inert or base-only routes fail.
    functions = [n for n in program.body if isinstance(n, ast.FunctionDef)
                 and n.name == 'source_paths_for_manifest']
    if len(functions) > 1:
        raise ValueError('P0_DUPLICATE_MANIFEST_DISPATCH')
    routes = set()
    if functions:
        fn = functions[0]
        args = fn.args
        # A replaced/decorated dispatcher or an arbitrary earlier assignment
        # cannot certify the active function. Accept only the observed direct
        # manifest argument and a manifest-derived first selector statement.
        direct_parameter = (not fn.decorator_list and not args.posonlyargs
                            and len(args.args) == 1 and args.args[0].arg == 'manifest'
                            and not args.vararg and not args.kwarg and not args.kwonlyargs)
        rebound = any(isinstance(n, ast.Name) and n.id == 'source_paths_for_manifest'
                      and isinstance(n.ctx, (ast.Store, ast.Del))
                      for n in ast.walk(program))
        if not direct_parameter or rebound:
            return found, routes
        # Only direct, reachable branches in the outer dispatcher can qualify.
        # Nested functions, arbitrary statements and reassignments of producer
        # symbols before dispatch fail closed, instead of asserting semantics.
        seen = set()
        schema_bound = False
        for node in fn.body:
            if isinstance(node, ast.Return):
                break
            if isinstance(node, ast.Assign):
                if (schema_bound or len(node.targets) != 1
                        or not _named(node.targets[0], 'schema')
                        or not _same_ast(node.value, _SCHEMA_SELECTOR)):
                    break
                schema_bound = True
                continue
            if not isinstance(node, ast.If):
                break  # Unknown control flow or shadowing: no later route counts.
            if not schema_bound or node.orelse:
                break
            comparison = node.test
            if (not isinstance(comparison, ast.Compare) or len(comparison.ops) != 1
                    or not isinstance(comparison.ops[0], ast.Eq)
                    or len(comparison.comparators) != 1):
                break
            left, right = comparison.left, comparison.comparators[0]
            if isinstance(left, ast.Name) and left.id == 'schema':
                literal = right
            elif isinstance(right, ast.Name) and right.id == 'schema':
                literal = left
            else:
                break
            if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)
                    and re.fullmatch(r'[A-Za-z0-9_-]+/native-services/v[1-9][0-9]*', literal.value)):
                break
            route = literal.value
            if route in seen:
                continue  # First matching branch wins, including a base-only one.
            seen.add(route)
            first_return = None
            valid_body = True
            for statement in node.body:
                if isinstance(statement, ast.Return):
                    first_return = statement.value
                    break
                if not isinstance(statement, (ast.Import, ast.ImportFrom, ast.Pass)):
                    valid_body = False
                    break
            if not valid_body or first_return is None:
                continue
            if _active_service_closure(first_return):
                routes.add(route)
    return found, routes


def inspect(main_root, transition_root, composed_root):
    main_root, transition_root, composed_root = (Path(p).absolute() for p in (main_root, transition_root, composed_root))
    main, main_routes = load_registry(main_root)
    prior, prior_routes = load_registry(transition_root)
    target, target_routes = load_registry(composed_root)
    must_keep = set(main['SOURCE_PATHS']) | set(prior['SOURCE_PATHS'])
    current = set(target['SOURCE_PATHS'])
    missing_finance = sorted(must_keep - current)
    missing_optional = {name: sorted(set(main.get(name, ())) - set(target.get(name, ()))) for name in REGISTRIES[1:]}
    missing_routes = sorted(main_routes - target_routes)
    common = sorted(set(main['SOURCE_PATHS']) & set(prior['SOURCE_PATHS']))
    changed = []
    for path in common:
        a, b = sha256(main_root, path), sha256(transition_root, path)
        if a != b:
            changed.append({'path': path, 'main_sha256': a, 'transition_sha256': b,
                            'composed_sha256': sha256(composed_root, path) if path in current else None})
    target_hashes = {name: sha256(composed_root, name) for name in target['SOURCE_PATHS']}
    complete = not missing_finance and not any(missing_optional.values()) and not missing_routes
    return {'schema': 'agi-alpha/p0-source-registry-join-preflight/v1',
            'scope': 'READ_ONLY_STATIC_SOURCE_CHECK_NOT_ACCOUNT_AUTHORITY_OR_SEMANTIC_QUALIFICATION',
            'main_source_count': len(main['SOURCE_PATHS']),
            'transition_source_count': len(prior['SOURCE_PATHS']),
            'union_source_count': len(must_keep),
            'composed_source_count': len(current),
            'missing_main_or_transition_financial_paths': missing_finance,
            'missing_main_optional_service_paths': missing_optional,
            'missing_main_manifest_routes': missing_routes,
            'shared_financial_paths_with_different_bytes': changed,
            'composed_source_hashes_sha256': hashlib.sha256(json.dumps(target_hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'registry_complete': complete,
            'semantic_review_and_authenticated_account_migration_required': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('--main-root', '--transition-root', '--composed-root'):
        parser.add_argument(arg, type=Path, required=True)
    args = parser.parse_args()
    verdict = inspect(args.main_root, args.transition_root, args.composed_root)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    if not verdict['registry_complete']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
