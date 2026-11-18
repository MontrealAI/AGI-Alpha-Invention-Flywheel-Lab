"""Bind two research decisions to the available source passages, and retain open hypotheses."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = {
    "missions.json": "7b69efe338670536dda78d3ca859f6a467415ffca153db87f42e5c31452dfb9a",
    "sources.json": "1423668b80c1736244a36c2b0a33aee80308690c824d3d8d0d84d1b0e4892240",
}
# A context names exactly the public excerpts its recipient could use.
CONTEXTS = (
    ("grid", ("A", "B")),
    ("lineage", ("D",)),
    ("lineage", ("C", "D")),
    ("grid", ("A",)),
)
# A curator reviewed each relation and its domain. Keywords alone do not
# establish entailment. Other statements remain open to independent review.
RELATIONS = {
    "grid": ("B", "matches or exceeds the throughput"),
    "lineage": ("C", "failures shared across distinct algorithmic trackers"),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value):
    return sha(json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode())


def registered(name):
    raw = (HERE / name).read_bytes()
    if sha(raw) != PINS[name]:
        raise ValueError(f"Registered {name} changed")
    return json.loads(raw)


def sources():
    rows = registered("sources.json")["sources"]
    if len({r["id"] for r in rows}) != len(rows) or any(
        sha(r["excerpt"].encode()) != r["excerpt_sha256"] for r in rows
    ):
        raise ValueError("A source excerpt has changed identity")
    return {r["id"]: r for r in rows}


def context(number):
    if type(number) is not int or not 1 <= number <= len(CONTEXTS):
        raise ValueError("Choose one of the four registered contexts")
    return CONTEXTS[number - 1]


def packet(number, prepared=False):
    mission, available = context(number)
    inputs = registered("missions.json")
    task = next(m for m in inputs["missions"] if m["id"] == mission)
    records = sources()
    offered = [{"id": slot, "excerpt": records[slot]["excerpt"]} for slot in available]
    if prepared:
        for row in offered:
            row["curated_scope"] = records[row["id"]]["scope"]
    return {"role": inputs["role"], "question": task["question"],
            "sources": offered, "shape": inputs["shape"]}


def assess(number, answer, *, withdraw=()):
    mission, available = context(number)
    known = sources()
    expected, anchor = RELATIONS[mission]
    remaining = set(available).difference(withdraw)
    expected_answer = "established" if expected in remaining else "unresolved"
    original = answer if isinstance(answer, dict) else {}
    result = {"narrow_decision": original.get("decision") == expected_answer,
              "source": None, "passage": None, "relation": None, "evidence_decision_accepted": False,
              "design_fields_present": all(isinstance(original.get(k), str) and original[k].strip()
                                           for k in ("claim", "uncertainty", "action", "test")),
              "open_design_verdict": "requires independent scientific review"}
    if original.get("decision") == "unresolved":
        empty = all(key in original and original[key] is None for key in ("source", "quote"))
        result.update(source="none" if empty else "unbound", relation="withheld",
                      evidence_decision_accepted=empty and expected not in remaining)
        return result
    if original.get("decision") != "established":
        result["relation"] = "missing_decision"
        return result
    ref = original.get("source")
    if not isinstance(ref, str) or ref not in remaining:
        result.update(source="unavailable", relation="ineligible")
        return result
    quote = original.get("quote")
    exact = isinstance(quote, str) and len(quote.split()) >= 4 and quote in known[ref]["excerpt"]
    material = ref == expected and exact and anchor in quote
    result.update(source="available", passage="verbatim" if exact else "not_bound",
                  relation=("bound" if material else "different_comparison" if ref != expected
                            else "missing_supporting_relation"),
                  evidence_decision_accepted=bool(material))
    return result


def conventional(number):
    """Ordinary curated exact-relation lookup. It has no free-text invention output."""
    mission, slots = context(number)
    support, anchor = RELATIONS[mission]
    records = sources()
    found = support in slots and anchor in records[support]["excerpt"]
    return {"decision": "established" if found else "unresolved", "source": support if found else None,
            "quote": records[support]["excerpt"] if found else None, "claim": None, "uncertainty": None,
            "action": None, "test": None}


def replay(file):
    receipt = json.loads(Path(file).read_text())
    rows = []
    seen = set()
    for trial in receipt["cases"]:
        number, arm = trial["context"], trial["route"]
        if arm not in {"prepared", "direct"} or (number, arm) in seen:
            raise ValueError("Unexpected or duplicated research context")
        seen.add((number, arm))
        if fingerprint(packet(number, arm == "prepared")) != trial["packet_sha256"]:
            raise ValueError("The trial used different source words or instructions")
        answer = trial["answer"]
        if fingerprint(answer) != trial["answer_sha256"]:
            raise ValueError("Recorded answer changed")
        verdict = assess(number, answer)
        source = RELATIONS[context(number)[0]][0]
        rows.append({"context": number, "route": arm, "verdict": verdict,
                     "same_answer_if_support_withdrawn": assess(number, answer, withdraw={source})})
    return rows


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("packet")
    p.add_argument("context", type=int, choices=range(1, 5))
    p.add_argument("--prepared", action="store_true")
    p = sub.add_parser("score")
    p.add_argument("context", type=int, choices=range(1, 5))
    p.add_argument("answer", type=Path)
    p.add_argument("--withdraw", action="append", default=[])
    p = sub.add_parser("replay")
    p.add_argument("receipt", type=Path)
    sub.add_parser("lookup")
    args = cli.parse_args()
    if args.mode == "packet":
        value = packet(args.context, args.prepared)
    elif args.mode == "score":
        value = assess(args.context, json.loads(args.answer.read_text()), withdraw=args.withdraw)
    elif args.mode == "replay":
        value = replay(args.receipt)
    else:
        value = [{"context": i, "answer": conventional(i), "assessment": assess(i, conventional(i))}
                 for i in range(1, 5)]
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
