"""Finite select-only error ceiling on previously exposed EIT102 decision bits.

Each allowed selector COPIES one of the three published binary predictions per
decision; it cannot flip bits, train, or acquire new observations. The
omniscient chooser bound is NOT an executable policy or a physical bound.
"""
from collections import Counter
from hashlib import sha256
import json

SOURCE_ARTIFACT_SHA256 = "8efee93d9e4b142907bea786701c6b78047b68a51e248b498c3df9e9c01e37b2"
SOURCE_RESULT_SHA256 = "7b8f0fcc58e0e1881d6bdc88d37b4c0a92216b25aa6de70440e05e061e99857c"
SOURCE_HEAD = "e1493a8d71abcad67a6e26d043ce05cec71a7d4d"
ORIGINAL_OWNER_HEAD = "a5859d378ca6298d1ae22e45dc6c083b060103ff"
ROWS_SHA256 = "3717c65a9f1c1a8fd2171ac83307aadd8bc60e84f7f2a8391062d1f181f8d22c"
# Physical target path, truth, full76, direct40, impute40: bit0 is first of
# eight material/quadrant decisions. SHA-pinned lossless projection of EIT102.
# No KTC acquisition/inverse or source owner's code is executed here.
ROWS = """level1/data1.mat 04 05 05 05
level1/data2.mat c0 c0 c0 c0
level1/data3.mat 01 01 01 01
level2/data1.mat 50 50 50 50
level2/data2.mat 08 08 08 08
level2/data3.mat 90 f0 f0 f0
level3/data1.mat 07 37 37 37
level3/data2.mat 0f 0f 0f 0f
level3/data3.mat 40 c0 d0 c0
level4/data1.mat 42 42 52 52
level4/data2.mat 1c 1c 1c 1c
level4/data3.mat 5a fa fa fa
level5/data1.mat ce ec ec ec
level5/data2.mat 04 25 25 25
level5/data3.mat 20 f0 f0 f0
level6/data1.mat f0 f0 f0 f0
level6/data2.mat 2d 2d 2d 2d
level6/data3.mat 5a fa fa fa
level7/data1.mat 87 f7 d7 f7
level7/data2.mat 2f 0f 0f 0f
level7/data3.mat 09 09 09 09"""
ARMS = ("full76", "direct40", "impute40")


def unpack(value):
    if not isinstance(value, str) or len(value) != 2 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("EXACT_HEX_DECISION_BYTE_REQUIRED")
    number = int(value, 16)
    return tuple((number >> i) & 1 for i in range(8))


def read_rows(raw=ROWS, *, pinned=True):
    if pinned and sha256(raw.encode()).hexdigest() != ROWS_SHA256:
        raise ValueError("EIT103_PUBLIC_PROJECTION_CHANGED")
    lines = raw.splitlines()
    if len(lines) != 21:
        raise ValueError("EIT103_EXACT_21_PHYSICAL_TARGETS_REQUIRED")
    rows, seen = [], set()
    for line in lines:
        cols = line.split()
        if len(cols) != 5:
            raise ValueError("EIT103_EXACT_ROW_REQUIRED")
        target, *bits = cols
        if target in seen or not target.startswith("level") or not target.endswith(".mat"):
            raise ValueError("EIT103_TARGET_IDENTITY_CHANGED")
        seen.add(target)
        rows.append(dict(target=target, **dict(zip(("truth", *ARMS), map(unpack, bits)))))
    return rows


def evaluate(rows):
    if len(rows) != 21 or len({r["target"] for r in rows}) != 21:
        raise ValueError("EIT103_EXACT_21_PHYSICAL_TARGETS_REQUIRED")
    errors, correct = Counter(), Counter()
    by_material, by_quadrant = [0, 0], [0, 0, 0, 0]
    majority = 0
    for row in rows:
        for key in ("truth", *ARMS):
            bits = row.get(key)
            if not isinstance(bits, tuple) or len(bits) != 8 or any(type(v) is not int or v not in (0, 1) for v in bits):
                raise ValueError("EIT103_EXACT_BINARY_DENOMINATOR_REQUIRED")
        for i, actual in enumerate(row["truth"]):
            predictions = [row[arm][i] for arm in ARMS]
            error_pattern = tuple(int(v != actual) for v in predictions)
            errors[error_pattern] += 1
            for arm, error in zip(ARMS, error_pattern):
                correct[arm] += 1 - error
            majority += int(int(sum(predictions) >= 2) == actual)
            if all(error_pattern):
                by_material[i // 4] += 1
                by_quadrant[i % 4] += 1
    assert sum(errors.values()) == 168
    unavoidable = errors[(1, 1, 1)]
    # An impossible ground-truth-informed chooser is correct iff at least
    # one published prediction matches truth. True only for select-only copying.
    return {
        "schema": "agi-alpha/eit103-select-only-fusion-bound/v1",
        "source_artifact_sha256": SOURCE_ARTIFACT_SHA256,
        "source_result_sha256": SOURCE_RESULT_SHA256,
        "source_original_owner_commit": ORIGINAL_OWNER_HEAD,
        "source_executed_commit": SOURCE_HEAD,
        "source_projection_sha256": ROWS_SHA256,
        "physical_specimens_previously_exposed": 21,
        "actual_new_acquisitions": 0,
        "binary_decisions": 168,
        "correct_by_fixed_arm": {a: correct[a] for a in ARMS},
        "correct_by_majority_vote": majority,
        "select_only_oracle_upper_bound_correct": 168 - unavoidable,
        "unanimously_wrong": unavoidable,
        "unanimously_correct": errors[(0, 0, 0)],
        "disagreement_positions": 168 - errors[(0, 0, 0)] - unavoidable,
        "unanimous_errors_by_material": by_material,
        "unanimous_errors_by_quadrant": by_quadrant,
        "error_patterns_full_direct_impute": {"".join(map(str, k)): v for k, v in sorted(errors.items())},
        "scope": "POST_HOC_ALREADY_EXPOSED_BINARY_OUTPUT_SELECTION_ONLY",
        "no_general_physical_or_algorithmic_impossibility_claim": True,
        "clairvoyant_oracle_executable": False,
        "financial_native_actions": 0,
        "actual_collected_revenue_usd": 0,
        "complete_cost_profit_usd": None,
        "usd_3b_trailing365_qualified": False,
        "decision": "REJECT_SELECT_ONLY_FUSION_AS_NEW_INFORMATION_CHANNEL_NO_BID_NO_DEPLOY",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(read_rows()), indent=2, sort_keys=True))
