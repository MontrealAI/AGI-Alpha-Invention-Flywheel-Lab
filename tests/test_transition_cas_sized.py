"""Large shape fixtures only: exact reported lower-bound byte sizes, not accounts."""
import hashlib,hmac,json,resource,time,unittest
from connected_enterprise import transition_evidence as te
from connected_enterprise.upgrades import validate_ticket
from commercial.ledger import canonical,digest

class SizedTests(unittest.TestCase):
 def test_exact_combined_lower_bound_shapes(self):
  report=[]
  for target in [42_937_362,52_345_223]:
   start=time.process_time();journal={'entries':[{'request':{'payload':''}}]}
   envelope={'body':journal,'signature':'0'*64}
   record={'connected_journal':journal,'snapshot':{'state_digest':'0'*64},'padding':''}
   pair={'prior_record':record,'prior_envelope':envelope}
   initial=len(canonical(pair));delta=target-initial
   journal['entries'][0]['request']['payload']='x'*(delta//2)
   record['padding']='x'*(delta%2)
   self.assertEqual(len(canonical(pair)),target)
   a={'file':'a'};b={'file':'b'}
   body={'schema':te.V1,'id':'synthetic-sized','account_path':'/synthetic/account',
    'from_source':{'files':a,'sha256':digest(a)},'to_source':{'files':b,'sha256':digest(b)},
    'counter':3,'expected_state_digest':'0'*64,'day':1,'historical_root':'/synthetic/source','verifier_files':{},**pair}
   key=b'synthetic-only';legacy={'body':body,'signature':hmac.new(key,te.DOMAIN+canonical(body),hashlib.sha256).hexdigest()}
   with self.assertRaisesRegex(ValueError,'BOUNDED_SOURCE_TRANSITION'):validate_ticket(legacy,key=key)
   blobs={};wire=te.externalize(body,blobs);ticket={'body':wire,'signature':hmac.new(key,te.DOMAIN+canonical(wire),hashlib.sha256).hexdigest()}
   with te.evidence_scope(blobs):self.assertEqual(validate_ticket(ticket,key=key),body)
   report.append({'shape_only_not_actual_account':True,'combined_bytes':target,'ticket_bytes':len(canonical(ticket)),
    'blob_sizes':sorted(map(len,blobs.values())),'cpu_seconds':time.process_time()-start,'peak_rss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
  print(json.dumps(report,sort_keys=True))
