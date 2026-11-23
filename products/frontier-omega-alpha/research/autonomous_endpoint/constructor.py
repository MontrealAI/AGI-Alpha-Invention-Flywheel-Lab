"""Fileless constructor and the two admissible materializations."""


def _number(value):
    integer, _, fraction = value.partition(".")
    return integer.zfill(30) + fraction.ljust(30, "0")


def _dominance(rows):
    scopes = {}
    for row in rows:
        scopes.setdefault(tuple(row["scope"]), []).append(row)
    kept, covered = [], {}
    for group in scopes.values():
        frontier = []
        for row in sorted(group, key=lambda point: (-point["load"], point["id"])):
            for witness in frontier:
                if (witness["load"] > row["load"] and witness["day"] <= row["day"]
                        and _number(witness["rate"]) >= _number(row["rate"])
                        and _number(witness["first"]) <= _number(row["first"])):
                    covered[row["id"]] = witness["id"]
                    break
            else:
                frontier.append(row)
        kept.extend(frontier)
    return {"kept": sorted(row["id"] for row in kept), "covered": covered}


def construct(development):
    """Choose a different acquisition representation only if development supports it."""
    reduced = _dominance(development)
    return {"method": "dominance" if reduced["covered"] else "projection",
            "development_rows": len(development), "development_kept": len(reduced["kept"])}


def materialize(payload):
    """Replay the frozen plan without receiving confirmation queries or answers."""
    rows = payload["rows"]
    if payload["method"] == "dominance":
        covered = _dominance(rows)["covered"]
    elif payload["method"] == "projection":
        covered = {}
    else:
        raise ValueError("Unknown acquisition plan")
    scopes = {}
    for row in sorted(rows, key=lambda point: point["id"]):
        if row["id"] not in covered:
            scopes.setdefault(tuple(row["scope"]), []).append([
                row["id"], row["day"], row["rate"], row["first"], row["load"],
            ])
    return {"groups": [{"scope": scope, "points": points} for scope, points in sorted(scopes.items())],
            "covered": covered}
