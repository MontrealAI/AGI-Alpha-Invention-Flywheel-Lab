"""Reviewed local succession logic; not a production security boundary."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import NamedTuple
import hashlib,json

@dataclass(frozen=True)
class Context:
    mission: str
    source: str
    supplier: str
    environment: str
    evaluator: str
    policy: str
    def __post_init__(self):
        if any(type(v) is not str or not v.strip() for v in asdict(self).values()):
            raise ValueError('Every context identity must be a nonempty string')
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()

class Warrant(NamedTuple):
    context: str
    not_before: int
    expires: int
    actions: frozenset[str]

def checked_time(value):
    if type(value) is not int or value < 0:
        raise ValueError('Time must be a nonnegative integer, not bool or float')
    return value

def checked_scope(actions):
    if not isinstance(actions,(tuple,list,set,frozenset)) or not actions:
        raise ValueError('A nonempty explicit collection of actions is required')
    if any(type(a) is not str or not a.strip() for a in actions):
        raise ValueError('Action identities must be nonempty strings')
    return frozenset(actions)

class Institution:
    """Local state-machine witness, not a hardened authorization service.

    Times are explicit logical ticks. Production needs a trusted clock and
    complete mediation; a caller-supplied integer does not establish either.
    """
    def __init__(self, identity, knowledge=()):
        if type(identity) is not str or not identity.strip():
            raise ValueError('Nonempty institution identity required')
        if not isinstance(knowledge,(tuple,list)) or any(type(k) is not str for k in knowledge):
            raise ValueError('Knowledge must be an explicit list/tuple of strings')
        self.identity=identity; self.knowledge=tuple(knowledge)
        self.proof=None; self.authority=None; self.history=[]; self._clock=0
    def _time(self,now):
        checked_time(now)
        if now < self._clock: raise ValueError('State transition cannot rewind time')
        return now
    def qualify(self,ctx,passed,producer,verifier,expires,supported_actions=('deliver',),*,now=0):
        self._time(now)
        # Beginning a current requalification withdraws the previous warrant.
        self.proof=None; self.authority=None; self._clock=now
        self.history.append(('qualification_started',str(now)))
        checked_time(expires)
        if (not isinstance(ctx,Context) or type(producer) is not str or not producer.strip()
                or type(verifier) is not str or not verifier.strip()
                or producer==verifier or passed is not True or expires<=now):
            raise ValueError('Valid context, distinct roles, passing evidence and future expiry required')
        scope=checked_scope(supported_actions)
        self.proof=Warrant(ctx.digest(),now,expires,scope)
        self.history.append(('qualified',ctx.digest()))
    def authorize(self,ctx,actions,owner_approval,now,expires):
        self._time(now); checked_time(expires); scope=checked_scope(actions)
        if owner_approval is not True or not isinstance(ctx,Context) or self.proof is None:
            raise ValueError('Explicit approval, context and proof required')
        p=self.proof
        if (p.context!=ctx.digest() or not p.not_before<=now<expires<=p.expires
                or not scope<=p.actions):
            raise ValueError('Context, scope or validity mismatch')
        self.authority=Warrant(p.context,now,expires,scope); self._clock=now
        self.history.append(('authorized',p.context))
    def permits(self,ctx,action,now):
        if (type(now) is not int or now<self._clock or not isinstance(ctx,Context)
                or type(action) is not str or not self.proof or not self.authority):
            return False
        return all(w.context==ctx.digest() and w.not_before<=now<w.expires
                   and action in w.actions for w in (self.proof,self.authority))
    def revoke(self,*,now=None):
        now=self._clock if now is None else self._time(now)
        self.authority=None; self._clock=now
        self.history.append(('revoked',self.identity))
    def export(self):
        return {'schema':1,'identity':self.identity,'knowledge':list(self.knowledge),
                'history':[list(x) for x in self.history]}
    @classmethod
    def restore(cls,bundle):
        if (type(bundle) is not dict or set(bundle)!={'schema','identity','knowledge','history'}
                or type(bundle['schema']) is not int or bundle['schema']!=1):
            raise ValueError('Invalid or privilege-bearing portable bundle')
        if (type(bundle['history']) is not list or any(
                type(x) is not list or len(x)!=2 or any(type(v) is not str for v in x)
                for x in bundle['history'])):
            raise ValueError('Malformed historical record')
        out=cls(bundle['identity'],bundle['knowledge'])
        out.history=[tuple(x) for x in bundle['history']]
        return out
