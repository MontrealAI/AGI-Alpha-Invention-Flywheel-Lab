"""Portable replay of the preserved first registered instrument-foundry run.

The original executable and results remain unchanged. Its original --check also
compares the recorded Python version string. This publication wrapper compares
every scientific field exactly while reporting runtime-version metadata and
excluding observational timing, which the original check already excludes.
"""
import json

import instrument_foundry as foundry


def main():
    expected = json.loads((foundry.ROOT / "foundry-results.json").read_text())
    actual = foundry.run()
    compared_expected = foundry.deterministic(expected)
    compared_actual = foundry.deterministic(actual)
    recorded_python = compared_expected.pop("python")
    replay_python = compared_actual.pop("python")
    if actual["run_status"] != "COMPLETE" or compared_actual != compared_expected:
        raise SystemExit("FAIL: scientific fields, source, protocol, or exact replay differ")
    print(json.dumps({
        "status": "PASS",
        "scope": "Exact scientific replay; original executable and result preserved",
        "recorded_python": recorded_python,
        "replay_python": replay_python,
        "excluded_observations": ["python version string", "per-request wall and CPU timing"],
        "requests_per_arm": actual["registered_requests_per_arm"],
        "source_sha256": actual["source_sha256"],
        "protocol_sha256": actual["protocol_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
