import argparse,copy,hashlib,json
from fractions import Fraction
from pathlib import Path
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.complete_offer_market import validate_policy,_choices
from enterprise.services import synthetic_order,produce
from enterprise.checkers import audit_delivery

MICRO=1000000
PRICES=(2,5,10,20)
WORLDS={'commodity':{'self_service':2,'human_ai':5},'central':{'self_service':5,'human_ai':10},'friction':{'self_service':12,'human_ai':20}}
SOURCES=('adaptive_enterprise/strategies.py','connected_enterprise/complete_offer_market.py','enterprise/services.py','enterprise/checkers.py','commercial/service.py','commercial/service_verifier.py')
OUTCOMES={
 'reconciliation':('Complete receivables close and exception schedule','Exact safe invoice/payment matching, partition of all rows, integer-cents conservation, explicit unmatched/ambiguous exceptions; no certified audit or debt collection.'),
 'kpi_variance':('Complete period variance schedule','Every supplied metric exactly once; exact prior/current/delta, direction and zero-base ratios; no inferred causal explanation or forecast.'),
 'evidence_matrix':('Complete requirements-to-evidence response','Every scoped requirement exactly once, verbatim supplied facts with source IDs, missing/conflicting sources explicit; no certification or unsupported eligibility claims.')}
REFERENCES=[
 {'url':'https://docs.getdbt.com/docs/build/data-tests','basis':'Reusable uniqueness, non-null, relationships and business-specific data tests; established production/checking method and competent self-service alternative, not demand evidence.'},
 {'url':'https://docs.getdbt.com/guides/set-up-ci','basis':'State-modified dependencies support established incremental revalidation; no discovery claim.'},
 {'url':'https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates','basis':'Dependency-update PR creation is already supplied; maintenance would require additional complete behavior checks and native implementation.'},
 {'url':'https://www.w3.org/TR/prov-overview/','basis':'Established provenance interchange, not proof of factual correctness.'},
 {'url':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces','basis':'Public unauthenticated submission/XBRL observation is possible; not customer demand.'},
 {'url':'https://www.bls.gov/ooh/business-and-financial/accountants-and-auditors.htm','basis':'Inspected May2025 median wage83680USD/year; wage reference, no measured complete task time.'},
 {'url':'https://www.bls.gov/news.release/ecec.nr0.htm','basis':'Inspected June2026 private-industry benefits30pct of compensation, aggregate only. Occupation-specific overhead and task durations unknown.'}]

def encoded(v):return (json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def build():
 root=Path(__file__).resolve().parents[1]
 candidates=[];screens=[]
 for sid,(outcome,acceptance) in OUTCOMES.items():
  offer=copy.deepcopy(next(o for o in offer_catalog() if o['service_id']==sid and o['method']=='canonical'))
  offer.update(outcome=outcome,verification=acceptance)
  raw=synthetic_order(sid,983);artifact=produce(sid,raw)
  good=audit_delivery(sid,raw,artifact)['accepted'];bad=copy.deepcopy(artifact)
  if sid=='reconciliation':bad['totals']['matched_invoice_cents']+=1
  elif sid=='kpi_variance':bad['rows'][0]['delta_cents']+=1
  else:bad['rows'][0]['value']='Unsupported assertion'
  rejected=not audit_delivery(sid,raw,bad)['accepted']
  if not good or not rejected:raise ValueError('CANDIDATE_INDEPENDENT_ACCEPTANCE_FAILED:'+sid)
  candidates.append({'id':sid,'outcome':outcome,'complete_contract':offer,'price_variants':[{'id':sid+':canonical:price'+str(p),'price_microUSD':p*MICRO} for p in PRICES],
    'terms':{'quote_expiry_hours':24,'lead_hours':3,'payment':'Voluntary qualified order before production; independently accepted outcome before protected cleared payment;48h clearing,240h deadline hypothesis.','support':'One bounded source correction, including documented limitations.','recourse':'Reject unsupported output; bounded correction or simulated refund; preserve fee/principal tail.','risk':'Seller bears failed production/checking and recourse; buyer supplies scoped accurate facts; no purchase/renewal compelled.'},
    'necessary_means':['Canonical deterministic producer','Independent source/completeness checker','Explicit source identities and USD units','Qualified reachable audience and capacity','Native JournalAccount and adaptive Account for any subsequent fiscal operation'],
    'outside_choices':['Human complete service','Human usingAI complete service','Autonomous rival complete service','Free complete self-service plus explicit operator opportunity cost','No purchase'],
    'reject':['Unavailable or unauthorized input','Missing explicit units','Unresolved ambiguity','Expired quote','Insufficient current cash/capacity','Outside choice dominates','Independent acceptance failure','Nonpayment/refund'],
    'smallest_decisive_test':'Existing complete producer output accepted; independently corrupted output rejected; exact public outside-choice pricing screen; then native order,delivery,collection and complete fiscal costs before commercial claim.',
    'executed_checks':{'good_accepted':good,'corrupt_rejected':rejected,'input_sha256':hashlib.sha256(encoded(raw)).hexdigest(),'output_sha256':hashlib.sha256(encoded(artifact)).hexdigest()},
    'retained_means':'Reusable checked source/schema/context may reduce later onboarding; available initial purchase/build must remain a baseline. Ordinary reuse, not new discovery or artificially earned-only dependence.'})
  for world,terms in WORLDS.items():
   outside=[{'name':'self_service','provider':'self_service','service_id':sid,'price':0,'quality_bps':10000,'delay_cost':terms['self_service']*MICRO}]
   outside.extend({'name':name,'provider':'rival' if name=='autonomous' else 'human','service_id':sid,'price':price*MICRO,'quality_bps':10000,'delay_cost':0} for name,price in [('human_ai',terms['human_ai']),('human',30),('autonomous',6)])
   profile={'id':sid,'services':[sid],'price_grids':{sid:[p*MICRO for p in PRICES]},'atoms':[{'weight_bps':w,'budget_microUSD':b*MICRO,'values':{sid:v*MICRO}} for w,b,v in [(2500,20,25),(5000,30,40),(2500,40,60)]],'outside_options':outside}
   validate_policy({'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile]})
   ctx={'profile':profile,'observed_spend':0,'rival_available':True};quotes=[]
   for price in PRICES:
    probability=Fraction(0)
    for atom in profile['atoms']:
     choices=_choices(ctx,atom,atom['budget_microUSD'],sid,price*MICRO)
     if any(c['provider']=='us' for c in choices):probability+=Fraction(atom['weight_bps'],10000*len(choices))
    collected=probability*Fraction(98,100)*price
    contribution=collected-probability*(Fraction(5,2)+Fraction(price*290,10000)+Fraction(3,10))-Fraction(3,20)
    annual=144*contribution-Fraction(75)-Fraction(365,10)
    quotes.append({'price_microUSD':price*MICRO,'probability_us':str(probability),'expected_collections_usd':str(collected),'expected_contribution_before_shared_cost_tax_usd':str(contribution),'conditional_144_exposures_profit_before_tax_usd':str(annual),'conditional_after20pct_positive_tax_usd':str(annual-max(Fraction(0),annual)*Fraction(1,5))})
   ranked=sorted(quotes,key=lambda q:(-Fraction(q['expected_contribution_before_shared_cost_tax_usd']),q['price_microUSD']))
   screens.append({'candidate':sid,'world':world,'public_profile':profile,'quotes':quotes,'best_exact_price_microUSD':ranked[0]['price_microUSD'],'best_expected_contribution_usd':ranked[0]['expected_contribution_before_shared_cost_tax_usd'],'no_offer_expected_contribution_usd':'0','decision':'offer' if Fraction(ranked[0]['expected_contribution_before_shared_cost_tax_usd'])>0 else 'hold'})
 return {'schema':'compounding-candidates055/v1','scope':'EXPOSED_AUTHORED_DEVELOPMENT_NOT_FISCAL_NATIVE_RESULT','base_commit':'4a87b455373be72811ad3a0c654a116c3604a374','source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SOURCES},'public_evidence':REFERENCES,'candidates':candidates,'software_maintenance':'Conceptually screened, not executable/admitted: canonical native producer/checker absent. Dependabot already raises updatePRs; extra complete-outcome implementation and liability burden unmeasured.'}, {'schema':'compounding-screen055/v1','scope':'EXACT_EXPECTED_VALUE_SCREEN_NOT_NATIVE_ACCOUNT_REVENUE','price_grid_usd':list(PRICES),'world_weights':None,'assumptions':'Authored, exposed and uncalibrated: complete quality equal; human30USD, autonomous6USD, humanAI5/10/20USD; free selfservice inconvenience2/5/12USD. Unknown operator task durations; no fabricated staffing/review hours. Independent buyer values/budgets are not derived from our quote or wages.','costs_microUSD':{'exposure':50000,'qualification':100000,'onboarding':500000,'production':1500000,'support':250000,'supplier':250000,'payment_fixed':300000,'shared_setup':75000000,'maintenance_daily':100000},'rates_bps':{'payment':290,'nonpayment':200,'positive_profit_tax':2000},'annual_screen':'12 total prospects,4 initially owned,12 monthly request slots each=144 potential requests, not144 reachable exposures/orders/collections. Annual budget atoms180/400/580USD must be conserved in native operation. The144-exposure calculation is a conditional sensitivity, not promised reach or the primary result. Native annual business may lose after75USD setup,36.50USD maintenance and paid acquisition. No account pooling,resets or post-hoc tariff/volume increases.','cost_limitations':'Additional paid reach, incremental development, refunds/claims, tax timing,capex/depreciation and obligations must enter native account when applicable. Unknown actual assistant/host/model billing remains unknown. No zero marginal invoice inference.','results':screens,'selection':'Three outcomes tie economically under matched outside assumptions. Reconciliation selected for existing independent completeness/cents-conservation execution path. Commodity holds; central price5 ties selfservice and is not guaranteed; friction price5 wins against6USD complete autonomous rival. No novelty, causal-compounding or actual-demand claim.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'campaign/compounding-enterprise-055');p.add_argument('--check',action='store_true');a=p.parse_args()
 c,s=build();a.output.mkdir(parents=True,exist_ok=True)
 for name,value in [('CANDIDATES.json',c),('SCREEN.json',s)]:
  target=a.output/name;raw=encoded(value)
  if a.check:
   if target.read_bytes()!=raw:raise ValueError('SCREEN_SOURCE_OR_RESULT_MISMATCH:'+name)
  else:target.write_bytes(raw)
 print(json.dumps({'accepted':True,'scope':s['scope'],'candidate_checks':6,'registered_candidates':3,'registered_worlds':3,'price_rows':36,'results':[{'candidate':r['candidate'],'world':r['world'],'price':r['best_exact_price_microUSD'],'decision':r['decision'],'expected_contribution_usd':r['best_expected_contribution_usd']} for r in s['results']]},sort_keys=True))

if __name__=='__main__':main()
