"""Bind the actual construction to the existing protected simulated exchange.

No buyer price, consent or complete costs are generated to force admission.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
PINNED={'protected_exchange.py':'378bf67ae24c18ad58b684ce8b13492fd06f8556','contracts.py':'a26129ff4ee72ed8b4f8467f6c9de07b8d67508c'}
for name,expected in PINNED.items():
    raw=(ROOT/'vendor/alpha_claim'/name).read_bytes()
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=expected:raise ValueError('PINNED_EXCHANGE_SOURCE_CHANGED')
sys.path.insert(0,str(ROOT))
from vendor.alpha_claim.contracts import digest
from vendor.alpha_claim.protected_exchange import ProtectedExchange
from inventions.phase_codes.runtime_v2 import Instrument

def run(candidate,certificate,output):
    start=time.monotonic();candidate=pathlib.Path(candidate);certificate=pathlib.Path(certificate);out=pathlib.Path(output);out.mkdir(parents=True,exist_ok=False)
    raw=candidate.read_bytes();cert=certificate.read_bytes();code=json.loads(raw);proof=json.loads(cert)
    fields=['n','physical_weights','global_phase_exponent','logical_order','codewords']
    projection=(json.dumps({k:code[k] for k in fields},indent=2)+'\n').encode()
    if (proof.get('status')!='CERTIFIED_EXACT_ALGEBRA_ONLY'
        or proof.get('candidate_sha256')!=hashlib.sha256(projection).hexdigest()
        or proof.get('verifier_sha256')!='83391efeb99982c276e8662ead9d706be0c7ce02f8f0281c4e072d012ffe5b4d'
        or not all(proof.get('checks',{}).values())):
        raise ValueError('TECHNICAL_CERTIFICATE_BINDING_FAILED')
    eligibility=Instrument(candidate,hashlib.sha256(raw).hexdigest()).recovery_contract
    task={'schema':'phase-code-delivery/v1','candidate_sha256':hashlib.sha256(raw).hexdigest(),'certificate_sha256':hashlib.sha256(cert).hexdigest(),'buyer_issued_specification':None,'price_microUSD':None,'complete_costs':None}
    def validate(t):
        if t!=task:raise ValueError('SOURCE_BOUND_TASK_MISMATCH')
    def check(t,artifact):
        validate(t)
        return {'accepted':False,'decisive':False,'artifactBound':artifact==code,'reason':'NO_BUYER_ISSUED_SPEC_PRICE_OR_COMPLETE_COSTS','technical_scope':'Exact mathematical code and ideal recovery are not a paid hardware delivery.'}
    ex=ProtectedExchange(out/'exchange.sqlite',key=b'q'*32,contract='phase-code/unpriced-research-boundary/v1',validate=validate,check=check,opening=0,working=0)
    try:
        acceptance=check(task,code)
        try:ex.offer('unpriced-proposal','unadmitted-research-beneficiary',None,'nonrecourse-simulated',task,20)
        except ValueError as exc:offer={'admitted':False,'reason':str(exc)}
        else:raise AssertionError('UNPRICED_OFFER_ADMITTED')
        try:ex.reserve_investment('additional-capability',1,1,intent_hash=digest(task))
        except ValueError as exc:investment={'decision':'DEFER','minimum_test_cap_simulated_microUSD':1,'reason':str(exc),'expected_value_argument':'Positive sentinel to exercise the funding gate, not a forecast or buyer valuation.'}
        else:raise AssertionError('UNFUNDED_SUCCESSOR_ADMITTED')
        snapshot=ex.snapshot();assert snapshot['revenue']==snapshot['collections']==snapshot['unrestrictedEarned']==0
        orders=int(ex.db.execute('SELECT COUNT(*) FROM trades').fetchone()[0]);assert orders==0
    finally:ex.close()
    r={'schema':'phase-code-commercial-boundary/v2','mode':'SIMULATED_ONLY_NO_TRANSACTIONS','task':task,'runtime_eligibility':eligibility,'technical_delivery_acceptance':acceptance,'offer':offer,'protected_settlement':'No order/funding/release created without an independently grounded price and acceptance contract. No fictional consent or sale.','admitted_orders':orders,'settlement_snapshot':snapshot,'complete_cost_profit':None,'unpriced_costs_remain_off_ledger':True,'recorded_real_revenue_USD':0,'simulated_receipts_microUSD':0,'available_simulated_earned_funds_microUSD':0,'earned_funded_successor':investment,'wall_seconds':time.monotonic()-start,'source':{'repository':'MontrealAI/AGI-Alpha-Agent-v0','commit':'a6b2d869a7736e7c414d7d615d86c616c2f82615','git_blobs':PINNED},'decision':'TECHNICAL_ARTIFACT_ONLY; COMMERCIAL_COHORT_NOT_ADMITTED; FUNDED_SUCCESSOR_DEFERRED'}
    (out/'COMMERCIAL.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'orders':orders,'simulated_receipts':0,'earned_funded_successor':investment['decision']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--certificate',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.candidate,a.certificate,a.output)
