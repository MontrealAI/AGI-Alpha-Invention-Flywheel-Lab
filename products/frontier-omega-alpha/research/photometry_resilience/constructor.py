"""Choose a broker route under fixed witness semantics inside seccomp."""


def construct(development):
    observed = development["matched_exposures"]
    return {"route": "combine-calibrated-brokers" if observed and not development["conflicts"] else "primary-only",
            "development_matched_exposures": observed, "development_conflicts": development["conflicts"]}
