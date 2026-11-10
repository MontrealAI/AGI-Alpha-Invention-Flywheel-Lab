# SPDX-License-Identifier: Apache-2.0
"""Official app-server message-phase regressions; synthetic transport only."""
import json
import unittest

import test_codex as fixture
from bridge.adapters import BridgeError


class CodexMessageTests(unittest.TestCase):
    setUp = fixture.CodexTests.setUp
    tearDown = fixture.CodexTests.tearDown
    request = fixture.CodexTests.request

    @staticmethod
    def item(ident, text, phase=None, method="item/completed", **scope):
        return {"method": method, "params": {"threadId": "thread-one", "turnId": "turn-one", **scope,
                "item": {"type": "agentMessage", "id": ident, "text": text, "phase": phase}}}

    @staticmethod
    def delta(ident, text):
        return {"method": "item/agentMessage/delta", "params": {"threadId": "thread-one", "turnId": "turn-one",
                "itemId": ident, "delta": text}}

    def output(self, events, **terminal):
        self.messages[3:] = [*events, {"method": "turn/completed", "params": {"threadId": "thread-one",
                             "turn": {"id": "turn-one", "status": "completed", **terminal}}}]
        observed = []
        result = self.service.generate(self.request(), on_event=observed.append)
        return result, observed

    def test_commentary_and_interleaved_final_deltas_return_only_final_json(self):
        final = '{"artifacts":[],"summary":"done"}'
        result, observed = self.output([
            self.item("progress", "", "commentary", "item/started"),
            self.delta("progress", "I will inspect the workspace. "),
            self.item("answer", "", "final_answer", "item/started"),
            self.delta("answer", '{"artifacts":[],'),
            self.delta("progress", "Inspection complete."),
            self.item("progress", "I will inspect the workspace. Inspection complete.", "commentary"),
            self.delta("answer", '"summary":"done"}'),
            self.item("answer", final, "final_answer"),
        ])
        self.assertEqual(result["text"], final)
        self.assertEqual(json.loads(result["text"])["summary"], "done")
        self.assertTrue(any(event["type"] == "progress" for event in observed))
        self.assertEqual([event["delta"] for event in observed if event["type"] == "delta"], [final])
        self.assertNotIn("Inspection", json.dumps(observed))

    def test_completed_item_text_is_authoritative_without_double_appending(self):
        result, _ = self.output([self.delta("answer", "incomplete draft"),
                                 self.item("answer", '{"complete":true}', "final_answer")])
        self.assertEqual(result["text"], '{"complete":true}')

    def test_final_item_does_not_require_deltas(self):
        result, _ = self.output([self.item("answer", "final only", "final_answer")])
        self.assertEqual(result["text"], "final only")

    def test_turn_snapshot_can_supply_completed_final_item(self):
        item = self.item("answer", "snapshot final", "final_answer")["params"]["item"]
        result, _ = self.output([], items=[item])
        self.assertEqual(result["text"], "snapshot final")

    def test_legacy_unknown_phase_uses_last_completed_message_only(self):
        result, _ = self.output([self.delta("preamble", "legacy preamble"), self.item("preamble", "legacy preamble"),
                                 self.delta("answer", "legacy answer"), self.item("answer", "legacy answer")])
        self.assertEqual(result["text"], "legacy answer")

    def test_latest_final_answer_excludes_partial_and_other_messages(self):
        result, _ = self.output([self.item("first", "superseded", "final_answer"),
                                 self.item("partial", "partial", "partial_answer"),
                                 self.item("second", "terminal", "final_answer"),
                                 self.item("other", "unknown")])
        self.assertEqual(result["text"], "terminal")

    def test_latest_completed_item_wins_when_start_and_completion_order_differ(self):
        for phase in (None, "final_answer"):
            with self.subTest(phase=phase):
                self.request = lambda: {**fixture.CodexTests.request(self), "run_id": "completion-order-" + str(phase)}
                result, _ = self.output([self.item("first-start", "", phase, "item/started"),
                                         self.item("second-start", "completed first", phase),
                                         self.item("first-start", "completed last", phase)])
                self.assertEqual(result["text"], "completed last")

    def test_commentary_partial_and_unfinished_messages_cannot_be_final(self):
        for phase, completed in [("commentary", True), ("partial_answer", True), ("final_answer", False), (None, False)]:
            with self.subTest(phase=phase, completed=completed):
                self.request = lambda: {**fixture.CodexTests.request(self), "run_id": "phase-" + str(phase) + str(completed)}
                events = [self.item("answer", "", phase, "item/started"), self.delta("answer", "not a completed answer")]
                if completed:
                    events.append(self.item("answer", "not a completed answer", phase))
                with self.assertRaises(BridgeError) as raised:
                    self.output(events)
                self.assertEqual(raised.exception.code, "CODEX_EMPTY")

    def test_null_completion_phase_does_not_reclassify_known_commentary(self):
        with self.assertRaises(BridgeError) as raised:
            self.output([self.item("progress", "", "commentary", "item/started"),
                         self.delta("progress", "progress only"), self.item("progress", "progress only")])
        self.assertEqual(raised.exception.code, "CODEX_EMPTY")

    def test_nonterminal_last_item_does_not_fall_back_to_earlier_legacy_text(self):
        for phase in ("commentary", "partial_answer"):
            with self.subTest(phase=phase):
                self.request = lambda: {**fixture.CodexTests.request(self), "run_id": "no-fallback-" + phase}
                with self.assertRaises(BridgeError) as raised:
                    self.output([self.item("preamble", "legacy preamble"), self.item("last", "not final", phase)])
                self.assertEqual(raised.exception.code, "CODEX_EMPTY")

    def test_unfinished_final_cannot_fall_back_to_superseded_final(self):
        with self.assertRaises(BridgeError) as raised:
            self.output([self.item("earlier", "superseded", "final_answer"),
                         self.item("last", "unfinished", "final_answer", "item/started")])
        self.assertEqual(raised.exception.code, "CODEX_EMPTY")

        self.request = lambda: {**fixture.CodexTests.request(self), "run_id": "interleaved-unfinished"}
        with self.assertRaises(BridgeError) as raised:
            self.output([self.item("first-start", "", "final_answer", "item/started"),
                         self.item("second-start", "completed first", "final_answer"),
                         self.delta("first-start", "unfinished later text")])
        self.assertEqual(raised.exception.code, "CODEX_EMPTY")

    def test_completed_message_must_match_active_thread_and_turn(self):
        for field in ("threadId", "turnId"):
            with self.subTest(field=field):
                self.request = lambda: {**fixture.CodexTests.request(self), "run_id": "wrong-" + field}
                with self.assertRaises(BridgeError) as raised:
                    self.output([self.delta("answer", "valid-looking"),
                                 self.item("answer", "wrong scope", "final_answer", **{field: "wrong"})])
                self.assertEqual(raised.exception.code, "CODEX_PROTOCOL")

    def test_message_identity_phase_and_delta_types_are_required(self):
        bad_events = [self.delta(None, "text"), self.delta("answer", None),
                      self.item("answer", "text", "made_up_phase"), self.item(None, "text", "final_answer")]
        for index, event in enumerate(bad_events):
            with self.subTest(index=index):
                self.request = lambda: {**fixture.CodexTests.request(self), "run_id": "malformed-" + str(index)}
                with self.assertRaises(BridgeError) as raised:
                    self.output([event, self.item("answer", "text", "final_answer")])
                self.assertEqual(raised.exception.code, "CODEX_PROTOCOL")


if __name__ == "__main__":
    unittest.main()
