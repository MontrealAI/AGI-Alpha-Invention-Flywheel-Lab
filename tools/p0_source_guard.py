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
        # Only direct, reachable branches in the outer dispatcher can qualify.
        # A nested def or an if after an unconditional return is not a route.
        seen = set()
        schema_bound = False
        for node in functions[0].body:
            if isinstance(node, ast.Return):
                break
            if isinstance(node, ast.Assign):
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if 'schema' in targets:
                    if schema_bound or len(targets) != 1:
                        break  # Changed selector: no later branch is authoritative.
                    schema_bound = True
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # Nested lexical scope is never called by this scan.
            if not isinstance(node, ast.If):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr, ast.Pass)):
                    continue
                break  # Unknown control flow: fail closed on subsequent routes.
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
            required_sources = {'source_paths', 'PRODUCTION_SOURCE_PATHS', 'INVENTORY_SOURCE_PATHS'}
            if required_sources & {value.id for value in ast.walk(first_return)
                                   if isinstance(value, ast.Name)}:
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
