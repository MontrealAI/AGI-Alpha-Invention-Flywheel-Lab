# SPDX-License-Identifier: Apache-2.0
"""Independent conventional arithmetic for the registered local missions."""

from fractions import Fraction


def occupancy(data):
    active = {row["line_id"] for row in data["services"] if row["scope"] == "regular"}
    relevant = [row for row in data["journeys"] if row["line_id"] in active and row["state"] == "operated"]
    occupied = sum(row["occupied"] * row["minutes"] for row in relevant)
    offered = sum(row["capacity"] * row["minutes"] for row in relevant)
    return {"occupancy": str(Fraction(occupied, offered))}


def transport_work(data):
    work = Fraction(0)
    masses = {"kg": Fraction(1, 1000), "t": Fraction(1)}
    lengths = {"m": Fraction(1, 1000), "km": Fraction(1)}
    for row in data["expeditions"]:
        work += row["charge"] * masses[row["u_charge"]] * row["trajet"] * lengths[row["u_trajet"]]
    return {"travail": str(work)}


def mean_power(data):
    rows = data["mesures"]
    missing = [f"mesures[{i}].{field}" for i, row in enumerate(rows)
               for field in ("energie_j", "duree_s") if row[field] is None]
    if missing:
        return {"decision": "ABSTAIN", "missing": missing,
                "identities": [rows[int(identifier.split("[")[1].split("]")[0])]["cycle"] for identifier in missing]}
    return {"puissance": str(Fraction(sum(row["energie_j"] for row in rows), sum(row["duree_s"] for row in rows)))}


REFERENCES = {"occupancy": occupancy, "transport": transport_work, "power": mean_power}
