"""Bounded, syndrome-preserving DEM-class mass correction kernel (original research).
Mass is exact ONLY over the deduplicated candidate pool, not entire logical cosets.
"""
import math
from collections import defaultdict
from functools import reduce
from operator import xor

def mask(indices):
    return reduce(xor, (1 << int(i) for i in indices), 0)

def bits(m):
    while m:
        b=m & -m; yield b.bit_length()-1; m ^= b

class MassKernel:
    def __init__(self, decoder, pair_cap=200000, move_cap=4096, expansion_cap=512):
        self.decoder=decoder; self.expansion_cap=expansion_cap
        self.h=[mask(e.symptom.detectors) for e in decoder.errors]
        self.l=[mask(e.symptom.observables) for e in decoder.errors]
        self.w=[e.likelihood_cost for e in decoder.errors]
        # A cost-ordered GF(2) basis provides a non-oracle valid fallback.
        self.basis={}
        for i in sorted(range(len(self.h)),key=self.w.__getitem__):
            h=self.h[i]; v=1<<i
            while h:
                j=h.bit_length()-1
                if j not in self.basis: self.basis[j]=(h,v);break
                a,b=self.basis[j]; h ^= a; v ^= b
        # Local zero-syndrome triples from pairs sharing a detector, plus equal columns.
        columns=defaultdict(list); incidence=defaultdict(list); moves=set()
        for i,h in enumerate(self.h):
            if h==0:moves.add(1<<i)
            columns[h].append(i)
            for d in bits(h): incidence[d].append(i)
        for ids in columns.values():
            for i in ids[1:]: moves.add((1<<ids[0]) ^ (1<<i))
        seen=set(); attempts=0
        for d,ids in sorted(incidence.items()):
            ids=sorted(ids,key=self.w.__getitem__)
            for a,i in enumerate(ids):
                if attempts>=pair_cap:break
                for j in ids[a+1:]:
                    if attempts>=pair_cap:break
                    if (i,j) in seen:continue
                    seen.add((i,j));attempts+=1
                    for k in columns.get(self.h[i]^self.h[j],[]):
                        if k!=i and k!=j:moves.add((1<<i)^(1<<j)^(1<<k))
            if attempts>=pair_cap:break
        self.moves=sorted(moves,key=lambda m:(self.cost(m),m))[:move_cap]
        assert all(self.syndrome(m)==0 for m in self.moves)
        self.prep_stats={'pair_attempts':attempts,'moves':len(self.moves),'rank':len(self.basis),'zero_syndrome_mechanisms':sum(h==0 for h in self.h)}
    def syndrome(self,m):return reduce(xor,(self.h[i] for i in bits(m)),0)
    def logical(self,m):return reduce(xor,(self.l[i] for i in bits(m)),0)
    def cost(self,m):return sum(self.w[i] for i in bits(m))
    def fallback(self,s):
        m=0
        while s:
            h,v=self.basis[s.bit_length()-1];s ^= h;m ^= v
        return m
    def pool(self,syndrome,orders=4,beam=10):
        s=mask(syndrome.nonzero()[0]); seeds=set();invalid=0
        for order in range(orders):
            m=mask(self.decoder.decode_to_errors(syndrome,order,beam))
            if self.syndrome(m)==s:seeds.add(m)
            else:invalid+=1
        fallback=not seeds
        if fallback:seeds.add(self.fallback(s))
        # Fixed bounded expansion; rank local neighbors by actual posterior cost.
        return self.expand(seeds,s),{'invalid_searches':invalid,'fallback':fallback,'seed_count':len(seeds)}
    def expand(self,seeds,s):
        candidates=set(seeds)
        per=max(1,self.expansion_cap//len(seeds))
        for seed in sorted(seeds):
            neighbors=sorted(((self.cost(seed^move),seed^move) for move in self.moves))
            candidates.update(m for _,m in neighbors[:per])
        assert all(self.syndrome(m)==s for m in candidates)
        return candidates
    def decide(self,pool):
        scored=sorted((self.cost(m),m,self.logical(m)) for m in pool)
        minimum=scored[0][0]; mass=defaultdict(float)
        for cost,_,logical in scored:mass[logical]+=math.exp(minimum-cost)
        # deterministic tie break agrees with minimum when masses tie
        best=scored[0][2]; summed=max(mass,key=lambda l:(mass[l],l==best,-l))
        return best,summed,mass
