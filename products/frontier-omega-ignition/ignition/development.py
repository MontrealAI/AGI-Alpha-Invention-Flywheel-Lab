"""Conventional projection/split inference and repair evidence from the builder-visible examples."""
from __future__ import annotations

from . import construction


def rows(definition):
    for batch, demo in enumerate(definition["demonstrations"], 1):
        for row, (source, expected) in enumerate(zip(demo["input"]["rows"], demo["expected"]["rows"]), 1):
            yield batch, row, source, expected


def _matches(values, expected, kind):
    try:
        for actual, wanted in zip(values, expected):
            converted = construction._convert(actual, kind)
            if type(converted) is not type(wanted) or converted != wanted:
                return False
    except construction.ConstructionError:
        return False
    return True


def fitting_columns(definition, target):
    """All minimum-complexity fits in the stated two families; positive and negative indices stay distinct."""
    pairs = tuple(rows(definition))
    expected = [out[target["name"]] for _, _, _, out in pairs]
    values = {source: [row[source] for _, _, row, _ in pairs] for source in definition["input_fields"]}
    base = {"target": target["name"], "type": target["type"]}
    copied = [{"source": source, **base} for source, observations in values.items()
              if _matches(observations, expected, target["type"])]
    if copied:
        return copied
    splits = []
    for source, observations in values.items():
        if any(type(v) is not str for v in observations):
            continue
        for separator in construction.SEPARATORS:
            # Bound every split. Only observed boundaries are considered evidence for this family.
            if not all(separator in v for v in observations):
                continue
            left = [v.split(separator, 8) for v in observations]
            right = [v.rsplit(separator, 8) for v in observations]
            for groups, positions in ((left, range(min(8, min(map(len, left))))),
                                      (right, range(-min(8, min(map(len, right))), 0))):
                for index in positions:
                    if _matches((parts[index] for parts in groups), expected, target["type"]):
                        splits.append({"source": source, "split": {"separator": separator, "index": index}, **base})
    return splits


def learn(definition):
    """An opt-in conventional specialist. It never chooses arbitrarily among indistinguishable fits."""
    columns = []
    for target in definition["targets"]:
        matches = fitting_columns(definition, target)
        if len(matches) != 1:
            reason = (f"{len(matches)} equally simple hypotheses fit" if matches else "no projection or split fits")
            return None, f"Public development examples for {target['name']}: {reason}. Supply a discriminating example or select the model to interpret the intended operation."
        columns.append(matches[0])
    return {"columns": columns, "input_fields": definition["input_fields"],
            "extra_fields": definition["extra_fields"]}, None


def _visible(value):
    if isinstance(value, str) and len(value) > 96:
        return {"prefix": value[:96], "characters": len(value), "truncated": True}
    return value


def mismatches(definition, program):
    """Inspect only the public build definition. This function cannot receive acceptance cases or receipts."""
    findings = []
    mismatched_targets = 0
    by_target = {col["target"]: col for col in program["columns"]}
    for target in definition["targets"]:
        name = target["name"]
        proposed = by_target[name]
        view = {**program, "columns": [proposed], "input_fields": definition["input_fields"]}
        witnesses = []
        count = 0
        for batch, index, source, expected in rows(definition):
            try:
                observed = construction._records(view, {"rows": [source]})["rows"][0][name]
                if type(observed) is type(expected[name]) and observed == expected[name]:
                    continue
                value = {"value": _visible(observed)}
            except construction.ConstructionError as err:
                value = {"error": err.code}
            count += 1
            if len(witnesses) < 3:
                witnesses.append({"development_batch": batch, "row": index,
                                  "expected": _visible(expected[name]), "observed": value})
        if not count:
            continue
        mismatched_targets += 1
        if len(findings) >= 8:
            continue
        fits = fitting_columns(definition, target)
        # Prioritize alternatives changing only the operator used in the actual proposal.
        # They still compete with every equally simple fitting source.
        fits.sort(key=lambda item: item["source"] != proposed.get("source"))
        findings.append({"target": name, "proposed_operation": proposed, "mismatched_public_rows": count,
                         "witnesses": witnesses, "fitting_hypothesis_count": len(fits),
                         "fitting_columns": fits[:6]})
    return {"mismatched_targets": mismatched_targets, "targets": findings,
            "scope": "Visible development examples only. Fitting columns are minimum-complexity projection or observed split hypotheses; other operations may fit. Use the original requirement to resolve ambiguity."}
