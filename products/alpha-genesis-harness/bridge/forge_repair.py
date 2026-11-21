# SPDX-License-Identifier: Apache-2.0
"""Finite source repair search for exact, subset-based numerical programs."""
from __future__ import annotations

import ast
from itertools import combinations

from . import forge_telemetry as telemetry


class NumericMutation(ast.NodeTransformer):
    def __init__(self, methods):
        self.methods = methods
        self.changed = set()

    def visit_Call(self, node):
        self.generic_visit(node)
        function = node.func
        name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
        if "complement" not in self.methods or name != "combinations" or len(node.args) != 2:
            return node
        population, size = node.args
        if (not isinstance(population, ast.Call) or not isinstance(population.func, ast.Name)
                or population.func.id != "range" or len(population.args) != 1
                or not isinstance(population.args[0], ast.Name) or not isinstance(size, ast.Name)):
            return node
        node.args[1] = ast.BinOp(ast.Name(population.args[0].id, ast.Load()), ast.Sub(), size)
        self.changed.add("complement")
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if "exact" not in self.methods or len(node.comparators) != 1:
            return node
        threshold = node.comparators[0]
        if isinstance(threshold, ast.Constant) and type(threshold.value) is float and 0 < threshold.value < 1e-6:
            node.comparators[0] = ast.Constant(0)
            self.changed.add("exact")
        return node

    def visit_If(self, node):
        self.generic_visit(node)
        test = node.test
        if ("empty" in self.methods and isinstance(test, ast.Compare) and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq) and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == 0 and isinstance(test.left, ast.Call)
                and isinstance(test.left.func, ast.Name) and test.left.func.id == "len"
                and len(node.body) == 1 and isinstance(node.body[0], ast.Continue) and not node.orelse):
            self.changed.add("empty")
            return None
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        iterable = node.iter
        if ("endpoint" not in self.methods or not isinstance(iterable, ast.Call)
                or not isinstance(iterable.func, ast.Name) or iterable.func.id != "range"
                or len(iterable.args) != 1):
            return node
        stop = iterable.args[0]
        if (isinstance(stop, ast.BinOp) and isinstance(stop.op, ast.Add) and isinstance(stop.left, ast.Name)
                and isinstance(stop.right, ast.Constant) and stop.right.value == 1):
            node.iter = ast.Tuple([stop.left], ast.Load())
            self.changed.add("endpoint")
        return node


def variants(source):
    yield (), source
    methods = ("complement", "empty", "exact", "endpoint")
    observed = set()
    for size in range(1, len(methods) + 1):
        for combination in combinations(methods, size):
            mutation = NumericMutation(combination)
            tree = mutation.visit(ast.parse(source))
            if not mutation.changed or tuple(sorted(mutation.changed)) in observed:
                continue
            active = tuple(sorted(mutation.changed))
            observed.add(active)
            yield active, ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def boundary_cases():
    return [
        {"id": "small-exact-direction", "input": {
            "A": [[2147483647, 1]], "y": [0], "target": [1, 0], "faults": 0}},
        {"id": "empty-constraint-nonzero-target", "input": {
            "A": [[2, 3]], "y": [11], "target": [0, 1], "faults": 1}},
        {"id": "empty-constraint-zero-target", "input": {
            "A": [[2, 3]], "y": [11], "target": [0, 0], "faults": 1}},
        {"id": "only-reading-may-fail", "input": {"A": [[2]], "y": [3], "target": [1], "faults": 1}},
        {"id": "empty-constraint-only-feasible-subset", "input": {
            "A": [[0]], "y": [1], "target": [0], "faults": 1}},
        {"id": "avoid-redundant-fault-counts", "input": {
            "A": [[1]] * 24, "y": [0] * 24, "target": [0], "faults": 24}},
    ]


def trial_candidates(source, development):
    """Evaluate every distinct variant solely against exposed checks."""
    for methods, candidate in variants(source):
        checks = [{"id": case["id"], **telemetry.score(candidate, case["input"])}
                  for case in development + boundary_cases()]
        yield candidate, {"methods": list(methods), "checks": checks, "passed": all(row["passed"] for row in checks)}
