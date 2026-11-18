"""Check recorded hashes offline. Optionally reacquire individual public publisher objects."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def confirm_arm(arm):
    outputs = arm["model_outputs_by_sha256"]
    for expected, output in outputs.items():
        require(digest(output) == expected, "Model output digest mismatch")
    for r in arm["stage_receipts"].values():
        if r["status"] == "completed":
            require(r["response_sha256"] in outputs, "Successful stage lacks a matching recorded answer")
        require(r.get("mode") == "local" and r.get("reported_model", r["model"]) in {None, r["model"]},
                "Provider identity mismatch")


def verify(record):
    for name, key in [("REGISTRATION.md","registration_sha256"),("RECOVERY_REGISTRATION.md","recovery_registration_sha256"),
                      ("OUTPUT_REGISTRATION.md","output_registration_sha256"),("recovery.py","output_driver_sha256")]:
        require(hashlib.sha256((HERE/name).read_bytes()).hexdigest() == record[key], name + " differs from receipt")
    primary = record["model_experiment"]
    confirm_arm(primary)
    receipts = primary["stage_receipts"]
    require(receipts["workflow.discover"]["response_sha256"] == receipts["direct.discover"]["response_sha256"],
            "Separate direct run did not reproduce the discovery")
    require(receipts["workflow.challenge"]["status"] == "failed" and primary["challenge_terminal_log"], "Missing initial failure")
    followup = record.get("recovery_experiment")
    if followup:
        confirm_arm(followup)
    extended = record.get("output_budget_experiment")
    if extended:
        confirm_arm(extended)
    ids = primary["arm_input_identity"]
    require(ids["workflow_discovery"] == ids["separate_direct_call"], "Input identity differs across arms")
    require(len(record["sources"]) == 4 and len({s["pinned_api_url"] for s in record["sources"]}) == 4, "Incomplete source inventory")
    for r in [primary["restart"]] + [x["restart"] for x in (followup,extended) if x]:
        require(r["status"] == "observed_unchanged" and not r["missions"], "Duplicate mission on unchanged releases")
    criteria = bool(extended and extended["research_decision"] in {"build","incumbent","stop","defer"}
                    and all(extended["stage_receipts"].get("workflow."+stage,{}).get("status") == "completed"
                            for stage in ("discover","challenge"))
                    and extended["repeat_children"] == 0 and extended["repeat_model_calls"] == 0)
    return {"offline_record_check": "pass", "publisher_objects":len(record["sources"]),
            "first_workflow_status":primary["workflow"]["status"], "separate_direct_stages":1,
            "recovery_status":followup["status"] if followup else "registered",
            "recovery_decision":followup["research_decision"] if followup else None,
            "final_status":extended["status"] if extended else "registered",
            "final_decision":extended["research_decision"] if extended else None,
            "final_registered_technical_criterion":criteria if extended else None}


def capture(record, out):
    sys.path.insert(0, str(PRODUCT))
    from ignition import research
    out.mkdir(mode=0o700)
    releases, baseline = [], []
    for src in record["sources"]:
        url = src["pinned_api_url"]
        parsed = urlsplit(url)
        prefix = "/repos/ggml-org/llama.cpp/"
        require(parsed.scheme == "https" and parsed.netloc == "api.github.com" and parsed.path.startswith(prefix)
                and not parsed.query and not parsed.fragment, "Unexpected publisher API destination")
        response = research._harness_fetch(url)
        row = json.loads(response["text"])
        require(row["html_url"] == src["url"], "Publisher source identity changed")
        if src["role"] == "Published release":
            require(parsed.path.removeprefix(prefix).startswith("releases/") and row["tag_name"] == src["version"]
                    and row["published_at"] == src["published_at"], "Release identity changed")
            excerpt = row.get("body") or row.get("name") or row["tag_name"]
            releases.append(row)
        else:
            require(parsed.path.removeprefix(prefix) == "commits/" + src["version"] and row["sha"] == src["version"],
                    "Comparison revision changed")
            excerpt = row["commit"]["message"]
            baseline.append(row)
        require(hashlib.sha256(excerpt[:research.TEXT_LIMIT].encode()).hexdigest() == src["source_excerpt_sha256"],
                "Publisher excerpt changed; this acquisition cannot replay the original evidence")
    for key, rows in (("releases",releases), ("baseline",baseline)):
        (out/f"latest-{key}.json").write_text(json.dumps(rows, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="write a fresh historical reconstruction in a new private directory")
    args = parser.parse_args()
    data = json.loads((HERE/"observation.json").read_text())
    report = verify(data)
    if args.capture:
        capture(data, args.capture)
        report["reacquired"] = 4
    print(json.dumps(report))
