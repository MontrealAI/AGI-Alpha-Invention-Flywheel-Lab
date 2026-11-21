#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prospective public-record experiment for the HARNESS economic mission."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import Runtime, strict_json
from bridge.economic_mission import ARTIFACT, SOURCE_LIMIT, checks, selected
from bridge.instruments import evaluate
from bridge.services import AccessRuntime
from bridge.workflows import WorkflowService, digest, equivalent, portable_digest

SOURCES = {
    "electricity": (
        "NESO national carbon intensity, Great Britain, 14–16 November 2026 UTC",
        "https://api.carbonintensity.org.uk/intensity/2026-11-14T00:00Z/2026-11-16T00:00Z",
    ),
    "exchange-rates": (
        "Bank of Canada daily reference exchange rates, 1–19 October 2026",
        "https://www.bankofcanada.ca/valet/observations/FXUSDCAD,FXEURCAD,FXGBPCAD/json?start_date=2026-10-01&end_date=2026-10-19",
    ),
    "seismic-archive": (
        "USGS reviewed and provisional earthquake catalogue records, 1–19 October 2026",
        "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-10-01&endtime=2026-10-19&minmagnitude=6&orderby=time-asc",
    ),
}

GOALS = {
    "window": (
        "electricity",
        "Retrospectively choose a continuous one-hour window for a constant-power flexible workload. "
        "Fields c0 to c5 are the published actual carbon intensities of six successive equal half-hour slots. "
        "A negative value is missing. Allowed slot indexes are at least ready and strictly below until. "
        "Return start (zero-based slot index) and total (the sum of the two published intensity values) "
        "for the feasible window with least integrated intensity. Break ties by earliest start. "
        "If no pair is feasible, return start=-1 and total=-1. Do not substitute a forecast for missing observations.",
    ),
    "quote": (
        "exchange-rates",
        "Retrospectively compare historical reference-rate conversions for equivalent hypothetical software quotes. "
        "Fields cad, usd, eur, gbp are whole local currency units. A negative quote is absent. "
        "Fields usd_rate, eur_rate, gbp_rate are the Bank's published CAD per unit multiplied by 10000. "
        "Choose the least converted amount with ties resolved in the order CAD, USD, EUR, GBP. "
        "Return currency (uppercase code) and scaled_cad (CAD multiplied by 10000, without rounding). "
        "With no offer return currency='NONE' and scaled_cad=-1. This is historical arithmetic on hypothetical quotes.",
    ),
    "catalogue": (
        "seismic-archive",
        "Retrospectively triage archived candidate events for a scientific catalogue inclusion threshold. "
        "Fields m, error and floor are the reported magnitude, magnitude error and inclusion threshold multiplied by 1000. "
        "A negative error indicates missing uncertainty. Field reviewed says whether the record was reviewed. "
        "Return only status='defer' when unreviewed, uncertainty is missing, or the symmetric uncertainty interval "
        "straddles the threshold. Return status='include' if the entire closed interval is at or above the threshold, "
        "or status='exclude' if the entire interval is below it. This is catalogue triage only.",
    ),
}


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def _snapshot(source):
    label, url = source
    with urlopen(url, timeout=30) as response:
        if response.geturl() != url or response.headers.get_content_type() != "application/json":
            raise ValueError(f"Unexpected primary source response: {label}")
        body = response.read(SOURCE_LIMIT + 1)
    if not 0 < len(body) <= SOURCE_LIMIT:
        raise ValueError(f"Source size outside the registered boundary: {label}")
    strict_json(body)
    return {"label": label, "url": url,
            "snapshot": {"body": body.decode("utf-8"), "sha256": hashlib.sha256(body).hexdigest()}}


def conventional_window(data):
    intensity = [data[f"c{i}"] for i in range(6)]
    candidates = [
        (sum(intensity[start:start + 2]), start)
        for start in range(data["ready"], data["until"] - 1)
        if min(intensity[start:start + 2]) >= 0
    ]
    total, start = min(candidates, default=(-1, -1))
    return {"start": start, "total": total}


