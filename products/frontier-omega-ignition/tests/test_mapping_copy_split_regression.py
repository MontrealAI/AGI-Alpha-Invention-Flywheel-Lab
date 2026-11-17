"""Test-first: a coincidentally matching copy must not hide an intent-required split.

All samples are public, synthetic development fixtures. No acceptance answers,
private data, account, model key, or historical failed run is changed here.
"""
import unittest

from ignition import construction, development


def fixture():
    return {
        "input_fields": ["parcel_code", "routing_note", "reported_mark"],
        "targets": [{"name": "sorting_mark", "type": "text"}],
        "extra_fields": "reject",
        "demonstrations": [{
            "input": {"rows": [
                {"parcel_code": "north-214", "routing_note": "route north overnight",
                 "reported_mark": "north"},
                {"parcel_code": "south-117", "routing_note": "scan south overnight",
                 "reported_mark": "south"},
            ]},
            "expected": {"rows": [
                {"sorting_mark": "north"}, {"sorting_mark": "south"}
            ]},
        }],
    }


class IncidentalCopyMasksRequiredSplit(unittest.TestCase):
    def test_complete_choice_menu_retains_semantic_split_despite_matching_copy(self):
        definition = fixture()
        # The purpose explicitly demands the SECOND routing_note word, but
        # reported_mark happens to agree on the two visible development rows.
        menu, why = development.menu(definition, "ascending")
        self.assertIsNone(why, why)
        self.assertIsNotNone(menu)
        choices = [
            (candidate["id"], operation["column"])
            for candidate in menu["candidates"]
            for operation in candidate["operations"]
        ]
        intended = [
            ident for ident, col in choices
            if col["source"] == "routing_note"
            and col.get("split") == {"separator": " ", "index": 1}
        ]
        self.assertEqual(len(intended), 1,
                         "The complete-choice route may not exclude the declared split merely "
                         "because a simpler but unintended public copy coincidentally fits.")
        selected = development.program_for(definition, menu, intended[0])
        result = construction._records(selected, {"rows": [
            {"parcel_code": "atlantic-17", "routing_note": "send amber urgent overnight",
             "reported_mark": "incorrect"}
        ]})
        self.assertEqual(result, {"rows": [{"sorting_mark": "amber"}]})

    def test_ordinary_simple_specialist_remains_an_explicit_separate_baseline(self):
        # Do not silently replace the established simple-copy incumbent.
        program, why = development.learn(fixture())
        self.assertIsNone(why, why)
        self.assertEqual(program["columns"][0]["source"], "reported_mark")
        self.assertNotIn("split", program["columns"][0])


if __name__ == "__main__":
    unittest.main()
