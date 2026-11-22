"""Direct inspection comparator for the registered external receipts."""

import re


def assess(stage, logs, allowed, requested):
    if not requested or not set(requested) <= set(stage["theorems"]):
        return False
    for checker in ("con-leche", "con-ron"):
        log = logs[checker]
        expected_summary = re.compile(
            rf"^{checker}: accepted {stage['challenge_declarations']} declarations, "
            rf"{len(stage['theorems'])} axioms justified by the solution .+ "
            rf"\({stage['solution_declarations']} declarations accepted\) \(--verified\)$",
            re.MULTILINE,
        )
        if len(expected_summary.findall(log)) != 1 or re.findall(r"^\s*Exit status: (\d+)$", log, re.MULTILINE) != ["0"]:
            return False
        for theorem in requested:
            if log.splitlines().count(f"{checker}: theorem {theorem} justified by the solution") != 1:
                return False
    for theorem in requested:
        lists = re.findall(rf"^'{re.escape(theorem)}' depends on axioms: \[([^\]]*)\]$", logs["audit"], re.MULTILINE)
        if len(lists) != 1 or set(re.split(r"\s*,\s*", lists[0])) != set(allowed):
            return False
        if "statement" in logs:
            if len(re.findall(rf"^theorem {re.escape(theorem)} :", logs["statement"], re.MULTILINE)) != 1:
                return False
    return True
