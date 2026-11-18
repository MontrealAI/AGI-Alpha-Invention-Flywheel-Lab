"""Measure complete offline source reads for the 34 cutoffs, independently of acquisition costs."""

import json
import platform
import sqlite3
import statistics
import time

if __package__:
    from . import adapter, capture, desk, direct
else:
    import adapter
    import capture
    import desk
    import direct


def run():
    reg = capture.manifest()
    cohort, control = capture.selection(capture.roster(reg))
    cases = [(event, t) for event in [*cohort, control] for t in desk.cutoffs(direct.schedule(event))]
    series = {k: [] for k in ("integrated_source_aware", "conventional_sql_cross_format")}
    for i in range(6):
        order = tuple(series) if i % 2 == 0 else tuple(reversed(series))
        for name in order:
            start = time.perf_counter()
            answers = []
            for event, t in cases:
                if name == "integrated_source_aware":
                    scope = {"event": event, "clock": "issued", "as_of": desk.utc(t)}
                    restricted = adapter.inspect_source(scope, "first_notice")
                    if restricted["state"] == "pending":
                        answer = "pending"
                    else:
                        decision = adapter.inspect_source(scope, "status_history")
                        answer = decision["finding"] or decision["state"]
                else:
                    answer = direct.decide(event, t)
                answers.append(answer)
            series[name].append(round(time.perf_counter() - start, 6))
            if not all(a in {"pending", "active", "retracted"} for a in answers):
                raise ValueError("The measured route returned an unqualified result.")
    components = {}
    for name, items in (
            ("complete_common_roster", [reg["roster"]]),
            ("complete_original_status_histories", [r for k, r in reg["originals"].items() if k.endswith("xml_fmt")]),
            ("conventional_mail_histories", [r for k, r in reg["originals"].items() if k.endswith(".lvc")]),
            ("corroborating_collaboration_circular", [reg["originals"]["36190.json"]])):
        components[name] = {"requests": len(items), "body_bytes": sum(i["size_bytes"] for i in items),
                            "request_wall_seconds_sum": round(sum(i["wall_seconds"] for i in items), 6)}
    unsuccessful = reg["unsuccessful_roster_read"]
    components["truncated_initial_roster_read"] = {"requests": 1, "body_bytes": unsuccessful["truncated_bytes"],
                                                   "request_wall_seconds_sum": unsuccessful["wall_seconds"]}
    return {
        "acquisition_components": components,
        "acquisition_total": {k: round(sum(i[k] for i in components.values()), 6)
                              for k in ("requests", "body_bytes", "request_wall_seconds_sum")},
        "measurement": "Local warm-OS-cache serial replay of all cutoffs, 6 runs in alternating order. "
                       "Every individual decision reloads and verifies its sources. Routing tries the "
                       "restricted source then the complete history when necessary. Conventional SQL reads "
                       "the same supplied sources and also cross-checks NASA's e-mail rendition. Common "
                       "cutoff construction excluded. A production observer could cache both histories.",
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "processor_arch": platform.machine(),
        "registered_cutoffs_per_timing": len(cases), "elapsed_seconds_per_34_cutoffs": series,
        "median_seconds_per_34_cutoffs": {k: round(statistics.median(v), 6) for k, v in series.items()},
        "unmeasured_costs": ["Complete investigator and engineering labor", "Human correction and review time",
                             "Price of included compute and web research", "Network egress and infrastructure",
                             "Maintenance, integration, support and adoption", "Telescope time and realized science benefit"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
