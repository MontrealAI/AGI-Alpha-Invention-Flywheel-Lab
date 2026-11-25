"""Compile a reviewed strategic brief into the retained exact game format."""

from hashlib import file_digest
import json
from pathlib import Path
import re
import sys

PRIOR = Path(__file__).resolve().parents[2] / "evidence-bound" / "strategic"
sys.path.insert(0, str(PRIOR))
from game import Game, check, compare


FIELDS = {
    "timing": ("private", "late", "adaptive", "unknown"),
    "units": ("same", "different", "unknown"),
    "missing": ("complete", "fee", "accuracy", "both"),
}
COMPATIBLE = {"timing": "private", "units": "same", "missing": "complete"}
CASE_KEYS = {"id", "lang", "brief", "payoffs", "accuracy", "fee"}
PLACEHOLDER = {"accuracy": [50, 50], "fee": 0}


def fingerprint(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    with Path(path).open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def valid_case(case):
    if not isinstance(case, dict) or set(case) != CASE_KEYS or case["lang"] not in ("en", "fr"):
        raise ValueError("Invalid public case envelope")
    if not isinstance(case["brief"], str) or not 1 <= len(case["brief"]) <= 2400:
        raise ValueError("Expected a bounded prose brief")
    # Validate the numerical types independently without filling any real input.
    rough = {key: case[key] for key in ("id", "payoffs", "accuracy", "fee")}
    for key, value in PLACEHOLDER.items():
        if rough[key] is None:
            rough[key] = value
    Game.from_document(rough)
    return case


def numeric_missing(case):
    if case["fee"] is None:
        return "both" if case["accuracy"] is None else "fee"
    return "accuracy" if case["accuracy"] is None else "complete"


def validate_interpretation(interpretation):
    if not isinstance(interpretation, dict) or set(interpretation) != set(FIELDS):
        raise ValueError("The interpretation must make all three declarations")
    for key, allowed in FIELDS.items():
        if interpretation[key] not in allowed:
            raise ValueError(f"Unknown {key} declaration")
    return interpretation


def review_case(case, reference):
    valid_case(case)
    validate_interpretation(reference)
    if reference["missing"] != numeric_missing(case):
        raise ValueError("Independent missing-data declaration contradicts authorized inputs")
    return reference


def compile_reviewed(case, proposal, authorized_interpretation):
    """Use an independently supplied semantic contract before exact evaluation."""
    validate_interpretation(proposal)
    review_case(case, authorized_interpretation)
    if proposal != authorized_interpretation:
        fields = [key for key in FIELDS if proposal[key] != authorized_interpretation[key]]
        return {"disposition": "interpretation_disagrees", "fields": fields}
    if proposal != COMPATIBLE:
        return {"disposition": "withhold", "issues": {key: proposal[key] for key in FIELDS
                                                     if proposal[key] != COMPATIBLE[key]}}
    game = Game.from_document({key: case[key] for key in ("id", "payoffs", "accuracy", "fee")})
    decision, bounds = compare(game)
    values = {key: str(check(game, key, value)) for key, value in bounds.items()}
    return {"disposition": "certified_scoped", "solver_input": game.document(), "exact_bounds": values,
            "decision": decision, "certificates": {key: value.document() for key, value in bounds.items()}}


class FormalizationEnvironment:
    """One strategic interpretation step with exact evidence-gated reward."""

    def __init__(self, case, separately_reviewed):
        self.case = valid_case(case)
        self._reference = review_case(case, separately_reviewed)
        self._finished = True

    def reset(self):
        self._finished = False
        return {key: self.case[key] for key in ("id", "lang", "brief")}

    def step(self, proposal):
        if self._finished:
            raise ValueError("Reset before taking a step")
        result = compile_reviewed(self.case, proposal, self._reference)
        self._finished = True
        false_admission = proposal == COMPATIBLE and self._reference != COMPATIBLE
        reward = 1 if proposal == self._reference else (-2 if false_admission else 0)
        return None, reward, True, result


def ordinary_interpretation(case):
    """Transparent conservative phrase rules and exact authorized field inspection."""
    valid_case(case)
    brief = case["brief"].casefold()

    def has(pattern):
        return re.search(pattern, brief) is not None

    late = has(r"after (?:the )?(?:binding|final|irrevocable|row |move)|too late|après (?:le |l’|la )?(?:choix|décision|action|engagement)|trop tard")
    adaptive = (has(r"(?:can|may|allowed to) (?:revise|change|switch|reset|reselect)|peut (?:réviser|modifier|changer|remplacer)")
                and not has(r"cannot (?:revise|change)|can(?:not|'t) change|ne peut (?:plus|pas)"))
    private = (has(r"before |avant |then choos|choisit ensuite|followed by")
               and has(r"private|secret|alone|only the|seul|privé|confident")
               and has(r"(?:public|announce|annonce|publie)") and has(r"fix|locks?|irrevocab|indéplaç|définitif"))
    timing = "unknown"
    if adaptive:
        timing = "adaptive"
    elif late:
        timing = "late"
    elif private:
        timing = "private"

    units = "unknown"
    if has(r"no (?:approved )?conversion|no (?:exchange|rate)|sans (?:aucune |taux de )?conversion|non convert|unités différentes|incommensur|cannot convert"):
        units = "different"
    elif has(r"same (?:unit|scale|currency|(?:game )?points)|both .* (?:points|usd|eur)|all .* (?:points|usd|eur)|même (?:unité|monnaie|échelle)|(?:ensemble|tous).* (?:points|usd|eur)"):
        units = "same"
    return {"timing": timing, "units": units, "missing": numeric_missing(case)}