def conventional_quote(data):
    currencies = ("cad", "usd", "eur", "gbp")
    quotes = [
        (data[currency] * (10000 if currency == "cad" else data[currency + "_rate"]), index)
        for index, currency in enumerate(currencies) if data[currency] >= 0
    ]
    if not quotes:
        return {"currency": "NONE", "scaled_cad": -1}
    amount, index = min(quotes)
    return {"currency": currencies[index].upper(), "scaled_cad": amount}


def conventional_catalogue(data):
    magnitude, uncertainty, floor = data["m"], data["error"], data["floor"]
    if not data["reviewed"] or uncertainty < 0:
        status = "defer"
    elif magnitude - uncertainty >= floor:
        status = "include"
    elif magnitude + uncertainty < floor:
        status = "exclude"
    else:
        status = "defer"
    return {"status": status}


REFERENCES = {"window": conventional_window, "quote": conventional_quote, "catalogue": conventional_catalogue}


def window_inputs(records):
    if len(records) < 84 or any(a["to"] != b["from"] for a, b in zip(records, records[1:])):
        raise ValueError("The registered source must supply at least 84 continuous half-hour rows.")
    for block in range(14):
        rows = records[block * 6:block * 6 + 6]
        intensity = [row["intensity"]["actual"] for row in rows]
        data = {f"c{i}": -1 if actual is None else actual for i, actual in enumerate(intensity)}
        yield {**data, "ready": block % 3, "until": 6 - block % 2}


def _scale(value, factor):
    return int(Decimal(str(value)) * factor)


def quote_inputs(records):
    for index, row in enumerate(records):
        yield {
            "cad": 182 + (index * 7) % 16,
            "usd": 132 - index % 6,
            "eur": -1 if index % 4 == 0 else 111 + index % 9,
            "gbp": 100 - index % 5,
            **{currency.lower() + "_rate": _scale(row["FX" + currency + "CAD"]["v"], 10000)
               for currency in ("USD", "EUR", "GBP")},
        }


def catalogue_inputs(records):
    for index, item in enumerate(records):
        properties = item["properties"]
        magnitude, uncertainty = properties["mag"], properties.get("magError")
        if magnitude is None:
            continue
        yield {"m": _scale(magnitude, 1000),
               "error": -1 if uncertainty is None else _scale(uncertainty, 1000),
               "floor": (6000, 6250, 6500)[index % 3], "reviewed": properties["status"] == "reviewed"}


def boundary_inputs(contract, sample):
    if contract == "window":
        return [
            {**sample, **{f"c{i}": 100 for i in range(6)}, "ready": 1, "until": 5},
            {**sample, **{f"c{i}": -1 if i % 2 else 100 for i in range(6)}, "ready": 0, "until": 6},
            {**sample, "ready": 4, "until": 5},
        ]
    if contract == "quote":
        return [
            {**sample, "cad": 100, "usd": 100, "usd_rate": 10000, "eur": -1, "gbp": -1},
            {**sample, "cad": -1, "usd": -1, "eur": -1, "gbp": -1},
        ]
    return []


def cases(sources):
    data = {key: strict_json(row["snapshot"]["body"]) for key, row in sources.items()}
    groups = {"window": list(window_inputs(data["electricity"]["data"])),
              "quote": list(quote_inputs(data["exchange-rates"]["observations"])),
              "catalogue": list(catalogue_inputs(data["seismic-archive"]["features"]))}
    contracts, successor = {}, {}
    for key, group in groups.items():
        # Remove identical inputs, preserving first occurrence and chronological order.
        unique = {}
        for row in group:
            unique.setdefault(digest(row), row)
        rows = list(unique.values())
        if len(rows) < 7:
            raise ValueError(f"Insufficient distinct observations for the registered {key} workload.")
        labelled = [{"input": row, "expected": REFERENCES[key](row)} for row in rows]
        if len({digest(row["expected"]) for row in labelled}) < 2:
            # The USGS summary feed can omit magnitude uncertainty. All-abstention
            # cases cannot qualify inclusion and exclusion, so keep it as evidence only.
            continue
        source, goal = GOALS[key]
        boundary = [{"input": row, "expected": REFERENCES[key](row)} for row in boundary_inputs(key, rows[0])]
        contracts[key] = {"source": source, "goal": goal, "development": labelled[:3],
                          "qualification": labelled[3:-2] + boundary}
        successor[key] = labelled[-2:]
    return contracts, successor


