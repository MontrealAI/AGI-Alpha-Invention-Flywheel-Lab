import argparse, importlib, importlib.metadata, json, pathlib, sys
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();sys.path.insert(0,str(pathlib.Path(a.source).resolve()))
from fastapi.testclient import TestClient
m=importlib.import_module('app_b.main');w=importlib.import_module('tutorial002');s=importlib.import_module('tutorial003')
rows=[]
def check(name,actual,expected):
    if actual!=expected: raise AssertionError((name,actual,expected))
    rows.append({'id':name,'observed':actual})
def result(response): return [response.status_code,response.json()]
with TestClient(m.app) as c:
    check('header_alias',result(c.get('/items/bar',headers={'x-token':'coneofsilence'})),[200,{'id':'bar','title':'Bar','description':'The bartenders'}])
    check('missing_header',c.get('/items/foo').status_code,422)
    check('auth_precedes_lookup',result(c.get('/items/case-74129',headers={'X-Token':'wrong'})),[400,{'detail':'Invalid X-Token header'}])
    item={'id':'held-74129','title':'Δ neutral title','description':None};auth={'X-Token':'coneofsilence'}
    check('create_optional',result(c.post('/items/',json={'id':item['id'],'title':item['title']},headers=auth)),[200,item])
    check('read_created',result(c.get('/items/'+item['id'],headers=auth)),[200,item])
    check('duplicate_refusal',result(c.post('/items/',json={'id':item['id'],'title':'altered'},headers=auth)),[400,{'detail':'Item already exists'}])
    check('duplicate_preserves_value',result(c.get('/items/'+item['id'],headers=auth)),[200,item])
    check('bad_auth_write',result(c.post('/items/',json={'id':'rejected-8191','title':'denied'},headers={'x-token':'wrong'})),[400,{'detail':'Invalid X-Token header'}])
    check('bad_auth_no_mutation',result(c.get('/items/rejected-8191',headers=auth)),[404,{'detail':'Item not found'}])
    check('invalid_body',c.post('/items/',json={'id':'invalid-8191'},headers=auth).status_code,422)
    check('invalid_body_no_mutation',result(c.get('/items/invalid-8191',headers=auth)),[404,{'detail':'Item not found'}])
with TestClient(w.app) as c:
    check('http_greeting',result(c.get('/')),[200,{'msg':'Hello World'}])
    with c.websocket_connect('/ws') as ws:
        check('websocket_greeting',ws.receive_json(),{'msg':'Hello WebSocket'})
        check('websocket_close',ws.receive(),{'type':'websocket.close','code':1000,'reason':''})
check('startup_initial_state',s.items,{})
with TestClient(s.app) as c:
    check('startup_foo',result(c.get('/items/foo')),[200,{'name':'Fighters'}])
    check('startup_bar',result(c.get('/items/bar')),[200,{'name':'Tenders'}])
versions={name:importlib.metadata.version(name) for name in ('fastapi','starlette','httpx','pydantic','pytest')}
pathlib.Path(a.output).write_text(json.dumps({'checks':rows,'versions':versions},sort_keys=True,indent=2,ensure_ascii=False)+'\n')
