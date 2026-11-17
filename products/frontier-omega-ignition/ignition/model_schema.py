"""Wire syntax for local models declaring native schema support. No scientific or acceptance verdicts."""
from hashlib import sha256
from pathlib import Path

from . import construction
from .research import CANDIDATE_FIELDS

LOADED_SOURCE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
TEXT = {"type":"string", "minLength":1}
NIL = {"type":"null"}


def obj(fields, optional=()):
    return {"type":"object", "properties":fields, "required":[k for k in fields if k not in optional],
            "additionalProperties":False}


def array(item, maximum=None):
    value = {"type":"array", "items":item}
    if maximum is not None:
        value["maxItems"] = maximum
    return value


def one(values):
    return {"enum":list(values)}


def maybe(spec):
    return {"anyOf":[NIL,spec]}


def source_refs(payload):
    return [row["id"] for row in payload["signals"]]


def candidate(payload):
    ids = source_refs(payload)
    fields = {key:TEXT for key in CANDIDATE_FIELDS}
    fields["sources"] = array(one(ids) if ids else TEXT, len(ids))
    return obj(fields)


def discovery(payload):
    return obj({"candidates":array(candidate(payload), 5), "favourite":maybe(one([f"C{i}" for i in range(1,6)]))})


def challenge(payload):
    ids = [row["id"] for row in payload["candidates"]]
    refs = source_refs(payload)
    requirements = payload["mission"]["requirements"]
    fit = obj({"requirement":one(requirements) if 0<len(requirements)<=256 and sum(map(len,requirements))<8000 else TEXT,
               "check":TEXT, "status":one(["supported","unresolved","unsupported"])})
    def branch(has_challenger):
        # A C(n+1) choice is syntactically possible only in the branch actually supplying that candidate.
        valid = ids + ([f"C{len(ids)+1}"] if has_challenger else [])
        objection = obj({"candidate":one(valid) if valid else TEXT, "target":one(["answer","set","test"]),
                         "claim":TEXT, "source":maybe(one(refs)) if refs else NIL, "quote":maybe(TEXT),
                         "predicate":one(["source withdrawn","document unavailable"])}, optional=("predicate",))
        return obj({"challenger":candidate(payload) if has_challenger else NIL,
                    "objections":array(objection, 24 if valid else 0),
                    "decision":one(["build","incumbent","defer","stop"]),
                    "selected":maybe(one(valid)) if valid else NIL, "reason":TEXT, "fit":array(fit,100)})
    return {"anyOf":[branch(False),branch(True)]}


def construction_proposal(payload):
    kind, definition = payload["kind"], payload["definition"]
    if kind == "manifest_audit":
        manifest = {"type":"object","properties":{},"required":[],
                    "additionalProperties":{"type":"string","minLength":64,"maxLength":64}}
        program = {"anyOf": [obj({"use_frozen_manifest": {"const": True}}), obj({"manifest":manifest})]}
    elif kind == "record_migration":
        if "demonstrations" in definition:
            fields = definition["input_fields"]
            target_names = [t["name"] for t in definition["targets"]]
        else:
            columns = definition["columns"]
            fields = definition.get("input_fields") or sorted({field for col in columns
                for field in (col["sources"] if "sources" in col else [col["source"]])})
            target_names = [col["target"] for col in columns]
        source, target = one(fields), one(target_names)
        kind_type, separator = one(sorted(construction.TYPES)), one(construction.SEPARATORS)
        split = obj({"separator":separator,"index":{"type":"integer","minimum":-8,"maximum":7}})
        single = obj({"source":source,"target":target,"type":kind_type,"split":split}, optional=("split",))
        joined = obj({"sources":{"type":"array","items":source,"minItems":2,"maxItems":4},
                      "separator":separator,"target":target,"type":kind_type})
        program = obj({"columns":array({"anyOf":[single,joined]},construction.MAX_FIELDS),
                       "extra_fields":one(["drop","reject"]),
                       "input_fields":array(source,construction.MAX_FIELDS)},optional=("input_fields",))
    else:
        raise ValueError("No local output grammar is defined for the requested construction family.")
    return obj({"kind":{"const":kind},"program":program})


def for_stage(stage, payload):
    if stage == "discover":
        return discovery(payload)
    if stage == "challenge":
        return challenge(payload)
    if stage in ("construct","direct_construct","repair"):
        return construction_proposal(payload)
    # A new specification is free-form JSON pending fresh operator checks.
    return None
