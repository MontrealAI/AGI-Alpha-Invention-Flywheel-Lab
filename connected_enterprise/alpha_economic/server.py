"""Loopback control plane. Deploy behind an authenticated HTTPS reverse proxy.

This development HTTP server is not an internet-facing multi-tenant service.
No credentials, customer source files or full account exports are served.
"""
from __future__ import annotations
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .core import canonical,parse


def make_server(engine,token,port=0,*,stripe=None):
    if not isinstance(token,str) or len(token)<32:raise ValueError('CONTROL_TOKEN_AT_LEAST_32_CHARACTERS')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def _reply(self,status,value):
            raw=canonical(value);self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'");self.end_headers();self.wfile.write(raw)
        def _authorized(self):
            if self.headers.get('Origin') is not None:return False
            host=self.headers.get('Host','').split(':')[0]
            return host in ('127.0.0.1','localhost') and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
        def do_GET(self):
            if not self._authorized():return self._reply(401,{'error':'UNAUTHORIZED'})
            if self.path=='/v1/status':return self._reply(200,engine.state.summary())
            if self.path.startswith('/v1/orders/'):
                job=self.path[len('/v1/orders/'):]
                try:
                    row=engine.state.get(job)
                    return self._reply(200,{'id':job,'state':row['state'],'checkout':row['data'].get('checkout'),
                        'artifact_sha256':row['data'].get('verification',{}).get('artifact_sha256')})
                except (ValueError,KeyError):return self._reply(404,{'error':'ORDER_NOT_FOUND'})
            return self._reply(404,{'error':'NOT_FOUND'})
        def do_POST(self):
            if not self._authorized():return self._reply(401,{'error':'UNAUTHORIZED'})
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if not 0<=length<=2_000_000 or self.headers.get('Transfer-Encoding') is not None:raise ValueError('BOUNDED_BODY_REQUIRED')
                if self.headers.get_content_type()!='application/json':raise ValueError('JSON_REQUIRED')
                raw=self.rfile.read(length)
                if len(raw)!=length:raise ValueError('TRUNCATED_BODY')
                if self.path=='/v1/requests':return self._reply(202,{'job':engine.submit(parse(raw))})
                if self.path in ('/v1/pause','/v1/resume'):
                    body=parse(raw)
                    if body!={}:raise ValueError('EMPTY_CONTROL_BODY_REQUIRED')
                    engine.state.pause(self.path.endswith('/pause'));return self._reply(200,engine.state.summary())
                if self.path=='/v1/payments/stripe':
                    if stripe is None:raise PermissionError('STRIPE_NOT_CONFIGURED')
                    event=stripe.webhook(raw,self.headers.get('Stripe-Signature',''))
                    with engine.state.db() as db:
                        old=db.execute('SELECT body FROM messages WHERE id=?',(event['id'],)).fetchone()
                        data=canonical(event).decode()
                        if old and old[0]!=data:raise ValueError('PROVIDER_EVENT_ID_REUSED_WITH_DIFFERENT_BODY')
                        if not old:db.execute('INSERT INTO messages VALUES(?,?,0)',(event['id'],data))
                    # Webhook is a durable notification ONLY. Worker re-reads
                    # provider state rather than trusting arrival order/status.
                    return self._reply(200,{'received':True,'duplicate':bool(old),'booked_as_revenue':False})
                return self._reply(404,{'error':'NOT_FOUND'})
            except (ValueError,KeyError,TypeError,PermissionError) as exc:
                return self._reply(400,{'error':type(exc).__name__})
        def setup(self):super().setup();self.connection.settimeout(10)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)
