"""Ω Singularity Direction Engine — exact bounded epistemic-direction experiment.

NOT an autonomous research agent, new physics, or evidence of commercial demand.
This first instrument shows when improving an algorithm on a fixed observation
channel cannot reveal the desired property, and when changing the observation
channel may be worthwhile after complete alternatives and costs are considered.

All amounts are *illustrative non-monetary utility units*. A conditionally
optimal plan is not a globally optimal scientific or commercial strategy.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from math import sqrt, isfinite
import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Iterable

SQRT2 = sqrt(2.0)
TARGET = (1/SQRT2, -1/SQRT2)  # A property invisible to same-channel measurements.
ORIGINAL = (1/SQRT2, 1/SQRT2)
SENSOR = TARGET


@dataclass(frozen=True)
class Channel:
    name: str
    vector: tuple[float,float]
    setup: int
    reading: int
    classification: str  # incumbent, installed, or proposed

    def __post_init__(self):
        if self.setup < 0 or self.reading <= 0:
            raise ValueError("positive finite costs required")
        if self.classification not in {"installed", "incumbent", "proposed"}:
            raise ValueError("unknown channel authority")
        if len(self.vector) != 2 or not all(isfinite(v) for v in self.vector):
            raise ValueError("finite 2D channel required")


@dataclass(frozen=True)
class World:
    label: str
    channels: tuple[Channel, ...]
    budget: int
    acceptance_variance: float
    accepted_value: int
    noise_std: float = 0.2

    def __post_init__(self):
        if not self.channels or len(set(c.name for c in self.channels)) != len(self.channels):
            raise ValueError("nonempty distinct channels required")
        if self.budget < 0 or self.accepted_value < 0:
            raise ValueError("invalid budget/value")
        if not 0 < self.acceptance_variance <= 1 or self.noise_std <= 0:
            raise ValueError("invalid uncertainty")


def posterior(counts: tuple[int, ...], channels: tuple[Channel, ...], noise_std: float):
    """Conjugate normal update, identity prior, exact closed-form 2x2 inverse."""
    p00 = p11 = 1.0
    p01 = 0.0
    scale = noise_std**-2
    for k,ch in zip(counts,channels):
        x,y = ch.vector
        p00 += k*x*x*scale
        p01 += k*x*y*scale
        p11 += k*y*y*scale
    determinant = p00*p11 - p01**2
    if determinant <= 0:
        raise ArithmeticError("invalid precision matrix")
    cov = ((p11/determinant, -p01/determinant),
           (-p01/determinant, p00/determinant))
    w0,w1 = TARGET
    loss = w0*w0*cov[0][0] + 2*w0*w1*cov[0][1] + w1*w1*cov[1][1]
    return loss,cov


def cost(counts: tuple[int, ...], channels: tuple[Channel, ...]):
    return sum(ch.setup + count*ch.reading for count,ch in zip(counts,channels) if count)


def find_plan(world: World):
    """Exact finite exhaustive solution; permits no investment or strong incumbent route.

    Maximizes (accepted outcome utility - spend) *under the declared model*.
    No budget can be spent unless a relevant measurement route exists.
    """
    max_each = [max(0,(world.budget - ch.setup)//ch.reading) for ch in world.channels]
    best = None
    possibilities=0
    feasible=0
    for counts in product(*(range(n+1) for n in max_each)):
        possibilities+=1
        spend=cost(counts,world.channels)
        if spend>world.budget:
            continue
        feasible+=1
        loss,_=posterior(counts,world.channels,world.noise_std)
        accepted = loss <= world.acceptance_variance + 1e-12
        utility=(world.accepted_value if accepted else 0)-spend
        new_constructed=any(k and ch.classification=="proposed" for k,ch in zip(counts,world.channels))
        incumbent_used=any(k and ch.classification=="incumbent" for k,ch in zip(counts,world.channels))
        record={"counts":dict(zip((c.name for c in world.channels),counts)),
                "cost_units":spend,"posterior_target_variance":round(loss,12),
                "model_acceptance":accepted,"net_utility_units":utility,
                "proposed_instrument_used":new_constructed,
                "incumbent_used":incumbent_used}
        # Tie-break: less spend, then prefer already-existing channels to invention.
        key=(utility,-spend,-int(new_constructed),int(incumbent_used))
        if best is None or key>best[0]:
            best=(key,record)
    if best is None:
        raise RuntimeError("zero-action plan should always be feasible")
    return dict(best[1], enumerated_plans=possibilities, budget_feasible_plans=feasible,
                accepted_evidence="CONDITIONAL_MODEL_ONLY")


def simulate(world: World, plan: dict, seed: int=20261116, trials: int=4000):
    """Independent Monte Carlo check of conditional MSE, no hidden truth used in planning."""
    rng=random.Random(seed)
    counts=tuple(plan['counts'][c.name] for c in world.channels)
    _,cov=posterior(counts,world.channels,world.noise_std)
    variance_sum=0.0
    for _ in range(trials):
        t0,t1=rng.gauss(0,1),rng.gauss(0,1)
        precision_y0=precision_y1=0.0
        for k,ch in zip(counts,world.channels):
            a,b=ch.vector
            for _ in range(k):
                y=a*t0+b*t1+rng.gauss(0,world.noise_std)
                precision_y0 += a*y/world.noise_std**2
                precision_y1 += b*y/world.noise_std**2
        m0=cov[0][0]*precision_y0 + cov[0][1]*precision_y1
        m1=cov[1][0]*precision_y0 + cov[1][1]*precision_y1
        discrepancy = TARGET[0]*(t0-m0) + TARGET[1]*(t1-m1)
        variance_sum += discrepancy**2
    return round(variance_sum/trials,7)


def world_examples():
    same=Channel('installed_same_channel',ORIGINAL,0,1,'installed')
    proposed=Channel('constructed_orthogonal_channel',SENSOR,3,1,'proposed')
    incumbent=Channel('existing_supplier_channel',SENSOR,2,1,'incumbent')
    wrong=Channel('proposed_but_uninformative_channel',ORIGINAL,2,1,'proposed')
    return [
        World('new_measurement_opens_a_previously_unobservable_property',(same,proposed),5,.05,9),
        World('existing_complete_supplier_dominates_new_construction',(same,proposed,incumbent),5,.05,9),
        World('unfunded_construction_does_not_become_feasible',(same,proposed),3,.05,9),
        World('low_value_outcome_does_not_warrant_construction',(same,proposed),5,.05,2),
        World('new_label_without_new_information_fails',(same,wrong),5,.05,9),
    ]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=None)
    p.add_argument('--trials',type=int,default=4000)
    p.add_argument('--seed',type=int,default=20261116)
    args=p.parse_args()
    if args.trials<1 or args.trials>100_000:p.error('1..100000 trials required')
    items=[]
    for w in world_examples():
        plan=find_plan(w)
        plan['empirical_target_mse']=simulate(w,plan,args.seed,args.trials)
        items.append({'world':w.label,'budget_units':w.budget,
                      'accepted_value_units':w.accepted_value,
                      'target_variance_limit':w.acceptance_variance,
                      'noise_std':w.noise_std,'plan':plan})
    no_go_loss,_=posterior((1000,), (world_examples()[0].channels[0],), .2)
    evidence={
        'schema':'montreal-ai.omega.direction.v0',
        'proposition':'Direction changes when information channel changes, not by repeating the same observation.',
        'scope':'exactly solved authored 2D linear-Gaussian hypothetical experiment; no physical invention or autonomous research achievement',
        'worlds':items,
        'nullspace_certificate':{
            'target':TARGET,'installed_sensor':ORIGINAL,
            'dot_product':round(sum(a*b for a,b in zip(TARGET,ORIGINAL)),12),
            'posterior_target_variance_after_1000_installed_readings':round(no_go_loss,12),
            'statement':'The target is orthogonal to the installed observation channel; no number of repeats on it adds information about the target under this model.'},
        'limits':[
            'Invented sensor is an authored hypothetical measurement operation, not a built/calibrated physical device.',
            'Values and costs are illustrative dimensionless units, not actual funding, bids, prices, revenue or profit.',
            'Same-information no-go follows from an authored linear observation model and does not prove a claim about real-world tomography.',
            'A good existing supplier wins when it offers the same accepted outcome at lower complete cost.',
            'This exact finite optimization does not establish an optimal research strategy in the open world.',
            'No model API is used; this does not demonstrate autonomous LLM direction invention.'
        ],
        'sources':[
            'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/campaign/blue-sky-064/CANDIDATES.md',
            'https://arxiv.org/abs/2610.19159',
            'https://www.nature.com/articles/s43586-026-00534-y'
        ],
        'seed':args.seed,'trials':args.trials,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    if args.output:
        args.output.parent.mkdir(exist_ok=True,parents=True)
        args.output.write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print('Ω DIRECTION ENGINE v0 — bounded structural experiment')
    for world in items:
        p=world['plan']
        print(f"{world['world']}: chosen {p['counts']} cost {p['cost_units']} risk {p['posterior_target_variance']:.6f} net={p['net_utility_units']} model_accept={p['model_acceptance']}")
    print('nullspace floor after 1000 repeats:', no_go_loss)
    if args.output:print('Wrote',args.output)

if __name__=='__main__':main()
