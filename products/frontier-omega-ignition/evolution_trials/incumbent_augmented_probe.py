"""Offline, competent conventional incumbent: stock broker view + original ZTF packets.

Separate from the FRONTIER FIELD producer. This is NOT a real customer,
independent third-party analyst, new sky observation or paid economic result.
The conventional raw-packet adjudicator is intentionally reused and named.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import time
from pathlib import Path

import broker_control as conventional
import incumbent_stock_probe as stock

HERE = Path(__file__).resolve().parent
REFERENCE_PATH = HERE / "BROKER_CONTROL.json"
PROTOCOL = HERE / "NUCLEUSWATCH_AUGMENTED_PROTOCOL.md"


def _source_paths() -> tuple[Path, ...]:
    """Exactly the six already-published source packets, not a favorable sample."""
    return (
        HERE / "broker_sources/3579392285815015017.avro.gz",
        HERE / "broker_sources/3580268845815015008.avro.gz",
        HERE / "broker_sources/3584356425815015004.avro.gz",
        HERE / "broker_sources/3584382785815015006.avro.gz",
        HERE.parent / "invention/early_survey/exposures/sources/g.avro.gz",
        HERE.parent / "invention/early_survey/exposures/sources/r.avro.gz",
    )


def checked_packet(body: bytes, candidate_id: str, expected_sha256: str) -> dict:
    """Fail before reading a packet whose bytes differ from the published pin."""
    if hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError("PINNED_ORIGINAL_PACKET_DIGEST_MISMATCH")
    row = conventional.packet_candidate(body, stock.TARGET)
    if str(row["candid"]) != candidate_id:
        raise ValueError("PINNED_PACKET_CANDID_MISMATCH")
    return row


def _stock_candidate(row: dict):
    return stock.stock_view({
        "mjd": row["jd"] - conventional.MJD_ZERO,
        "fid": row["fid"],
        "magpsf": row["magpsf"],
        "sigmapsf": row["sigmapsf"],
        "candid": str(row["candid"]),
        "rfid": row["rfid"],
        "field": row["field"],
        "rcid": row["rcid"],
        "programid": row["programid"],
        "pid": row["pid"],
    })


def compare(*, verified_wheel: Path | None = None) -> dict:
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    if stock.nucleuswatch.__version__ != stock.EXPECTED_VERSION:
        raise ValueError("UPSTREAM_VERSION_NOT_PINNED")
    if verified_wheel is not None:
        if hashlib.sha256(verified_wheel.read_bytes()).hexdigest() != stock.WHEEL_SHA256:
            raise ValueError("PINNED_WHEEL_DIGEST_MISMATCH")
    if not PROTOCOL.is_file():
        raise ValueError("FROZEN_PROTOCOL_MISSING")
    published = json.loads(REFERENCE_PATH.read_bytes())
    expected = published["source_sha256"]["packets"]
    notice = conventional.notice_from_file()
    if notice.target != stock.TARGET or sorted(notice.bands) != ["g", "r"]:
        raise ValueError("ORIGINAL_NOTICE_CHANGED")
    index_bytes = (HERE / "broker_sources/alerce-window.vot").read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != published["source_sha256"]["index"]:
        raise ValueError("PINNED_TAP_DIGEST_MISMATCH")
    indexed, as_of = conventional.index_rows(index_bytes, notice)
    rows, compressed_bytes = {}, {}
    for path in _source_paths():
        raw = gzip.decompress(path.read_bytes())
        row = conventional.packet_candidate(raw, notice.target)
        candidate_id = str(row["candid"])
        if candidate_id not in expected or candidate_id in rows:
            raise ValueError("UNKNOWN_OR_DUPLICATE_PINNED_PACKET")
        rows[row["candid"]] = checked_packet(raw, candidate_id, expected[candidate_id])
        compressed_bytes[candidate_id] = len(raw)
    if len(rows) != 6 or set(rows) != set(indexed) or set(map(str, rows)) != set(expected):
        raise ValueError("INCOMPLETE_OR_CHANGED_PINNED_COHORT")
    native = conventional.adjudicate(notice, indexed, rows, as_of)
    if native != published["result"]:
        raise ValueError("ORDINARY_SOURCE_RESULT_DIFFERS_FROM_PUBLISHED_FIXTURE")

    # The upstream unmodified stock adapter is useful as an object/candidate
    # front end. The independent raw packets carry the required provenance.
    visible = {}
    for cid, row in rows.items():
        frame = _stock_candidate(row)
        if len(frame) != 1 or str(frame.iloc[0]["candid"]) != str(cid):
            raise ValueError("UPSTREAM_STOCK_CANDIDATE_NOT_PRESERVED")
        if frame.iloc[0]["band"] != ("g" if row["fid"] == 1 else "r"):
            raise ValueError("UPSTREAM_STOCK_BAND_NOT_PRESERVED")
        if any(key in frame.columns for key in stock.REQUIRED_PROVENANCE):
            raise ValueError("UPSTREAM_STOCK_PROVENANCE_SCHEMA_CHANGED")
        visible[cid] = frame

    # Fixed synthetic negative: modify the raw original packet bytes.
    # This must be rejected by the source pin, not accepted as a new exposure.
    first_id = min(expected)
    raw_first = gzip.decompress(_source_paths()[0].read_bytes())
    if str(conventional.packet_candidate(raw_first, notice.target)["candid"]) != first_id:
        raise ValueError("ADVERSARIAL_PACKET_SELECTION_MISMATCH")
    changed = bytearray(raw_first)
    changed[-1] ^= 1
    tamper_rejected = False
    try:
        checked_packet(bytes(changed), first_id, expected[first_id])
    except ValueError as error:
        tamper_rejected = str(error) == "PINNED_ORIGINAL_PACKET_DIGEST_MISMATCH"
    if not tamper_rejected:
        raise AssertionError("CHANGED_ORIGINAL_PACKET_WAS_ACCEPTED")

    # Explicitly SYNTHETIC counterfactual. Its stock view remains unchanged,
    # while a reindexed alternative reference cannot satisfy the notice.
    g_id = int(published["result"]["bands"]["g"]["witness"]["candid"])
    original_g = rows[g_id]
    alternative = copy.deepcopy(rows)
    alternative_index = dict(indexed)
    changed_rfid = original_g["rfid"] + 1
    alternative[g_id]["rfid"] = changed_rfid
    mjd, fid, _, pid = alternative_index[g_id]
    alternative_index[g_id] = (mjd, fid, changed_rfid, pid)
    if not _stock_candidate(original_g).equals(_stock_candidate(alternative[g_id])):
        raise AssertionError("STOCK_NO_LONGER_LOSES_REFERENCE_METADATA")
    counterfactual = conventional.adjudicate(notice, alternative_index, alternative, as_of)
    if (counterfactual["bands"]["g"]["status"] == "persisted"
            or counterfactual["bands"]["g"].get("witness") is not None
            or counterfactual["bands"]["r"] != native["bands"]["r"]):
        raise AssertionError("AUGMENTED_ROUTE_ACCEPTED_OFF_REFERENCE_WITNESS")
    for band, cid in (("g", "3587249065815015015"), ("r", "3587389715815015003")):
        item = native["bands"][band]
        if item["witness"]["candid"] != cid or item["status"] != "persisted":
            raise AssertionError("ORDINARY_AUGMENTED_WITNESS_MISMATCH")
        if not item["same_reference_stack"] or item["programid"] != 1:
            raise AssertionError("ORDINARY_AUGMENTED_REFERENCE_MISMATCH")
        if not math.isfinite(item["quadrature_error_mag"]):
            raise AssertionError("ORDINARY_AUGMENTED_FORMAL_ERROR_MISSING")
    return {
        "schema": "agi-alpha/augmented-incumbent-provenance/v1",
        "original_source": stock.OWNER_SOURCE,
        "parent_control_head": "a02b64bdae56f6b8649012e5222f2c1ac943913c",
        "upstream_version": stock.nucleuswatch.__version__,
        "upstream_wheel_sha256": stock.WHEEL_SHA256 if verified_wheel else None,
        "frozen_protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "type": "EXPOSED_ARCHIVE_ENGINEERING_REPLAY_NOT_FRESH_CONFIRMATION",
        "origin": "nucleuswatch-stock-candidate-view-plus-existing-conventional-original-packet-adjudicator",
        "original_packet_count": len(rows),
        "original_index_sha256": published["source_sha256"]["index"],
        "original_packet_sha256": expected,
        "original_packet_bytes_uncompressed": sum(compressed_bytes.values()),
        "candidate_count": len(visible),
        "witness_ids": {band: native["bands"][band]["witness"]["candid"] for band in ("g", "r")},
        "matched_original_report": True,
        "original_byte_tamper_rejected": tamper_rejected,
        "synthetic_off_reference_undetectable_stock_only": True,
        "synthetic_off_reference_rejected_augmented": True,
        "new_accepted_sky_observations": 0,
        "new_paying_customers": 0,
        "new_collected_revenue_usd": 0,
        "operator_hours": None,
        "human_comparator_complete_cost_usd": None,
        "model_and_host_billing_usd": None,
        "business_demand": "UNMEASURED",
        "scientific_output_verdict": "EXPOSED_CASE_FUNCTIONAL_TIE_NO_INCREMENTAL_ADVANTAGE_ESTABLISHED",
        "economic_verdict": "NO_DEPLOY",
        "measured_process_wall_seconds": time.perf_counter() - wall_start,
        "measured_process_cpu_seconds": time.process_time() - cpu_start,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-wheel", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(verified_wheel=args.verified_wheel)
    body = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(body, end="")
    else:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(body)
        print(json.dumps({"receipt": str(args.output),
                          "sha256": hashlib.sha256(body.encode()).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