def _terminal(service, ident):
    started = perf_counter()
    while True:
        state = service.step(ident)
        if state["status"] != "ready":
            return state, perf_counter() - started


def compare(service, ident, contract, artifact, rows, max_operations):
    observations = {}
    arms = {
        "retained_harness": lambda row: service.reuse(ident, row)["outputs"][ARTIFACT]["output"],
        "ordinary_same_artifact": lambda row: evaluate(artifact, row, max_operations)["output"],
        "conventional_specialist": REFERENCES[contract],
    }
    for name, run in arms.items():
        started = perf_counter()
        values = [run(row["input"]) for row in rows]
        observations[name] = {"wall_seconds": perf_counter() - started, "outputs": values,
                              "passed": sum(equivalent(value, row["expected"]) for value, row in zip(values, rows))}
    return {"cases": rows, "comparisons": observations,
            "scope": "Fresh source-derived instances of the chosen task. Exact-content reuse, no cost extrapolation."}


def run(args):
    args.work.mkdir(parents=True, exist_ok=False)
    if args.sources:
        sources = strict_json(args.sources.read_bytes())
        actual = {key: (row["label"], row["url"]) for key, row in sources.items()}
        if actual != SOURCES:
            raise ValueError("Only the registered primary sources are accepted by this experiment.")
    else:
        with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
            sources = dict(zip(SOURCES, pool.map(_snapshot, SOURCES.values())))
    _json(args.work / "SOURCES.json", sources)
    contracts, successor = cases(sources)
    route = {"provider": args.provider, "model": args.model}
    spec = {
        "objective": "Discover and construct one unexpectedly valuable productive capability MONTREAL.AI can own or operate.",
        "context": ("Look for a real decision we could deliver reliably at scale. The initial "
                    "scope is historical offline analysis. Deployment, outreach and financial authority are absent."),
        "roles": {"researcher": route, "builder": route}, "strategy": "single-model",
        "local_only": True, "tool_permissions": ["construct_instrument"],
        "max_iterations": 3, "max_actions": 3, "max_output_tokens": 2304,
        "economic_mission": {"beneficiary": "MONTREAL.AI", "language": args.language,
                             "sources": sources, "contracts": contracts, "confirm_citations": True},
    }
    _json(args.work / "MISSION.json", spec)
    registration = {"spec_sha256": digest(spec), "successor_sha256": digest(successor),
                    "conventional": sorted(REFERENCES), "model": args.model,
                    "max_construction_attempts": spec["max_iterations"],
                    "insufficient_observation_coverage": sorted(set(REFERENCES) - set(contracts))}
    _json(args.work / "REGISTRATION.json", registration)
    config = strict_json(args.config.read_bytes())
    runtime = AccessRuntime(Runtime(config), config)
    progress_path = args.work / "WORKSPACE"
    service = WorkflowService(runtime, progress_path)
    try:
        ident = service.create(spec)["id"]
        (args.work / "RUN-ID").write_text(ident + "\n", encoding="utf-8")
        state, elapsed = _terminal(service, ident)
        _json(args.work / "INSPECT.json", state)
        archive = service.export(ident) if state["status"] in {"complete", "needs_review", "exhausted"} else None
        if archive is not None:
            _json(args.work / "ARCHIVE.json", archive)
        choice = selected(state)
        receipt = {"status": state["status"], "run_id": ident, **registration,
                   "wall_seconds": elapsed, "verdicts": state["verdicts"],
                   "observations": state["economic_mission"]["observations"],
                   "decision": state["economic_mission"]["decision"], "choice": choice,
                   "verification": state["verification"], "model_requests": state["request_costs"],
                   "frozen": state["economic_mission"]["frozen"],
                   "complete_cost_known": False, "realized_value_observed": False,
                   "unsatisfied_controls": ["Independent beneficiary adoption and value/cost evidence",
                                            "Strong tool-augmented frontier reference",
                                            "Improved inventor-method comparison"]}
        if state["status"] == "complete":
            for name in (ARTIFACT, "RUN_INSTRUMENT.py"):
                (args.work / name).write_text(archive["files"][name], encoding="utf-8")
            contract = choice["contract"]
            artifact = strict_json(archive["files"][ARTIFACT])
            max_operations = state["spec"]["max_operations"]
            receipt["qualification_comparison"] = compare(
                service, ident, contract, artifact, checks(archive["state"], final=True), max_operations)
            receipt["fresh_transfer"] = compare(service, ident, contract, artifact, successor[contract], max_operations)
            receipt["unsatisfied_controls"].append("Fresh construction without retained artifact")
        _json(args.work / "RESULT.json", receipt)
        print(json.dumps({"status": receipt["status"], "choice": choice, "result": str(args.work / "RESULT.json")},
                         ensure_ascii=False), flush=True)
    finally:
        service.close()


