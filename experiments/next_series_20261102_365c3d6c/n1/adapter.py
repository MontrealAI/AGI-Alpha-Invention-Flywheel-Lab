import copy
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
UNRESOLVED = {
    "channel_to_stream": "UNKNOWN_CHANNEL_IDENTITY",
    "installed_calibration": "UNKNOWN_INSTALLED_CALIBRATION",
    "temperature_compensation": "UNKNOWN_TEMPERATURE_COMPENSATION",
    "clock_alignment": "UNKNOWN_CLOCK_ALIGNMENT",
    "archive_state_tag": "UNKNOWN_STATE_TAG",
    "batch_release_rule": "UNKNOWN_BATCH_RELEASE_RULE",
    "batch_mixing_rule": "UNKNOWN_BATCH_MIXING_RULE",
    "one_pass_quantity_route": "UNKNOWN_QUANTITY_ROUTE",
    "proxy_contract": "PROXY_NOT_DEFINED",
}


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def assess(observation, evidence, policy, model_only):
    reasons = []
    numeric_rejection = False
    if not isinstance(observation, dict):
        return {"quality_status": "MODEL_HOLD" if model_only else "HOLD", "reasons": ["INVALID_OBSERVATION"], "qualified_volume_l": None, "physical_admission": False}
    if not isinstance(evidence, dict):
        evidence = {}
        reasons.append("INVALID_EVIDENCE")
    else:
        evidence = dict(evidence)
    if not isinstance(policy, dict):
        policy = {}
        reasons.append("INVALID_POLICY")
    tag = observation.get("source_tag")
    structured = {"channel_to_stream", "installed_calibration", "proxy_contract"}
    for field, reason in UNRESOLVED.items():
        value = evidence.get(field)
        expected_type = dict if field in structured else str
        absent = not isinstance(value, expected_type) or not value
        if isinstance(value, str) and value.strip().upper() in {"", "UNKNOWN", "HOLD", "NOT_DEFINED"}:
            absent = True
        if absent:
            reasons.append(reason)
            evidence[field] = None
    mapping = evidence.get("channel_to_stream") or {}
    mapped_stream = mapping.get(tag) if isinstance(tag, str) else None
    if not isinstance(mapped_stream, str) or not mapped_stream.strip() or mapped_stream.upper() == "UNKNOWN":
        mapped_stream = None
        reasons.append("UNKNOWN_SOURCE_TAG")
    if mapped_stream is not None and mapped_stream != "diluate_outlet":
        reasons.append("WRONG_STREAM")
    if observation.get("unit") != "uS/cm":
        reasons.append("UNIT_MISMATCH")
    temperature = evidence.get("temperature_compensation")
    if temperature is not None and observation.get("temperature_basis") != temperature:
        reasons.append("TEMPERATURE_BASIS_MISMATCH")
    samples = observation.get("samples")
    if not isinstance(samples, list) or not samples or any(not isinstance(s, dict) for s in samples):
        samples = []
        reasons.append("MISSING_SAMPLES")
    times = [s.get("time_s") for s in samples]
    values = [s.get("value") for s in samples]
    valid_samples = bool(samples) and all(finite_number(x) for x in times + values)
    if not valid_samples:
        reasons.append("NONFINITE_OR_MISSING_SAMPLE")
    elif any(x < 0 for x in values):
        reasons.append("NEGATIVE_CONDUCTIVITY")
    elif any(b <= a for a, b in zip(times, times[1:])):
        reasons.append("NONMONOTONE_CLOCK")
    batch = observation.get("batch") or {}
    if not isinstance(batch, dict):
        batch = {}
    batch_id = batch.get("id")
    start, end = batch.get("start_s"), batch.get("end_s")
    valid_batch = isinstance(batch_id, str) and bool(batch_id.strip()) and finite_number(start) and finite_number(end) and end > start
    if not valid_batch:
        reasons.append("UNKNOWN_BATCH_INTERVAL")
    if batch.get("mixed") is not False:
        reasons.append("UNRESOLVED_BATCH_MIXING")
    if any(s.get("batch_id") != batch_id for s in samples):
        reasons.append("GAP_OR_SAMPLE_CROSSES_BATCH")
    if valid_samples and valid_batch:
        if times[0] != start or times[-1] != end:
            reasons.append("INCOMPLETE_BATCH_COVERAGE")
        max_gap = policy.get("maximum_gap_s")
        if not finite_number(max_gap) or any(b - a > max_gap for a, b in zip(times, times[1:])):
            reasons.append("EXCESSIVE_OR_UNKNOWN_SAMPLE_GAP")
    calibration = evidence.get("installed_calibration")
    if calibration is not None:
        if observation.get("calibration_id") != calibration.get("id"):
            reasons.append("CALIBRATION_ID_MISMATCH")
        lo, hi = calibration.get("valid_from_s"), calibration.get("valid_until_s")
        if not (finite_number(lo) and finite_number(hi) and lo <= hi):
            reasons.append("UNKNOWN_CALIBRATION_INTERVAL")
        elif valid_samples and any(t < lo or t > hi for t in times):
            reasons.append("STALE_CALIBRATION")
    offset = observation.get("clock_offset_s")
    allowed_offset = policy.get("maximum_clock_offset_s")
    if not (finite_number(offset) and finite_number(allowed_offset)) or abs(offset) > allowed_offset:
        reasons.append("TIMESTAMP_OFFSET_OR_UNKNOWN")
    state = observation.get("state_code")
    if isinstance(state, bool) or state != 7:
        reasons.append("NOT_DRAIN_DILUATE_STATE")
    if observation.get("reversal") is not False:
        reasons.append("REVERSAL_OR_UNKNOWN")
    release = observation.get("release")
    if not isinstance(release, dict) or release.get("kind") != "batch_release":
        release = {}
        reasons.append("MISSING_RELEASE_EVENT")
    if release.get("batch_id") != batch_id:
        reasons.append("RELEASE_BATCH_MISMATCH")
    released_at = release.get("time_s")
    if not finite_number(released_at) or not valid_batch or released_at < end:
        reasons.append("RELEASE_BEFORE_COMPLETE_OBSERVATION_OR_UNKNOWN")
    counter = observation.get("counter") or {}
    if not isinstance(counter, dict):
        counter = {}
    c0, c1 = counter.get("start"), counter.get("end")
    interval = observation.get("discharge_interval_s")
    valid_interval = isinstance(interval, list) and len(interval) == 2 and all(finite_number(x) for x in interval) and interval[1] > interval[0]
    if not valid_interval or not finite_number(released_at) or interval[0] < released_at:
        reasons.append("UNBOUND_DISCHARGE_INTERVAL")
    valid_counter = finite_number(c0) and finite_number(c1)
    if not valid_counter or c1 < c0:
        reasons.append("COUNTER_RESET_OR_INVALID")
    if counter.get("unit") != "L":
        reasons.append("COUNTER_UNIT_MISMATCH")
    if counter.get("route") != "one_pass_product":
        reasons.append("RECYCLE_OR_UNKNOWN_COUNTER_ROUTE")
    if counter.get("batch_id") != batch_id:
        reasons.append("COUNTER_BATCH_MISMATCH")
    proxy = evidence.get("proxy_contract")
    upper = None
    if proxy is not None and valid_samples:
        uncertainty = proxy.get("absolute_uncertainty_uS_cm")
        limit = proxy.get("maximum_uS_cm")
        if not (finite_number(uncertainty) and uncertainty >= 0 and finite_number(limit) and limit >= 0):
            reasons.append("UNKNOWN_PROXY_ENVELOPE")
        else:
            upper = max(values) + uncertainty
            if upper > limit:
                reasons.append("OUTSIDE_PROXY_ENVELOPE")
                numeric_rejection = True
    reasons = sorted(set(reasons))
    if model_only:
        status = "MODEL_PASS" if not reasons else ("MODEL_REJECT" if numeric_rejection else "MODEL_HOLD")
    else:
        status = "HOLD"
        reasons = sorted(set(reasons + ["PUBLIC_ADAPTER_NOT_ADMITTED"]))
    quantity_known = valid_counter and c1 >= c0 and counter.get("unit") == "L"
    return {
        "source_tag": tag,
        "physical_stream": mapped_stream if mapped_stream is not None else "UNKNOWN",
        "unit": observation.get("unit", "UNKNOWN"),
        "temperature_compensation": temperature if temperature is not None else "UNKNOWN",
        "calibration_basis": calibration if calibration is not None else "UNKNOWN",
        "clock_interval_s": interval if valid_interval else "UNKNOWN",
        "archive_clock_alignment": evidence.get("clock_alignment") or "UNKNOWN",
        "reported_state_code": state,
        "authenticated_operating_state": "Drain Diluate" if state == 7 and evidence.get("archive_state_tag") is not None else "UNKNOWN",
        "releasable_batch": batch_id if not reasons else "UNKNOWN",
        "quality_status": status,
        "reasons": reasons,
        "unqualified_counter_increment_l": c1 - c0 if quantity_known else None,
        "quantity_status": "MODEL_INTERVAL_VALID" if model_only and not reasons else "UNQUALIFIED_COUNTER_ONLY",
        "proxy_upper_bound_uS_cm": upper,
        "qualified_volume_l": c1 - c0 if model_only and not reasons else None,
        "volume_scope": "AUTHORED_MODEL_ONLY" if model_only else "NO_QUALIFIED_PUBLIC_VOLUME",
        "physical_admission": False,
        "potability": "NOT_ASSESSED",
    }


