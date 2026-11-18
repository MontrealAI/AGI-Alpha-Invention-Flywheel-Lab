"""Check the attribution of an open proposal without assuming its research idea is sound."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import evaluate as study

PACKET_DIGEST = "4d8286fcb99071b0da4bde04a911c5f4105334cb5e1261d5bec41a12935c012b"


def packet():
    raw = (study.HERE / "open_prompt.json").read_bytes()
    if study.sha(raw) != PACKET_DIGEST:
        raise ValueError("The registered facilities mission changed")
    offered = json.loads(raw)
    refs = study.sources()
    if len(offered["sources"]) != len(refs) or any(
        r["id"] not in refs or r["excerpt"] != refs[r["id"]]["excerpt"] for r in offered["sources"]
    ):
        raise ValueError("The open mission has different primary evidence")
    return offered


def assess(answer, withdrawn=()):
    prompt = packet()
    if not isinstance(answer, dict) or not isinstance(answer.get("candidates"), list):
        raise ValueError("A candidate list is required")
    if len(answer["candidates"]) > 5:
        raise ValueError("The registered open mission has at most five slots")
    refs = {r["id"]: r["excerpt"] for r in prompt["sources"] if r["id"] not in withdrawn}
    fields = set(prompt["shape"]["candidates"][0]) - {"citations"}
    rows = []
    for candidate in answer["candidates"]:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("citations"), list):
            raise ValueError("A proposal must include citations or an empty list")
        citations = []
        for citation in candidate["citations"]:
            source = citation.get("source") if isinstance(citation, dict) else None
            quote = citation.get("quote") if isinstance(citation, dict) else None
            active = isinstance(source, str) and source in refs
            exact = active and isinstance(quote, str) and len(quote.split()) >= 4 and quote in refs[source]
            citations.append({"source": source, "available": active, "verbatim": exact})
        rows.append({"candidate_sha256": study.fingerprint(candidate), "citations": citations,
                     "complete_fields": all(isinstance(candidate.get(f), str) and candidate[f].strip() for f in fields),
                     "all_citations_bound": bool(citations) and all(x["verbatim"] for x in citations),
                     "scientific_verdict": "requires independent assessment of the proposed relation and test"})
    return rows


def replay():
    raw = json.loads((study.HERE / "open_included.json").read_text())
    if raw["packet_sha256"] != PACKET_DIGEST or raw["answer_sha256"] != study.fingerprint(raw["answer"]):
        raise ValueError("The open generation no longer matches the recorded prompt or response")
    rows = assess(raw["answer"])
    reviews = raw["independent_review"]["by_candidate_sha256"]
    if {r["candidate_sha256"] for r in rows} != set(reviews):
        raise ValueError("A qualitative review no longer matches its original candidate")
    for row in rows:
        row["qualitative"] = reviews[row["candidate_sha256"]]
        row["material_premise_and_test"] = bool(
            row["complete_fields"] and row["all_citations_bound"] and row["qualitative"]["claim_supported"]
            and row["qualitative"]["material"] and row["qualitative"]["test_decisive"]
        )
    withdrawals = {ref["id"]: [r["all_citations_bound"] for r in assess(raw["answer"], {ref["id"]})]
                   for ref in packet()["sources"]}
    return {"rows": rows, "withdrawal": withdrawals,
            "scope": "Proposed experiments with checked source premises. Field and economic outcomes require execution."}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("answer", type=Path, nargs="?", help="score arbitrary proposals; default replays recorded review")
    cli.add_argument("--withdraw", action="append", default=[])
    options = cli.parse_args()
    result = assess(json.loads(options.answer.read_text()), options.withdraw) if options.answer else replay()
    print(json.dumps(result, indent=2, ensure_ascii=False))