def replay(path):
    """Re-evaluate a qualified export using the pinned portable evaluator."""
    archive = strict_json(path.read_bytes())
    if (archive.get("schema") != "alpha-genesis-workflow-export/v1"
            or archive.get("sha256") != portable_digest({k: v for k, v in archive.items() if k != "sha256"})):
        raise ValueError("Invalid HARNESS export identity.")
    state, files = archive["state"], archive["files"]
    economic = state["economic_mission"]
    sealed = economic["frozen"]
    acceptance = checks(state, final=True)
    evaluator = Path(__file__).resolve().parents[1] / "bridge/instruments.py"
    evaluator_sha256 = hashlib.sha256(evaluator.read_bytes()).hexdigest()
    if (state["status"] != "complete" or state["spec_hash"] != digest(state["spec"]) or not acceptance
            or sealed["qualification_sha256"] != digest(acceptance)
            or sealed["sha256"] != hashlib.sha256(files[ARTIFACT].encode()).hexdigest()
            or economic["source_identity"]["instruments.py"] != evaluator_sha256
            or hashlib.sha256(files["RUN_INSTRUMENT.py"].encode()).hexdigest() != evaluator_sha256):
        raise ValueError("Archived instrument, evaluator or qualification inputs changed.")
    passed = 0
    started = perf_counter()
    with tempfile.TemporaryDirectory(prefix="omega-replay-") as temporary:
        root = Path(temporary)
        asset, inputs = root / ARTIFACT, root / "input.json"
        asset.write_text(files[ARTIFACT], encoding="utf-8")
        for check in acceptance:
            _json(inputs, check["input"])
            raw = subprocess.check_output([sys.executable, "-B", str(evaluator), str(asset), str(inputs),
                                           "--max-operations", str(state["spec"]["max_operations"])])
            passed += equivalent(strict_json(raw)["output"], check["expected"])
    return {"qualification": "passed" if passed == len(acceptance) else "rejected",
            "passed": passed, "total": len(acceptance), "candidate_sha256": sealed["sha256"],
            "evaluator_sha256": evaluator_sha256, "wall_seconds": perf_counter() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--sources", type=Path, help="Replay a previous exact public-source capture.")
    parser.add_argument("--language", choices=("en", "fr"), default="en")
    parser.add_argument("--replay", type=Path, help="Re-execute the frozen qualification from a completed archive.")
    args = parser.parse_args()
    if args.replay:
        result = replay(args.replay)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["qualification"] == "passed" else 1
    if not all((args.config, args.provider, args.model, args.work)):
        parser.error("Live experiment needs --config, --provider, --model and --work.")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