def adapt_public(observation):
    manifest = json.loads((HERE / "SOURCE_MANIFEST.json").read_text())
    contract = json.loads((HERE / "CONTRACT.json").read_text())
    return assess(observation, manifest["adapter_evidence"], contract["public_policy"], False)


def model_fixture():
    evidence = {
        "channel_to_stream": {"MODEL_DILUATE": "diluate_outlet", "MODEL_BRINE": "concentrate_outlet"},
        "installed_calibration": {"id": "MODEL_CAL", "valid_from_s": -1, "valid_until_s": 20},
        "temperature_compensation": "MODEL_ATC_25C",
        "clock_alignment": "AUTHORED_SYNCHRONIZED_CLOCK",
        "archive_state_tag": "MODEL_STATE",
        "batch_release_rule": "AUTHORED_COMPLETE_BATCH_THEN_RELEASE",
        "batch_mixing_rule": "AUTHORED_NO_CROSS_BATCH_MIXING",
        "one_pass_quantity_route": "AUTHORED_SINGLE_PRODUCT_METER",
        "proxy_contract": {"maximum_uS_cm": 1000, "absolute_uncertainty_uS_cm": 1},
    }
    observation = {
        "source_tag": "MODEL_DILUATE", "unit": "uS/cm", "temperature_basis": "MODEL_ATC_25C",
        "calibration_id": "MODEL_CAL", "clock_offset_s": 0,
        "samples": [{"time_s": t, "value": 100, "batch_id": "MODEL_BATCH"} for t in [0, 5, 10]],
        "batch": {"id": "MODEL_BATCH", "start_s": 0, "end_s": 10, "mixed": False},
        "state_code": 7, "reversal": False,
        "release": {"kind": "batch_release", "time_s": 12, "batch_id": "MODEL_BATCH"},
        "discharge_interval_s": [12, 13],
        "counter": {"start": 100, "end": 110, "unit": "L", "route": "one_pass_product", "batch_id": "MODEL_BATCH"},
    }
    return copy.deepcopy(observation), copy.deepcopy(evidence), {"maximum_gap_s": 5, "maximum_clock_offset_s": 0.1}
