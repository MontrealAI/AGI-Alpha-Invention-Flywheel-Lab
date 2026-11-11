"""Streaming137: original exact observer parity and bounded input traversal.

All fixtures here are pure *observer* unit tapes, not audited native financial
worlds, actual orders or customer evidence. The original nested-sum oracle is
intentionally retained unchanged from frozen main for independent comparison.
"""
import copy
import unittest

from connected_enterprise.scale import (
    MICRO, TARGETS_USD, YEAR_HOURS, _milestones, _calendar, _covered,
    _point, _receivables,
)


def prior_nested_sum_oracle(tape, aggregation, epoch):
    records = []
    for dollars in TARGETS_USD:
        threshold = dollars * MICRO
        revenue_crossing = qualified_crossing = None
        for item in aggregation["collections"]:
            hour = item["hour"]
            amount = sum(
                row["amount"] for row in aggregation["collections"]
                if hour - YEAR_HOURS < row["hour"] <= hour
                and row["action_index"] <= item["action_index"]
            )
            if amount < threshold:
                continue
            index = item["action_index"]
            summary = tape["actions"][index]["after"]
            record = {
                "hour": hour,
                "calendar_utc": _calendar(epoch, hour),
                "trailing_365_day_collections_microUSD": amount,
                "complete_365_day_history": hour >= YEAR_HOURS,
                "state_microUSD": _point(
                    summary, _receivables(tape["actions"][:index + 1])
                ),
            }
            if revenue_crossing is None:
                revenue_crossing = record
            if qualified_crossing is None and summary["profit"] > 0 and _covered(summary):
                qualified_crossing = record
        records.append({
            "target_usd": dollars,
            "target_microUSD": threshold,
            "revenue_attainment": revenue_crossing,
            "profitable_obligation_covered_attainment": qualified_crossing,
            "status": "REACHED" if revenue_crossing else "NOT_REACHED_WITHIN_EXECUTED_HORIZON",
            "subsequent_terminal_obligation_covered": _covered(tape["summary"]),
            "subsequent_terminal_profit_microUSD": tape["summary"]["profit"],
        })
    return records


def baseline_summary():
    return {
        "collections": 0, "recoveryIncome": 0, "revenue": 0,
        "expenses": 0, "expensePaid": 0, "cash": 50_000_000 * MICRO,
        "profit": 0, "payables": 0, "tailReserve": 0,
        "custodyReserve": 0, "workingCapital": 0,
        "unrestrictedEarned": 0, "available": 0,
        "equityProtectionBacking": 0, "investmentStopped": False,
    }


def observable_tape(entries):
    """Integer signed amounts; synthetic financial observation, not ledger audit."""
    state = baseline_summary()
    actions = [{"op": "offer", "args": {"id": "fixture", "price": 1},
                "day": 0, "before": copy.deepcopy(state),
                "after": copy.deepcopy(state)}]
    collection_rows = []
    for hour, amount, protected in entries:
        before = copy.deepcopy(state)
        state["collections"] += amount
        state["revenue"] += amount
        state["cash"] += amount
        state["profit"] += amount
        state["payables"] = 0 if protected else 1
        state["investmentStopped"] = False
        state["unrestrictedEarned"] = max(0, state["profit"])
        state["available"] = max(0, state["cash"])
        idx = len(actions)
        actions.append({"op": "event", "args": {"id": "fixture", "action": "release"},
                        "day": hour, "before": before,
                        "after": copy.deepcopy(state)})
        collection_rows.append({"hour": hour, "amount": amount, "action_index": idx})
    return {"actions": actions, "summary": copy.deepcopy(state)}, {"collections": collection_rows}


class CountingCollections(list):
    def __init__(self, rows, maximum):
        super().__init__(rows)
        self.maximum = maximum
        self.visits = 0

    def __iter__(self):
        for row in super().__iter__():
            self.visits += 1
            if self.visits > self.maximum:
                raise AssertionError("QUADRATIC_SOURCE_COLLECTION_TRAVERSAL")
            yield row


class MilestoneStreaming137Tests(unittest.TestCase):
    def test_full_original_record_parity_signed_same_hour_boundary_and_protection(self):
        entries = [
            (0, 600_000 * MICRO, False),
            (0, 500_000 * MICRO, False),
            (0, -200_000 * MICRO, True),
            (1, 200_000 * MICRO, True),
            (2, 10_000_000 * MICRO, False),
            (2, -11_000_000 * MICRO, True),
            (YEAR_HOURS, 10_000 * MICRO, True),
            (YEAR_HOURS + 1, 1_100_000 * MICRO, True),
            (YEAR_HOURS + 1, -200_000 * MICRO, False),
            (YEAR_HOURS + 1, 200_000 * MICRO, True),
        ]
        tape, aggregation = observable_tape(entries)
        epoch = "2026-11-01T00:00:00Z"
        old = prior_nested_sum_oracle(tape, aggregation, epoch)
        new = _milestones(tape, aggregation, epoch)
        self.assertEqual(new, old)
        self.assertEqual(new[0]["revenue_attainment"]["hour"], 0)
        self.assertEqual(new[0]["profitable_obligation_covered_attainment"]["hour"], 1)
        self.assertTrue(new[0]["revenue_attainment"] is not None)
        self.assertIsNone(new[-1]["revenue_attainment"])
        # Original receipts at t=0 are excluded from a t=8760 rolling window.
        self.assertLess(
            new[0]["profitable_obligation_covered_attainment"]["hour"], YEAR_HOURS
        )

    def test_original_record_parity_bounded_no_attainment_and_many_thresholds(self):
        for entries in (
            [],
            [(2, 50 * MICRO, True)],
            [(1, 13_000_000 * MICRO, False), (1, 0, True)],
            [(1, 15_000_000 * MICRO, True), (2, -14_500_000 * MICRO, True)],
            [(1, 1_000_000_000 * MICRO, True), (1, -1_000_000_000 * MICRO, True)],
            [(0, 12_000_000 * MICRO, True), (YEAR_HOURS, 12_000_000 * MICRO, True)],
        ):
            with self.subTest(entries=entries):
                tape, aggregation = observable_tape(entries)
                self.assertEqual(
                    _milestones(tape, aggregation, "2026-11-01T00:00:00Z"),
                    prior_nested_sum_oracle(tape, aggregation, "2026-11-01T00:00:00Z"),
                )

    def test_large_history_source_visits_are_linear_not_quadratic(self):
        # This is a parser/observer traversal test, NOT a million-buyer trial.
        n = 10_000
        summary = baseline_summary()
        summary.update(profit=200 * MICRO, revenue=200 * MICRO,
                       collections=200 * MICRO)
        actions = [{"op": "cost", "args": {"id": "observer-only"},
                    "after": summary} for _ in range(n)]
        rows = [{"hour": i, "amount": 200 * MICRO, "action_index": i}
                for i in range(n)]
        visited = CountingCollections(rows, maximum=6 * n)
        out = _milestones(
            {"actions": actions, "summary": summary},
            {"collections": visited},
            "2026-11-01T00:00:00Z",
        )
        self.assertEqual(len(out), len(TARGETS_USD))
        self.assertLessEqual(visited.visits, 6 * n)


if __name__ == "__main__":
    unittest.main()
