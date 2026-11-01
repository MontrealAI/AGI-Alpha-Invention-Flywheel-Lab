"""Synthetic-only trust-boundary probe; never reads any actual account or key."""
import json, sys, time
from types import SimpleNamespace

TARGET_MODULE = """import sys
p=sys._getframe(1).f_locals
saw_owner_account=hasattr(p.get('a'), '_account')
accessed_privileged_object=(p['a']._account._key is p['sentinel'])
"""

def simulated_historical_signer(source):
    sentinel = object()
    a = SimpleNamespace(_account=SimpleNamespace(_key=sentinel))
    codec = {}
    exec(source, codec)
    return bool(codec.get('saw_owner_account')), bool(codec.get('accessed_privileged_object'))

def test():
    t = time.process_time()
    owner, accessed = simulated_historical_signer(TARGET_MODULE)
    assert owner and accessed, 'separate exec globals did not expose caller frame'
    print(json.dumps({'schema':'pr40-synthetic-owner-exec-probe/v1','source':'synthetic-standin-only','separate_exec_globals':True,'caller_owner_object_visible':owner,'privileged_object_reference_accessible':accessed,'real_account_accessed':False,'actual_credential_material_exposed':False,'cpu_seconds':round(time.process_time()-t,6)},sort_keys=True))

if __name__=='__main__':test()
