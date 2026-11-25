"""Author only. Calibrate selection without using candidate model outputs."""
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from random import Random
from secrets import randbits
import json
import sys

reference = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(reference.parent))
from strategic_reference import exact

root = Path(__file__).resolve().parent
seed = randbits(128)
rng = Random(seed)
planning = []


def raw_advantage(case):
    return Fraction(exact({**case, "fee": 0})["advantage_after_fee"])


def draw(low, high, choice, require_useful=False):
    while True:
        n = rng.randint(low, high)
        rows = [[rng.randint(-19, 22), rng.randint(-19, 22)] for _ in range(n)]
        if len({tuple(a) for a in rows}) != n:
            continue
        q0, q1 = rng.sample(range(46, 99), 2)
        if abs(q0-q1) < 11 or max(q0,q1) < 68:
            continue
        case = {"payoffs":rows,"accuracy":[q0,q1],"fee":0}
        gain = raw_advantage(case)
        if gain < Fraction(1, 5):
            continue
        if require_useful and abs(gain-raw_advantage({**case,"payoffs":rows[:2]})) < Fraction(1, 2):
            continue
        for fee in rng.sample(range(1, 13),12):
            delta = gain-fee
            criterion = delta > Fraction(1, 10) if choice=="BUY" else delta < -Fraction(1, 10)
            if criterion:
                return {**case, "fee":fee}


for family, n_range in (("asymmetric-two", (2,2)), ("asymmetric-extra-action", (3,5))):
    for choice in ("BUY","SKIP"):
        for _ in range(6):
            case = draw(*n_range, choice, family=="asymmetric-extra-action")
            planning.append((family, None, case))

for choice in ("BUY","SKIP"):
    for k in range(3):
        base = draw(3,4,choice)
        shift = rng.choice([-10,-7,5,9])
        pair = f"shift-{choice.lower()}-{k}"
        moved = {**base, "payoffs":[[x+shift,y+shift] for x,y in base["payoffs"]]}
        assert exact(base)["choice"] == exact(moved)["choice"] == choice
        planning.extend([("value-shift",pair,base),("value-shift",pair,moved)])

for a,q,fee in [(15,50,5),(10,75,6),(21,60,9),(12,80,8)]:
    case = {"payoffs":[[a,-a],[-a,a]],"accuracy":[q,100],"fee":fee}
    assert raw_advantage(case) == fee
    planning.append(("boundary-tie",None,case))
    if a in (15,10):
        for step in [-1,1]:
            planning.append(("boundary-adjacent",f"boundary-{a}",{**case,"fee":fee+step}))
for rows,q in [
    ([[15,9],[2,8],[1,-5]],[99,72]),
    ([[-3,18],[-4,1],[-17,12]],[88,97]),
    ([[6,14],[-4,5],[5,3],[2,-6]],[100,91]),
    ([[8,17],[1,2],[-9,12]],[95,69]),
]:
    case = {"payoffs":rows,"accuracy":q,"fee":0}
    assert raw_advantage(case) == 0
    planning.append(("boundary-tie",None,case))

assert len(planning)==48
rng.shuffle(planning)
cases, refs = [], []
for n,(family,pair,raw) in enumerate(planning):
    case = {"id":f"sg-{n+1:02d}",**raw}
    assert all(-32<=p<=32 for row in case["payoffs"] for p in row)
    cases.append(case)
    refs.append({"id":case["id"],"family":family,"pair":pair,**exact(case)})
assert len({json.dumps({k:v for k,v in x.items() if k!="id"},sort_keys=True) for x in cases})==48


def save(name, records, lines=False):
    at = root / name
    with at.open("x",encoding="utf-8") as stream:
        if lines:
            for x in records:
                stream.write(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n")
        else:
            json.dump(records,stream,sort_keys=True,indent=2)
            stream.write("\n")
    at.chmod(0o600)
    return sha256(at.read_bytes()).hexdigest()


save("strategic.private.seed.json",{"seed":str(seed)})
d1 = save("strategic.private.cases.jsonl",cases,lines=True)
d2 = save("strategic.private.oracle.json",refs)
registration = {
    "schema":"frontier/independent-strategic-confirmation/v1",
    "registered_at_utc":datetime.now(timezone.utc).isoformat(),
    "input_sha256":d1,
    "oracle_sha256":d2,
    "generator_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
    "exact_reference_sha256":sha256(reference.read_bytes()).hexdigest(),
    "planned_cases":48,
    "predeclared_strata":{"asymmetric-two":12,"asymmetric-extra-action":12,"value-shift":12,
        "boundary-tie":8,"boundary-adjacent":4},
    "convention":"BUY exactly when the robust gain after fee is positive. Ties SKIP.",
    "materiality":"Primary admission requires at least 36/48 exact decisions, eight more correct than the strongest matched no-tool base comparator, at least 60% exact decisions in each of the three 12-case strata, and at most two false purchases on the eight exact ties. Compare actual rates, robust regret, abstention and wall time separately. Ordinary exact-solver routing is a strong complete control. Paired cases share a structure and the population is synthetic.",
    "scope":"Independent case authorship and private evaluation files under the same administrative environment. Not separated custody or an operational claim."
}
d3=save("strategic.registration.json",registration)
print(json.dumps({"denominator":len(cases),"registration_sha256":d3,"input_sha256":d1,"oracle_sha256":d2}))
