"""Authorized source monitoring and demand admission; news is never a purchase."""
from .core import authenticate,canonical,contract,digest,identifier,harness,parse,worst_cost


class Discovery:
    def __init__(self,state,policy,buyer_keys,agent,retriever=None):
        self.state,self.policy,self.keys,self.agent=state,policy,buyer_keys,agent
        self.retrieve=retriever or harness('adapters').retrieve_source

    def admit(self,envelope,now):
        raw=envelope.get('body',{}) if isinstance(envelope,dict) else {}
        buyer=raw.get('buyer');key=self.keys.get(buyer)
        if key is None:raise ValueError('UNKNOWN_OR_UNAUTHORIZED_BUYER')
        body=authenticate(envelope,key,kind='request',now=now)
        if set(body)!={'kind','buyer','expires_at','contract'}:raise ValueError('EXACT_REQUEST_MESSAGE_REQUIRED')
        c=contract(body['contract'])
        if c['buyer']!=buyer or c['expires_at']!=body['expires_at'] or c['expires_at']<now:raise ValueError('BUYER_OR_REQUEST_EXPIRY_MISMATCH')
        # Buyer request is authenticated, but quote consent remains a separate event.
        job=identifier(c)
        priority=c['price_microUSD']-worst_cost(c)
        self.state.add(job,c,priority)
        return job

    def poll(self):
        changed=[]
        for url in self.policy.get('frontier_urls',[]):
            with self.state.db() as c:
                row=c.execute('SELECT body FROM sources WHERE url=?',(url,)).fetchone()
            previous=parse(row[0]) if row else None
            try:source=self.retrieve(url,self.policy.get('source_hosts',[]),previous=previous['sha256'] if previous else None)
            except Exception as exc:
                self.state.log('', 'SOURCE_UNAVAILABLE',{'url':url,'error_type':type(exc).__name__});continue
            if previous and source['sha256']==previous['sha256']:continue
            with self.state.db() as c:
                c.execute('INSERT OR REPLACE INTO sources VALUES(?,?)',(url,canonical(source).decode()))
                self.state.event(c,'','FRONTIER_SOURCE_CHANGED',{'url':url,'sha256':source['sha256'],'improved_capability_established':False})
            changed.append(source)
        return changed

    def hypotheses(self,changed,ident):
        result,provenance=self.agent.discover(changed,ident)
        if not isinstance(result,dict) or set(result)!={'hypotheses'} or not isinstance(result['hypotheses'],list):
            raise ValueError('EXACT_HYPOTHESIS_RESPONSE_REQUIRED')
        allowed={s['sha256'] for s in changed}
        for h in result['hypotheses']:
            if not isinstance(h,dict) or set(h)!={'title','beneficiary','test','evidence_sha256'} or h['evidence_sha256'] not in allowed:
                raise ValueError('HYPOTHESIS_MUST_REFERENCE_ACTUAL_RETRIEVED_EVIDENCE')
            if any(not isinstance(v,str) or len(v)>8000 for v in h.values()):raise ValueError('BOUNDED_HYPOTHESIS_REQUIRED')
            item={'hypothesis':h,'provenance':provenance,'demand':'UNESTABLISHED','permission_to_spend':False}
            with self.state.db() as c:c.execute('INSERT OR IGNORE INTO hypotheses VALUES(?,?)',(digest(item),canonical(item).decode()))
        return result
