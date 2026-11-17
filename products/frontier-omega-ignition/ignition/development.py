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


def fitting_columns(definition, target, *, include_splits_when_copy=False):
    """Prefer a copy for the conventional learner, but retain all visible fits for explicit choice.

    A copied field can accidentally agree with a transformed field on development
    rows. In the choice menu that coincidence must not remove the intended split.
    Positive and negative split indices remain distinct on fresh records.
    """
    pairs = tuple(rows(definition))
    expected = [out[target["name"]] for _, _, _, out in pairs]
    values = {source: [row[source] for _, _, row, _ in pairs] for source in definition["input_fields"]}
    base = {"target": target["name"], "type": target["type"]}
    copied = [{"source": source, **base} for source, observations in values.items()
              if _matches(observations, expected, target["type"])]
    if copied and not include_splits_when_copy:
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
    return copied + splits


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


# This is the interactive response/transport envelope. Never drop a fitting candidate
# and present an incomplete menu as if it were exhaustive.
MAX_CHOICES = 16
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")
SEPARATOR_NAMES = {" ": "space", "-": "hyphen", "_": "underscore", "/": "slash",
                   ".": "period", ",": "comma", ":": "colon", "|": "pipe"}


def describe(column):
    source, target = column["source"], column["target"]
    if "split" in column:
        part = column["split"]
        index, name = part["index"], SEPARATOR_NAMES[part["separator"]]
        position = (ORDINALS[index] if index >= 0 else "last" if index == -1 else
                    ORDINALS[-index - 1] + " from the end")
        operation = f"take the {position} component of {source} split on {name}"
    else:
        operation = f"copy {source}"
    return {"target": target, "description": f"{target}: {operation} as {column['type']}", "column": column}


def choice_columns(definition):
    return [fitting_columns(definition, target, include_splits_when_copy=True) for target in definition["targets"]]


def menu(definition, order, *, fits_by_target=None):
    """Bounded Cartesian product of all supported observable copy and split fits per target."""
    from itertools import product

    fixed, ambiguous, size = [], [], 1
    if fits_by_target is None:
        fits_by_target = choice_columns(definition)
    for target, fits in zip(definition["targets"], fits_by_target):
        if not fits:
            return None, f"No public projection or split fits {target['name']}. Supply a new specification."
        if len(fits) == 1:
            fixed.append(describe(fits[0]))
        else:
            size *= len(fits)
            if size > MAX_CHOICES:
                return None, f"The public examples admit more than {MAX_CHOICES} complete mappings. Supply a discriminating development example."
            ambiguous.append(fits)
    candidates = []
    for chosen in product(*ambiguous):
        operations = [describe(column) for column in chosen]
        columns = sorted([x["column"] for x in fixed + operations], key=lambda x: x["target"])
        identity = construction.fingerprint({"columns": columns, "input_fields": sorted(definition["input_fields"]),
                                             "extra_fields": definition["extra_fields"]})
        candidates.append({"id": "H-" + identity[:12], "operations": operations,
                           "description": " · ".join(x["description"] for x in operations) or "Unique public-example fit"})
    if len({c["id"] for c in candidates}) != len(candidates):
        return None, "Candidate identifiers collide. The ambiguous mapping cannot be verified."
    return {"question": "Which complete mapping matches the original purpose? Abstain if it does not establish a choice.",
            "fixed_operations": fixed, "candidates": sorted(candidates, key=lambda c: c["id"], reverse=order == "descending")}, None


def program_for(definition, menu, chosen):
    candidate = next((c for c in menu["candidates"] if c["id"] == chosen), None)
    if candidate is None:
        raise ValueError("Selection must identify a registered hypothesis")
    columns = [op["column"] for op in menu["fixed_operations"] + candidate["operations"]]
    return {"columns": sorted(columns, key=lambda col: col["target"]), "input_fields": definition["input_fields"],
            "extra_fields": definition["extra_fields"]}


def has_distinguishing_evidence(mission, menu):
    """Conservative lexical admission check. A match permits asking the model, never selects its answer."""
    import re

    texts = [mission["purpose"], *mission["requirements"]]
    if any(re.search(r"\b(?:either is acceptable|choose either|no preference|unspecified operation|source is ambiguous)\b", text, re.I) for text in texts):
        return False
    clauses = [set(re.findall(r"[a-z0-9_]+", clause.lower()))
               for text in texts for clause in re.split(r"[;,.!?]|\b(?:and|but|while)\b", text, flags=re.I)]
    terms = {"extract", "extracting", "take", "use", "using", "from", "copy", "copying", "copies",
             "select", "read", "segment", "component", "word", "part", "field", "column", "portion", "position"}
    by_target = {}
    for candidate in menu["candidates"]:
        for operation in candidate["operations"]:
            column = operation["column"]
            cues = {column["source"].lower(), column["source"].lower().replace("_", " ")}
            if "id" in cues:
                cues.add("identifier")
            if "split" in column:
                bit = column["split"]
                index = bit["index"]
                cues.add(ORDINALS[index] if index >= 0 else "last" if index == -1 else "end")
                cues.add(SEPARATOR_NAMES[bit["separator"]])
            by_target.setdefault(column["target"], {})[construction.fingerprint(column)] = cues
    for target, alternatives in by_target.items():
        groups = list(alternatives.values())
        if len(groups) < 2:
            continue
        shared = set.intersection(*groups)
        distinct = [cues - shared for cues in groups]
        vocabulary = set.union(*distinct)
        observed = set()
        for words in clauses:
            if not words & terms or (len(by_target) > 1 and target.lower() not in words):
                continue
            if words & {"reject", "refuse", "invalid", "malformed"}:
                continue
            evidence = words & vocabulary
            if not evidence:
                continue
            if words & {"or", "either", "not", "never", "except"}:
                return False
            observed.update(evidence)
        # Evidence must distinguish one operation for each ambiguous target. A cue
        # that excludes only one of three fits does not license a model to guess.
        if not observed or sum(observed <= cues for cues in distinct) != 1:
            return False
    return True
